"""FastAPI cloud server — exposes BTC predictor state to Android and web clients."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.models import (
    PerformanceStats,
    SessionRecord,
    SignalsPayload,
    SystemStatus,
    WsMessage,
    WsMessageType,
)
from src.api.state_bridge import StateBridge
from src.api.websocket_manager import ConnectionManager

logger = logging.getLogger(__name__)

ws_manager = ConnectionManager()
state_bridge = StateBridge()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on startup, clean up on shutdown."""
    broadcast_task = asyncio.create_task(_broadcast_signals_loop())
    yield
    broadcast_task.cancel()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="BTC-15m Predictor API",
    description="Cloud API for the BTC 15-minute direction predictor. Powers the Android companion app.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/v1/signals", response_model=SignalsPayload, tags=["signals"])
async def get_signals():
    """Current market signals, conviction scores, and active session state."""
    payload = await state_bridge.get_signals()
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Predictor not running or no data available yet",
        )
    return payload


@app.get("/api/v1/status", response_model=SystemStatus, tags=["system"])
async def get_system_status():
    """Current system health and operational status."""
    return await state_bridge.get_system_status()


@app.get("/api/v1/performance", response_model=PerformanceStats, tags=["performance"])
async def get_performance():
    """Aggregated trading performance statistics."""
    return await state_bridge.get_performance()


@app.get("/api/v1/sessions", response_model=list[SessionRecord], tags=["sessions"])
async def get_sessions(limit: int = 50, offset: int = 0):
    """Paginated session history (most recent first)."""
    return await state_bridge.get_sessions(limit=limit, offset=offset)


@app.get("/api/v1/sessions/{session_id}", response_model=SessionRecord, tags=["sessions"])
async def get_session(session_id: str):
    """Single session detail by ID."""
    session = await state_bridge.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """
    Real-time push channel. Android app connects here to receive live updates
    without polling. Messages are typed WsMessage JSON objects.

    Message types:
      SIGNALS_UPDATE  — conviction scores + market snapshot (every 5s)
      SESSION_STARTED — new bet placed
      SESSION_ENDED   — session resolved (WIN/LOSS)
      BET_PLACED      — individual bet placed (C2/C3/C4)
      BET_RESOLVED    — individual bet result
      CIRCUIT_BREAKER — circuit breaker tripped/reset
      ALERT           — critical system alert
    """
    await ws_manager.connect(websocket)
    try:
        # Send current state immediately on connect
        payload = await state_bridge.get_signals()
        if payload:
            msg = WsMessage(
                type=WsMessageType.SIGNALS_UPDATE,
                payload=payload.model_dump(mode="json"),
            )
            await websocket.send_text(msg.model_dump_json())

        # Keep connection alive, handle ping frames
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("ping")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ── Background broadcast loop ─────────────────────────────────────────────────

async def _broadcast_signals_loop():
    """Broadcast signals update to all connected WebSocket clients every 5 seconds."""
    while True:
        await asyncio.sleep(5)
        if ws_manager.active_connections:
            try:
                payload = await state_bridge.get_signals()
                if payload:
                    msg = WsMessage(
                        type=WsMessageType.SIGNALS_UPDATE,
                        payload=payload.model_dump(mode="json"),
                    )
                    await ws_manager.broadcast(msg.model_dump_json())
            except Exception as exc:
                logger.error("Broadcast error: %s", exc)


def notify_clients(message: WsMessage):
    """
    Called by the event loop when a session event occurs.
    Schedules a broadcast on the running event loop.
    """
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(ws_manager.broadcast(message.model_dump_json()))
    except RuntimeError:
        pass  # No event loop — server not running
