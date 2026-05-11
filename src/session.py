"""
Session state machine — manages the 3-bet martingale lifecycle.
State persists to JSON so restarts don't lose active sessions.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from config.constants import SESSION_STATE_FILE

log = logging.getLogger(__name__)


class SessionPhase(Enum):
    IDLE = "IDLE"                  # No active session
    SESSION_ACTIVE = "SESSION_ACTIVE"  # Session open
    BET_PLACED = "BET_PLACED"          # Bet placed on current candle
    BET_RESOLVED = "BET_RESOLVED"      # Candle resolved
    SESSION_WON = "SESSION_WON"        # Won (≥1 of 3 correct)
    SESSION_LOST = "SESSION_LOST"      # Lost (0 of 3 correct)


@dataclass
class BetRecord:
    candle_label: str        # "C2", "C3", "C4"
    direction: str           # "GREEN" or "RED"
    confidence: float
    market_price: float      # Price at which bet was placed
    bet_amount: float        # USDC bet
    placed_at: str           # ISO timestamp
    resolved: bool = False
    won: Optional[bool] = None
    close_price: Optional[float] = None
    close_time: Optional[str] = None


@dataclass
class SessionState:
    phase: SessionPhase = SessionPhase.IDLE
    analysis_id: str = ""

    # Direction
    locked_direction: str = ""    # "GREEN" or "RED"
    current_direction: str = ""    # May differ from locked if flipped

    # Timing
    c1_close_time: int = 0        # Unix ms
    c1_close_price: float = 0.0
    session_started_at: str = ""

    # Bet records
    bets: list[BetRecord] = field(default_factory=list)
    current_bet_candle: str = ""  # "C2", "C3", "C4"

    # Counters
    wins: int = 0
    losses: int = 0
    bets_remaining: int = 3

    # Outcome
    resolved_at: str = ""
    total_pnl: float = 0.0        # Net P&L in USDC

    # Flags
    flip_occurred: bool = False
    flip_reason: str = ""

    @property
    def is_active(self) -> bool:
        return self.phase in (
            SessionPhase.SESSION_ACTIVE,
            SessionPhase.BET_PLACED,
            SessionPhase.BET_RESOLVED,
        )

    @property
    def bet_number(self) -> int:
        return len(self.bets)

    @property
    def next_candle(self) -> str:
        labels = ["C2", "C3", "C4"]
        return labels[len(self.bets)] if len(self.bets) < 3 else ""


class SessionManager:
    """
    Manages session lifecycle for the 3-bet martingale.
    State is persisted to SESSION_STATE_FILE so restarts are safe.

    Usage:
        sm = SessionManager()
        await sm.start(analysis_id="...", direction="GREEN", ...)
        await sm.place_bet(market_price=0.72, amount=10.0)
        await sm.resolve_bet(won=True, close_price=96500.0)
        if sm.is_session_over:
            await sm.log_outcome()
    """

    def __init__(self, state_file: Path = SESSION_STATE_FILE):
        self.state_file = Path(state_file)
        self._lock = asyncio.Lock()
        self._state: Optional[SessionState] = None

    # ── Persistence ────────────────────────────────────────────────────────

    async def load(self) -> SessionState:
        """Load session state from disk."""
        async with self._lock:
            if self._state:
                return self._state
            if not self.state_file.exists():
                self._state = SessionState()
                return self._state
            try:
                raw = self.state_file.read_text()
                data = json.loads(raw)
                self._state = SessionState(
                    phase=SessionPhase(data.get("phase", "IDLE")),
                    analysis_id=data.get("analysis_id", ""),
                    locked_direction=data.get("locked_direction", ""),
                    current_direction=data.get("current_direction", ""),
                    c1_close_time=data.get("c1_close_time", 0),
                    c1_close_price=data.get("c1_close_price", 0.0),
                    session_started_at=data.get("session_started_at", ""),
                    bets=[BetRecord(**b) for b in data.get("bets", [])],
                    current_bet_candle=data.get("current_bet_candle", ""),
                    wins=data.get("wins", 0),
                    losses=data.get("losses", 0),
                    bets_remaining=data.get("bets_remaining", 3),
                    resolved_at=data.get("resolved_at", ""),
                    total_pnl=data.get("total_pnl", 0.0),
                    flip_occurred=data.get("flip_occurred", False),
                    flip_reason=data.get("flip_reason", ""),
                )
                log.info(f"Session state loaded: phase={self._state.phase.value}, "
                         f"bets={len(self._state.bets)}")
                return self._state
            except Exception as e:
                log.warning(f"Failed to load session state: {e}")
                self._state = SessionState()
                return self._state

    async def save(self) -> None:
        """Persist session state to disk."""
        if not self._state:
            return
        data = {
            "phase": self._state.phase.value,
            "analysis_id": self._state.analysis_id,
            "locked_direction": self._state.locked_direction,
            "current_direction": self._state.current_direction,
            "c1_close_time": self._state.c1_close_time,
            "c1_close_price": self._state.c1_close_price,
            "session_started_at": self._state.session_started_at,
            "bets": [
                {
                    "candle_label": b.candle_label,
                    "direction": b.direction,
                    "confidence": b.confidence,
                    "market_price": b.market_price,
                    "bet_amount": b.bet_amount,
                    "placed_at": b.placed_at,
                    "resolved": b.resolved,
                    "won": b.won,
                    "close_price": b.close_price,
                    "close_time": b.close_time,
                }
                for b in self._state.bets
            ],
            "current_bet_candle": self._state.current_bet_candle,
            "wins": self._state.wins,
            "losses": self._state.losses,
            "bets_remaining": self._state.bets_remaining,
            "resolved_at": self._state.resolved_at,
            "total_pnl": self._state.total_pnl,
            "flip_occurred": self._state.flip_occurred,
            "flip_reason": self._state.flip_reason,
        }
        async with self._lock:
            self.state_file.write_text(json.dumps(data, indent=2))

    # ── Session Lifecycle ──────────────────────────────────────────────────

    async def start(
        self,
        analysis_id: str,
        direction: str,
        confidence: float,
        c1_close_time: int,
        c1_close_price: float,
    ) -> SessionState:
        """Open a new session with locked direction."""
        state = await self.load()
        if state.is_active:
            log.warning(f"Session already active: {state.phase.value} — cannot start new")
            return state

        state.phase = SessionPhase.SESSION_ACTIVE
        state.analysis_id = analysis_id
        state.locked_direction = direction
        state.current_direction = direction
        state.c1_close_time = c1_close_time
        state.c1_close_price = c1_close_price
        state.session_started_at = datetime.now(timezone.utc).isoformat()
        state.bets = []
        state.wins = 0
        state.losses = 0
        state.bets_remaining = 3
        state.flip_occurred = False
        state.flip_reason = ""
        state.current_bet_candle = "C2"
        state.total_pnl = 0.0

        await self.save()
        log.info(f"Session STARTED: direction={direction} confidence={confidence:.2f} "
                 f"c1_close={c1_close_price}")
        return state

    async def place_bet(
        self,
        candle_label: str,
        direction: str,
        confidence: float,
        market_price: float,
        bet_amount: float,
    ) -> SessionState:
        """Record a bet placement."""
        state = await self.load()
        if not state.is_active:
            raise RuntimeError("Cannot place bet: no active session")

        bet = BetRecord(
            candle_label=candle_label,
            direction=direction,
            confidence=confidence,
            market_price=market_price,
            bet_amount=bet_amount,
            placed_at=datetime.now(timezone.utc).isoformat(),
        )
        state.bets.append(bet)
        state.phase = SessionPhase.BET_PLACED
        state.current_bet_candle = candle_label
        state.bets_remaining = 3 - len(state.bets)

        await self.save()
        log.info(f"Bet placed: {candle_label} {direction} @ ${market_price:.4f} "
                 f"size=${bet_amount:.2f} | remaining={state.bets_remaining}")
        return state

    async def resolve_bet(
        self,
        won: bool,
        close_price: float,
    ) -> SessionState:
        """Resolve the most recent bet. Determines if session continues or ends."""
        state = await self.load()
        if not state.bets:
            raise RuntimeError("Cannot resolve: no bet to resolve")

        bet = state.bets[-1]
        bet.resolved = True
        bet.won = won
        bet.close_price = close_price
        bet.close_time = datetime.now(timezone.utc).isoformat()

        if won:
            state.wins += 1
        else:
            state.losses += 1

        state.phase = SessionPhase.BET_RESOLVED

        # ── Session outcome ────────────────────────────────────────────────
        if won:
            # WIN on any bet → session ends as WIN
            state.phase = SessionPhase.SESSION_WON
            state.resolved_at = datetime.now(timezone.utc).isoformat()
            log.info(f"Session WON on {bet.candle_label} | "
                     f"wins={state.wins} losses={state.losses}")

        elif len(state.bets) >= 3:
            # All 3 bets placed and all lost → session ends as LOSS
            state.phase = SessionPhase.SESSION_LOST
            state.resolved_at = datetime.now(timezone.utc).isoformat()
            log.info(f"Session LOST | all 3 bets lost")

        # else: session continues, waiting for next candle

        await self.save()
        return state

    async def flip_direction(
        self,
        new_direction: str,
        reason: str,
        confidence: float,
    ) -> SessionState:
        """Flip direction mid-session (only on C2 or C3 loss)."""
        state = await self.load()
        if state.flip_occurred:
            log.warning("Flip already occurred — ignoring duplicate flip request")
            return state
        if len(state.bets) >= 2:
            # Can only flip once and only between C2 and C3
            state.current_direction = new_direction
            state.flip_occurred = True
            state.flip_reason = reason
            await self.save()
            log.warning(f"DIRECTION FLIPPED: {state.locked_direction} → {new_direction} | "
                        f"reason: {reason}")
            return state
        return state

    async def end_session(self, total_pnl: float = 0.0) -> SessionState:
        """Explicitly end a session (for error recovery)."""
        state = await self.load()
        state.phase = SessionPhase.IDLE
        state.resolved_at = datetime.now(timezone.utc).isoformat()
        state.total_pnl = total_pnl
        await self.save()
        return state

    async def reset(self) -> SessionState:
        """Reset to idle (after logging outcome)."""
        state = await self.load()
        self._state = SessionState()
        if self.state_file.exists():
            self.state_file.unlink()
        return self._state

    # ── Helpers ────────────────────────────────────────────────────────────

    @property
    def is_session_over(self) -> bool:
        if not self._state:
            return True
        return self._state.phase in (
            SessionPhase.SESSION_WON,
            SessionPhase.SESSION_LOST,
        )

    @property
    def session_won(self) -> bool:
        return self._state and self._state.phase == SessionPhase.SESSION_WON

    def bet_pnl(self, market_price: float, bet_amount: float, won: bool) -> float:
        """Calculate P&L for a bet given market price and outcome."""
        if not won:
            return -bet_amount
        # Polymarket YES token: pays bet_amount / price
        # e.g., price=0.72, bet $10 → returns $10/0.72 = $13.89, profit = $3.89
        return bet_amount / market_price - bet_amount

    def summary(self) -> str:
        if not self._state:
            return "No session state"
        s = self._state
        bets_str = " | ".join(
            f"{b.candle_label}: {'✅' if b.won else '❌' if b.resolved else '⏳'}{b.direction}"
            for b in s.bets
        )
        return (f"Phase: {s.phase.value} | Dir: {s.current_direction} "
                f"({('FLIPPED from ' + s.locked_direction) if s.flip_occurred else 'locked'}) "
                f"| Bets: {bets_str} | PnL: ${s.total_pnl:.2f}")
