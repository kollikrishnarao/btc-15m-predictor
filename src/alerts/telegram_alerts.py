"""
Telegram alerts — rich notifications for all session lifecycle events.
Supports text, inline buttons, and file uploads (CSV).
"""
from __future__ import annotations

import asyncio
import logging
import io
from datetime import datetime, timezone
from typing import Optional

import aiohttp

from config.constants import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger(__name__)


def _build_tg_url(method: str) -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"


async def _tg_request(
    session: aiohttp.ClientSession,
    method: str,
    data: Optional[dict] = None,
) -> dict:
    url = _build_tg_url(method)
    async with session.post(
        url, json=data or {}, timeout=aiohttp.ClientTimeout(total=10)
    ) as resp:
        resp.raise_for_status()
        return await resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# Alert Templates
# ─────────────────────────────────────────────────────────────────────────────

class TelegramAlerts:
    """
    Sends formatted alerts to Telegram.

    Usage:
        alerts = TelegramAlerts()
        await alerts.session_started(direction="GREEN", confidence=0.72, ...)
        await alerts.bet_placed(candle="C2", price=0.72, size=10.0, ...)
        await alerts.session_won(candle="C3", pnl=3.89, ...)
        await alerts.session_lost(total_loss=10.0, ...)
        await alerts.circuit_breaker(consecutive_losses=3, ...)
        await alerts.stats(win_rate=0.65, ...)
    """

    def __init__(self, chat_id: str = TELEGRAM_CHAT_ID):
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()

    async def _send(
        self,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: Optional[dict] = None,
    ) -> bool:
        """Send a message to the configured Telegram chat."""
        if not TELEGRAM_BOT_TOKEN or not self.chat_id:
            log.debug(f"[NO TELEGRAM] {text[:100]}")
            return False

        try:
            result = await _tg_request(
                self._session,
                "sendMessage",
                {
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "reply_markup": json.dumps(reply_markup) if reply_markup else None,
                    "disable_web_page_preview": True,
                },
            )
            if result.get("ok"):
                return True
            else:
                log.warning(f"Telegram send failed: {result}")
                return False
        except Exception as e:
            log.warning(f"Telegram send error: {e}")
            return False

    async def _send_document(
        self,
        file_content: bytes,
        filename: str,
        caption: str,
    ) -> bool:
        """Send a file (e.g., CSV) to Telegram."""
        if not TELEGRAM_BOT_TOKEN or not self.chat_id:
            log.debug(f"[NO TELEGRAM] Would send file: {filename}")
            return False

        try:
            bio = io.BytesIO(file_content)
            form = aiohttp.FormData()
            form.add_field("chat_id", self.chat_id)
            form.add_field("caption", caption)
            form.add_field("document", bio, filename=filename,
                           content_type="text/csv")

            url = _build_tg_url("sendDocument")
            async with self._session.post(
                url, data=form, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                result = await resp.json()
                return result.get("ok", False)
        except Exception as e:
            log.warning(f"Telegram file send error: {e}")
            return False

    # ── Alert Methods ──────────────────────────────────────────────────────

    async def session_started(
        self,
        direction: str,
        confidence: float,
        rationale: str,
        market_url: str = "",
        regime: str = "UNKNOWN",
    ):
        emoji = "🟢" if direction == "GREEN" else "🔴"
        bucket = "HIGH" if confidence >= 0.70 else "MEDIUM"
        text = (
            f"{emoji} *SESSION STARTED*\n"
            f"Direction: *{direction}* ({emoji})\n"
            f"Confidence: *{confidence:.2f}* ({bucket})\n"
            f"Regime: {regime}\n\n"
            f"📊 *Rationale:*\n{rationale[:300]}...\n\n"
            f"{('🔗 [Market](' + market_url + ')') if market_url else ''}"
        )
        await self._send(text)

    async def bet_placed(
        self,
        candle: str,
        direction: str,
        price: float,
        size: float,
        market_url: str = "",
        bet_number: int = 1,
    ):
        emoji = "🟢" if direction == "GREEN" else "🔴"
        text = (
            f"⚡ *BET PLACED — {candle}*\n"
            f"{emoji} Direction: *{direction}*\n"
            f"💰 Size: *${size:.2f}* @ ${price:.4f}\n"
            f"Bet {bet_number}/3 | 3-bet martingale\n"
            f"{('🔗 [Market](' + market_url + ')') if market_url else ''}"
        )
        await self._send(text)

    async def bet_resolved(
        self,
        candle: str,
        won: bool,
        close_price: float,
        bets_remaining: int,
        session_pnl: float,
    ):
        result_emoji = "✅" if won else "❌"
        text = (
            f"{result_emoji} *{candle} RESOLVED — {'WIN' if won else 'LOSS'}*\n"
            f"Close price: ${close_price:.2f}\n"
            f"Session P&L: *${session_pnl:+.2f}*\n"
            f"{f'⏳ {bets_remaining} bet(s) remaining' if bets_remaining > 0 else '🏁 Session over'}"
        )
        await self._send(text)

    async def session_won(
        self,
        winning_candle: str,
        pnl: float,
        total_bets: int,
        confidence: float,
        flip_occurred: bool = False,
        market_url: str = "",
    ):
        text = (
            f"🏆 *SESSION WON*\n"
            f"Won on: *{winning_candle}*\n"
            f"Profit: *+${pnl:.2f}*\n"
            f"Bets used: {total_bets}/3\n"
            f"Confidence: {confidence:.2f}\n"
            f"{'🔄 Direction flipped mid-session' if flip_occurred else ''}\n"
            f"{('🔗 [Market](' + market_url + ')') if market_url else ''}"
        )
        await self._send(text)

    async def session_lost(
        self,
        total_loss: float,
        direction: str,
        all_bets: list,
        loss_reason: str = "",
        market_url: str = "",
    ):
        bets_text = "\n".join(
            f"  • {b['candle']}: {'✅' if b['won'] else '❌'} {b['close_price']:.2f}"
            for b in all_bets
        )
        text = (
            f"💀 *SESSION LOST*\n"
            f"Direction called: {direction}\n"
            f"Loss: *-${total_loss:.2f}*\n"
            f"Reason: {loss_reason[:200] if loss_reason else 'All 3 bets lost'}\n\n"
            f"Bets:\n{bets_text}\n"
            f"{('🔗 [Market](' + market_url + ')') if market_url else ''}"
        )
        await self._send(text)

    async def circuit_breaker(
        self,
        consecutive_losses: int,
        reason: str,
        edge_required: str,
    ):
        text = (
            f"🚨 *CIRCUIT BREAKER ACTIVATED*\n"
            f"Consecutive losses: *{consecutive_losses}*\n"
            f"Reason: {reason}\n"
            f"Next bet requires: edge > {edge_required}\n\n"
            f"⏸️ System will pause until edge threshold met."
        )
        await self._send(text)

    async def analysis_skipped(
        self,
        reason: str,
        confidence: float,
        candle_id: str,
    ):
        text = (
            f"⏭️ *ANALYSIS SKIPPED*\n"
            f"Candle: {candle_id}\n"
            f"Reason: {reason}\n"
            f"Confidence: {confidence:.2f} (< 0.55 threshold)"
        )
        await self._send(text)

    async def alert(
        self,
        level: str,   # INFO, WARNING, ERROR, CRITICAL
        message: str,
    ):
        emoji_map = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "🔴", "CRITICAL": "🚨"}
        text = f"{emoji_map.get(level, 'ℹ️')} *{level}*\n{message}"
        await self._send(text)

    async def stats(
        self,
        win_rate: float,
        total_sessions: int,
        total_pnl: float,
        last_20: list,
        consecutive_losses: int = 0,
        consecutive_wins: int = 0,
    ):
        outcomes = " ".join(
            "🟢" if w else "🔴" for w in last_20[-20:]
        )
        streak = ""
        if consecutive_wins >= 2:
            streak = f"\n🔥 Win streak: {consecutive_wins}"
        elif consecutive_losses >= 2:
            streak = f"\n📉 Loss streak: {consecutive_losses}"

        text = (
            f"📊 *PERFORMANCE STATS*\n"
            f"Total sessions: {total_sessions}\n"
            f"Win rate: *{win_rate*100:.1f}%*\n"
            f"Running P&L: *${total_pnl:+.2f}*\n"
            f"Last 20: {outcomes or 'None'}"
            f"{streak}"
        )
        await self._send(text)

    async def export_csv(self, csv_content: str) -> bool:
        """Send the predictions CSV to the Telegram chat."""
        filename = f"btc_predictions_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv"
        return await self._send_document(
            csv_content.encode(),
            filename=filename,
            caption="📊 BTC Predictions Export",
        )


import json  # noqa: E402
