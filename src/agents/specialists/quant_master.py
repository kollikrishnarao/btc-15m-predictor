"""
QUANT MASTER — Technical analysis specialist.
Owns: MOMENTUM + TREND dimensions.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.agents.base.base_agent import AgentSignal, BaseAgent
from src.features.market_state import MarketState


class QuantMaster(BaseAgent):
    name = "QUANT_MASTER"
    model = "claude-sonnet-4-6"
    max_tokens = 1024
    temperature = 0.2

    @property
    def system_prompt(self) -> str:
        return """You are QUANT MASTER — senior technical analyst for a BTC 15-minute trading system.

Your dimensions: MOMENTUM + TREND
Weights: momentum=0.25, trend=0.20

Task: Analyze C1 candlestick + technical indicators → produce conviction scores.

Score scale: 0.0 (bearish) — 0.5 (neutral) — 1.0 (bullish)

Analyze: RSI, MACD histogram, price velocity, VWAP position,
Supertrend direction, ADX strength, EMA alignment, Bollinger Bands position,
KDJ, pivot levels, candle patterns.

Return STRICT JSON:
{
  "dimension": "momentum_trend",
  "score": 0.68,
  "confidence": 0.72,
  "regime": "TRENDING_UP",
  "key_signals": ["RSI-14 at 62 — not overbought", "MACD histogram positive and rising"],
  "contradictions": ["ADX only 18 — weak trend confirmation"],
  "risk_flags": ["BB at upper band — mean reversion risk"]
}"""

    def build_prompt(self, state: MarketState, reflection: dict) -> str:
        t = state.technical
        c1 = state.c1

        candles_5 = []
        for c in (state.candles[-6:-1] if len(state.candles) >= 6 else state.candles[-5:]):
            candles_5.append(
                f"  {'GREEN' if c.is_green else 'RED'}: O={c.open:.1f} H={c.high:.1f} "
                f"L={c.low:.1f} C={c.close:.1f} V={c.volume:.2f} | "
                f"body={c.body_pct:.2f}% pattern={c.candle_pattern}"
            )

        return f"""## TECHNICAL ANALYSIS DATA

### C1 Candlestick (Primary Signal)
Direction: {'GREEN' if c1.is_green else 'RED'}
Body: {c1.body_pct:.3f}% of range
Wick: upper={c1.upper_wick_pct:.1f}% lower={c1.lower_wick_pct:.1f}%
Close position: {c1.close_position:.2f} (0=bottom, 1=top)
Pattern: {c1.candle_pattern}

### Last 5 Candles
""" + "\n".join(candles_5) + f"""

### Technical Indicators
RSI-14: {t.rsi_14:.1f} ({'OVERBOUGHT' if t.rsi_14 > 70 else 'OVERSOLD' if t.rsi_14 < 30 else 'NEUTRAL'})
RSI-4: {t.rsi_4:.1f}
MACD: line={t.macd_line:.2f} signal={t.macd_signal:.2f} histogram={t.macd_histogram:.4f}
MACD slope: {t.macd_histogram_slope:.5f}
VWAP: ${t.vwap:.2f} | Price vs VWAP: {((state.current_price - t.vwap) / t.vwap * 100):.3f}%
ADX: {t.adx:.1f}
Supertrend: {'UP (bullish)' if t.supertrend_up else 'DOWN (bearish)'}
EMA9: ${t.ema_9:.2f} | EMA21: ${t.ema_21:.2f} | EMA99: ${t.ema_99:.2f}
EMA structure: {'BULLISH (9>21>99)' if t.ema_9 > t.ema_21 > t.ema_99 else 'BEARISH (9<21<99)' if t.ema_9 < t.ema_21 < t.ema_99 else 'MIXED'}
Bollinger Bands: upper=${t.bb_upper:.2f} mid=${t.bb_middle:.2f} lower=${t.bb_lower:.2f}
BB %B: {t.bb_position_pct:.2f}
Pivots: R2=${t.pivot_r2:.1f} R1=${t.pivot_r1:.1f} PP=${t.pivot_pivot:.1f} S1=${t.pivot_s1:.1f} S2=${t.pivot_s2:.1f}
KDJ: K={t.k:.1f} D={t.d:.1f} J={t.j:.1f}
Price velocity (5-candle): {t.price_velocity_5:.3f}%
RVOL: {state.rvol:.2f}x

