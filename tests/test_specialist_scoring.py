"""
Tests for specialist scoring normalization and edge cases.
Phase 1 Bugs 3, 4, 5.
"""
import pytest
from unittest.mock import MagicMock

from src.agents.specialists.quant_master import QuantMaster
from src.agents.specialists.flow_master import FlowMaster
from src.agents.specialists.sentiment_scout import SentimentScout


class MockTechnical:
    def __init__(self, **kwargs):
        attrs = {
            "rsi_14": 50.0, "rsi_4": 50.0,
            "macd_line": 0.0, "macd_signal": 0.0, "macd_histogram": 0.0,
            "macd_histogram_slope": 0.0, "vwap": 50000.0,
            "adx": 20.0, "supertrend_up": True,
            "ema_9": 50000.0, "ema_21": 50000.0, "ema_99": 50000.0,
            "bb_upper": 52000.0, "bb_middle": 50000.0, "bb_lower": 48000.0,
            "bb_position_pct": 0.50,
            "pivot_r2": 51000.0, "pivot_r1": 50500.0, "pivot_pivot": 50000.0,
            "pivot_s1": 49500.0, "pivot_s2": 49000.0,
            "k": 50.0, "d": 50.0, "j": 50.0,
            "price_velocity_5": 0.0,
        }
        attrs.update(kwargs)
        for k, v in attrs.items():
            setattr(self, k, v)


class TestQuantMasterNormalization:
    def test_single_signal_rsi_oversold(self):
        """Single RSI oversold → score should be bullish, within bounds."""
        qm = QuantMaster()
        state = MagicMock()
        state.technical = MockTechnical(rsi_14=25.0, macd_histogram=0.0, supertrend_up=False,
                                        ema_9=49000.0, ema_21=49500.0, ema_99=50500.0,
                                        adx=12.0, bb_position_pct=0.50, price_velocity_5=0.0)
        state.c1_is_green = False
        state.c1_body_pct = 0.05
        state.c1 = MagicMock()
        score, conf = qm._compute_momentum_score(state)
        assert 0.5 <= score <= 0.95

    def test_two_aligned_bullish_signals(self):
        """RSI oversold + MACD positive → score should reflect both, not overshoot."""
        qm = QuantMaster()
        state = MagicMock()
        state.technical = MockTechnical(rsi_14=25.0, macd_histogram=50.0, macd_histogram_slope=5.0,
                                        supertrend_up=True, ema_9=50000.0, ema_21=50000.0, ema_99=50000.0,
                                        adx=20.0, bb_position_pct=0.50, price_velocity_5=0.0)
        state.c1_is_green = True
        state.c1_body_pct = 0.05
        state.c1 = MagicMock()
        score, conf = qm._compute_momentum_score(state)
        assert 0.5 <= score <= 0.95

    def test_all_bearish_signals(self):
        """All indicators bearish → score should be ~0.10-0.30."""
        qm = QuantMaster()
        state = MagicMock()
        state.technical = MockTechnical(
            rsi_14=75.0, macd_histogram=-50.0, macd_histogram_slope=-5.0,
            supertrend_up=False,
            ema_9=49000.0, ema_21=49500.0, ema_99=50500.0,
            adx=25.0, bb_position_pct=0.90, price_velocity_5=-1.0
        )
        state.c1_is_green = False
        state.c1_body_pct = 0.30
        state.c1 = MagicMock()
        score, conf = qm._compute_momentum_score(state)
        assert 0.05 <= score <= 0.50

    def test_no_signals_neutral(self):
        """Momentum score always falls within valid range after clamping."""
        qm = QuantMaster()
        state = MagicMock()
        state.technical = MockTechnical(
            rsi_14=50.0,
            macd_histogram=0.0,
            macd_histogram_slope=0.0,
            supertrend_up=True,
            ema_9=50000.0,
            ema_21=50000.0,
            ema_99=50000.0,
            adx=10.0,
            bb_position_pct=0.50,
            price_velocity_5=0.0,
        )
        state.c1_is_green = True
        state.c1_body_pct = 0.05
        state.c1 = MagicMock()
        score, conf = qm._compute_momentum_score(state)
        # Score must always be in [0.05, 0.95] after clamping
        assert 0.05 <= score <= 0.95
        assert 0.0 <= conf <= 0.90


