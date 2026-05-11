"""
My (Hermes Agent / claude-sonnet-4-6) reasoning prompt — the main decision engine.
I am the final authority. The advisor agent runs in parallel and I reconcile with it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from src.features.market_state import MarketState


# System prompt — this is who I am in this architecture
REASONING_SYSTEM_PROMPT = """You are the MAIN REASONING ENGINE for an institutional-grade BTC 15-minute direction prediction system.
You are the final decision authority. An advisor agent runs in parallel and you reconcile with its view.

Strategy: Predict whether ≥2 of the next 3 candles (C2, C3, C4) will close GREEN or RED.
GREEN = candle close > candle open | RED = candle close < candle open

3-bet martingale: bet on C2 first. If it loses, bet on C3. If it loses, bet on C4.
Win on any 1 of 3 bets. No concurrent sessions.

Your job:
1. Reason deeply from ALL data provided
2. Produce a weighted confidence score across 6 dimensions
3. Reconcile with the advisor's opinion
4. Output GREEN / RED / SKIP with full rationale
5. Identify contradictions between signal categories

CRITICAL:
- Pre-filter has already passed (if you are seeing this data, it means hard rules passed)
- Be honest about uncertainty — SKIP is a valid and often correct response
- Never fabricate data — reason only from what is provided
- The market is not always predictable — know when to stand aside

Return ONLY valid JSON matching this schema:

{
  "call": "GREEN | RED | SKIP",
  "confidence": 0.72,
  "confidence_bucket": "HIGH | MEDIUM | LOW",
  "signal_scores": {
    "momentum": 0.75,
    "trend": 0.68,
    "orderflow": 0.82,
    "smart_money": 0.60,
    "sentiment": 0.55,
    "macro": 0.70
  },
  "dimension_weights": {
    "momentum": 0.25,
    "trend": 0.20,
    "orderflow": 0.20,
    "smart_money": 0.15,
    "sentiment": 0.10,
    "macro": 0.10
  },
  "weighted_confidence": 0.72,
  "advisor_reconciliation": {
    "advisor_called": "GREEN | RED | SKIP",
    "advisor_confidence": 0.70,
    "agreed": true,
    "conservative_override": false,
    "override_reason": ""
  },
  "analysis": {
    "candlestick": "...",
    "momentum": "...",
    "trend": "...",
    "orderflow": "...",
    "smart_money": "...",
    "sentiment": "...",
    "macro": "..."
  },
  "contradictions": [
    {"category_1": "...", "category_2": "...", "description": "...", "resolution": "..."}
  ],
  "key_bullish_signals": ["..."],
  "key_bearish_signals": ["..."],
  "risk_factors": ["..."],
  "flip_consideration": {
    "should_consider": false,
    "trigger": "",
    "counter_signal_strength": 0.0,
    "original_signal_strength": 0.0,
    "recommendation": "..."
  }
}

Confidence bucket thresholds:
- HIGH ≥ 0.70: Enter session immediately
- MEDIUM 0.55–0.69: Enter only if ≥2 signal categories score ≤0.30 or ≥0.70
- LOW < 0.55: SKIP
"""


@dataclass
class ReasoningOutput:
    """My structured output — the final decision."""
    call: str              # GREEN, RED, or SKIP
    confidence: float
    confidence_bucket: str # HIGH, MEDIUM, LOW
    signal_scores: dict[str, float]
    dimension_weights: dict[str, float]
    weighted_confidence: float
    advisor_reconciliation: dict
    analysis: dict
    contradictions: list[dict]
    key_bullish_signals: list[str]
    key_bearish_signals: list[str]
    risk_factors: list[str]
    flip_consideration: dict
    raw_response: str = ""


def build_reasoning_prompt(
    state: MarketState,
    reflection: dict,
    advisor_opinion: Optional[dict] = None,
    flip_context: Optional[dict] = None,
) -> tuple[str, str]:
    """
    Build the full reasoning prompt I use to make the decision.
    Returns (system_prompt, user_prompt).

    flip_context is provided when a C2/C3 loss triggers a flip check:
      {"original_direction": "GREEN", "loss_candle": "C2",
       "counter_signals": {...}, "advisor_flip_confidence": 0.65}
    """
    t = state.technical
    c1 = state.c1

    # ── Candle history ────────────────────────────────────────────────────
    candles_5 = []
    for c in (state.candles[-6:-1] if len(state.candles) >= 6 else state.candles[-5:]):
        direction = "GREEN" if c.is_green else "RED"
        candles_5.append(
            f"  {direction}: O={c.open:.1f} H={c.high:.1f} L={c.low:.1f} "
            f"C={c.close:.1f} V={c.volume:.2f} | body={c.body_pct:.2f}% "
            f"cp={c.close_position:.2f} pattern={c.candle_pattern}"
        )

    # ── Advisor context ──────────────────────────────────────────────────
    advisor_block = ""
    if advisor_opinion:
        advisor_block = f"""
