"""
Technical indicators for 15m BTC candles.
Pure Python/NumPy implementations (no ta-lib required).
Includes candlestick pattern recognition, all standard TA.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from src.data_sources.binance_client import Candle

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TechnicalState:
    # Candlestick
    c1_pattern: str = "UNKNOWN"
    c1_body_pct: float = 0.0
    c1_close_position: float = 0.5
    c1_upper_wick_pct: float = 0.0
    c1_lower_wick_pct: float = 0.0
    c1_body_wick_ratio: float = 0.0

    # Momentum
    rsi_14: float = 50.0
    rsi_4: float = 50.0
    macd_line: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0
    macd_histogram_slope: float = 0.0
    price_velocity_5: float = 0.0   # % change over last 5 candles

    # Trend
    vwap: float = 0.0
    adx: float = 25.0
    supertrend_up: bool = True
    supertrend_atr: float = 0.0
    ema_9: float = 0.0
    ema_21: float = 0.0
    ema_99: float = 0.0
    ema_cross_up: bool = True
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_position_pct: float = 0.5   # %B: 0=lower, 1=upper

    # Volatility
    atr_14: float = 0.0
    keltner_upper: float = 0.0
    keltner_lower: float = 0.0

    # Pivots
    pivot_r1: float = 0.0
    pivot_r2: float = 0.0
    pivot_s1: float = 0.0
    pivot_s2: float = 0.0
    pivot_pivot: float = 0.0

    # KDJ
    k: float = 50.0
    d: float = 50.0
    j: float = 50.0

    # Volume
    rvol: float = 1.0   # Relative volume vs 20-candle avg
    volume_ma20: float = 0.0

    # Candlestick patterns (last 5 candles)
    recent_patterns: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Indicator Calculations
# ─────────────────────────────────────────────────────────────────────────────

def compute_indicators(candles: list[Candle]) -> TechnicalState:
    """
    Compute all technical indicators from a list of Candle objects.
    Requires at least 50 candles for stable computation.
    """
    if not candles or len(candles) < 10:
        raise ValueError(f"Need at least 10 candles, got {len(candles)}")

    n = len(candles)
    c1 = candles[-1]

    # ── Arrays ─────────────────────────────────────────────────────────────
    o = np.array([c.open for c in candles], dtype=np.float64)
    h = np.array([c.high for c in candles], dtype=np.float64)
    l = np.array([c.low for c in candles], dtype=np.float64)
    cl = np.array([c.close for c in candles], dtype=np.float64)
    v = np.array([c.volume for c in candles], dtype=np.float64)

    # ── Candlestick features (C1) ─────────────────────────────────────────
    recent_patterns = [candles[max(0, i)].candle_pattern for i in range(-5, 0)]
    recent_patterns_str = ", ".join(recent_patterns)

    # ── RSI ───────────────────────────────────────────────────────────────
    rsi_14 = _rsi(cl, 14)
    rsi_4 = _rsi(cl, 4)

    # ── MACD ──────────────────────────────────────────────────────────────
    macd_line, macd_signal, macd_hist = _macd(cl)
    # MACD histogram slope: change over last 3 values
    if len(cl) >= 4:
        macd_hist_arr = _macd_full(cl)
        hist_diff = np.diff(macd_hist_arr[-4:])
        macd_hist_slope = float(np.mean(hist_diff))
    else:
        macd_hist_slope = 0.0

    # ── Bollinger Bands ────────────────────────────────────────────────────
    bb_upper, bb_middle, bb_lower = _bollinger_bands(h, l, cl, 20, 2)
    bb_range = bb_upper - bb_lower
    bb_pos = (c1.close - bb_lower) / max(bb_range, 1e-9)

    # ── ATR ───────────────────────────────────────────────────────────────
    atr_14 = _atr(h, l, cl, 14)

    # ── VWAP ──────────────────────────────────────────────────────────────
    vwap = _vwap(h, l, cl, v)

    # ── EMA ──────────────────────────────────────────────────────────────
    ema_9 = _ema(cl, 9)
    ema_21 = _ema(cl, 21)
    ema_99 = _ema(cl, 99)

    # ── ADX ──────────────────────────────────────────────────────────────
    adx = _adx(h, l, cl, 14)

    # ── Supertrend ────────────────────────────────────────────────────────
    supertrend_up, supertrend_atr = _supertrend(h, l, cl, 10, 3.0)

    # ── Keltner Channel ───────────────────────────────────────────────────
    keltner_upper = ema_21 + 2 * atr_14
    keltner_lower = ema_21 - 2 * atr_14

    # ── Pivot Points ──────────────────────────────────────────────────────
    pp, r1, s1, r2, s2 = _pivot_points(h, l, cl)

    # ── KDJ ──────────────────────────────────────────────────────────────
    k_val, d_val, j_val = _kdj(h, l, cl, 9, 3, 3)

    # ── Volume ────────────────────────────────────────────────────────────
    vol_ma20 = float(np.mean(v[-20:]))
    rvol = c1.volume / max(vol_ma20, 1e-9)

    # ── Price velocity (5-candle) ────────────────────────────────────────
    if n >= 5:
        price_velocity_5 = (cl[-1] - cl[-5]) / cl[-5] * 100
    else:
        price_velocity_5 = 0.0

    return TechnicalState(
        # Candlestick
        c1_pattern=c1.candle_pattern,
        c1_body_pct=c1.body_pct,
        c1_close_position=c1.close_position,
        c1_upper_wick_pct=c1.upper_wick_pct,
        c1_lower_wick_pct=c1.lower_wick_pct,
        c1_body_wick_ratio=c1.body_wick_ratio,
        recent_patterns=recent_patterns_str,
        # Momentum
        rsi_14=rsi_14,
        rsi_4=rsi_4,
        macd_line=macd_line,
        macd_signal=macd_signal,
        macd_histogram=macd_hist,
        macd_histogram_slope=macd_hist_slope,
        price_velocity_5=price_velocity_5,
        # Trend
        vwap=vwap,
        adx=adx,
        supertrend_up=supertrend_up,
        supertrend_atr=supertrend_atr,
        ema_9=ema_9,
        ema_21=ema_21,
        ema_99=ema_99,
        ema_cross_up=ema_9 > ema_21,
        bb_upper=bb_upper,
        bb_middle=bb_middle,
        bb_lower=bb_lower,
        bb_position_pct=bb_pos,
        # Volatility
        atr_14=atr_14,
        keltner_upper=keltner_upper,
        keltner_lower=keltner_lower,
        # Pivots
        pivot_r1=r1,
        pivot_r2=r2,
        pivot_s1=s1,
        pivot_s2=s2,
        pivot_pivot=pp,
        # KDJ
        k=k_val,
        d=d_val,
        j=j_val,
        # Volume
        rvol=rvol,
        volume_ma20=vol_ma20,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Indicator Implementations
# ─────────────────────────────────────────────────────────────────────────────

def _rsi(close: np.ndarray, period: int) -> float:
    delta = np.diff(close, prepend=close[-1])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = _sma(gain, period)
    avg_loss = _sma(loss, period)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))


def _macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema_array(close, fast)
    ema_slow = _ema_array(close, slow)
    macd_line = ema_fast - ema_slow
    macd_sig = _ema_array(macd_line, signal)
    macd_hist = macd_line - macd_sig
    return float(macd_line[-1]), float(macd_sig[-1]), float(macd_hist[-1])


def _macd_full(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema_array(close, fast)
    ema_slow = _ema_array(close, slow)
    macd_line = ema_fast - ema_slow
    macd_sig = _ema_array(macd_line, signal)
    return macd_line - macd_sig


def _bollinger_bands(high, low, close, period: int = 20, std_dev: float = 2.0):
    mid = _sma_array(close, period)
    std = _std_array(close, period)
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return float(upper[-1]), float(mid[-1]), float(lower[-1])


def _atr(high, low, close, period: int = 14) -> float:
    tr = np.empty(len(close), dtype=np.float64)
    tr[0] = high[0] - low[0]
    for i in range(1, len(close)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    return float(_sma(tr, period))


def _vwap(high, low, close, volume):
    typical = (high + low + close) / 3.0
    cum_tpv = np.cumsum(typical * volume)
    cum_vol = np.cumsum(volume)
    return float((cum_tpv / np.maximum(cum_vol, 1e-9))[-1])


def _pivot_points(high, low, close):
    """Classic pivot points from previous period HLC."""
    p = close[-2]
    r1 = 2 * p - low[-2]
    s1 = 2 * p - high[-2]
    r2 = p + (high[-2] - low[-2])
    s2 = p - (high[-2] - low[-2])
    return float(p), float(r1), float(s1), float(r2), float(s2)


def _ema(close: np.ndarray, period: int) -> float:
    arr = _ema_array(close, period)
    return float(arr[-1])


def _ema_array(arr: np.ndarray, period: int) -> np.ndarray:
    alpha = 2.0 / (period + 1)
    result = np.empty_like(arr)
    result[0] = arr[0]
    for i in range(1, len(arr)):
        result[i] = alpha * arr[i] + (1 - alpha) * result[i - 1]
    return result


def _adx(high, low, close, period: int = 14) -> float:
    n = len(close)
    if n < period * 2:
        return 25.0

    tr = np.empty(n, dtype=np.float64)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i],
                     abs(high[i] - close[i - 1]),
                     abs(low[i] - close[i - 1]))

    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    for i in range(1, n):
        up = high[i] - high[i - 1]
        dn = low[i - 1] - low[i]
        if up > dn and up > 0:
            plus_dm[i] = up
        if dn > up and dn > 0:
            minus_dm[i] = dn

    alpha = 1.0 / period
    atr = float(tr[:period].sum())
    s_plus = float(plus_dm[:period].sum())
    s_minus = float(minus_dm[:period].sum())

    plus_di_list, minus_di_list, dx_list = [], [], []
    for i in range(period, n):
        atr = (atr * (period - 1) + tr[i]) / period
        s_plus = (s_plus * (period - 1) + plus_dm[i]) / period
        s_minus = (s_minus * (period - 1) + minus_dm[i]) / period
        pdi = 100 * s_plus / atr if atr > 0 else 0
        mdi = 100 * s_minus / atr if atr > 0 else 0
        dx = 100 * abs(pdi - mdi) / (pdi + mdi + 1e-9)
        plus_di_list.append(pdi)
        minus_di_list.append(mdi)
        dx_list.append(dx)

    if len(dx_list) < period:
        return 25.0

    adx_val = sum(dx_list[-period:]) / period
    alpha_adx = 1.0 / period
    for val in dx_list[-period:]:
        adx_val = adx_val * (1 - alpha_adx) + val * alpha_adx
    return float(adx_val) if not np.isnan(adx_val) else 25.0


def _supertrend(high, low, close, period: int = 10, multiplier: float = 3.0):
    atr_arr = _atr(high, low, close, period)
    hl2 = (high[-1] + low[-1]) / 2.0
    upper_band = hl2 + multiplier * atr_arr
    lower_band = hl2 - multiplier * atr_arr
    prev_close = close[-2]
    in_uptrend = True
    for i in range(len(close) - 2, max(0, len(close) - 20), -1):
        if close[i] > upper_band:
            in_uptrend = True
        elif close[i] < lower_band:
            in_uptrend = False
        else:
            break
    return in_uptrend, float(atr_arr)


def _kdj(high, low, close, n: int = 9, m1: int = 3, m2: int = 3):
    """KDJ indicator (stochastic variant)."""
    if len(close) < n:
        return 50.0, 50.0, 50.0
    RSV = np.zeros(len(close))
    for i in range(n - 1, len(close)):
        hh = max(high[i - n + 1:i + 1])
        ll = min(low[i - n + 1:i + 1])
        if hh == ll:
            RSV[i] = 50.0
        else:
            RSV[i] = (close[i] - ll) / (hh - ll) * 100

    k = np.zeros(len(close))
    d = np.zeros(len(close))
    k[n - 1] = 50.0
    d[n - 1] = 50.0
    for i in range(n, len(close)):
        k[i] = (2 / 3) * k[i - 1] + (1 / 3) * RSV[i]
        d[i] = (2 / 3) * d[i - 1] + (1 / 3) * k[i]
    j = 3 * k - 2 * d
    return float(k[-1]), float(d[-1]), float(j[-1])


def _sma(arr: np.ndarray, period: int) -> float:
    if len(arr) < period:
        return float(np.mean(arr))
    return float(np.mean(arr[-period:]))


def _sma_array(arr: np.ndarray, period: int) -> np.ndarray:
    if len(arr) < period:
        return np.full_like(arr, np.nan)
    result = np.convolve(arr, np.ones(period) / period, mode="valid")
    return np.concatenate([np.full(period - 1, np.nan), result])


def _std_array(arr: np.ndarray, period: int) -> np.ndarray:
    if len(arr) < period:
        return np.zeros_like(arr)
    result = np.array([np.std(arr[i:i + period]) for i in range(len(arr) - period + 1)])
    return np.concatenate([np.full(period - 1, np.nan), result])
