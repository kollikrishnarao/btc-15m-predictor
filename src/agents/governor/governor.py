"""
GOVERNOR AGENT — The chief orchestrator.
Owns: Loop 1 (Trading Cycle), Loop 5 (Reflection Cycle).
Final decision authority for all trading decisions.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import anthropic

from config.constants import ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, BRAINS, CONFIDENCE_HIGH, CONFIDENCE_MEDIUM
from src.agents.advisor import AdvisorAgent, AdvisorOpinion
from src.agents.base.base_agent import AgentSignal
from src.execution.polymarket_client import PolymarketClient, OrderResult
from src.features.market_state import MarketState
from src.pre_filter import PreFilterResult, run_pre_filter
from src.session import SessionManager, SessionPhase

log = logging.getLogger(__name__)


# Dimension weights (fixed by strategy)
DIMENSION_WEIGHTS = {
    "momentum": 0.25,
    "trend": 0.20,
    "orderflow": 0.20,
    "smart_money": 0.15,
    "sentiment": 0.10,
    "macro": 0.10,
}

# Regime-adaptive weight profiles (Phase 2.4)
REGIME_WEIGHT_PROFILES = {
    "TRENDING_UP": {
        "momentum": 0.30, "trend": 0.25, "orderflow": 0.15,
        "smart_money": 0.15, "sentiment": 0.05, "macro": 0.10,
    },
    "TRENDING_DOWN": {
        "momentum": 0.30, "trend": 0.25, "orderflow": 0.15,
        "smart_money": 0.15, "sentiment": 0.05, "macro": 0.10,
    },
    "RANGING": {
        "momentum": 0.15, "trend": 0.10, "orderflow": 0.30,
        "smart_money": 0.20, "sentiment": 0.10, "macro": 0.15,
    },
    "VOLATILE": {
        "momentum": 0.10, "trend": 0.10, "orderflow": 0.25,
        "smart_money": 0.25, "sentiment": 0.15, "macro": 0.15,
    },
    "RISK_ON": {
        "momentum": 0.25, "trend": 0.20, "orderflow": 0.20,
        "smart_money": 0.15, "sentiment": 0.10, "macro": 0.10,
    },
    "RISK_OFF": {
        "momentum": 0.20, "trend": 0.15, "orderflow": 0.20,
        "smart_money": 0.20, "sentiment": 0.10, "macro": 0.15,
    },
    "NEUTRAL": {
        "momentum": 0.25, "trend": 0.20, "orderflow": 0.20,
        "smart_money": 0.15, "sentiment": 0.10, "macro": 0.10,
    },
    "UNKNOWN": {  # Fallback — same as default
        "momentum": 0.25, "trend": 0.20, "orderflow": 0.20,
        "smart_money": 0.15, "sentiment": 0.10, "macro": 0.10,
    },
}


# ── Governor LLM Synthesis Prompt ────────────────────────────────────────

GOVERNOR_SYNTHESIS_SYSTEM = """You are the GOVERNOR of a BTC 15-minute trading system.
You have received signals from 4 specialist agents and 1 independent advisor.
Synthesize these into a final trading decision.

Score: 0.0=bearish, 0.5=neutral, 1.0=bullish
Call: GREEN (score>0.5), RED (score<0.5), SKIP (score≈0.5 or contradictory)

