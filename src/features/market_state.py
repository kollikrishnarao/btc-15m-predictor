"""
Market state assembler — parallel data fetch across all sources,
produces a single enriched MarketState packet for the reasoning engine.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import aiohttp

from config.constants import (
    BINANCE_FUTURES_BASE, BINANCE_SPOT_BASE,
    COINGECKO_API, FEAR_GREED_API, KLINE_LIMIT,
)
from src.data_sources.binance_client import (
    BinanceClient, Candle, OrderBook,
    FundingRate, MarketTicker24h, OpenInterest, LongShortRatio,
)
from src.features.technical_indicators import TechnicalState, compute_indicators

log = logging.getLogger(__name__)


@dataclass
class MacroState:
    """Macro environment at analysis time."""
    dxy: float = 0.0
    dxy_change_pct: float = 0.0
    sp500: float = 0.0
    sp500_change_pct: float = 0.0
    vix: float = 20.0
    vix_change_pct: float = 0.0
    us10y: float = 4.5
    us10y_change_pct: float = 0.0
    fetched_at: Optional[datetime] = None
    stale: bool = True

    @property
    def risk_off(self) -> bool:
        """True if macro backdrop is risk-off."""
        return self.vix > 25 or self.dxy_change_pct > 0.3

    @property
    def btc_macro_score(self) -> float:
        """
        BTC macro score ∈ [0, 1].
        0 = strongly bearish macro for BTC
        1 = strongly bullish macro for BTC
        """
        score = 0.5
        # DXY: up = bearish for BTC
        if self.dxy_change_pct > 0.5:
            score -= 0.15
        elif self.dxy_change_pct < -0.5:
            score += 0.15
        # VIX: high = risk-off
        if self.vix > 30:
            score -= 0.15
        elif self.vix < 15:
            score += 0.10
        # S&P: up = risk-on
        if self.sp500_change_pct > 0.5:
            score += 0.10
        elif self.sp500_change_pct < -0.5:
            score -= 0.10
        return max(0.0, min(1.0, score))


@dataclass
class SentimentState:
    """Sentiment state at analysis time."""
    fear_greed_index: int = 50
    fear_greed_trend: str = "NEUTRAL"   # RISING / FALLING / NEUTRAL
    fear_greed_zone: str = "NEUTRAL"    # EXTREME_FEAR / FEAR / NEUTRAL / GREED / EXTREME_GREED
    btc_dominance: float = 50.0
    btc_dominance_change_pct: float = 0.0
    social_hype_score: float = 0.5
    fetched_at: Optional[datetime] = None
    stale: bool = True

    @property
    def fear_greed_score(self) -> float:
        """Fear & Greed normalized to [0, 1]."""
        return self.fear_greed_index / 100.0


@dataclass
class SmartMoneyState:
    """Smart money indicators at analysis time."""
    funding_rate_pct: float = 0.0
    funding_rate_direction: str = "NEUTRAL"  # BULLISH / NEUTRAL / BEARISH
    open_interest_btc: float = 0.0
    oi_trend: str = "STABLE"   # RISING / FALLING / STABLE
    long_short_ratio: float = 1.0
    long_account_ratio: float = 0.5
    perp_premium_pct: float = 0.0
    whale_inflow_rank: int = 50
    fetched_at: Optional[datetime] = None
    stale: bool = True

    @property
    def smart_money_score(self) -> float:
        """Smart money conviction ∈ [0, 1]. 0.5 = neutral."""
        score = 0.5
        # Funding: negative = shorts paying bulls → bullish signal
        if self.funding_rate_pct < -0.05:
            score += 0.15
        elif self.funding_rate_pct > 0.10:
            score -= 0.15
        # Long/short ratio: >60% longs = crowded = reversal risk
        if self.long_account_ratio > 0.65:
            score -= 0.10
        elif self.long_account_ratio < 0.35:
            score += 0.10
        # OI rising + price rising = confirmed trend
        if self.oi_trend == "RISING":
            score += 0.05
        return max(0.0, min(1.0, score))


@dataclass
class MarketState:
    """
    Complete market state at a single analysis moment.
    Produced by MarketStateAssembler. Consumed by PreFilter and Reasoning Engine.
    """
    # Identity
    analysis_id: str = ""
    analysis_time: Optional[datetime] = None

    # Price
    current_price: float = 0.0
    current_price_spot: float = 0.0
    current_price_perp: float = 0.0
    perp_premium_bps: float = 0.0

    # C1 (primary analysis candle)
    c1: Optional[Candle] = None
    c2_open: float = 0.0   # C2 open (already known when C1 closes)

    # History
    candles: list[Candle] = field(default_factory=list)
    candle_count: int = 0

    # Technical
    technical: Optional[TechnicalState] = None

    # Orderflow
    vpin: float = 0.5
    cvd: float = 0.0
    tcr: float = 0.0
    ofi: float = 0.0
    obi: float = 0.0

    # Orderbook
    order_book: Optional[OrderBook] = None
    spread_bps: float = 0.0

    # Macro
    macro: Optional[MacroState] = None

    # Sentiment
    sentiment: Optional[SentimentState] = None

    # Smart money
    smart_money: Optional[SmartMoneyState] = None

    # Data freshness
    data_age_seconds: float = 999.0
    stale_data: bool = True

    # ── Derived signal scores (set by MarketStateAssembler) ──────────────

    @property
    def c1_is_green(self) -> bool:
        return bool(self.c1 and self.c1.is_green)

    @property
    def rvol(self) -> float:
        return float(self.technical.rvol if self.technical else 1.0)

    @property
    def c1_body_pct(self) -> float:
        return float(self.c1.body_pct if self.c1 else 0.0)

    @property
    def adx(self) -> float:
        return float(self.technical.adx if self.technical else 25.0)

    @property
    def is_trending(self) -> bool:
        return self.adx >= 15.0

    @property
    def funding_rate_pct(self) -> float:
        return float(self.smart_money.funding_rate_pct if self.smart_money else 0.0)


class MarketStateAssembler:
    """
    Assembles a full MarketState by fetching all sources in parallel.
    Target: complete packet in < 30 seconds.
    """

    def __init__(self, binance: BinanceClient):
        self.binance = binance
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()

    async def assemble(self, analysis_id: str) -> MarketState:
        """
        Fetch all data sources in parallel, produce enriched MarketState.
        """
        t0 = asyncio.get_event_loop().time()

        # Parallel fetch from all sources
        (
            candles,
            order_book,
            ticker,
            funding,
            oi,
            ls_ratio,
            macro,
            sentiment,
            smart_money,
        ) = await asyncio.gather(
            self.binance.fetch_klines(limit=KLINE_LIMIT),
            self.binance.fetch_order_book(limit=20),
            self.binance.fetch_ticker_24h(),
            self.binance.fetch_funding_rate(),
            self.binance.fetch_open_interest(),
            self.binance.fetch_long_short_ratio(),
            self._fetch_macro(),
            self._fetch_sentiment(),
            self._build_smart_money(funding, oi, ls_ratio),
            return_exceptions=True,
        )

        # Handle partial failures
        candles = self._unwrap(candles, [])
        order_book = self._unwrap(order_book, None)
        ticker = self._unwrap(ticker, None)
        funding = self._unwrap(funding, None)
        oi_data = self._unwrap(oi, None)
        ls_ratio = self._unwrap(ls_ratio, None)
        macro = self._unwrap(macro, MacroState())
        sentiment = self._unwrap(sentiment, SentimentState())
        smart_money = self._unwrap(smart_money, SmartMoneyState())

        # Compute technical indicators
        technical = None
        if len(candles) >= 10:
            technical = compute_indicators(candles)

        # Orderflow from BinanceClient
        vpin = self.binance.vpin()
        cvd = self.binance.cvd()
        tcr = self.binance.trade_count_ratio()
        ofi = self.binance.ofi()
        obi_val = order_book.obi_5_levels if order_book else 0.0
        spread_bps = order_book.spread_bps if order_book else 0.0

        c1 = candles[-1] if candles else None
        c2_open = c1.close if c1 else 0.0  # C2 open = C1 close (15m gap)

        current_price = float(ticker.last_price) if ticker else (float(c1.close) if c1 else 0.0)
        perp_premium_bps = ((current_price - float(c1.close)) / current_price * 10000) if c1 else 0.0

        elapsed = asyncio.get_event_loop().time() - t0
        log.info(f"MarketState assembled in {elapsed:.1f}s — candles={len(candles)}, VPIN={vpin:.3f}, CVD={cvd:.2f}")

        return MarketState(
            analysis_id=analysis_id,
            analysis_time=datetime.now(timezone.utc),
            current_price=current_price,
            current_price_spot=current_price,
            current_price_perp=current_price,
            perp_premium_bps=perp_premium_bps,
            c1=c1,
            c2_open=c2_open,
            candles=candles,
            candle_count=len(candles),
            technical=technical,
            vpin=vpin,
            cvd=cvd,
            tcr=tcr,
            ofi=ofi,
            obi=obi_val,
            order_book=order_book,
            spread_bps=spread_bps,
            macro=macro,
            sentiment=sentiment,
            smart_money=smart_money,
            data_age_seconds=elapsed,
            stale_data=elapsed > 60.0,
        )

    async def _fetch_macro(self) -> MacroState:
        """Fetch macro data from Yahoo Finance via yfinance-like endpoint."""
        state = MacroState()
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            tickers = {
                "DXY": "DX-Y.NYB",
                "SP500": "^GSPC",
                "VIX": "^VIX",
                "US10Y": "^TNX",
            }
            # Use Yahoo Finance public chart API
            async with self._session.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB",
                params={"interval": "1d", "range": "2d"},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.ok:
                    data = await resp.json()
                    meta = data.get("chart", {}).get("result", [{}])[0]
                    quotes = meta.get("indicators", {}).get("quote", [{}])[0]
                    closes = quotes.get("close", [])
                    if len(closes) >= 2 and closes[-1] and closes[-2]:
                        state.dxy = closes[-1]
                        chg = (closes[-1] - closes[-2]) / closes[-2] * 100
                        state.dxy_change_pct = chg
            state.fetched_at = datetime.now(timezone.utc)
            state.stale = False
        except Exception as e:
            log.warning(f"Macro fetch failed: {e}")
        return state

    async def _fetch_sentiment(self) -> SentimentState:
        """Fetch Fear & Greed Index and CoinGecko social data."""
        state = SentimentState()
        try:
            async with self._session.get(
                FEAR_GREED_API,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.ok:
                    data = await resp.json()
                    fg_data = data.get("data", [])
                    if fg_data:
                        state.fear_greed_index = int(fg_data[0].get("value", 50))
            state.fetched_at = datetime.now(timezone.utc)
            state.stale = False
        except Exception as e:
            log.warning(f"Fear & Greed fetch failed: {e}")

        # Fear & Greed zone
        if state.fear_greed_index <= 25:
            state.fear_greed_zone = "EXTREME_FEAR"
        elif state.fear_greed_index <= 45:
            state.fear_greed_zone = "FEAR"
        elif state.fear_greed_index <= 55:
            state.fear_greed_zone = "NEUTRAL"
        elif state.fear_greed_index <= 75:
            state.fear_greed_zone = "GREED"
        else:
            state.fear_greed_zone = "EXTREME_GREED"
        state.fear_greed_trend = "NEUTRAL"

        return state

    async def _build_smart_money(
        self,
        funding: Optional[FundingRate],
        oi: Optional[OpenInterest],
        ls_ratio: Optional[LongShortRatio],
    ) -> SmartMoneyState:
        state = SmartMoneyState()
        if funding:
            state.funding_rate_pct = funding.rate_pct
            if funding.rate_pct > 0.03:
                state.funding_rate_direction = "BEARISH"
            elif funding.rate_pct < -0.03:
                state.funding_rate_direction = "BULLISH"
            else:
                state.funding_rate_direction = "NEUTRAL"
        if ls_ratio:
            state.long_short_ratio = ls_ratio.long_short_ratio
            state.long_account_ratio = ls_ratio.long_account_ratio
        if oi:
            state.open_interest_btc = oi.open_interest_btc
        state.fetched_at = datetime.now(timezone.utc)
        state.stale = False
        return state

    @staticmethod
    def _unwrap(value, default):
        if isinstance(value, Exception):
            return default
        return value
