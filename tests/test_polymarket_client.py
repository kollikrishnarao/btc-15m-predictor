"""
Tests for Polymarket client — Kelly sizing, spread check.
"""
import pytest

from src.execution.polymarket_client import kelly_fractional_size


class TestKellySizing:
    def test_kelly_basic(self):
        # 70% confidence, market at $0.50
        size = kelly_fractional_size(
            confidence=0.70,
            market_price=0.50,
            bankroll=1000.0,
        )
        # Should be positive when confidence > 0.5
        assert size > 0

    def test_kelly_respects_cap(self):
        # 90% confidence — should still cap at 25%
        size = kelly_fractional_size(
            confidence=0.90,
            market_price=0.50,
            bankroll=1000.0,
        )
        assert size <= 250.0  # 25% of $1000

    def test_kelly_zero_edge(self):
        # 50% confidence on 50/50 market — no edge
        size = kelly_fractional_size(
            confidence=0.50,
            market_price=0.50,
            bankroll=1000.0,
        )
        assert size == 0.0  # No edge → no bet

    def test_kelly_low_confidence(self):
        # 52% confidence — very small edge
        size = kelly_fractional_size(
            confidence=0.52,
            market_price=0.50,
            bankroll=1000.0,
        )
        # Should bet but small
        assert size > 0
        assert size < 50.0

    def test_kelly_respects_minimum(self):
        # Very small bankroll with fractional Kelly
        size = kelly_fractional_size(
            confidence=0.70,
            market_price=0.50,
            bankroll=5.0,
        )
        # Should round up to $1 minimum
        assert size >= 1.0

    def test_kelly_expensive_market(self):
        # YES at $0.90 — expensive, lower bet size
        size_cheap = kelly_fractional_size(
            confidence=0.70,
            market_price=0.50,
            bankroll=1000.0,
        )
        size_expensive = kelly_fractional_size(
            confidence=0.70,
            market_price=0.90,
            bankroll=1000.0,
        )
        # Higher price → smaller position for same dollar exposure
        assert size_expensive < size_cheap