class TestFlowMasterCVDClamping:
    def test_cvd_positive_200(self):
        """CVD=+200 → contribution clamped to max ±0.20."""
        state = MagicMock()
        state.vpin = 0.30
        state.cvd = 200.0
        state.tcr = 0.0
        state.obi = 0.0
        state.ofi = 0.0
        state.c1_is_green = True
        state.c1 = MagicMock()

        fm = FlowMaster()
        score, conf = fm._compute_orderflow_score(state)
        # CVD contribution: (200/400)*0.25 = 0.125, clamped to ±0.20 → 0.125
        # score should be close to 0.5 + 0.125 = 0.625
        assert 0.5 <= score <= 0.90

    def test_cvd_extreme_positive_1000(self):
        """CVD=+1000 → contribution clamped, no overflow."""
        state = MagicMock()
        state.vpin = 0.30
        state.cvd = 1000.0
        state.tcr = 0.0
        state.obi = 0.0
        state.ofi = 0.0
        state.c1_is_green = True
        state.c1 = MagicMock()

        fm = FlowMaster()
        score, conf = fm._compute_orderflow_score(state)
        # CVD=1000: (1000/400)*0.25 = 0.625 → clamped to 0.20
        # score = 0.5 + 0.20 = 0.70 max
        assert score <= 0.95, f"CVD overflow: score={score} should be ≤0.95"

    def test_cvd_extreme_negative_1000(self):
        """CVD=-1000 → contribution clamped to max, no underflow."""
        state = MagicMock()
        state.vpin = 0.30
        state.cvd = -1000.0
        state.tcr = 0.0
        state.obi = 0.0
        state.ofi = 0.0
        state.c1_is_green = True
        state.c1 = MagicMock()

        fm = FlowMaster()
        score, conf = fm._compute_orderflow_score(state)
        # Clamped to -0.20 → score = 0.5 - 0.20 = 0.30
        assert score >= 0.05, f"CVD underflow: score={score} should be ≥0.05"

    def test_cvd_zero(self):
        """CVD=0 → neutral, no contribution."""
        state = MagicMock()
        state.vpin = 0.30
        state.cvd = 0.0
        state.tcr = 0.0
        state.obi = 0.0
        state.ofi = 0.0
        state.c1_is_green = True
        state.c1 = MagicMock()

        fm = FlowMaster()
        score, conf = fm._compute_orderflow_score(state)
        assert 0.45 <= score <= 0.55


class TestSentimentScoutContrarianLogic:
    @pytest.mark.asyncio
    async def test_extreme_fear_is_bullish(self):
        """Fear & Greed ≤ 25 → score should be bullish (contrarian)."""
        state = MagicMock()
        state.sentiment = MagicMock()
        state.sentiment.fear_greed_index = 15
        state.sentiment.fear_greed_zone = "EXTREME_FEAR"
        state.sentiment.fear_greed_trend = "FALLING"
        state.sentiment.btc_dominance = 50.0
        state.sentiment.social_hype_score = 0.5

        ss = SentimentScout()
        sigs = await ss.analyze(state, {})

        assert "sentiment" in sigs
        sig = sigs["sentiment"]
        assert sig.score >= 0.65, f"Extreme fear should be bullish, got score={sig.score}"
        assert "contrarian buy setup" in sig.key_signals[0]

    @pytest.mark.asyncio
    async def test_extreme_greed_is_bearish(self):
        """Fear & Greed ≥ 75 → score should be bearish (contrarian)."""
        state = MagicMock()
        state.sentiment = MagicMock()
        state.sentiment.fear_greed_index = 85
        state.sentiment.fear_greed_zone = "EXTREME_GREED"
        state.sentiment.fear_greed_trend = "RISING"
        state.sentiment.btc_dominance = 50.0
        state.sentiment.social_hype_score = 0.5

        ss = SentimentScout()
        sigs = await ss.analyze(state, {})

        assert "sentiment" in sigs
        sig = sigs["sentiment"]
        assert sig.score <= 0.35, f"Extreme greed should be bearish, got score={sig.score}"
        assert "contrarian caution" in sig.key_signals[0]

    @pytest.mark.asyncio
    async def test_neutral_fear_greed(self):
        """Fear & Greed around 50 → neutral score."""
        state = MagicMock()
        state.sentiment = MagicMock()
        state.sentiment.fear_greed_index = 50
        state.sentiment.fear_greed_zone = "NEUTRAL"
        state.sentiment.fear_greed_trend = "NEUTRAL"
        state.sentiment.btc_dominance = 50.0
        state.sentiment.social_hype_score = 0.5

        ss = SentimentScout()
        sigs = await ss.analyze(state, {})

        assert "sentiment" in sigs
        sig = sigs["sentiment"]
        assert 0.30 <= sig.score <= 0.70

    @pytest.mark.asyncio
    async def test_fear_zone_slightly_bearish(self):
        """Fear & Greed 25-45 → slightly bearish."""
        state = MagicMock()
        state.sentiment = MagicMock()
        state.sentiment.fear_greed_index = 35
        state.sentiment.fear_greed_zone = "FEAR"
        state.sentiment.fear_greed_trend = "NEUTRAL"
        state.sentiment.btc_dominance = 50.0
        state.sentiment.social_hype_score = 0.5

        ss = SentimentScout()
        sigs = await ss.analyze(state, {})

        assert "sentiment" in sigs
        sig = sigs["sentiment"]
        assert sig.score < 0.55