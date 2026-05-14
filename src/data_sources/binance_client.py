"""
Binance data ingestion — REST + WebSocket for BTC/USDT 15m candles.
Full data layer: OHLCV, orderbook, aggTrades, funding, OI, long/short ratio.

Supports SOCKS5 proxy via BINANCE_PROXY env var (e.g., socks5://user:pass@host:port).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import aiohttp_socks  # SOCKS5 proxy support
import websockets

log = logging.getLogger(__name__)

SPOT_BASE    = "https://api.binance.com/api/v3"
FUTURES_BASE = "https://fapi.binance.com/fapi/v1"
WS_COMBINED  = "wss://stream.binance.com:9443/stream"
SYMBOL_SPOT  = "btcusdt"
SYMBOL_FUT   = "BTCUSDT"


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Candle:
    """Single 15-minute OHLCV candle."""
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float
    trades: int
    buy_volume: float
    sell_volume: float
    is_closed: bool = True

    @property
    def is_green(self) -> bool:
        return self.close >= self.open

    @property
    def body_pct(self) -> float:
        return abs(self.close - self.open) / self.close * 100

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def close_position(self) -> float:
        """Where close sits in the range: 0.0=bottom, 1.0=top"""
        r = self.range
        if r == 0:
            return 0.5
        return (self.close - self.low) / r

    @property
    def upper_wick_pct(self) -> float:
        r = self.range
        if r == 0:
            return 0.0
        return (self.high - max(self.open, self.close)) / r * 100

    @property
    def lower_wick_pct(self) -> float:
        r = self.range
        if r == 0:
            return 0.0
        return (min(self.open, self.close) - self.low) / r * 100

    @property
    def body_wick_ratio(self) -> float:
        total_wick = self.upper_wick_pct + self.lower_wick_pct
        if total_wick == 0:
            return 999.0
        return self.body_pct / total_wick

    @property
    def candle_pattern(self) -> str:
        """Basic candlestick pattern classification."""
        cp = self.close_position
        uwk = self.upper_wick_pct
        lwk = self.lower_wick_pct
        bp = self.body_pct

        if bp < 0.05:
            return "DOJI"
        if lwk > 60 and uwk < 15 and cp > 0.7:
            return "HAMMER"
        if uwk > 60 and lwk < 15 and cp < 0.3:
            return "SHOOTING_STAR"
        if cp > 0.65 and self.is_green:
            return "BULLISH_CLOSE"
        if cp < 0.35 and not self.is_green:
            return "BEARISH_CLOSE"
        if uwk > 40 and lwk > 40 and bp < 0.5:
            return "SPINNING_TOP"
        if self.is_green and lwk > bp * 2:
            return "DRAGONFLY"
        if not self.is_green and uwk > bp * 2:
            return "GRAVESTONE"
        if cp > 0.5 and self.is_green and uwk < 10 and lwk < 20:
            return "MARUBOZU_BULL"
        if cp < 0.5 and not self.is_green and uwk < 10 and lwk < 20:
            return "MARUBOZU_BEAR"
        return "NEUTRAL"


@dataclass
class AggTrade:
    """Aggregated trade from Binance WS."""
    price: float
    quantity: float
    is_buyer_maker: bool  # True = aggressive seller (initiated sell → was buy at bid)
    timestamp: int
    trade_id: int

    @property
    def is_buy_initiated(self) -> bool:
        """True = buy-side aggression (taker bought, price went up)."""
        return not self.is_buyer_maker


@dataclass
class OrderBookEntry:
    price: float
    quantity: float


@dataclass
class OrderBook:
    bids: list[OrderBookEntry]
    asks: list[OrderBookEntry]
    last_update: datetime

    @property
    def mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return (self.bids[0].price + self.asks[0].price) / 2

    @property
    def spread_bps(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        mid = self.mid_price
        if mid == 0:
            return 0.0
        return (self.asks[0].price - self.bids[0].price) / mid * 10000

    @property
    def obi(self) -> float:
        """Order Book Imbalance: (bid_vol - ask_vol) / total_vol ∈ [-1, +1]"""
        bid_vol = sum(e.quantity for e in self.bids)
        ask_vol = sum(e.quantity for e in self.asks)
        total = bid_vol + ask_vol
        if total == 0:
            return 0.0
        return (bid_vol - ask_vol) / total

    @property
    def obi_5_levels(self) -> float:
        """OBI using only top 5 levels."""
        bid_vol = sum(e.quantity for e in self.bids[:5])
        ask_vol = sum(e.quantity for e in self.asks[:5])
        total = bid_vol + ask_vol
        if total == 0:
            return 0.0
        return (bid_vol - ask_vol) / total


@dataclass
class FundingRate:
    rate_pct: float          # e.g. 0.01 = 0.01%
    next_funding_time: int
    timestamp: datetime


@dataclass
class MarketTicker24h:
    last_price: float
    price_change_pct: float
    volume_24h: float
    quote_volume_24h: float
    high_24h: float
    low_24h: float


@dataclass
class OpenInterest:
    open_interest_btc: float
    timestamp: datetime


@dataclass
class LongShortRatio:
    long_account_ratio: float    # 0.0–1.0
    short_account_ratio: float   # 0.0–1.0
    long_short_ratio: float      # e.g. 1.5 = 1.5x more longs than shorts


# ─────────────────────────────────────────────────────────────────────────────
# Binance Client
# ─────────────────────────────────────────────────────────────────────────────

class BinanceClient:
    """
    Full Binance data ingestion: REST + combined WebSocket.

    WebSocket streams (single connection):
      btcusdt@kline_15m        → 15m candle close events
      btcusdt@depth20@100ms     → Order book depth (20 levels) at 10Hz
      btcusdt@aggTrade         → Aggregated trade stream
      btcusdt@bookTicker        → Top-of-book (bid/ask) updates

    Usage:
        async with BinanceClient() as client:
            candles = await client.fetch_klines(limit=100)
            kline_q = await client.subscribe_kline("15m")
            # ...
    """

    SPOT_BASE    = SPOT_BASE
    FUTURES_BASE = FUTURES_BASE
    WS_COMBINED  = WS_COMBINED
    SYMBOL_SPOT  = SYMBOL_SPOT
    SYMBOL_FUT   = SYMBOL_FUT

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_subscribers: dict[str, asyncio.Queue] = {}
        self._trade_buffer: list[AggTrade] = []
        self._trade_buffer_max = 500
        self._order_book: Optional[OrderBook] = None
        self._book_ticker: dict = {}
        self._last_candle: Optional[Candle] = None
        # SOCKS5 proxy support — set BINANCE_PROXY env var (e.g. socks5://user:pass@host:port)
        proxy = os.getenv("BINANCE_PROXY", "")
        self._connector = aiohttp_socks.ProxyConnector.from_url(proxy) if proxy else None

    # ── Session ───────────────────────────────────────────────────────────────

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(connector=self._connector)
        return self

    async def __aexit__(self, *args):
        await self._close_ws()
        if self._session:
            await self._session.close()

    async def _close_ws(self):
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    # ── REST helpers ─────────────────────────────────────────────────────────

    async def _get(self, base: str, path: str, params: Optional[dict] = None,
                   timeout: int = 10) -> dict:
        url = f"{base}{path}"
        async with self._session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _spot_get(self, path: str, params: Optional[dict] = None) -> dict:
        return await self._get(self.SPOT_BASE, path, params)

    async def _futures_get(self, path: str, params: Optional[dict] = None) -> dict:
        return await self._get(self.FUTURES_BASE, path, params)

    # ── REST Endpoints ───────────────────────────────────────────────────────

    async def fetch_klines(
        self, symbol: Optional[str] = None, interval: str = "15m", limit: int = 100
    ) -> list[Candle]:
        """Fetch historical 15m klines (OHLCV candles)."""
        symbol = (symbol or self.SYMBOL_SPOT).upper()
        raw = await self._spot_get(
            "/klines",
            {"symbol": symbol, "interval": interval, "limit": limit}
        )
        candles = []
        for r in raw:
            candles.append(Candle(
                open_time=int(r[0]),
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                volume=float(r[5]),
                close_time=int(r[6]),
                quote_volume=float(r[7]),
                trades=int(r[8]),
                buy_volume=float(r[10]) if len(r) > 10 else 0.0,
                sell_volume=float(r[11]) if len(r) > 11 else 0.0,
            ))
        if candles:
            self._last_candle = candles[-1]
        return candles

    async def fetch_order_book(self, symbol: Optional[str] = None, limit: int = 20
                               ) -> OrderBook:
        """Fetch top N levels of the order book."""
        symbol = (symbol or self.SYMBOL_SPOT).upper()
        raw = await self._spot_get("/depth", {"symbol": symbol, "limit": limit})
        bids = [OrderBookEntry(price=float(p), quantity=float(q))
                for p, q in raw.get("bids", [])]
        asks = [OrderBookEntry(price=float(p), quantity=float(q))
                for p, q in raw.get("asks", [])]
        ob = OrderBook(bids=bids, asks=asks, last_update=datetime.now(timezone.utc))
        self._order_book = ob
        return ob

    async def fetch_ticker_24h(self, symbol: Optional[str] = None
                                ) -> MarketTicker24h:
        """Fetch 24h rolling ticker stats."""
        symbol = (symbol or self.SYMBOL_SPOT).upper()
        raw = await self._spot_get("/ticker/24hr", {"symbol": symbol})
        return MarketTicker24h(
            last_price=float(raw["lastPrice"]),
            price_change_pct=float(raw["priceChangePercent"]),
            volume_24h=float(raw["volume"]),
            quote_volume_24h=float(raw["quoteVolume"]),
            high_24h=float(raw["highPrice"]),
            low_24h=float(raw["lowPrice"]),
        )

    async def fetch_recent_trades(self, symbol: Optional[str] = None, limit: int = 100
                                   ) -> list[AggTrade]:
        """Fetch most recent trades for TCR/seeding."""
        symbol = (symbol or self.SYMBOL_SPOT).upper()
        raw = await self._spot_get("/trades", {"symbol": symbol, "limit": limit})
        trades = []
        for t in reversed(raw):
            trades.append(AggTrade(
                price=float(t["price"]),
                quantity=float(t["qty"]),
                is_buyer_maker=bool(t["isBuyerMaker"]),
                timestamp=int(t["time"]),
                trade_id=int(t["id"]),
            ))
        return trades

    async def fetch_funding_rate(self, symbol: Optional[str] = None) -> FundingRate:
        """Fetch current funding rate from USDT-M futures."""
        symbol = (symbol or self.SYMBOL_FUT).upper()
        raw = await self._futures_get("/fundingRate",
                                      {"symbol": symbol, "limit": 3})
        entries = raw if isinstance(raw, list) else [raw]
        if not entries:
            raise ValueError(f"No funding rate data for {symbol}")
        latest = entries[0]
        return FundingRate(
            rate_pct=float(latest["fundingRate"]) * 100,
            next_funding_time=int(latest["fundingTime"]),
            timestamp=datetime.now(timezone.utc),
        )

    async def fetch_open_interest(self, symbol: Optional[str] = None) -> OpenInterest:
        """Fetch current open interest from USDT-M futures."""
        symbol = (symbol or self.SYMBOL_FUT).upper()
        raw = await self._futures_get("/openInterest", {"symbol": symbol})
        return OpenInterest(
            open_interest_btc=float(raw["openInterest"]),
            timestamp=datetime.now(timezone.utc),
        )

    async def fetch_long_short_ratio(self, symbol: Optional[str] = None
                                     ) -> Optional[LongShortRatio]:
        """Fetch top traders long/short ratio from Binance."""
        symbol = (symbol or self.SYMBOL_FUT).upper()
        try:
            raw = await self._futures_get(
                "/topLongShortPositionRatio",
                {"symbol": symbol, "period": "15m", "limit": 10}
            )
            entries = raw if isinstance(raw, list) else []
            if entries:
                latest = entries[-1]
                return LongShortRatio(
                    long_account_ratio=float(latest["longAccount"]),
                    short_account_ratio=float(latest["shortAccount"]),
                    long_short_ratio=float(latest["longShortRatio"]),
                )
        except Exception as e:
            log.debug(f"Long/short ratio fetch failed: {e}")

        # Fallback: compute from trade buffer TCR
        tcr = self.trade_count_ratio(n=200)
        long_r = max(0.05, min(0.95, 0.5 + tcr * 0.45))
        short_r = 1.0 - long_r
        ratio = long_r / max(short_r, 0.001)
        ratio = max(0.05, min(19.0, ratio))
        return LongShortRatio(
            long_account_ratio=long_r,
            short_account_ratio=short_r,
            long_short_ratio=ratio,
        )

    # ── WebSocket ───────────────────────────────────────────────────────────

    async def subscribe_kline(self, interval: str = "15m") -> asyncio.Queue[Candle]:
        """
        Subscribe to Binance combined WS stream.
        Returns a queue that receives Candle objects on each 15m candle close.
        """
        q: asyncio.Queue[Candle] = asyncio.Queue()
        self._ws_subscribers["kline_15m"] = q
        await self._ensure_ws()
        return q

    async def _ensure_ws(self):
        if self._ws and self._ws.state == websockets.State.OPEN:
            return
        await self._close_ws()

        streams = [
            f"{self.SYMBOL_SPOT}@kline_15m",
            f"{self.SYMBOL_SPOT}@depth20@100ms",
            f"{self.SYMBOL_SPOT}@aggTrade",
            f"{self.SYMBOL_SPOT}@bookTicker",
        ]
        url = f"{self.WS_COMBINED}?streams={'/'.join(streams)}"
        log.info(f"Connecting to Binance WS: {url[:100]}...")
        self._ws = await websockets.connect(url, ping_interval=20)
        asyncio.create_task(self._ws_reader())

    async def _ws_reader(self):
        """Route incoming WS messages to appropriate handlers."""
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                stream = msg.get("stream", "")
                data = msg.get("data", {})
                await self._route_ws(stream, data)
        except websockets.ConnectionClosed as exc:
            log.warning(f"WS disconnected: {exc} — will reconnect on next subscribe")
            self._ws = None

    async def _route_ws(self, stream: str, data: dict):
        if stream == f"{self.SYMBOL_SPOT}@kline_15m":
            k = data.get("k", data)
            candle = Candle(
                open_time=int(k["t"]),
                open=float(k["o"]),
                high=float(k["h"]),
                low=float(k["l"]),
                close=float(k["c"]),
                volume=float(k["v"]),
                close_time=int(k["T"]),
                quote_volume=float(k["q"]) if k.get("q") else 0.0,
                trades=int(k["n"]) if k.get("n") else 0,
                buy_volume=float(k["V"]) if k.get("V") else 0.0,
                sell_volume=float(k["Q"]) if k.get("Q") else 0.0,
                is_closed=bool(k["x"]) if k.get("x") is not None else False,
            )
            self._last_candle = candle
            if candle.is_closed and "kline_15m" in self._ws_subscribers:
                await self._ws_subscribers["kline_15m"].put(candle)

        elif stream.endswith("@depth20@100ms"):
            bids = [OrderBookEntry(price=float(p), quantity=float(q))
                    for p, q in data.get("bids", [])]
            asks = [OrderBookEntry(price=float(p), quantity=float(q))
                    for p, q in data.get("asks", [])]
            self._order_book = OrderBook(
                bids=bids, asks=asks,
                last_update=datetime.now(timezone.utc)
            )

        elif stream == f"{self.SYMBOL_SPOT}@aggTrade":
            trade = AggTrade(
                price=float(data["p"]),
                quantity=float(data["q"]),
                is_buyer_maker=bool(data["m"]),
                timestamp=int(data["T"]),
                trade_id=int(data["a"]),
            )
            self._trade_buffer.append(trade)
            if len(self._trade_buffer) > self._trade_buffer_max:
                self._trade_buffer = self._trade_buffer[-self._trade_buffer_max:]

        elif stream == f"{self.SYMBOL_SPOT}@bookTicker":
            self._book_ticker = data

    # ── Orderflow Metrics ───────────────────────────────────────────────────

    def seed_trade_buffer(self, trades: list[AggTrade]):
        """Seed the trade buffer from REST recent trades."""
        for t in trades:
            self._trade_buffer.append(t)
        if len(self._trade_buffer) > self._trade_buffer_max:
            self._trade_buffer = self._trade_buffer[-self._trade_buffer_max:]

    def vpin(self, n_buckets: int = 50) -> float:
        """
        Volume-synchronized Probability of Informed Trading.

        Buckets the trade stream into fixed-volume buckets.
        VPIN = rolling average of |V_buy - V_sell| / V_total per bucket.

        High VPIN (>0.6) = institutional informed trading active = directional move incoming.
        """
        if len(self._trade_buffer) < n_buckets:
            return 0.5

        # Get volume per trade
        volumes = [t.quantity for t in self._trade_buffer]
        total_vol = sum(volumes)
        if total_vol == 0:
            return 0.5

        bucket_vol = total_vol / n_buckets
        vpin_values = []

        cum_vol = 0.0
        buy_vol = 0.0
        sell_vol = 0.0
        bucket_idx = 0

        for t in self._trade_buffer:
            if t.is_buy_initiated:
                buy_vol += t.quantity
            else:
                sell_vol += t.quantity
            cum_vol += t.quantity

            if cum_vol >= bucket_vol * (bucket_idx + 1) and bucket_idx < n_buckets:
                bucket_total = buy_vol + sell_vol
                if bucket_total > 0:
                    vpin_values.append(abs(buy_vol - sell_vol) / bucket_total)
                buy_vol = 0.0
                sell_vol = 0.0
                bucket_idx += 1

        if not vpin_values:
            return 0.5
        return sum(vpin_values) / len(vpin_values)

    def cvd(self, n: int = 200) -> float:
        """
        Cumulative Volume Delta over last N trades.

        CVD = sum of (buy_qty - sell_qty) for last N trades.
        Positive CVD = net buying pressure.
        Negative CVD = net selling pressure.
        """
        trades = self._trade_buffer[-n:]
        return sum(
            t.quantity if t.is_buy_initiated else -t.quantity
            for t in trades
        )

    def trade_count_ratio(self, n: int = 200) -> float:
        """
        Trade Count Ratio ∈ [-1, +1].

        TCR = (buy_trades - sell_trades) / total_trades.
        Positive = buyer-aggression dominant.
        Negative = seller-aggression dominant.
        """
        trades = self._trade_buffer[-n:]
        if not trades:
            return 0.0
        buy_trades = sum(1 for t in trades if t.is_buy_initiated)
        total = len(trades)
        return (buy_trades - (total - buy_trades)) / total

    def ofi(self, n: int = 20) -> float:
        """
        Order Flow Imbalance over last N trades.

        Weighted OFI = sum of signed trade sizes (buy-initiated = +, sell-initiated = -).
        Normalized by number of trades.
        """
        trades = self._trade_buffer[-n:]
        if not trades:
            return 0.0
        total = sum(
            t.quantity if t.is_buy_initiated else -t.quantity
            for t in trades
        )
        return total / len(trades)