### ADVISOR AGENT OPINION (run independently on Claude Opus 4.7)
Advisor call: {advisor_opinion.get('call', 'UNKNOWN')}
Advisor confidence: {advisor_opinion.get('confidence', 0.50):.2f}
Advisor strength: {advisor_opinion.get('advisor_strength', 'UNKNOWN')}
Advisor regime: {advisor_opinion.get('regime', 'UNKNOWN')}
Advisor key signals: {', '.join(advisor_opinion.get('key_signals', []))}
Advisor risk flags: {', '.join(advisor_opinion.get('risk_flags', []))}
"""
    else:
        advisor_block = "\n### ADVISOR AGENT: Not configured — you are the sole decision-maker.\n"

    # ── Flip context ───────────────────────────────────────────────────────
    flip_block = ""
    if flip_context:
        flip_block = f"""
### ⚠️ DIRECTION FLIP CHECK TRIGGERED
Previous direction: {flip_context['original_direction']}
Loss on candle: {flip_context['loss_candle']}
Counter-signal strength: {flip_context.get('counter_signal_strength', 0.0):.2f}
Original signal strength: {flip_context.get('original_signal_strength', 0.0):.2f}
Advisor recommends flip: {flip_context.get('advisor_flip_confidence', 0.0):.2f}
Consider flipping direction ONLY if counter-evidence is overwhelming."""

    user_prompt = f"""## MARKET DATA FOR ANALYSIS

### Identity
Analysis ID: {state.analysis_id}
Analysis time: {state.analysis_time}
Data age: {state.data_age_seconds:.0f}s
{flip_block}

### Current Price
BTC price (spot/perp): ${state.current_price:.2f}
Perp premium: {state.perp_premium_bps:.1f} bps

### C1 Candlestick (PRIMARY ANALYSIS POINT)
Direction: {"GREEN ✅" if c1.is_green else "RED 🔴"}
Body: {c1.body_pct:.3f}% of range | Wick: upper={c1.upper_wick_pct:.1f}% lower={c1.lower_wick_pct:.1f}%
Body/wick ratio: {c1.body_wick_ratio:.2f} (>1.0 = body dominates = conviction)
Close position: {c1.close_position:.2f} (0=bottom of range, 1=top of range)
Pattern: {c1.candle_pattern}
Volume: {c1.volume:.4f} BTC | RVOL: {state.rvol:.2f}x average

### Last 5 Candles (Pattern Context)
""" + "\n".join(candles_5) + f"""

### Technical Analysis
RSI-14: {t.rsi_14:.1f} ({'OVERBOUGHT' if t.rsi_14 > 70 else 'OVERSOLD' if t.rsi_14 < 30 else 'NEUTRAL'})
RSI-4: {t.rsi_4:.1f} (fast momentum)
MACD: line={t.macd_line:.2f} signal={t.macd_signal:.2f} histogram={t.macd_histogram:.4f}
MACD histogram slope: {t.macd_histogram_slope:.5f} (positive = accelerating up)
VWAP: ${t.vwap:.2f} | Price vs VWAP: {((state.current_price - t.vwap) / t.vwap * 100):.3f}%
ADX: {t.adx:.1f} ({'STRONG TREND' if t.adx > 25 else 'WEAK TREND' if t.adx < 15 else 'MODERATE'})
Supertrend: {"🟢 UP — bearish only with >0.10% counter-move" if t.supertrend_up else "🔴 DOWN — bullish only with >0.10% counter-move"}
EMA9: ${t.ema_9:.2f} | EMA21: ${t.ema_21:.2f} | EMA99: ${t.ema_99:.2f}
EMA structure: {"🟢 BULLISH (9>21>99)" if t.ema_9 > t.ema_21 > t.ema_99 else "🔴 BEARISH (9<21<99)" if t.ema_9 < t.ema_21 < t.ema_99 else "⚪ MIXED"}
Bollinger Bands: upper=${t.bb_upper:.2f} mid=${t.bb_middle:.2f} lower=${t.bb_lower:.2f}
BB %B: {t.bb_position_pct:.2f} — {'near upper band' if t.bb_position_pct > 0.8 else 'near lower band' if t.bb_position_pct < 0.2 else 'mid-range'}
ATR-14: ${t.atr_14:.2f}
Keltner: upper=${t.keltner_upper:.2f} lower=${t.keltner_lower:.2f}
Pivots: R2=${t.pivot_r2:.2f} R1=${t.pivot_r1:.2f} PP=${t.pivot_pivot:.2f} S1=${t.pivot_s1:.2f} S2=${t.pivot_s2:.2f}
KDJ: K={t.k:.1f} D={t.d:.1f} J={t.j:.1f}
Price velocity (5-candle): {t.price_velocity_5:.3f}%

