"""
Prediction logger + feedback loop.
Append-only CSV. Back-fills outcomes when sessions resolve.
Computes rolling stats for the reflection context.
"""
from __future__ import annotations

import asyncio
import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.constants import (
    PERFORMANCE_LOG_FILE,
    PREDICTIONS_CSV,
    REFLECTION_CACHE,
    REFLECTION_OUTCOMES_COUNT,
)

log = logging.getLogger(__name__)


class PredictionLogger:
    """
    Append-only CSV logger + rolling performance tracker.

    Schema (columns in predictions.csv):
      analysis_id, timestamp, direction, confidence, confidence_bucket,
      signal_scores_json, advisor_call, advisor_confidence, flip_occurred,
      locked_direction, current_direction, session_won, session_lost,
      winning_candle, total_bets, total_pnl,
      market_price, market_url, c1_price, c1_pattern, rsi_14, vpin,
      winning_candles, losing_candles, regime, notes

    Outcomes are back-filled when session resolves.
    Reflection context is recomputed after every session.
    """

    CSV_COLUMNS = [
        "analysis_id", "timestamp", "direction", "confidence",
        "confidence_bucket", "signal_scores_json", "advisor_call",
        "advisor_confidence", "advisor_strength", "locked_direction",
        "current_direction", "session_won", "session_lost",
        "winning_candle", "total_bets", "total_pnl",
        "market_price", "market_url", "c1_price", "c1_pattern",
        "rsi_14", "vpin", "cvd", "funding_rate", "fear_greed",
        "winning_candles", "losing_candles", "regime",
        "pre_filter_reason", "reasoning_json", "notes",
    ]

    def __init__(
        self,
        csv_path: Path = PREDICTIONS_CSV,
        perf_path: Path = PERFORMANCE_LOG_FILE,
        reflection_path: Path = REFLECTION_CACHE,
    ):
        self.csv_path = Path(csv_path)
        self.perf_path = Path(perf_path)
        self.reflection_path = Path(reflection_path)
        self._lock = asyncio.Lock()
        self._ensure_csv()

    def _ensure_csv(self):
        if not self.csv_path.exists():
            self.csv_path.write_text(",".join(self.CSV_COLUMNS) + "\n")

    # ── Log Analysis ──────────────────────────────────────────────────────

    async def log_analysis(
        self,
        analysis_id: str,
        timestamp: str,
        direction: str,
        confidence: float,
        confidence_bucket: str,
        signal_scores: dict,
        advisor_call: str,
        advisor_confidence: float,
        advisor_strength: str,
        locked_direction: str,
        current_direction: str,
        pre_filter_reason: str,
        reasoning_json: dict,
        market_price: float,
        market_url: str,
        c1_price: float,
        c1_pattern: str,
        rsi_14: float,
        vpin: float,
        cvd: float,
        funding_rate: float,
        fear_greed: int,
        regime: str,
    ) -> None:
        """Append a new analysis row to the CSV."""
        row = {
            "analysis_id": analysis_id,
            "timestamp": timestamp,
            "direction": direction,
            "confidence": confidence,
            "confidence_bucket": confidence_bucket,
            "signal_scores_json": json.dumps(signal_scores),
            "advisor_call": advisor_call,
            "advisor_confidence": advisor_confidence,
            "advisor_strength": advisor_strength,
            "locked_direction": locked_direction,
            "current_direction": current_direction,
            "session_won": "",
            "session_lost": "",
            "winning_candle": "",
            "total_bets": "",
            "total_pnl": "",
            "market_price": market_price,
            "market_url": market_url,
            "c1_price": c1_price,
            "c1_pattern": c1_pattern,
            "rsi_14": rsi_14,
            "vpin": vpin,
            "cvd": cvd,
            "funding_rate": funding_rate,
            "fear_greed": fear_greed,
            "winning_candles": "",
            "losing_candles": "",
            "regime": regime,
            "pre_filter_reason": pre_filter_reason,
            "reasoning_json": json.dumps(reasoning_json)[:500],
            "notes": "",
        }
        async with self._lock:
            with open(self.csv_path, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_COLUMNS)
                writer.writerow(row)
        log.debug(f"Logged analysis {analysis_id}: {direction} @ {confidence:.2f}")

    async def log_session_outcome(
        self,
        analysis_id: str,
        session_won: bool,
        session_lost: bool,
        winning_candle: str,
        total_bets: int,
        total_pnl: float,
        winning_candles: list,
        losing_candles: list,
        flip_occurred: bool,
        notes: str = "",
    ) -> None:
        """Back-fill outcome fields for an analysis row identified by analysis_id."""
        rows = []
        async with self._lock:
            if not self.csv_path.exists():
                return
            with open(self.csv_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["analysis_id"] == analysis_id:
                        row["session_won"] = str(session_won)
                        row["session_lost"] = str(session_lost)
                        row["winning_candle"] = winning_candle
                        row["total_bets"] = str(total_bets)
                        row["total_pnl"] = f"{total_pnl:.4f}"
                        row["winning_candles"] = ",".join(winning_candles)
                        row["losing_candles"] = ",".join(losing_candles)
                        row["notes"] = notes
                    rows.append(row)

            with open(self.csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)

        # Recompute reflection context
        await self._update_reflection_cache()
        log.info(f"Outcome logged: {analysis_id} → {'WON' if session_won else 'LOST'} PnL=${total_pnl:.2f}")

    # ── Performance Stats ──────────────────────────────────────────────────

    async def compute_stats(self) -> dict:
        """Compute running performance stats from CSV."""
        if not self.csv_path.exists():
            return self._empty_stats()

        try:
            with open(self.csv_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            resolved = [r for r in rows if r["session_won"] in ("True", "False")]
            if not resolved:
                return self._empty_stats()

            won = sum(1 for r in resolved if r["session_won"] == "True")
            total = len(resolved)
            win_rate = won / total if total > 0 else 0.0

            pnls = [float(r["total_pnl"]) for r in resolved if r["total_pnl"]]
            total_pnl = sum(pnls)
            avg_pnl = total_pnl / total if total > 0 else 0.0

            last_20 = resolved[-20:]
            last_20_outcomes = [
                (r["direction"], r["session_won"] == "True")
                for r in last_20
            ]

            # Consecutive streaks
            consecutive_losses = 0
            consecutive_wins = 0
            for r in reversed(resolved):
                if r["session_lost"] == "True":
                    consecutive_losses += 1
                    consecutive_wins = 0
                elif r["session_won"] == "True":
                    consecutive_wins += 1
                    consecutive_losses = 0
                else:
                    break

            return {
                "total_sessions": total,
                "sessions_won": won,
                "sessions_lost": total - won,
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "avg_pnl_per_session": avg_pnl,
                "last_20": last_20_outcomes,
                "consecutive_losses": consecutive_losses,
                "consecutive_wins": consecutive_wins,
            }
        except Exception as e:
            log.warning(f"Stats computation failed: {e}")
            return self._empty_stats()

    async def get_reflection_context(self) -> dict:
        """Get the reflection context for the next analysis prompt."""
        async with self._lock:
            if self.reflection_path.exists():
                try:
                    return json.loads(self.reflection_path.read_text())
                except Exception:
                    pass
            return self._build_reflection({})

    # ── Reflection Cache ───────────────────────────────────────────────────

    async def _update_reflection_cache(self) -> None:
        stats = await self.compute_stats()
        context = self._build_reflection(stats)
        async with self._lock:
            self.reflection_path.write_text(json.dumps(context, indent=2))

    def _build_reflection(self, stats: dict) -> dict:
        last_20 = stats.get("last_20", [])
        win_rate_20 = (
            sum(1 for _, w in last_20 if w) / len(last_20)
            if last_20 else 0.0
        )

        # Format last 20 as string for prompt
        outcomes_str = " | ".join(
            f"{'✅' if w else '❌'}{d[:1]}" for d, w in last_20
        )

        # Determine regime from recent outcomes + win rate
        if stats.get("win_rate", 0) >= 0.60:
            regime = "CONFIRMED_EDGE"
        elif stats.get("consecutive_losses", 0) >= 3:
            regime = "DRAWDOWN"
        elif win_rate_20 < 0.45:
            regime = "REGIME_SHIFT"
        else:
            regime = "NORMAL"

        # Average session length (bets until win)
        return {
            "last_20_outcomes": last_20[-REFLECTION_OUTCOMES_COUNT:],
            "last_20_outcomes_formatted": outcomes_str or "No history yet",
            "rolling_win_rate_20": win_rate_20,
            "total_sessions": stats.get("total_sessions", 0),
            "win_rate": stats.get("win_rate", 0.0),
            "total_pnl": stats.get("total_pnl", 0.0),
            "consecutive_losses": stats.get("consecutive_losses", 0),
            "consecutive_wins": stats.get("consecutive_wins", 0),
            "regime": regime,
            "avg_session_length": 1.5,  # Will be computed from data
            "strongest_signal_category": "orderflow",   # TODO: compute from CSV
            "weakest_signal_category": "macro",
            "last_flip": "None",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _empty_stats() -> dict:
        return {
            "total_sessions": 0, "sessions_won": 0, "sessions_lost": 0,
            "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl_per_session": 0.0,
            "last_20": [], "consecutive_losses": 0, "consecutive_wins": 0,
        }

    # ── CSV Export ─────────────────────────────────────────────────────────

    async def export_csv(self) -> str:
        """Return full CSV content as string for Telegram export."""
        async with self._lock:
            if self.csv_path.exists():
                return self.csv_path.read_text()
            return ""
