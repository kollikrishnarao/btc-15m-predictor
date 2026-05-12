"""
StateBridge — reads live predictor state and converts it to API models.

The predictor writes its state to JSON files (session.json, predictions.csv).
This bridge reads those files + the in-memory session manager and assembles
the API response models. It acts as a read-only adapter between the predictor
internals and the REST API.
"""
from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

from src.api.models import (
    ActiveSession,
    BetResult,
    CircuitBreakerStatus,
    ConvictionScores,
    Direction,
    MarketSnapshot,
    OrderflowMetrics,
    PerformanceStats,
    SessionOutcome,
    SessionRecord,
    SignalsPayload,
    SystemStatus,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp/btc-predictor-v2"))
SESSION_FILE = DATA_DIR / "session.json"
PREDICTIONS_CSV = DATA_DIR / "predictions.csv"
SIGNALS_CACHE_FILE = DATA_DIR / "signals_cache.json"


class StateBridge:
    """Reads predictor state files and assembles API response models."""

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_signals(self) -> Optional[SignalsPayload]:
        try:
            return self._load_signals()
        except Exception as exc:
            logger.warning("get_signals failed: %s", exc)
            return None

    async def get_system_status(self) -> SystemStatus:
        try:
            return self._load_system_status()
        except Exception as exc:
            logger.warning("get_system_status failed: %s", exc)
            return SystemStatus(
                is_running=False,
                circuit_breaker=CircuitBreakerStatus.ACTIVE,
                consecutive_losses=0,
                data_freshness_seconds=9999.0,
                binance_ws_connected=False,
                cycle_phase="UNKNOWN",
                last_cycle_at=None,
                next_cycle_at=None,
            )

    async def get_performance(self) -> PerformanceStats:
        try:
            return self._compute_performance()
        except Exception as exc:
            logger.warning("get_performance failed: %s", exc)
            return _empty_performance()

    async def get_sessions(self, limit: int = 50, offset: int = 0) -> list[SessionRecord]:
        try:
            all_sessions = self._load_sessions_from_csv()
            return all_sessions[offset: offset + limit]
        except Exception as exc:
            logger.warning("get_sessions failed: %s", exc)
            return []

    async def get_session(self, session_id: str) -> Optional[SessionRecord]:
        sessions = await self.get_sessions(limit=1000)
        return next((s for s in sessions if s.session_id == session_id), None)

    # ── Private loaders ───────────────────────────────────────────────────────

    def _load_signals(self) -> Optional[SignalsPayload]:
        if not SIGNALS_CACHE_FILE.exists():
            return _mock_signals()  # Return mock data when predictor is not running

        with open(SIGNALS_CACHE_FILE) as f:
            data = json.load(f)

        market = MarketSnapshot(
            btc_price=data.get("btc_price", 0.0),
            price_change_pct_24h=data.get("price_change_pct_24h", 0.0),
            volume_24h=data.get("volume_24h", 0.0),
            funding_rate=data.get("funding_rate", 0.0),
            open_interest=data.get("open_interest", 0.0),
            fear_greed_index=data.get("fear_greed_index", 50),
            adx=data.get("adx", 0.0),
            rvol=data.get("rvol", 1.0),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
        )

        scores = data.get("conviction_scores", {})
        conviction = ConvictionScores(
            momentum=scores.get("momentum", 0.5),
            trend=scores.get("trend", 0.5),
            orderflow=scores.get("orderflow", 0.5),
            smart_money=scores.get("smart_money", 0.5),
            sentiment=scores.get("sentiment", 0.5),
            macro=scores.get("macro", 0.5),
            weighted_total=scores.get("weighted_total", 0.5),
        )

        of = data.get("orderflow", {})
        orderflow = OrderflowMetrics(
            vpin=of.get("vpin", 0.0),
            cvd=of.get("cvd", 0.0),
            ofi=of.get("ofi", 0.0),
            tcr=of.get("tcr", 0.0),
            obi=of.get("obi", 0.0),
            cvd_divergence=of.get("cvd_divergence", False),
        )

        active_session = None
        session_data = data.get("active_session")
        if session_data:
            active_session = ActiveSession(
                direction=Direction(session_data["direction"]),
                conviction=session_data["conviction"],
                bet_number=session_data["bet_number"],
                current_bet_size=session_data["current_bet_size"],
                total_at_risk=session_data["total_at_risk"],
                entry_price=session_data["entry_price"],
                started_at=datetime.fromisoformat(session_data["started_at"]),
                candle_target=session_data["candle_target"],
            )

        system = self._load_system_status()

        return SignalsPayload(
            market=market,
            conviction=conviction,
            orderflow=orderflow,
            active_session=active_session,
            system=system,
            last_direction=Direction(data.get("last_direction", "IDLE")),
            advisor_call=Direction(data.get("advisor_call", "SKIP")),
            advisor_confidence=data.get("advisor_confidence", 0.5),
        )

    def _load_system_status(self) -> SystemStatus:
        if not SESSION_FILE.exists():
            return SystemStatus(
                is_running=False,
                circuit_breaker=CircuitBreakerStatus.ACTIVE,
                consecutive_losses=0,
                data_freshness_seconds=9999.0,
                binance_ws_connected=False,
                cycle_phase="STOPPED",
                last_cycle_at=None,
                next_cycle_at=None,
            )

        with open(SESSION_FILE) as f:
            data = json.load(f)

        consecutive_losses = data.get("consecutive_losses", 0)
        cb_tripped = data.get("circuit_breaker_active", False) or consecutive_losses >= 3

        last_cycle_str = data.get("last_cycle_at")
        last_cycle = datetime.fromisoformat(last_cycle_str) if last_cycle_str else None

        next_cycle = None
        if last_cycle:
            minutes = last_cycle.minute
            next_boundary = ((minutes // 15) + 1) * 15
            if next_boundary >= 60:
                next_cycle = last_cycle.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                next_cycle = last_cycle.replace(minute=next_boundary, second=0, microsecond=0)

        freshness = 9999.0
        signals_ts_str = data.get("signals_timestamp")
        if signals_ts_str:
            signals_ts = datetime.fromisoformat(signals_ts_str)
            freshness = (datetime.utcnow() - signals_ts).total_seconds()

        return SystemStatus(
            is_running=data.get("is_running", False),
            circuit_breaker=CircuitBreakerStatus.TRIPPED if cb_tripped else CircuitBreakerStatus.ACTIVE,
            consecutive_losses=consecutive_losses,
            data_freshness_seconds=freshness,
            binance_ws_connected=data.get("binance_ws_connected", False),
            cycle_phase=data.get("cycle_phase", "IDLE"),
            last_cycle_at=last_cycle,
            next_cycle_at=next_cycle,
        )

    def _load_sessions_from_csv(self) -> list[SessionRecord]:
        if not PREDICTIONS_CSV.exists():
            return _mock_sessions()

        sessions: list[SessionRecord] = []
        with open(PREDICTIONS_CSV, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    sessions.append(_csv_row_to_session(row))
                except Exception as exc:
                    logger.debug("Skipping malformed CSV row: %s", exc)

        return list(reversed(sessions))  # Most recent first

    def _compute_performance(self) -> PerformanceStats:
        sessions = self._load_sessions_from_csv()
        if not sessions:
            return _empty_performance()

        completed = [s for s in sessions if s.outcome != SessionOutcome.IN_PROGRESS]
        wins = [s for s in completed if s.outcome == SessionOutcome.WIN]
        losses = [s for s in completed if s.outcome == SessionOutcome.LOSS]

        total = len(completed)
        win_rate_all = len(wins) / total if total else 0.0

        last_20 = completed[:20]
        wins_20 = [s for s in last_20 if s.outcome == SessionOutcome.WIN]
        win_rate_20 = len(wins_20) / len(last_20) if last_20 else 0.0

        total_pnl = sum(s.total_pnl for s in completed)

        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        daily_pnl = sum(
            s.total_pnl for s in completed
            if s.started_at and s.started_at.date() == today
        )
        weekly_pnl = sum(
            s.total_pnl for s in completed
            if s.started_at and (today - s.started_at.date()).days < 7
        )

        bankroll = 20.0 + total_pnl

        consecutive_wins = 0
        consecutive_losses = 0
        for s in completed:
            if s.outcome == SessionOutcome.WIN:
                consecutive_wins += 1
                consecutive_losses = 0
            else:
                consecutive_losses += 1
                consecutive_wins = 0

        avg_conv_wins = (sum(s.conviction for s in wins) / len(wins)) if wins else 0.5
        avg_conv_losses = (sum(s.conviction for s in losses) / len(losses)) if losses else 0.5

        dims = ["momentum", "trend", "orderflow", "smart_money", "sentiment", "macro"]
        dim_accuracy: dict[str, float] = {}
        for dim in dims:
            dim_sessions = [
                s for s in completed
                if getattr(s, f"{dim}_score", 0.5) > 0.65
            ]
            if len(dim_sessions) >= 5:
                dim_accuracy[dim] = len([s for s in dim_sessions if s.outcome == SessionOutcome.WIN]) / len(dim_sessions)
            else:
                dim_accuracy[dim] = 0.5

        best_dim = max(dim_accuracy, key=dim_accuracy.get) if dim_accuracy else "orderflow"
        worst_dim = min(dim_accuracy, key=dim_accuracy.get) if dim_accuracy else "macro"

        return PerformanceStats(
            total_sessions=total,
            win_rate_all=win_rate_all,
            win_rate_20=win_rate_20,
            total_pnl=total_pnl,
            daily_pnl=daily_pnl,
            weekly_pnl=weekly_pnl,
            bankroll=bankroll,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            avg_conviction_on_wins=avg_conv_wins,
            avg_conviction_on_losses=avg_conv_losses,
            best_dimension=best_dim,
            worst_dimension=worst_dim,
            dimension_accuracy=dim_accuracy,
        )


# ── CSV → model helpers ───────────────────────────────────────────────────────

def _csv_row_to_session(row: dict) -> SessionRecord:
    outcome_str = row.get("outcome", "IN_PROGRESS").upper()
    outcome = SessionOutcome(outcome_str) if outcome_str in SessionOutcome.__members__ else SessionOutcome.IN_PROGRESS

    direction_str = row.get("direction", "SKIP").upper()
    direction = Direction(direction_str) if direction_str in Direction.__members__ else Direction.SKIP

    started_at_str = row.get("timestamp") or row.get("started_at", "")
    started_at = datetime.fromisoformat(started_at_str) if started_at_str else datetime.utcnow()

    pnl = float(row.get("pnl", 0.0))

    bet = BetResult(
        candle=row.get("candle", "C2"),
        direction=direction,
        outcome=outcome,
        bet_size=float(row.get("bet_size", 1.0)),
        pnl=pnl,
    )

    return SessionRecord(
        session_id=row.get("session_id", str(uuid4())),
        started_at=started_at,
        ended_at=datetime.fromisoformat(row["ended_at"]) if row.get("ended_at") else None,
        direction=direction,
        conviction=float(row.get("conviction", 0.5)),
        outcome=outcome,
        bets=[bet],
        total_pnl=pnl,
        flip_occurred=row.get("flip_occurred", "false").lower() == "true",
        regime=row.get("regime", "UNKNOWN"),
        momentum_score=float(row.get("momentum_score", 0.5)),
        trend_score=float(row.get("trend_score", 0.5)),
        orderflow_score=float(row.get("orderflow_score", 0.5)),
        smart_money_score=float(row.get("smart_money_score", 0.5)),
        sentiment_score=float(row.get("sentiment_score", 0.5)),
        macro_score=float(row.get("macro_score", 0.5)),
    )


# ── Mock data (when predictor is not running) ─────────────────────────────────

def _mock_signals() -> SignalsPayload:
    return SignalsPayload(
        market=MarketSnapshot(
            btc_price=103_250.0,
            price_change_pct_24h=1.24,
            volume_24h=28_500_000_000.0,
            funding_rate=0.0105,
            open_interest=18_200_000_000.0,
            fear_greed_index=62,
            adx=27.4,
            rvol=1.35,
            timestamp=datetime.utcnow(),
        ),
        conviction=ConvictionScores(
            momentum=0.72,
            trend=0.68,
            orderflow=0.75,
            smart_money=0.58,
            sentiment=0.60,
            macro=0.51,
            weighted_total=0.67,
        ),
        orderflow=OrderflowMetrics(
            vpin=0.54,
            cvd=1842.5,
            ofi=0.31,
            tcr=0.18,
            obi=0.22,
            cvd_divergence=False,
        ),
        active_session=None,
        system=SystemStatus(
            is_running=False,
            circuit_breaker=CircuitBreakerStatus.ACTIVE,
            consecutive_losses=0,
            data_freshness_seconds=0.0,
            binance_ws_connected=False,
            cycle_phase="IDLE",
            last_cycle_at=None,
            next_cycle_at=None,
        ),
        last_direction=Direction.GREEN,
        advisor_call=Direction.GREEN,
        advisor_confidence=0.71,
    )


def _mock_sessions() -> list[SessionRecord]:
    base = datetime.utcnow()
    mock = []
    for i in range(10):
        outcome = SessionOutcome.WIN if i % 3 != 2 else SessionOutcome.LOSS
        pnl = 1.0 if outcome == SessionOutcome.WIN else -7.0 if i % 9 == 2 else -3.0
        direction = Direction.GREEN if i % 2 == 0 else Direction.RED
        mock.append(SessionRecord(
            session_id=f"mock-{i:04d}",
            started_at=base - timedelta(hours=i * 2),
            ended_at=base - timedelta(hours=i * 2 - 1),
            direction=direction,
            conviction=0.65 + (i % 3) * 0.05,
            outcome=outcome,
            bets=[BetResult(candle="C2", direction=direction, outcome=outcome, bet_size=1.0, pnl=pnl)],
            total_pnl=pnl,
            flip_occurred=False,
            regime="TRENDING_UP",
            momentum_score=0.70,
            trend_score=0.65,
            orderflow_score=0.72,
            smart_money_score=0.58,
            sentiment_score=0.55,
            macro_score=0.50,
        ))
    return mock


def _empty_performance() -> PerformanceStats:
    return PerformanceStats(
        total_sessions=0,
        win_rate_all=0.0,
        win_rate_20=0.0,
        total_pnl=0.0,
        daily_pnl=0.0,
        weekly_pnl=0.0,
        bankroll=20.0,
        consecutive_wins=0,
        consecutive_losses=0,
        avg_conviction_on_wins=0.5,
        avg_conviction_on_losses=0.5,
        best_dimension="orderflow",
        worst_dimension="macro",
        dimension_accuracy={},
    )