### Orderflow
VPIN: {state.vpin:.4f} — {'⚠️ HIGH (institutional activity — directional move likely)' if state.vpin > 0.6 else 'normal range'}
CVD (200-trade): {state.cvd:.4f} BTC — {'📈 POSITIVE (buy pressure)' if state.cvd > 0 else '📉 NEGATIVE (sell pressure)'}
TCR (200-trade): {state.tcr:.3f} — {'buy-aggression dominant' if state.tcr > 0 else 'sell-aggression dominant'}
OFI (20-trade): {state.ofi:.4f}
Order Book Imbalance (5-level): {state.obi:.3f} — {'bid pressure' if state.obi > 0.1 else 'ask pressure' if state.obi < -0.1 else 'balanced'}
Spread: {state.spread_bps:.1f} bps

### Smart Money
Funding rate: {state.smart_money.funding_rate_pct:.4f}% — {state.smart_money.funding_rate_direction}
Long/Short ratio: {state.smart_money.long_short_ratio:.3f} — {'🟢 longs dominant' if state.smart_money.long_short_ratio > 1.1 else '🔴 shorts dominant' if state.smart_money.long_short_ratio < 0.9 else 'balanced'}
Long account %: {state.smart_money.long_account_ratio:.1%}
Open interest: {state.smart_money.open_interest_btc:.0f} BTC
Perp premium: {state.perp_premium_bps:.1f} bps

### Sentiment
Fear & Greed Index: {state.sentiment.fear_greed_index} — {state.sentiment.fear_greed_zone}
BTC Dominance: {state.sentiment.btc_dominance:.2f}%
Social hype: {state.sentiment.social_hype_score:.2f}

### Macro
DXY: {state.macro.dxy:.3f} ({state.macro.dxy_change_pct:+.3f}%) — {'BTC headwind' if state.macro.dxy_change_pct > 0.3 else 'BTC tailwind' if state.macro.dxy_change_pct < -0.3 else 'neutral'}
S&P 500: {state.macro.sp500:.2f} ({state.macro.sp500_change_pct:+.3f}%)
VIX: {state.macro.vix:.2f} ({'risk-off' if state.macro.risk_off else 'risk-on'})
BTC macro score: {state.macro.btc_macro_score:.2f}/1.0
{advisor_block}

### Reflection Context (Recent History — use to detect regime shifts)
Last 20 outcomes: {reflection.get('last_20_outcomes_formatted', 'N/A')}
Running win rate (20): {reflection.get('rolling_win_rate_20', 0.0)*100:.1f}%
Consecutive losses: {reflection.get('consecutive_losses', 0)}
Consecutive wins: {reflection.get('consecutive_wins', 0)}
Market regime: {reflection.get('regime', 'UNKNOWN')}
Avg session length: {reflection.get('avg_session_length', 1.5):.1f} candles
Last flip: {reflection.get('last_flip', 'None')}

---

Analyze this data. Apply your 7-step framework. Produce a JSON decision.

IMPORTANT:
- If you recommend GREEN: you believe ≥2 of C2, C3, C4 will close GREEN
- If you recommend RED: you believe ≥2 of C2, C3, C4 will close RED
- If you recommend SKIP: market conditions are insufficient for a confident call
- A SKIP is not a failure — it is discipline
- Be honest about contradictions — list them explicitly
- The pre-filter has already passed — do not re-apply the same rules
"""

    return REASONING_SYSTEM_PROMPT, user_prompt


def parse_reasoning_output(raw: str) -> ReasoningOutput:
    """Parse the JSON output from the reasoning engine."""
    try:
        json_str = raw.strip()
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            json_str = "\n".join(
                lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            )
        data = json.loads(json_str)
        return ReasoningOutput(
            call=data.get("call", "SKIP"),
            confidence=float(data.get("weighted_confidence", data.get("confidence", 0.50))),
            confidence_bucket=data.get("confidence_bucket", "LOW"),
            signal_scores=data.get("signal_scores", {}),
            dimension_weights=data.get("dimension_weights", {}),
            weighted_confidence=float(data.get("weighted_confidence", 0.50)),
            advisor_reconciliation=data.get("advisor_reconciliation", {}),
            analysis=data.get("analysis", {}),
            contradictions=data.get("contradictions", []),
            key_bullish_signals=data.get("key_bullish_signals", []),
            key_bearish_signals=data.get("key_bearish_signals", []),
            risk_factors=data.get("risk_factors", []),
            flip_consideration=data.get("flip_consideration", {}),
            raw_response=raw,
        )
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse reasoning output: {e}\nRaw: {raw[:500]}")
