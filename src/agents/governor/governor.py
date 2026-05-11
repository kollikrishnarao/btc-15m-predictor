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

        # Reconcile
        final_call, final_confidence = self._reconcile(
            weighted_confidence, advisor_opinion, specialist_signals
        )

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

    # Specialist dim → Governor dim mapping
    _SPECIALIST_TO_DIM = {
        "momentum": "momentum",
        "orderflow": "orderflow",
        "smart_money": "smart_money",
        "sentiment": "sentiment",
        "trend": "momentum",
        "macro": "smart_money",
    }

    def _compute_weighted_confidence(self, signals: dict[str, AgentSignal]) -> float:
        """Compute weighted conviction from all specialist signals."""
        total = 0.0
        for dim, weight in DIMENSION_WEIGHTS.items():
            mapped = self._SPECIALIST_TO_DIM.get(dim, dim)
            if mapped in signals:
                total += signals[mapped].score * weight
            else:
                total += 0.5 * weight  # Neutral if no signal
        return round(total, 3)

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
        - If advisor agrees or says SKIP: use engine confidence
        - If advisor disagrees: use more conservative call unless engine > advisor by 0.15
        """
        if advisor.call == "SKIP":
            return "SKIP", engine_confidence

        # Check if any dimension has extreme signal (supports the call)
        extremes = sum(
            1 for s in signals.values()
            if s.score <= 0.30 or s.score >= 0.70
        )

        if advisor.call == "SKIP":
            return "SKIP", engine_confidence

        if advisor.call == signals.get("momentum", AgentSignal("momentum", 0.5, 0.5, "UNKNOWN")).dimension:
            # Advisor matches momentum direction
            return advisor.call, max(engine_confidence, advisor.confidence)

        # Advisor disagrees
        gap = engine_confidence - advisor.confidence
        if gap > 0.15:
            # Engine significantly more confident — stay with engine
            return signals.get("momentum", None) and "GREEN" or "RED", engine_confidence
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