### Reflection Context
Regime: {reflection.get('regime', 'UNKNOWN')}
Consecutive losses: {reflection.get('consecutive_losses', 0)}
Last outcomes: {reflection.get('last_20_outcomes_formatted', 'N/A')}
"""

    async def analyze(self, state: MarketState, reflection: dict) -> dict[str, AgentSignal]:
        """Produce signals for MOMENTUM and TREND dimensions."""
        if not state.technical or not state.c1:
            return {
                "momentum": AgentSignal(dimension="momentum", score=0.5, confidence=0.0, regime="UNKNOWN", key_signals=["Insufficient data"]),
                "trend": AgentSignal(dimension="trend", score=0.5, confidence=0.0, regime="UNKNOWN", key_signals=["Insufficient data"]),
            }

        # Compute per-dimension scores
        mom_score, mom_conf = self._compute_momentum_score(state)
        trend_score, trend_conf = self._compute_trend_score(state)

        # Ambiguous zone — use LLM for deeper analysis
        if 0.40 <= mom_score <= 0.60 and 0.40 <= trend_score <= 0.60:
            prompt = self.build_prompt(state, reflection)
            raw, latency = await self.call_llm(prompt)
            parsed = self.parse_signal_json(raw)
            if parsed:
                s = float(parsed.get("score", 0.5))
                c = float(parsed.get("confidence", 0.5))
                return {
                    "momentum": AgentSignal(dimension="momentum", score=s, confidence=c, regime=parsed.get("regime", "UNKNOWN"), key_signals=parsed.get("key_signals", []), contradictions=parsed.get("contradictions", []), risk_flags=parsed.get("risk_flags", []), raw_reasoning=raw, latency_ms=latency),
                    "trend": AgentSignal(dimension="trend", score=s, confidence=c, regime=parsed.get("regime", "UNKNOWN"), key_signals=parsed.get("key_signals", []), contradictions=parsed.get("contradictions", []), risk_flags=parsed.get("risk_flags", []), raw_reasoning=raw, latency_ms=latency),
                }

        regime = self._infer_regime(state)
        return {
            "momentum": AgentSignal(
                dimension="momentum",
                score=round(mom_score, 3),
                confidence=round(mom_conf, 3),
                regime=regime,
                key_signals=self._get_momentum_signals(state),
                risk_flags=self._get_risk_flags(state),
            ),
            "trend": AgentSignal(
                dimension="trend",
                score=round(trend_score, 3),
                confidence=round(trend_conf, 3),
                regime=regime,
                key_signals=self._get_trend_signals(state),
                risk_flags=self._get_risk_flags(state),
            ),
        }

    def _compute_momentum_score(self, state: MarketState) -> tuple[float, float]:
        """Compute MOMENTUM score — RSI, MACD, RVOL, price velocity."""
        t = state.technical
        score = 0.5
        weight_total = 0.0

        # RSI momentum
        if t.rsi_14 < 30:
            score += 0.20; weight_total += 0.20
        elif t.rsi_14 > 70:
            score -= 0.20; weight_total += 0.20
        elif t.rsi_14 > 55:
            score += 0.10; weight_total += 0.15
        elif t.rsi_14 < 45:
            score -= 0.10; weight_total += 0.15

        # MACD histogram momentum
        if t.macd_histogram > 0:
            score += 0.15; weight_total += 0.15
            if t.macd_histogram_slope > 0:
                score += 0.05; weight_total += 0.05
        else:
            score -= 0.15; weight_total += 0.15
            if t.macd_histogram_slope < 0:
                score -= 0.05; weight_total += 0.05

        # Price velocity
        if t.price_velocity_5 > 0.5:
            score += 0.10; weight_total += 0.10
        elif t.price_velocity_5 < -0.5:
            score -= 0.10; weight_total += 0.10

        # C1 body conviction
        if state.c1_is_green and state.c1_body_pct > 0.20:
            score += 0.10; weight_total += 0.10
        elif not state.c1_is_green and state.c1_body_pct > 0.20:
            score -= 0.10; weight_total += 0.10

        if weight_total > 0:
            actual_delta = score - 0.5
            normalized_delta = (actual_delta / max(weight_total, 0.01)) * 0.40
            score = 0.5 + normalized_delta
        score = max(0.05, min(0.95, score))
        confidence = min(0.90, 0.40 + weight_total)
        return score, confidence

    def _compute_trend_score(self, state: MarketState) -> tuple[float, float]:
        """Compute TREND score — Supertrend, ADX, EMA alignment, BB position."""
        t = state.technical
        score = 0.5
        weight_total = 0.0

        # Supertrend
        if t.supertrend_up:
            score += 0.20; weight_total += 0.20
        else:
            score -= 0.20; weight_total += 0.20

        # EMA alignment
        if t.ema_9 > t.ema_21 > t.ema_99:
            score += 0.15; weight_total += 0.15
        elif t.ema_9 < t.ema_21 < t.ema_99:
            score -= 0.15; weight_total += 0.15

        # ADX trend strength
        if t.adx > 25:
            weight_total += 0.15
        elif t.adx < 15:
            weight_total -= 0.05

        # BB position
        if t.bb_position_pct > 0.85:
            score -= 0.10; weight_total += 0.10
        elif t.bb_position_pct < 0.15:
            score += 0.10; weight_total += 0.10

        if weight_total > 0:
            actual_delta = score - 0.5
            normalized_delta = (actual_delta / max(weight_total, 0.01)) * 0.40
            score = 0.5 + normalized_delta
        score = max(0.05, min(0.95, score))
        confidence = min(0.90, 0.40 + weight_total)
        return score, confidence

    def _get_momentum_signals(self, state: MarketState) -> list[str]:
        t = state.technical
        sigs = []
        if t.rsi_14 < 30:
            sigs.append(f"RSI-14 oversold ({t.rsi_14:.1f})")
        elif t.rsi_14 > 70:
            sigs.append(f"RSI-14 overbought ({t.rsi_14:.1f})")
        if t.macd_histogram > 0:
            sigs.append("MACD histogram positive")
        if t.price_velocity_5 > 0.5:
            sigs.append(f"Price velocity +{t.price_velocity_5:.3f}%")
        elif t.price_velocity_5 < -0.5:
            sigs.append(f"Price velocity {t.price_velocity_5:.3f}%")
        if state.c1_is_green:
            sigs.append(f"C1 GREEN {state.c1_body_pct:.2f}% body")
        else:
            sigs.append(f"C1 RED {state.c1_body_pct:.2f}% body")
        return sigs

    def _get_trend_signals(self, state: MarketState) -> list[str]:
        t = state.technical
        sigs = []
        if t.supertrend_up:
            sigs.append("Supertrend UP")
        else:
            sigs.append("Supertrend DOWN")
        if t.ema_9 > t.ema_21 > t.ema_99:
            sigs.append("Bullish EMA alignment")
        elif t.ema_9 < t.ema_21 < t.ema_99:
            sigs.append("Bearish EMA alignment")
        if t.adx > 25:
            sigs.append(f"ADX {t.adx:.1f} — strong trend")
        elif t.adx < 15:
            sigs.append(f"ADX {t.adx:.1f} — choppy")
        if t.bb_position_pct > 0.85:
            sigs.append("Near upper BB")
        elif t.bb_position_pct < 0.15:
            sigs.append("Near lower BB")
        return sigs

    def _infer_regime(self, state: MarketState) -> str:
        t = state.technical
        if t.adx > 25:
            if t.ema_9 > t.ema_21 > t.ema_99:
                return "TRENDING_UP"
            elif t.ema_9 < t.ema_21 < t.ema_99:
                return "TRENDING_DOWN"
        return "RANGING"

    def _get_key_signals(self, state: MarketState) -> list[str]:
        t = state.technical
        signals = []
        if t.rsi_14 < 30:
            signals.append(f"RSI-14 oversold ({t.rsi_14:.1f})")
        elif t.rsi_14 > 70:
            signals.append(f"RSI-14 overbought ({t.rsi_14:.1f})")
        if t.macd_histogram > 0:
            signals.append("MACD histogram positive")
        if t.supertrend_up:
            signals.append("Supertrend bullish")
        if t.ema_9 > t.ema_21 > t.ema_99:
            signals.append("Bullish EMA alignment")
        if state.c1_is_green:
            signals.append(f"C1 GREEN with {state.c1_body_pct:.2f}% body")
        return signals

    def _get_risk_flags(self, state: MarketState) -> list[str]:
        t = state.technical
        flags = []
        if t.bb_position_pct > 0.90:
            flags.append("Near upper Bollinger Band — reversal risk")
        if t.adx < 15:
            flags.append("Low ADX — choppy market")
        if t.rsi_4 > 80:
            flags.append("Fast RSI overbought")
        return flags