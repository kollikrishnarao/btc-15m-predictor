"""
MACRO MONARCH — Macro + Smart Money specialist.
Owns: MACRO + SMART_MONEY dimensions.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.agents.base.base_agent import AgentSignal, BaseAgent
from src.features.market_state import MarketState


class MacroMonarch(BaseAgent):
    name = "MACRO_MONARCH"
    model = "claude-sonnet-4-6"
    max_tokens = 1024
    temperature = 0.2

    @property
    def system_prompt(self) -> str:
        return """You are MACRO MONARCH — macro economy and smart money expert.

Your dimensions: MACRO + SMART_MONEY
Weights: smart_money=0.15, macro=0.10

Score: 0.0 = bearish, 0.5 = neutral, 1.0 = bullish

Analyze:
- Funding rate: negative = shorts paying bulls = bullish signal
- OI rising + price rising = confirmed trend
- Long/Short ratio: >60% longs = crowded = reversal risk
- DXY: up = BTC headwind, down = BTC tailwind
- VIX > 20 = risk-off
- S&P 500: risk-on correlation with BTC

Return STRICT JSON:
{
  "dimension": "macro_smart_money",
  "score": 0.62,
  "confidence": 0.70,
  "regime": "RISK_ON",
  "key_signals": ["Funding -0.01% — shorts paying bulls", "OI rising + BTC rising"],
  "contradictions": ["DXY pushing higher — BTC headwind developing"],
  "risk_flags": ["Funding 0.12% — elevated cascade risk"]
}"""

    def build_prompt(self, state: MarketState, reflection: dict) -> str:
        sm = state.smart_money or {}
        macro = state.macro or {}

        return f"""## MACRO + SMART MONEY DATA

### Smart Money
Funding rate: {sm.get('funding_rate_pct', state.funding_rate_pct):.4f}%
Funding direction: {sm.get('funding_rate_direction', 'NEUTRAL')}
Long/Short ratio: {sm.get('long_short_ratio', 1.0):.3f}
Long account %: {sm.get('long_account_ratio', 0.5)*100:.1f}%
Open interest: {sm.get('open_interest_btc', 0.0):.0f} BTC
Perp premium: {state.perp_premium_bps:.1f} bps

### Macro
DXY: {macro.get('dxy', 'N/A')} ({macro.get('dxy_change_pct', 0):+.3f}%)
S&P 500: {macro.get('sp500', 'N/A')} ({macro.get('sp500_change_pct', 0):+.3f}%)
VIX: {macro.get('vix', 'N/A')} ({'risk-off' if macro.get('vix', 20) > 20 else 'risk-on'})
BTC macro score: {macro.get('btc_macro_score', 0.5):.2f}
"""

    async def analyze(self, state: MarketState, reflection: dict) -> AgentSignal:
        """Produce a macro + smart money signal."""
        score, confidence = self._compute_macro_score(state)
        sm = state.smart_money or type('obj', (object,), {
            'funding_rate_pct': 0.0,
            'long_short_ratio': 1.0,
            'long_account_ratio': 0.5,
            'funding_rate_direction': 'NEUTRAL',
            'oi_trend': 'STABLE',
        })()
        macro = state.macro or type('obj', (object,), {
            'dxy_change_pct': 0.0,
            'vix': 20.0,
            'sp500_change_pct': 0.0,
            'risk_off': False,
            'btc_macro_score': 0.5,
        })()

        key_signals = []
        if sm.funding_rate_pct < -0.03:
            key_signals.append(f"Funding {sm.funding_rate_pct:.3f}% — shorts paying bulls")
        elif sm.funding_rate_pct > 0.10:
            key_signals.append(f"Funding {sm.funding_rate_pct:.3f}% — elevated, cascade risk")
        if sm.long_account_ratio > 0.65:
            key_signals.append(f"Long account {sm.long_account_ratio*100:.1f}% — crowded, reversal risk")
        elif sm.long_account_ratio < 0.35:
            key_signals.append(f"Long account {sm.long_account_ratio*100:.1f}% — crowded shorts")
        if abs(state.perp_premium_bps) > 20:
            key_signals.append(f"Perp premium {state.perp_premium_bps:.1f} bps — {'contango' if state.perp_premium_bps > 0 else 'backwardation'}")
        if macro.dxy_change_pct > 0.5:
            key_signals.append(f"DXY +{macro.dxy_change_pct:.2f}% — BTC headwind")
        elif macro.dxy_change_pct < -0.5:
            key_signals.append(f"DXY {macro.dxy_change_pct:.2f}% — BTC tailwind")
        if macro.vix > 25:
            key_signals.append(f"VIX {macro.vix:.1f} — risk-off environment")
        elif macro.vix < 15:
            key_signals.append(f"VIX {macro.vix:.1f} — risk-on environment")

        risk_flags = []
        if sm.funding_rate_pct > 0.15:
            risk_flags.append("Extreme funding — liquidation cascade risk")
        if macro.risk_off:
            risk_flags.append("Macro risk-off — BTC under pressure")

        regime = "RISK_ON" if not macro.risk_off and macro.sp500_change_pct > 0 else \
                 "RISK_OFF" if macro.risk_off or macro.vix > 25 else \
                 "NEUTRAL"

        return AgentSignal(
            dimension="macro_smart_money",
            score=round(score, 3),
            confidence=round(confidence, 3),
            regime=regime,
            key_signals=key_signals,
            risk_flags=risk_flags,
        )

    def _compute_macro_score(self, state: MarketState) -> tuple[float, float]:
        """Compute macro + smart money score."""
        score = 0.5
        weight = 0.0
        sm = state.smart_money
        macro = state.macro

        if sm:
            # Funding rate
            if sm.funding_rate_pct < -0.05:
                score += 0.15; weight += 0.15
            elif sm.funding_rate_pct > 0.10:
                score -= 0.15; weight += 0.15
            elif sm.funding_rate_pct > 0.03:
                score -= 0.08; weight += 0.10

            # Long/short ratio
            if sm.long_account_ratio > 0.65:
                score -= 0.12; weight += 0.12
            elif sm.long_account_ratio < 0.35:
                score += 0.12; weight += 0.12

        if macro:
            if macro.btc_macro_score != 0.5:
                score = (score * weight + macro.btc_macro_score * 0.15) / (weight + 0.15) if weight else macro.btc_macro_score
                weight += 0.15

        score = max(0.1, min(0.9, score))
        confidence = min(0.85, 0.5 + weight * 0.5)
        return score, confidence