Return STRICT JSON:
{
    "call": "GREEN|RED|SKIP",
    "confidence": 0.XX,
    "regime": "TRENDING_UP|TRENDING_DOWN|RANGING|VOLATILE|UNKNOWN",
    "risk_level": "LOW|MEDIUM|HIGH"
}"""


@dataclass
class GovernorDecision:
    """Final output from the Governor."""
    call: str              # GREEN, RED, or SKIP
    weighted_confidence: float
    confidence_bucket: str  # HIGH, MEDIUM, LOW
    signal_scores: dict[str, float]
    advisor_reconciliation: dict
    regime: str
    analysis: dict
    contradictions: list[dict]
    key_signals: list[str]
    risk_factors: list[str]
    raw_reasoning: str = ""
    latency_ms: float = 0.0


class GovernorAgent:
    """
    The Governor is the final decision authority.
    It receives signals from all specialists, reconciles with the Advisor,
    applies confidence gates, and makes the final call.

    In v1.0, specialists are called sequentially and their scores are
    aggregated manually. This can be parallelized in v2.0.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.model = BRAINS["reasoning"]["model"]
        self.max_tokens = BRAINS["reasoning"]["max_tokens"]
        self.temperature = BRAINS["reasoning"]["temperature"]
        self._client: Optional[anthropic.AsyncAnthropic] = None
        self._advisor: Optional[AdvisorAgent] = None
        self._session_mgr = SessionManager()

    async def __aenter__(self):
        if self.api_key:
            self._client = anthropic.AsyncAnthropic(
                api_key=self.api_key,
                base_url=ANTHROPIC_BASE_URL,
            )
        self._advisor = AdvisorAgent()
        await self._advisor.__aenter__()
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
        if self._advisor:
            await self._advisor.__aexit__(*args)

    async def make_decision(
        self,
        state: MarketState,
        specialist_signals: dict[str, AgentSignal],
        reflection: dict,
    ) -> GovernorDecision:
        """
        Given market state and specialist signals, make the final decision.
        Runs the Advisor in parallel, reconciles, applies confidence gates.
        """
        t0 = asyncio.get_event_loop().time()

        # Run Advisor in parallel with our own reasoning
        advisor_task = asyncio.create_task(
            self._advisor.analyze(state, reflection)
        )

        # Compute weighted conviction from specialist signals
        weighted_confidence = self._compute_weighted_confidence(specialist_signals)
        regime = self._compute_regime(specialist_signals)

        # Wait for advisor
        advisor_opinion = await advisor_task

        # Reconcile with arithmetic result
        arithmetic_call, arithmetic_confidence = self._reconcile(
            weighted_confidence, advisor_opinion, specialist_signals
        )

        # Phase 2.2: LLM synthesis — call Governor's own LLM for final judgment
        synthesis = await self._synthesize(specialist_signals, advisor_opinion, arithmetic_call, arithmetic_confidence)

        # Use LLM synthesis if it provides a confident override
        if synthesis and synthesis.get("call"):
            final_call = synthesis["call"]
            final_confidence = synthesis.get("confidence", arithmetic_confidence)
            if synthesis.get("regime") and synthesis["regime"] != "UNKNOWN":
                regime = synthesis["regime"]
            # Log override
            if final_call != arithmetic_call:
                log.info(f"Governor LLM OVERRIDE: {arithmetic_call} → {final_call}")
        else:
            final_call, final_confidence = arithmetic_call, arithmetic_confidence

        # Apply confidence gate
        bucket = self._confidence_bucket(final_confidence)
        if bucket == "LOW":
            final_call = "SKIP"

        latency = (asyncio.get_event_loop().time() - t0) * 1000

        return GovernorDecision(
            call=final_call,
            weighted_confidence=final_confidence,
            confidence_bucket=bucket,
            signal_scores={
                dim: sig.score for dim, sig in specialist_signals.items()
            },
            advisor_reconciliation={
                "advisor_call": advisor_opinion.call,
                "advisor_confidence": advisor_opinion.confidence,
                "advisor_strength": advisor_opinion.advisor_strength,
                "agreed": advisor_opinion.call == final_call or final_call == "SKIP",
            },
            regime=regime,
            analysis=self._build_analysis(specialist_signals),
            contradictions=self._find_contradictions(specialist_signals),
            key_signals=self._extract_key_signals(specialist_signals),
            risk_factors=self._extract_risk_factors(specialist_signals, state),
            latency_ms=latency,
        )

    def _compute_weighted_confidence(self, signals: dict[str, AgentSignal], regime: str = "UNKNOWN") -> float:
        """Compute weighted conviction from all specialist signals.
        Phase 2.4: Uses regime-adaptive weights.
        Phase 2.7: Adds interaction terms (confirmation bonus, divergence penalty, consensus floor).
        """
        # Select weight profile based on regime
        weights = REGIME_WEIGHT_PROFILES.get(regime, REGIME_WEIGHT_PROFILES["UNKNOWN"])

        # Step 1: Base linear score
        base = 0.0
        for dim, weight in weights.items():
            if dim in signals:
                base += signals[dim].score * weight
            else:
                base += 0.5 * weight

        # Step 2: Confirmation bonus — orderflow and momentum agree
        confirmation_bonus = 0.0
        if "orderflow" in signals and "momentum" in signals:
            agreement = 1.0 - abs(signals["orderflow"].score - signals["momentum"].score)
            confirmation_bonus = agreement * 0.05  # Up to +0.05 when they fully agree

        # Step 3: Divergence penalty — when any two dimensions strongly disagree
        max_divergence = 0.0
        dims = list(signals.keys())
        for i, d1 in enumerate(dims):
            for d2 in dims[i+1:]:
                div = abs(signals[d1].score - signals[d2].score)
                max_divergence = max(max_divergence, div)
        divergence_penalty = max(0, (max_divergence - 0.30) * 0.10)

        # Step 4: Consensus floor bonus — when all dimensions loosely agree
        if len(signals) >= 3:
            min_score = min(s.score for s in signals.values())
            max_score = max(s.score for s in signals.values())
            spread = max_score - min_score
            consensus_bonus = max(0, (0.50 - spread) * 0.05)
        else:
            consensus_bonus = 0.0

        final = base + confirmation_bonus - divergence_penalty + consensus_bonus
        return round(max(0.0, min(1.0, final)), 3)

    def _compute_regime(self, signals: dict[str, AgentSignal]) -> str:
        """Infer market regime from specialist signals."""
        regimes = [s.regime for s in signals.values() if s.regime]
        if not regimes:
            return "UNKNOWN"
        # Majority vote
        from collections import Counter
        return Counter(regimes).most_common(1)[0][0]

    def _reconcile(
        self,
        engine_confidence: float,
        advisor: AdvisorOpinion,
        signals: dict[str, AgentSignal],
    ) -> tuple[str, float]:
        """
        Reconcile engine confidence with advisor opinion.
        - Derive engine direction from weighted confidence score (>0.5 = GREEN, <0.5 = RED)
        - If advisor agrees: use higher confidence
        - If advisor disagrees with engine significantly more confident (>0.15): use engine
        - If advisor disagrees with similar confidence: use conservative call (SKIP or advisor)
        """
        if advisor.call == "SKIP":
            return "SKIP", engine_confidence

        # Derive engine's directional call from weighted score
        engine_direction = "GREEN" if engine_confidence > 0.5 else "RED"

        if advisor.call == engine_direction:
            # Agreement — use higher confidence
            return engine_direction, max(engine_confidence, advisor.confidence)

        # Advisor disagrees
        gap = engine_confidence - advisor.confidence
        if gap > 0.15:
            # Engine significantly more confident — stay with engine
            return engine_direction, engine_confidence
        else:
            # Advisor disagrees with similar confidence — flip to advisor's call
            return advisor.call, advisor.confidence

    def _confidence_bucket(self, confidence: float) -> str:
        if confidence >= CONFIDENCE_HIGH:
            return "HIGH"
        elif confidence >= CONFIDENCE_MEDIUM:
            return "MEDIUM"
        else:
            return "LOW"

    def _build_analysis(self, signals: dict[str, AgentSignal]) -> dict:
        return {
            dim: {
                "score": sig.score,
                "confidence": sig.confidence,
                "regime": sig.regime,
                "key_signals": sig.key_signals,
            }
            for dim, sig in signals.items()
        }

    def _find_contradictions(self, signals: dict[str, AgentSignal]) -> list[dict]:
        contradictions = []
        dims = list(signals.keys())
        for i, d1 in enumerate(dims):
            for d2 in dims[i+1:]:
                diff = abs(signals[d1].score - signals[d2].score)
                if diff > 0.30:
                    contradictions.append({
                        "category_1": d1,
                        "category_2": d2,
                        "score_1": signals[d1].score,
                        "score_2": signals[d2].score,
                        "gap": diff,
                        "resolution": f"weight by confidence — {signals[d1].confidence:.2f} vs {signals[d2].confidence:.2f}",
                    })
        return contradictions

    def _extract_key_signals(self, signals: dict[str, AgentSignal]) -> list[str]:
        """Extract the most actionable signals across all dimensions."""
        all_signals = []
        for dim, sig in signals.items():
            for s in sig.key_signals:
                all_signals.append(f"[{dim.upper()}] {s}")
        return all_signals[:5]  # Top 5

    def _extract_risk_factors(self, signals: dict[str, AgentSignal], state: MarketState) -> list[str]:
        """Extract risk factors from specialist signals and market state."""
        risks = []
        for sig in signals.values():
            risks.extend(sig.risk_flags)
        if state.vpin > 0.70:
            risks.append(f"VPIN elevated ({state.vpin:.3f}) — institutional uncertainty")
        return list(set(risks))[:5]

    async def _synthesize(
        self,
        signals: dict[str, AgentSignal],
        advisor: AdvisorOpinion,
        arithmetic_call: str,
        arithmetic_confidence: float,
    ) -> dict:
        """
        Phase 2.2: Governor LLM synthesis — call Sonnet 4.6 to produce final judgment.
        Timeout: 10 seconds. Falls back to arithmetic result on timeout or error.
        """
        if not self._client:
            return {}

        # Build summary of all signals
        dim_lines = []
        for dim, sig in signals.items():
            conf_str = "high" if sig.confidence > 0.7 else "medium" if sig.confidence > 0.5 else "low"
            dir_str = "BULLISH" if sig.score > 0.6 else "BEARISH" if sig.score < 0.4 else "NEUTRAL"
            dim_lines.append(f"  {dim}: score={sig.score:.2f} conf={conf_str} ({dir_str}) regime={sig.regime}")

        specialist_summary = "\n".join(dim_lines) if dim_lines else "No specialist signals available"

        user_prompt = f"""## Specialist Signals
{specialist_summary}

## Advisor Opinion
Call: {advisor.call} | Confidence: {advisor.confidence:.2f} | Strength: {advisor.advisor_strength}
Key signals: {', '.join(advisor.key_signals[:3]) if advisor.key_signals else 'None'}

## Arithmetic Baseline
Weighted confidence: {arithmetic_confidence:.3f}
Direction from arithmetic: {arithmetic_call}

## Your Task
Synthesize all signals above. Identify contradictions, assess trustworthiness
of the arithmetic score, and make a final call. Return STRICT JSON."""

        try:
            resp = await asyncio.wait_for(
                self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=GOVERNOR_SYNTHESIS_SYSTEM,
                    messages=[{"role": "user", "content": user_prompt}],
                ),
                timeout=10.0,
            )
            raw = ""
            for block in resp.content:
                if block.type == "text":
                    raw += block.text
            parsed = self.parse_signal_json(raw)
            return parsed or {}
        except asyncio.TimeoutError:
            log.warning("Governor synthesis timed out — using arithmetic result")
            return {}
        except Exception as e:
            log.error(f"Governor synthesis failed: {e}")
            return {}

    async def execute_decision(
        self,
        decision: GovernorDecision,
        state: MarketState,
    ) -> Optional[OrderResult]:
        """Execute the Governor's decision on Polymarket."""
        if decision.call == "SKIP":
            log.info(f"Governor SKIP — confidence={decision.weighted_confidence:.2f}")
            return None

        log.info(f"Governor ENTER: {decision.call} @ {decision.weighted_confidence:.2f}")

        # Discover and place bet on Polymarket
        async with PolymarketClient() as pm:
            market = await pm.find_best_btc_market(decision.call)
            if not market:
                log.error("No suitable Polymarket BTC market found")
                return None

            price = market.yes_price if decision.call == "GREEN" else market.no_price

            # Compute bet size ($1 base, Kelly sizing)
            bet_size = pm.compute_bet_size(
                confidence=decision.weighted_confidence,
                market_price=price,
                bankroll=1000.0,
            )

            result = await pm.place_order(
                market=market,
                direction=decision.call,
                size=bet_size,
                market_price=price,
            )

            return result

    async def run_reflection(
        self,
        session_won: bool,
        winning_candle: str,
        pnl: float,
        decision: GovernorDecision,
        state: MarketState,
    ) -> dict:
        """Run Loop 5: Reflection after every session ends."""
        log.info(f"Governor reflection: won={session_won}, pnl={pnl:.2f}, candle={winning_candle}")

        # The reflection context is updated in prediction_logger
        # This is where we could adjust weights, detect regime shifts, etc.
        # For v1.0, keep it simple — the logger handles most of this.

        return {
            "session_won": session_won,
            "winning_candle": winning_candle,
            "pnl": pnl,
            "confidence": decision.weighted_confidence,
            "regime": decision.regime,
        }