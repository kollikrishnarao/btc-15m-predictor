"""
Tests for pre-filter hard rules.
"""
import pytest
from unittest.mock import MagicMock

from src.pre_filter import run_pre_filter, get_skip_risk_score, SkipReason
from src.features.market_state import MarketState
from src.features.technical_indicators import TechnicalState
from src.data_sources.binance_client import Candle


def _mock_candle(body_pct=0.5, is_green=True, volume=1.0) -> Candle:
    open_ = 95000
    close = open_ * (1 + 0.01 * body_pct if is_green else 1 - 0.01 * body_pct)
    return Candle(
        open_time=0, open=open_, high=max(open_, close) * 1.002,
        low=min(open_, close) * 0.998, close=close,
        volume=volume, close_time=0, quote_volume=0,
        trades=100, buy_volume=volume * 0.5, sell_volume=volume * 0.5,
    )


def _mock_state(
    c1_body_pct=0.5,
    rvol=1.0,
    vpin=0.3,
    adx=25.0,
    funding=0.01,
    supertrend_up=True,
    is_green=True,
) -> MarketState:
    candle = _mock_candle(body_pct=c1_body_pct, is_green=is_green)
    state = MarketState(
        analysis_id="test",
        candles=[candle],
        c1=candle,
        vpin=vpin,
        cvd=0.0,
        tcr=0.0,
        ofi=0.0,
        obi=0.0,
        spread_bps=5.0,
        data_age_seconds=10.0,
        stale_data=False,
    )
    state.technical = MagicMock()
    state.technical.adx = adx
    state.technical.supertrend_up = supertrend_up
    state.technical.rvol = rvol
    state.smart_money = MagicMock()
    state.smart_money.funding_rate_pct = funding
    state.sentiment = MagicMock()
    state.sentiment.fear_greed_index = 50
    state.macro = MagicMock()
    state.macro.btc_macro_score = 0.5
    return state


class TestPreFilter:
    def test_passes_healthy_state(self):
        state = _mock_state()
        result = run_pre_filter(state, session_active=False, consecutive_losses=0)
        assert result.passed

    def test_active_session_blocks(self):
        state = _mock_state()
        result = run_pre_filter(state, session_active=True)
        assert not result.passed
        assert result.reason == SkipReason.SESSION_ACTIVE

    def test_stale_data_blocks(self):
        state = _mock_state()
        state.stale_data = True
        state.data_age_seconds = 120.0
        result = run_pre_filter(state)
        assert not result.passed
        assert result.reason == SkipReason.DATA_STALE

    def test_doji_blocks(self):
        state = _mock_state(c1_body_pct=0.05)
        result = run_pre_filter(state)
        assert not result.passed
        assert result.reason == SkipReason.DOJI_CANDLE

    def test_low_volume_blocks(self):
        state = _mock_state(rvol=0.3)
        result = run_pre_filter(state)
        assert not result.passed
        assert result.reason == SkipReason.LOW_VOLUME

    def test_high_vpin_blocks(self):
        state = _mock_state(vpin=0.85)
        result = run_pre_filter(state)
        assert not result.passed
        assert result.reason == SkipReason.VPIN_TOXICITY

    def test_low_adx_blocks(self):
        state = _mock_state(adx=10.0)
        result = run_pre_filter(state)
        assert not result.passed
        assert result.reason == SkipReason.NO_TREND

    def test_extreme_funding_blocks(self):
        state = _mock_state(funding=0.20)
        result = run_pre_filter(state)
        assert not result.passed
        assert result.reason == SkipReason.EXTREME_FUNDING

    def test_circuit_breaker_requires_edge(self):
        state = _mock_state()
        result = run_pre_filter(
            state, session_active=False, consecutive_losses=3, min_edge=0.0
        )
        assert not result.passed


class TestRiskScores:
    def test_risk_scores_in_range(self):
        state = _mock_state()
        risk = get_skip_risk_score(state)
        for v in risk.values():
            assert 0.0 <= v <= 1.0
