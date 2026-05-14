"""
Data Quality Gate — validates MarketState before agents process it.
Phase 2.5: Prevents garbage-in → garbage-out by checking data integrity.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.features.market_state import MarketState

log = logging.getLogger(__name__)


@dataclass
class DataQualityReport:
    """Result of validating a MarketState."""
    passed: bool
    warnings: list[str]
    failures: list[str]

    def log(self):
        for f in self.failures:
            log.error(f"[DATA QUALITY] FAILURE: {f}")
        for w in self.warnings:
            log.warning(f"[DATA QUALITY] WARNING: {w}")
        if self.passed:
            log.info("[DATA QUALITY] Passed")


def validate_market_state(state: MarketState) -> DataQualityReport:
    """
    Validate all data in MarketState before agents process it.
    Returns a report with warnings and failures (any failure = block analysis).
    """
    failures = []
    warnings = []

    # Check price validity
    price = getattr(state, "current_price", None)
    if price is None or price <= 0:
        failures.append("current_price is None, zero, or negative")
    elif price < 1_000 or price > 1_000_000:
        warnings.append(f"Price ${price:.2f} outside typical BTC range ($1k–$1M)")

    # Check orderflow data presence
    vpin = getattr(state, "vpin", 0.0)
    cvd = getattr(state, "cvd", 0.0)
    if vpin == 0.0 and cvd == 0.0:
        warnings.append("VPIN and CVD both zero — orderflow data may be missing")

    # Check technical indicators
    tech = getattr(state, "technical", None)
    if tech:
        if getattr(tech, "rsi_14", 0.0) == 0.0 and getattr(state, "candles", None):
            warnings.append("RSI-14 is exactly zero — may be uncomputed")

    # Check candle data sufficiency
    candles = getattr(state, "candles", None)
    if candles is None or len(candles) < 5:
        warnings.append(f"Only {len(candles) if candles else 0} candles available — need ≥5 for indicators")

    # Check spread / liquidity
    spread = getattr(state, "spread_bps", 0.0)
    if spread <= 0:
        warnings.append("Spread is zero — orderbook data may be missing")

    # Check VPIN toxicity
    if vpin > 0.80:
        warnings.append(f"VPIN very elevated ({vpin:.3f}) — high uncertainty")

    return DataQualityReport(
        passed=len(failures) == 0,
        warnings=warnings,
        failures=failures,
    )