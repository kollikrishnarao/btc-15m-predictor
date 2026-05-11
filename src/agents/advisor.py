"""
Advisor Agent — runs on Claude Opus 4.7 with max reasoning.
Independent parallel analysis that cross-validates the main engine.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Optional

import anthropic

from config.constants import ANTHROPIC_ADVISOR_KEY, ANTHROPIC_BASE_URL, BRAINS
from src.features.market_state import MarketState

log = logging.getLogger(__name__)

ADVISOR_SYSTEM_PROMPT = """You are a senior quantitative analyst and crypto market structure expert.
You are the ADVISOR AGENT — an independent parallel analysis system.
Your job is to provide an independent assessment of the next 3 BTC 15-minute candle directions.

## Your Role
You are NOT the final decision-maker. You are a rigorous cross-validator.
Your output will be reconciled with the main reasoning engine's output.
When you and the main engine disagree, the main engine weighs the more conservative call
unless it has >0.15 higher confidence than you.

## The Question
Will ≥2 of the next 3 candles (C2, C3, C4) close GREEN or RED?
GREEN = candle close > candle open (price went up)
RED = candle close < candle open (price went down)

## Context You Must Consider

### Data You Receive
- C1 candlestick details (body size, wicks, pattern, close position in range)
- Technical indicators (RSI, MACD, Bollinger Bands, VWAP, ATR, Supertrend, ADX)
- Orderflow metrics (VPIN, CVD, TCR, OBI, OFI)
- Smart money (funding rate, open interest, long/short ratio)
- Sentiment (Fear & Greed Index + zone)
- Macro (DXY, S&P 500, VIX)
- Reflection context (recent session history, win rate, regime)

### Your Analysis Framework
Step 1 — CANDLESTICK: What does C1's formation tell us about immediate momentum?
Step 2 — MOMENTUM: Are RSI, MACD, price velocity aligned?
Step 3 — TREND: Does ADX confirm the trend? Is BB tightening or expanding?
Step 4 — ORDERFLOW: Is VPIN elevated? Is CVD diverging from price?
Step 5 — SMART MONEY: Are institutions positioned for the same direction?
Step 6 — SENTIMENT: Extreme Fear or Greed zone? Contrarian or confirming signal?
Step 7 — MACRO: Does macro backdrop support or contradict the direction?

### Output Format — STRICT JSON
Return ONLY valid JSON. No markdown, no preamble, no explanation.

```json
{
  "call": "GREEN | RED | SKIP",
  "confidence": 0.72,
  "reasoning": {
    "candlestick": "brief assessment of C1 formation",
    "momentum": "RSI/MACD/velocity assessment",
    "trend": "trend alignment + ADX assessment",
    "orderflow": "VPIN/CVD/TCR assessment",
    "smart_money": "funding/OI/long-short assessment",
    "sentiment": "Fear&Greed zone + signal",
    "macro": "macro context + direction",
    "contradictions": "any signals that point in opposite directions"
  },
  "key_signals": ["list of 3-5 strongest signals with direction"],
  "risk_flags": ["any risk factors that could invalidate this call"],
  "advisor_strength": "HIGH | MEDIUM | LOW",
  "regime_assessment": "TRENDING_UP | TRENDING_DOWN | RANGING | VOLATILE"
}
```

