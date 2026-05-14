"""
SENTIMENT SCOUT — Sentiment & narrative specialist.
Owns: SENTIMENT dimension.
"""
from __future__ import annotations

from src.agents.base.base_agent import AgentSignal, BaseAgent
from src.features.market_state import MarketState


class SentimentScout(BaseAgent):
    name = "SENTIMENT_SCOUT"
    model = "claude-sonnet-4-6"
    max_tokens = 768
    temperature = 0.2

    @property
    def system_prompt(self) -> str:
        return """You are SENTIMENT SCOUT — market sentiment and narrative analyst.

Your dimension: SENTIMENT (weight: 0.10)
Score: 0.0 = extremely fearful/bearish, 0.5 = neutral, 1.0 = extremely greedy/bullish

Interpret Fear & Greed Index:
- <25: EXTREME FEAR → contrarian BUY signal
- 25-45: FEAR → slightly bearish
- 45-55: NEUTRAL
- 55-75: GREED → slightly bullish
- >75: EXTREME GREED → contrarian caution

Also consider BTC dominance shifts and social volume.

Return STRICT JSON:
{
  "dimension": "sentiment",
  "score": 0.42,
  "confidence": 0.65,
  "regime": "FEAR",
  "key_signals": ["Fear & Greed in FEAR zone (38)", "Contrarian bounce setup"],
  "contradictions": [],
  "risk_flags": ["Social volume declining"]
}"""

    def build_prompt(self, state: MarketState, reflection: dict) -> str:
        sentiment = state.sentiment or type('obj', (object,), {
            'fear_greed_index': 50,
            'fear_greed_zone': 'NEUTRAL',
            'fear_greed_trend': 'NEUTRAL',
            'btc_dominance': 50.0,
            'social_hype_score': 0.5,
        })()
        return f"""## SENTIMENT DATA

Fear & Greed Index: {sentiment.fear_greed_index} — {sentiment.fear_greed_zone}
Fear & Greed trend: {sentiment.fear_greed_trend}
BTC Dominance: {sentiment.btc_dominance:.1f}%
Social hype: {sentiment.social_hype_score:.2f}

Reflect: {reflection.get('last_20_outcomes_formatted', 'N/A')}
"""

    async def analyze(self, state: MarketState, reflection: dict) -> dict[str, AgentSignal]:
        """Produce a sentiment signal."""
        score, confidence = self._compute_sentiment_score(state)
        sentiment = state.sentiment or type('obj', (object,), {
            'fear_greed_index': 50,
            'fear_greed_zone': 'NEUTRAL',
            'fear_greed_trend': 'NEUTRAL',
            'btc_dominance': 50.0,
            'social_hype_score': 0.5,
        })()

        key_signals = []
        fg = sentiment.fear_greed_index
        if fg <= 25:
            key_signals.append(f"EXTREME FEAR ({fg}) — contrarian buy setup")
            score = max(score, 0.65)  # Bullish contrarian: extreme fear = bullish
        elif fg <= 45:
            key_signals.append(f"FEAR zone ({fg})")
        elif fg >= 75:
            key_signals.append(f"EXTREME GREED ({fg}) — contrarian caution, reversal risk")
            score = min(score, 0.35)  # Bearish contrarian: extreme greed = bearish
        elif fg >= 55:
            key_signals.append(f"GREED zone ({fg})")

        if sentiment.fear_greed_trend == "FALLING":
            key_signals.append("Fear & Greed FALLING")
        elif sentiment.fear_greed_trend == "RISING":
            key_signals.append("Fear & Greed RISING")

        if sentiment.btc_dominance > 55:
            key_signals.append(f"BTC dominance {sentiment.btc_dominance:.1f}% — BTC strength")
        elif sentiment.btc_dominance < 48:
            key_signals.append(f"BTC dominance {sentiment.btc_dominance:.1f}% — alt season rotation")

        risk_flags = []
        if fg <= 20:
            risk_flags.append("Extreme fear — market capitulation possible")
        if sentiment.btc_dominance > 58:
            risk_flags.append("Very high BTC dominance — alt coin risk-off")

        return {
            "sentiment": AgentSignal(
                dimension="sentiment",
                score=round(score, 3),
                confidence=round(confidence, 3),
                regime=sentiment.fear_greed_zone or "NEUTRAL",
                key_signals=key_signals,
                risk_flags=risk_flags,
            )
        }

    def _compute_sentiment_score(self, state: MarketState) -> tuple[float, float]:
        """Compute sentiment score from Fear & Greed and BTC dominance."""
        sentiment = state.sentiment
        if not sentiment:
            return 0.5, 0.3

        fg = sentiment.fear_greed_index
        fg_score = fg / 100.0

        weight = 0.7
        dom = sentiment.btc_dominance
        if dom > 55:
            fg_score = min(fg_score + 0.05, 0.95)
            weight += 0.15
        elif dom < 48:
            fg_score = max(fg_score - 0.05, 0.05)
            weight += 0.15

        score = fg_score
        confidence = min(0.80, 0.4 + weight * 0.3)
        return score, confidence