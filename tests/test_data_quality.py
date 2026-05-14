"""
Tests for data quality gate.
Phase 2.5.
"""
import pytest
from unittest.mock import MagicMock

from src.data_quality import validate_market_state, DataQualityReport


class TestDataQualityGate:
    def test_passes_valid_state(self):
        """Healthy market state passes."""
        state = MagicMock()
        state.current_price = 95000.0
        state.vpin = 0.35
        state.cvd = 150.0
        state.spread_bps = 5.0
        state.candles = [MagicMock() for _ in range(10)]

        tech = MagicMock()
        tech.rsi_14 = 55.0
        state.technical = tech

        dq = validate_market_state(state)
        assert dq.passed is True
        assert len(dq.failures) == 0

    def test_catches_zero_price(self):
        """Zero price → failure."""
        state = MagicMock()
        state.current_price = 0.0
        state.vpin = 0.0
        state.cvd = 0.0
        state.spread_bps = 0.0
        state.candles = []
        state.technical = None

        dq = validate_market_state(state)
        assert dq.passed is False
        assert any("price" in f.lower() for f in dq.failures)

    def test_catches_none_price(self):
        """None price → failure."""
        state = MagicMock()
        state.current_price = None
        state.vpin = 0.0
        state.cvd = 0.0
        state.spread_bps = 0.0
        state.candles = []
        state.technical = None

        dq = validate_market_state(state)
        assert dq.passed is False

    def test_catches_negative_price(self):
        """Negative price → failure."""
        state = MagicMock()
        state.current_price = -100.0
        state.vpin = 0.0
        state.cvd = 0.0
        state.spread_bps = 0.0
        state.candles = []
        state.technical = None

        dq = validate_market_state(state)
        assert dq.passed is False

    def test_warns_price_outside_btc_range(self):
        """Price far outside BTC range → warning (not failure)."""
        state = MagicMock()
        state.current_price = 500.0  # Too low for BTC
        state.vpin = 0.0
        state.cvd = 0.0
        state.spread_bps = 0.0
        state.candles = []
        state.technical = None

        dq = validate_market_state(state)
        assert dq.passed is True  # Warning only, not failure
        assert len(dq.warnings) > 0

    def test_warns_zero_vpin_and_cvd(self):
        """VPIN and CVD both zero → warning."""
        state = MagicMock()
        state.current_price = 95000.0
        state.vpin = 0.0
        state.cvd = 0.0
        state.spread_bps = 5.0
        state.candles = [MagicMock() for _ in range(10)]
        state.technical = MagicMock()
        state.technical.rsi_14 = 55.0

        dq = validate_market_state(state)
        assert dq.passed is True
        assert any("VPIN" in w or "CVD" in w for w in dq.warnings)

    def test_warns_insufficient_candles(self):
        """Less than 5 candles → warning."""
        state = MagicMock()
        state.current_price = 95000.0
        state.vpin = 0.35
        state.cvd = 150.0
        state.spread_bps = 5.0
        state.candles = [MagicMock()]  # Only 1 candle
        state.technical = MagicMock()
        state.technical.rsi_14 = 55.0

        dq = validate_market_state(state)
        assert dq.passed is True  # Warning only
        assert any("candle" in w.lower() for w in dq.warnings)

    def test_warns_zero_rsi(self):
        """RSI exactly zero → warning."""
        state = MagicMock()
        state.current_price = 95000.0
        state.vpin = 0.35
        state.cvd = 150.0
        state.spread_bps = 5.0
        state.candles = [MagicMock() for _ in range(10)]
        state.technical = MagicMock()
        state.technical.rsi_14 = 0.0

        dq = validate_market_state(state)
        assert dq.passed is True
        assert any("RSI" in w for w in dq.warnings)

    def test_warns_zero_spread(self):
        """Spread zero → warning."""
        state = MagicMock()
        state.current_price = 95000.0
        state.vpin = 0.35
        state.cvd = 150.0
        state.spread_bps = 0.0  # Zero spread
        state.candles = [MagicMock() for _ in range(10)]
        state.technical = MagicMock()
        state.technical.rsi_14 = 55.0

        dq = validate_market_state(state)
        assert dq.passed is True
        assert any("spread" in w.lower() for w in dq.warnings)

    def test_warns_very_high_vpin(self):
        """VPIN > 0.80 → warning."""
        state = MagicMock()
        state.current_price = 95000.0
        state.vpin = 0.85  # Very high
        state.cvd = 150.0
        state.spread_bps = 5.0
        state.candles = [MagicMock() for _ in range(10)]
        state.technical = MagicMock()
        state.technical.rsi_14 = 55.0

        dq = validate_market_state(state)
        assert dq.passed is True  # Warning, not failure (pre-filter handles VPIN > 0.75)
        assert any("VPIN" in w for w in dq.warnings)

    def test_multiple_warnings_no_failures(self):
        """Multiple warnings but no failures → passes."""
        state = MagicMock()
        state.current_price = 95000.0
        state.vpin = 0.0  # Warning
        state.cvd = 0.0   # Warning
        state.spread_bps = 0.0  # Warning
        state.candles = [MagicMock() for _ in range(3)]  # Warning
        state.technical = MagicMock()
        state.technical.rsi_14 = 0.0  # Warning

        dq = validate_market_state(state)
        assert dq.passed is True
        assert len(dq.warnings) >= 4

    def test_report_log_method(self):
        """DataQualityReport.log() runs without error."""
        report = DataQualityReport(passed=False, failures=["test failure"], warnings=["test warning"])
        # Should not raise
        report.log()

        report2 = DataQualityReport(passed=True, failures=[], warnings=["test warning"])
        report2.log()