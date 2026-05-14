"""
FLOW MASTER — Orderflow & microstructure specialist.
Owns: ORDERFLOW dimension.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.agents.base.base_agent import AgentSignal, BaseAgent
from src.features.market_state import MarketState


class FlowMaster(BaseAgent):
    name = "FLOW_MASTER"
    model = "claude-sonnet-4-6"
    max_tokens = 1024
    temperature = 0.2

    @property
    def system_prompt(self) -> str:
        return """You are FLOW MASTER — orderflow and market microstructure expert.

Your dimension: ORDERFLOW (weight: 0.20)
Score: 0.0 = bearish flow, 0.5 = neutral, 1.0 = bullish flow

Analyze: VPIN, CVD, TCR, OFI, OBI, order book depth, spread, trade size distribution.

VPIN > 0.60 = institutional activity active = directional move incoming.
CVD positive = net buy pressure. CVD divergence from price = hidden reversal.
TCR > 0.15 = strong buy aggression.
OBI > 0.25 = strong bid-side pressure.

Return STRICT JSON:
{
  "dimension": "orderflow",
  "score": 0.72,
  "confidence": 0.80,
  "regime": "TRENDING_UP",
  "key_signals": ["VPIN 0.65 — institutional directional move likely", "CVD diverging from price"],
  "contradictions": [],
  "risk_flags": ["VPIN elevated but spread widening"]
}"""

    def build_prompt(self, state: MarketState, reflection: dict) -> str:
        return f"""## ORDERFLOW DATA

### Metrics
VPIN: {state.vpin:.4f} — {'⚠️ HIGH (institutional activity)' if state.vpin > 0.60 else 'normal'}
CVD (200-trade): {state.cvd:.4f} BTC — {'📈 POSITIVE (buy pressure)' if state.cvd > 0 else '📉 NEGATIVE (sell pressure)'}
TCR (200-trade): {state.tcr:.3f} — {'buy-aggression' if state.tcr > 0 else 'sell-aggression'}
OFI (20-trade): {state.ofi:.4f} — {'positive' if state.ofi > 0 else 'negative'}
Order Book Imbalance (5-level): {state.obi:.3f} — {'bid pressure' if state.obi > 0.1 else 'ask pressure' if state.obi < -0.1 else 'balanced'}
Spread: {state.spread_bps:.1f} bps

### Context
CVD sign: {'POSITIVE' if state.cvd > 0 else 'NEGATIVE'}
Price direction (C1): {'GREEN' if state.c1_is_green else 'RED'}
CVD vs Price divergence: {'YES' if (state.cvd > 0) != state.c1_is_green else 'NO'}

### Reflection
Consecutive losses: {reflection.get('consecutive_losses', 0)}
"""

    async def analyze(self, state: MarketState, reflection: dict) -> dict[str, AgentSignal]:
        """Produce an orderflow signal."""
        score, confidence = self._compute_orderflow_score(state)
        risk_flags = []
        if state.vpin > 0.70:
            risk_flags.append(f"VPIN elevated ({state.vpin:.3f}) — high uncertainty")
        if abs(state.obi) > 0.40:
            risk_flags.append(f"Extreme OBI ({state.obi:.3f}) — potential reversal")
        divergence = (state.cvd > 0) != state.c1_is_green if state.c1 else False
        key_signals = []
        if state.vpin > 0.60:
            key_signals.append(f"VPIN {state.vpin:.3f} > 0.60 — institutional directional move")
        if state.cvd > 100:
            key_signals.append(f"CVD strongly positive ({state.cvd:.1f}) — buy pressure")
        if state.cvd < -100:
            key_signals.append(f"CVD strongly negative ({state.cvd:.1f}) — sell pressure")
        if abs(state.tcr) > 0.15:
            key_signals.append(f"TCR {state.tcr:.3f} — strong {'buy' if state.tcr > 0 else 'sell'} aggression")
        if state.obi > 0.25:
            key_signals.append(f"OBI {state.obi:.3f} > 0.25 — bid pressure")
        if divergence:
            key_signals.append("CVD divergence from price — hidden reversal pressure")
        if abs(state.ofi) > 0.05:
            key_signals.append(f"OFI {state.ofi:.4f} — {'positive' if state.ofi > 0 else 'negative'} flow")
        if abs(state.tcr) < 0.05:
            key_signals.append("TCR near zero — balanced aggression")

        regime = "TRENDING_UP" if state.cvd > 50 and state.vpin > 0.50 else \
                 "TRENDING_DOWN" if state.cvd < -50 and state.vpin > 0.50 else \
                 "RANGING"

        return {
            "orderflow": AgentSignal(
                dimension="orderflow",
                score=round(score, 3),
                confidence=round(confidence, 3),
                regime=regime,
                key_signals=key_signals,
                contradictions=[f"CVD divergence from C1" if divergence else ""],
                risk_flags=risk_flags,
            )
        }

    def _compute_orderflow_score(self, state: MarketState) -> tuple[float, float]:
        """Compute orderflow score from VPIN, CVD, TCR, OBI, OFI."""
        score = 0.5
        weight = 0.0

        # VPIN contribution
        if state.vpin > 0.70:
            # High VPIN = directional, weight depends on direction
            vpin_contribution = 0.15
            weight += 0.15
            # Direction from CVD
            if state.cvd > 0:
                score += vpin_contribution  # Bullish institutional flow
            else:
                score -= vpin_contribution  # Bearish institutional flow
        elif state.vpin > 0.50:
            weight += 0.10
            if state.cvd > 0:
                score += 0.08
            else:
                score -= 0.08

        # CVD contribution — clamp to ±0.20 per metric
        if abs(state.cvd) > 200:
            weight += 0.25
            cvd_delta = (state.cvd / 400) * 0.25
            score += max(-0.20, min(0.20, cvd_delta))
        elif abs(state.cvd) > 100:
            weight += 0.15
            cvd_delta = (state.cvd / 400) * 0.15
            score += max(-0.20, min(0.20, cvd_delta))

        # TCR contribution — clamp to ±0.15 per metric
        if abs(state.tcr) > 0.15:
            weight += 0.15
            score += max(-0.15, min(0.15, state.tcr * 0.15))
        elif abs(state.tcr) > 0.05:
            weight += 0.08
            score += max(-0.08, min(0.08, state.tcr * 0.08))

        # OBI contribution — clamp to ±0.15 per metric
        if abs(state.obi) > 0.25:
            weight += 0.15
            score += max(-0.15, min(0.15, state.obi * 0.15))

        # OFI contribution — clamp to ±0.10 per metric
        if abs(state.ofi) > 0.05:
            weight += 0.10
            score += max(-0.10, min(0.10, (state.ofi / 0.1) * 0.10))

        # Normalize
        if weight > 0:
            score = 0.5 + (score - 0.5) / (weight / 0.90)
        score = max(0.1, min(0.9, score))
        confidence = min(0.9, 0.5 + weight * 0.5)
        return score, confidence