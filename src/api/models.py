"""Pydantic models for the REST API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Direction(str, Enum):
    GREEN = "GREEN"
    RED = "RED"
    SKIP = "SKIP"
    IDLE = "IDLE"


class SessionOutcome(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    IN_PROGRESS = "IN_PROGRESS"


class CircuitBreakerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    TRIPPED = "TRIPPED"


class ConvictionScores(BaseModel):
    momentum: float = Field(ge=0.0, le=1.0)
    trend: float = Field(ge=0.0, le=1.0)
    orderflow: float = Field(ge=0.0, le=1.0)
    smart_money: float = Field(ge=0.0, le=1.0)
    sentiment: float = Field(ge=0.0, le=1.0)
    macro: float = Field(ge=0.0, le=1.0)
    weighted_total: float = Field(ge=0.0, le=1.0)


class OrderflowMetrics(BaseModel):
    vpin: float
    cvd: float
    ofi: float
    tcr: float
    obi: float
    cvd_divergence: bool


class MarketSnapshot(BaseModel):
    btc_price: float
    price_change_pct_24h: float
    volume_24h: float
    funding_rate: float
    open_interest: float
    fear_greed_index: int
    adx: float
    rvol: float
    timestamp: datetime


class ActiveSession(BaseModel):
    direction: Direction
    conviction: float
    bet_number: int  # 1, 2, or 3
    current_bet_size: float
    total_at_risk: float
    entry_price: float
    started_at: datetime
    candle_target: str  # "C2", "C3", "C4"


class SystemStatus(BaseModel):
    is_running: bool
    circuit_breaker: CircuitBreakerStatus
    consecutive_losses: int
    data_freshness_seconds: float
    binance_ws_connected: bool
    cycle_phase: str  # "IDLE", "ANALYZING", "WAITING", "RESOLVING"
    last_cycle_at: Optional[datetime]
    next_cycle_at: Optional[datetime]


class SignalsPayload(BaseModel):
    market: MarketSnapshot
    conviction: ConvictionScores
    orderflow: OrderflowMetrics
    active_session: Optional[ActiveSession]
    system: SystemStatus
    last_direction: Direction
    advisor_call: Direction
    advisor_confidence: float


class BetResult(BaseModel):
    candle: str  # "C2", "C3", "C4"
    direction: Direction
    outcome: SessionOutcome
    bet_size: float
    pnl: float


class SessionRecord(BaseModel):
    session_id: str
    started_at: datetime
    ended_at: Optional[datetime]
    direction: Direction
    conviction: float
    outcome: SessionOutcome
    bets: list[BetResult]
    total_pnl: float
    flip_occurred: bool
    regime: str
    momentum_score: float
    trend_score: float
    orderflow_score: float
    smart_money_score: float
    sentiment_score: float
    macro_score: float


class PerformanceStats(BaseModel):
    total_sessions: int
    win_rate_all: float
    win_rate_20: float  # rolling last 20
    total_pnl: float
    daily_pnl: float
    weekly_pnl: float
    bankroll: float
    consecutive_wins: int
    consecutive_losses: int
    avg_conviction_on_wins: float
    avg_conviction_on_losses: float
    best_dimension: str
    worst_dimension: str
    dimension_accuracy: dict[str, float]


class WsMessageType(str, Enum):
    SIGNALS_UPDATE = "SIGNALS_UPDATE"
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_ENDED = "SESSION_ENDED"
    BET_PLACED = "BET_PLACED"
    BET_RESOLVED = "BET_RESOLVED"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    SYSTEM_STATUS = "SYSTEM_STATUS"
    ALERT = "ALERT"


class WsMessage(BaseModel):
    type: WsMessageType
    payload: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
