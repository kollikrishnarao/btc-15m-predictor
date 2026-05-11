"""
Pre-filter: deterministic hard rules that run BEFORE the LLM.
Any single trigger → SKIP immediately. No LLM call wasted.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from config.constants import (
    MAX_FUNDING_RATE_PCT,
    MIN_ADX_TREND,
    MIN_CANDLE_BODY_PCT,
    MIN_VOLUME_RATIO,
    MAX_VPIN_TOXICITY,
    TREND_REVERSAL_BTC_MOVE_PCT,
)
from src.features.market_state import MarketState

log = logging.getLogger(__name__)


class SkipReason(Enum):
    NO_CANDLE = "no_candle"
    DOJI_CANDLE = "doji_candle"
    LOW_VOLUME = "low_volume"
    VPIN_TOXICITY = "vpin_toxicity"
    NO_TREND = "no_trend"
    EXTREME_FUNDING = "extreme_funding"
    TREND_FILTER_OPPOSING = "trend_filter_opposing"
    DATA_STALE = "data_stale"
    SESSION_ACTIVE = "session_active"


@dataclass
class PreFilterResult:
    passed: bool
    reason: SkipReason | None = None
    details: str = ""

    def log(self) -> None:
        if self.passed:
            log.debug("Pre-filter PASSED — proceeding to reasoning")
        else:
            log.info(f"Pre-filter SKIPPED: {self.reason.value} — {self.details}")


def run_pre_filter(
    state: MarketState,
    session_active: bool = False,
    consecutive_losses: int = 0,
    last_direction: str | None = None,
    min_edge: float = 0.0,
) -> PreFilterResult:
    """
    Run all pre-filter hard rules.
    Returns immediately on first failure (short-circuit).
    """
    # ── Rule 0: Active session ───────────────────────────────────────────
    if session_active:
        return PreFilterResult(False, SkipReason.SESSION_ACTIVE,
                               "Session already active — wait for resolution")

    # ── Rule 1: Stale data ───────────────────────────────────────────────
    if state.stale_data:
        return PreFilterResult(False, SkipReason.DATA_STALE,
                               f"Data is stale ({state.data_age_seconds:.0f}s old)")

    # ── Rule 2: No C1 candle ──────────────────────────────────────────────
    if not state.c1:
        return PreFilterResult(False, SkipReason.NO_CANDLE,
                               "No C1 candle available")

    # ── Rule 3: Doji (C1 body < 0.1%) ─────────────────────────────────────
    if state.c1_body_pct < MIN_CANDLE_BODY_PCT:
        return PreFilterResult(
            False, SkipReason.DOJI_CANDLE,
            f"C1 body {state.c1_body_pct:.3f}% < {MIN_CANDLE_BODY_PCT}% threshold (doji — no signal)"
        )

    # ── Rule 4: Low volume (C1 vol < 0.7x 20-candle avg) ─────────────────
    rvol = state.rvol
    if rvol < MIN_VOLUME_RATIO:
        return PreFilterResult(
            False, SkipReason.LOW_VOLUME,
            f"C1 RVOL {rvol:.2f}x < {MIN_VOLUME_RATIO}x threshold — weak conviction"
        )

    # ── Rule 5: VPIN toxicity (>0.75 = extreme institutional uncertainty) ──
    if state.vpin > MAX_VPIN_TOXICITY:
        return PreFilterResult(
            False, SkipReason.VPIN_TOXICITY,
            f"VPIN {state.vpin:.3f} > {MAX_VPIN_TOXICITY} — institutional uncertainty, skip"
        )

    # ── Rule 6: ADX < 15 (no trend = choppy = unpredictable) ──────────────
    adx = state.adx
    if adx < MIN_ADX_TREND:
        return PreFilterResult(
            False, SkipReason.NO_TREND,
            f"ADX {adx:.1f} < {MIN_ADX_TREND} — no clear trend, skip"
        )

    # ── Rule 7: Extreme funding (>0.15% = liquidation cascade risk) ───────
    funding = state.funding_rate_pct
    if abs(funding) > MAX_FUNDING_RATE_PCT:
        return PreFilterResult(
            False, SkipReason.EXTREME_FUNDING,
            f"Funding {funding:.3f}% > {MAX_FUNDING_RATE_PCT}% — cascade liquidation risk"
        )

    # ── Rule 8: Trend filter — signal vs 15m trend ─────────────────────────
    if last_direction and state.technical:
        trend_is_up = state.technical.supertrend_up
        signal_is_green = (last_direction == "GREEN")

        # If signal opposes 15m trend, check for strong BTC momentum exception
        if trend_is_up and not signal_is_green:
            # RED signal during UP trend → check if BTC moved >0.10% down
            if state.c1_is_green:
                # Market didn't actually fall — trend exception not met
                return PreFilterResult(
                    False, SkipReason.TREND_FILTER_OPPOSING,
                    "RED signal opposes 15m UP trend — no counter-move exception"
                )
        elif not trend_is_up and signal_is_green:
            # GREEN signal during DOWN trend → check if BTC moved >0.10% up
            if not state.c1_is_green:
                return PreFilterResult(
                    False, SkipReason.TREND_FILTER_OPPOSING,
                    "GREEN signal opposes 15m DOWN trend — no counter-move exception"
                )

    # ── Rule 9: Consecutive loss circuit ───────────────────────────────────
    if consecutive_losses >= 3 and min_edge <= 0:
        return PreFilterResult(
            False, SkipReason.TREND_FILTER_OPPOSING,
            "3 consecutive losses — edge requirement not met"
        )

    return PreFilterResult(True)


def get_skip_risk_score(state: MarketState) -> dict[str, float]:
    """
    Compute a risk score for each pre-filter dimension.
    Used by the reasoning engine to weight confidence.
    Returns dict of dimension → risk score (0=low risk, 1=high risk).
    """
    risk = {}
    risk["volume"] = max(0.0, 1.0 - state.rvol)
    risk["trend"] = max(0.0, (25.0 - state.adx) / 25.0)
    risk["vpin"] = state.vpin
    risk["funding"] = min(1.0, abs(state.funding_rate_pct) / 0.15)
    risk["doji"] = 1.0 if state.c1_body_pct < 0.3 else 0.0
    return risk
