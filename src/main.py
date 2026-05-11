"""
BTC 15m Direction Predictor — Entry Point
Institutional-grade: multi-agent reasoning, orderflow, Polymarket execution.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

import structlog

from config import constants as C
from src.event_loop import BTCPredictor


def setup_logging(level: int = logging.INFO):
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.JSONRenderer() if "--json" in sys.argv else structlog.dev.ConsoleRenderer(),
        ],
    )


def check_env():
    """Verify critical environment variables are set."""
    missing = []
    if not C.ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not C.TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN (optional, for alerts)")

    if missing:
        print(f"⚠️  Missing env vars: {', '.join(missing)}")
        print("   Copy .env.example → .env and fill in your keys.\n")

    if not C.ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY is required to run the reasoning engine.")
        sys.exit(1)


async def main():
    parser = argparse.ArgumentParser(
        description="BTC 15m Direction Predictor — Institutional Grade"
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Enable live Polymarket trading (not paper mode)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Paper trading mode (default)"
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output logs as JSON"
    )
    args = parser.parse_args()

    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    setup_logging(log_level)

    check_env()

    predictor = BTCPredictor(dry_run=not args.live)

    # Graceful shutdown
    loop = asyncio.get_event_loop()

    async def shutdown():
        await predictor.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    try:
        await predictor.run()
    except KeyboardInterrupt:
        pass
    finally:
        await predictor.stop()


if __name__ == "__main__":
    asyncio.run(main())