## Critical Rules
- Return ONLY JSON. No text outside the JSON object.
- Confidence must be between 0.50 and 0.99.
- If you cannot form a confident call (>0.55), return SKIP.
- If market data is incomplete or stale, return SKIP.
- Do not hallucinate data. Only reason from what is provided.
"""


@dataclass
class AdvisorOpinion:
    """Output from the Advisor Agent."""
    call: str          # GREEN, RED, or SKIP
    confidence: float
    reasoning: dict
    key_signals: list[str]
    risk_flags: list[str]
    advisor_strength: str
    regime: str
    raw_response: str = ""
    latency_ms: float = 0.0


class AdvisorAgent:
    """
    Advisor Agent — runs on Claude Opus 4.7 with extended thinking.
    Executes in parallel with the main reasoning engine.
    Provides independent advisory opinion that the main engine reconciles.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ANTHROPIC_ADVISOR_KEY
        self.model = BRAINS["advisor"]["model"]
        self.max_tokens = BRAINS["advisor"]["max_tokens"]
        self.temperature = BRAINS["advisor"]["temperature"]
        self.thinking = BRAINS["advisor"]["thinking"]
        self._client: Optional[anthropic.AsyncAnthropic] = None

    async def __aenter__(self):
        if self.api_key:
            self._client = anthropic.AsyncAnthropic(
                api_key=self.api_key,
                base_url=ANTHROPIC_BASE_URL,
            )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    def build_prompt(self, state: MarketState, reflection: dict) -> str:
        """Build the advisor analysis prompt from a MarketState."""
        t = state.technical
        c1 = state.c1

        candles_5 = []
        for c in (state.candles[-6:-1] if len(state.candles) >= 6 else state.candles[-5:]):
            direction = "GREEN" if c.is_green else "RED"
            candles_5.append(
                f"  {direction}: O={c.open:.1f} H={c.high:.1f} L={c.low:.1f} "
                f"C={c.close:.1f} V={c.volume:.2f} | body={c.body_pct:.2f}% "
                f"cp={c.close_position:.2f} pattern={c.candle_pattern}"
            )

        prompt = f"""## ANALYSIS DATA

### Market
Current price: ${state.current_price:.2f}
C1 timestamp: {state.analysis_time}
Data age: {state.data_age_seconds:.0f}s

### C1 Candlestick (Primary Signal)
Direction: {"GREEN" if c1.is_green else "RED"}
Body: {c1.body_pct:.3f}% | Wick upper: {c1.upper_wick_pct:.1f}% lower: {c1.lower_wick_pct:.1f}%
Body/wick ratio: {c1.body_wick_ratio:.2f}
Close position in range: {c1.close_position:.2f} (0=bottom, 1=top)
Pattern: {c1.candle_pattern}
Volume: {c1.volume:.4f} BTC | RVOL: {state.rvol:.2f}x

### Last 5 Candles (Context)
""" + "\n".join(candles_5) + f"""

### Technical Indicators
RSI-14: {t.rsi_14:.1f} | RSI-4: {t.rsi_4:.1f}
MACD: line={t.macd_line:.2f} signal={t.macd_signal:.2f} histogram={t.macd_histogram:.4f}
MACD histogram slope: {t.macd_histogram_slope:.4f}
VWAP: ${t.vwap:.2f} | Current vs VWAP: {((state.current_price - t.vwap) / t.vwap * 100):.3f}%
ADX: {t.adx:.1f} | Supertrend: {"UP" if t.supertrend_up else "DOWN"} | ATR: ${t.atr_14:.2f}
EMA9: ${t.ema_9:.2f} | EMA21: ${t.ema_21:.2f} | EMA99: ${t.ema_99:.2f}
EMA alignment: {"BULLISH" if t.ema_9 > t.ema_21 > t.ema_99 else "BEARISH" if t.ema_9 < t.ema_21 < t.ema_99 else "MIXED"}
Bollinger Bands: upper=${t.bb_upper:.2f} middle=${t.bb_middle:.2f} lower=${t.bb_lower:.2f}
BB %B position: {t.bb_position_pct:.2f} (0=at lower band, 1=at upper band)
Pivots: R2=${t.pivot_r2:.2f} R1=${t.pivot_r1:.2f} PP=${t.pivot_pivot:.2f} S1=${t.pivot_s1:.2f} S2=${t.pivot_s2:.2f}
KDJ: K={t.k:.1f} D={t.d:.1f} J={t.j:.1f}
Price velocity (5-candle): {t.price_velocity_5:.3f}%

### Orderflow
VPIN: {state.vpin:.4f} (high = institutional activity)
CVD (200-trade): {state.cvd:.4f} BTC | CVD sign: {"POSITIVE (buy pressure)" if state.cvd > 0 else "NEGATIVE (sell pressure)"}
TCR (200-trade): {state.tcr:.3f} | OFI: {state.ofi:.4f}
Order Book Imbalance (5-level): {state.obi:.3f} (positive = bid-side pressure)

### Smart Money
Funding rate: {state.smart_money.funding_rate_pct:.4f}% | Direction: {state.smart_money.funding_rate_direction}
Long/Short ratio: {state.smart_money.long_short_ratio:.3f} | Long account %: {state.smart_money.long_account_ratio:.1%}
Open interest: {state.smart_money.open_interest_btc:.0f} BTC
Perp premium: {state.perp_premium_bps:.1f} bps

### Sentiment
Fear & Greed Index: {state.sentiment.fear_greed_index} | Zone: {state.sentiment.fear_greed_zone}
BTC Dominance: {state.sentiment.btc_dominance:.2f}%

### Macro
DXY: {state.macro.dxy:.3f} ({state.macro.dxy_change_pct:+.3f}%)
S&P 500: {state.macro.sp500:.2f} ({state.macro.sp500_change_pct:+.3f}%)
VIX: {state.macro.vix:.2f}
BTC macro score: {state.macro.btc_macro_score:.2f}

### Reflection Context
Last 20 outcomes: {reflection.get("last_20_outcomes_formatted", "N/A")}
Running win rate: {reflection.get("rolling_win_rate_20", 0.0)*100:.1f}%
Consecutive losses: {reflection.get("consecutive_losses", 0)}
Consecutive wins: {reflection.get("consecutive_wins", 0)}
Market regime: {reflection.get("regime", "UNKNOWN")}
"""

        return prompt

    async def analyze(self, state: MarketState, reflection: dict) -> AdvisorOpinion:
        """
        Run advisor analysis with max reasoning on Claude Opus 4.7.
        Returns AdvisorOpinion with call, confidence, and reasoning.
        """
        if not self.api_key or not self._client:
            log.warning("No ANTHROPIC_ADVISOR_KEY — advisor returning neutral SKIP")
            return AdvisorOpinion(
                call="SKIP", confidence=0.50, reasoning={},
                key_signals=[], risk_flags=[],
                advisor_strength="LOW", regime="UNKNOWN",
                raw_response="No API key configured",
            )

        prompt = self.build_prompt(state, reflection)
        t0 = asyncio.get_event_loop().time()

        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=ADVISOR_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                thinking={
                    "type": "enabled",
                    "budget_tokens": 2048,
                },
            )

            latency_ms = (asyncio.get_event_loop().time() - t0) * 1000

            # Extract content blocks
            text_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content += block.text
                elif block.type == "thinking":
                    log.debug(f"Advisor thinking: {block.text[:200]}...")

            return self._parse_response(text_content, latency_ms, response.id)

        except Exception as e:
            log.error(f"Advisor agent error: {e}")
            return AdvisorOpinion(
                call="SKIP", confidence=0.50, reasoning={},
                key_signals=[], risk_flags=[],
                advisor_strength="LOW", regime="UNKNOWN",
                raw_response=f"Error: {e}",
            )

    def _parse_response(self, raw: str, latency_ms: float, msg_id: str = ""
                        ) -> AdvisorOpinion:
        """Parse JSON from advisor response."""
        try:
            # Try to extract JSON from response
            json_str = raw.strip()
            # Handle if response has markdown code blocks
            if json_str.startswith("```"):
                lines = json_str.split("\n")
                json_str = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            data = json.loads(json_str)
            return AdvisorOpinion(
                call=data.get("call", "SKIP"),
                confidence=float(data.get("confidence", 0.50)),
                reasoning=data.get("reasoning", {}),
                key_signals=data.get("key_signals", []),
                risk_flags=data.get("risk_flags", []),
                advisor_strength=data.get("advisor_strength", "LOW"),
                regime=data.get("regime_assessment", "UNKNOWN"),
                raw_response=raw,
                latency_ms=latency_ms,
            )
        except json.JSONDecodeError as e:
            log.warning(f"Advisor JSON parse failed: {e} — raw: {raw[:300]}")
            return AdvisorOpinion(
                call="SKIP", confidence=0.50, reasoning={},
                key_signals=[], risk_flags=[],
                advisor_strength="LOW", regime="UNKNOWN",
                raw_response=raw,
                latency_ms=latency_ms,
            )
