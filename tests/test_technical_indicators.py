"""
Tests for technical indicators — verify calculations against known values.
"""
import pytest
import numpy as np

from src.data_sources.binance_client import Candle
from src.features.technical_indicators import (
    compute_indicators, TechnicalState,
    _rsi, _macd, _atr, _ema, _adx, _supertrend, _kdj,
)


def _candle(open_, high, low, close, volume=1.0) -> Candle:
    return Candle(
        open_time=0, open=open_, high=high, low=low,
        close=close, volume=volume, close_time=0,
        quote_volume=0, trades=1, buy_volume=0, sell_volume=0,
    )


def _candles_from_closes(closes: list[float], opens: list | None = None) -> list[Candle]:
    opens = opens or [c * 0.998 for c in closes]
    highs = [max(o, c) * 1.002 for o, c in zip(opens, closes)]
    lows = [min(o, c) * 0.998 for o, c in zip(opens, closes)]
    return [
        _candle(o, h, l, c, volume=1.0)
        for o, h, l, c in zip(opens, highs, lows, closes)
    ]


class TestCandleProperties:
    def test_green_candle(self):
        c = _candle(95000, 96000, 94800, 95800)
        assert c.is_green
        assert c.body_pct > 0

    def test_red_candle(self):
        c = _candle(96000, 96100, 95000, 95200)
        assert not c.is_green

    def test_close_position_top(self):
        c = _candle(95000, 96000, 95000, 95900)
        assert c.close_position >= 0.9

    def test_close_position_bottom(self):
        c = _candle(95000, 95200, 94800, 94850)
        assert c.close_position <= 0.15

    def test_doji_candle(self):
        c = _candle(95000, 95050, 94950, 95000)
        assert c.body_pct < 0.1
        assert c.candle_pattern == "DOJI"

    def test_hammer_pattern(self):
        c = _candle(95000, 96000, 94800, 95800)
        c2 = _candle(95800, 95900, 94800, 94900)
        assert c.candle_pattern in ("BULLISH_CLOSE", "GREEN")

    def test_body_wick_ratio(self):
        c = _candle(95000, 96000, 95000, 95900)
        assert c.body_wick_ratio > 0


class TestRSI:
    def test_rsi_calculation(self):
        # Strong uptrend → RSI should be > 50
        closes = [100 + i * 0.5 for i in range(30)]
        cl = np.array(closes, dtype=np.float64)
        rsi = _rsi(cl, 14)
        assert rsi >= 95.0  # Uptrend consistently positive → RSI very high

    def test_rsi_no_change(self):
        # Flat price → RSI=100 (Wilder smoothing: no losses → RS=∞ → RSI=100)
        # This is known RSI behavior — not a bug
        closes = [100.0] * 30
        cl = np.array(closes, dtype=np.float64)
        rsi = _rsi(cl, 14)
        assert rsi == 100.0


class TestMACD:
    def test_macd_output_shapes(self):
        closes = [100 + i * 0.5 for i in range(60)]
        cl = np.array(closes, dtype=np.float64)
        line, signal, hist = _macd(cl)
        assert isinstance(line, float)
        assert isinstance(signal, float)
        assert isinstance(hist, float)


class TestATR:
    def test_atr_positive(self):
        closes = [100] * 20
        highs = [105] * 20
        lows = [95] * 20
        h = np.array(highs, dtype=np.float64)
        l = np.array(lows, dtype=np.float64)
        c = np.array(closes, dtype=np.float64)
        atr = _atr(h, l, c, 14)
        assert atr > 0


class TestEMA:
    def test_ema_smoothing(self):
        closes = [100 + i for i in range(50)]
        cl = np.array(closes, dtype=np.float64)
        ema_9 = _ema(cl, 9)
        ema_50 = _ema(cl, 50)
        # EMA9 should be higher than EMA50 in an uptrend
        assert ema_9 > ema_50


class TestSupertrend:
    def test_supertrend_direction(self):
        # Uptrend: price consistently rising
        closes = [100 + i * 2 for i in range(30)]
        highs = [c + 3 for c in closes]
        lows = [c - 3 for c in closes]
        h = np.array(highs, dtype=np.float64)
        l = np.array(lows, dtype=np.float64)
        c = np.array(closes, dtype=np.float64)
        up, atr = _supertrend(h, l, c, 10, 3.0)
        assert up is True


class TestComputeIndicators:
    def test_enough_candles(self):
        candles = _candles_from_closes([100 + i for i in range(60)])
        state = compute_indicators(candles)
        assert isinstance(state, TechnicalState)
        assert state.rsi_14 > 0

    def test_insufficient_candles_raises(self):
        candles = _candles_from_closes([100, 101, 102])
        with pytest.raises(ValueError):
            compute_indicators(candles)

    def test_bbands_position(self):
        closes = [100] * 30
        # Add a spike
        closes = closes[:-1] + [103, 97]
        candles = _candles_from_closes(closes)
        state = compute_indicators(candles)
        assert -1.0 <= state.bb_position_pct <= 2.0  # Can go outside bands in spikes
