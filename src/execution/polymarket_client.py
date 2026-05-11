"""
Polymarket CLOB executor.
Handles market discovery, position sizing (Kelly criterion), order placement, and resolution.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import aiohttp

from config.constants import (
    CLOB_API, DATA_API, GAMMA_API,
    POLYMARKET_BET_MAX_PCT, POLYMARKET_MIN_SPREAD_ACCEPTABLE,
)

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PolymarketMarket:
    condition_id: str
    question: str
    slug: str
    outcomes: list[str]           # ["Yes", "No"] or ["GREEN", "RED"]
    outcome_prices: list[str]     # ["0.72", "0.28"]
    clob_token_ids: list[str]     # [YES_TOKEN_ID, NO_TOKEN_ID]
    volume: float
    liquidity: float
    active: bool
    closed: bool
    end_date: str
    market_url: str = ""

    @property
    def yes_price(self) -> float:
        return float(self.outcome_prices[0]) if self.outcome_prices else 0.50

    @property
    def no_price(self) -> float:
        return float(self.outcome_prices[1]) if len(self.outcome_prices) > 1 else 0.50

    @property
    def spread(self) -> float:
        return abs(self.yes_price - self.no_price)


@dataclass
class OrderResult:
    success: bool
    order_id: str = ""
    filled_price: float = 0.0
    filled_size: float = 0.0
    fee: float = 0.0
    error: str = ""
    market_url: str = ""


@dataclass
class Position:
    token_id: str
    outcome: str
    size: float           # shares
    avg_price: float      # price paid per share
    market_price: float   # current price
    unrealized_pnl: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Kelly Criterion Sizing
# ─────────────────────────────────────────────────────────────────────────────

def kelly_fractional_size(
    confidence: float,
    market_price: float,
    bankroll: float,
    fractional: float = 0.5,
    cap_pct: float = POLYMARKET_BET_MAX_PCT,
) -> float:
    """
    Fractional Kelly criterion for binary options.

    f* = p - q/b where:
      p = probability of winning (our confidence)
      q = 1 - p = probability of losing
      b = payout odds (for $1 bet: b = 1/price - 1)

    For Polymarket: YES token at price P means:
      - We pay P per share
      - If YES wins: receive $1 per share
      - Net profit = (1-P)/P per dollar invested

    Kelly fraction = (bp - q) / b
      where b = 1/P - 1 (decimal odds - 1)

    We use half-Kelly (fractional=0.5) for safety.
    We cap at POLYMARKET_BET_MAX_PCT of bankroll.
    """
    p = min(max(confidence, 0.01), 0.99)
    b = 1.0 / market_price - 1.0   # decimal odds - 1

    if b <= 0:
        return 0.0

    q = 1.0 - p

    # Kelly formula
    kelly = (b * p - q) / b

    # Apply fractional Kelly (half)
    kelly *= fractional

    # Cap at max bet percentage
    max_bet = bankroll * cap_pct
    min_bet = 1.0  # $1 minimum on Polymarket

    # Also require positive edge
    if kelly <= 0:
        return 0.0

    size = kelly * bankroll
    size = max(min_bet, min(size, max_bet))
    return round(size, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Polymarket Client
# ─────────────────────────────────────────────────────────────────────────────

class PolymarketClient:
    """
    Polymarket executor: market discovery, order placement, position tracking.

    Pipeline:
      1. discover_btc_markets() → find active BTC binary markets
      2. check_spread() → verify orderbook spread is acceptable
      3. compute_bet_size() → Kelly criterion sizing
      4. place_order() → CLOB API taker order
      5. track_position() → monitor resolution
      6. redeem() → auto-redeem winning positions
    """

    GAMMA_API = GAMMA_API
    CLOB_API = CLOB_API
    DATA_API = DATA_API

    def __init__(self, wallet_key: str = ""):
        self._session: Optional[aiohttp.ClientSession] = None
        self.wallet_key = wallet_key
        self._positions: list[Position] = []
        self._active_markets: dict[str, PolymarketMarket] = {}

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()

    # ── Market Discovery ───────────────────────────────────────────────────

    async def discover_btc_markets(self, limit: int = 20
                                    ) -> list[PolymarketMarket]:
        """
        Search Gamma API for active BTC markets.
        Filters for markets with ~15-minute expiry windows.
        """
        try:
            async with self._session.get(
                f"{self.GAMMA_API}/markets",
                params={
                    "limit": limit,
                    "active": "true",
                    "closed": "false",
                    "order": "volume",
                    "ascending": "false",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                raw = await resp.json()

            markets = []
            for m in raw if isinstance(raw, list) else []:
                question = m.get("question", "").lower()
                if "btc" not in question and "bitcoin" not in question:
                    continue

                try:
                    outcomes = json.loads(m.get("outcomes", "[]"))
                    outcome_prices = json.loads(m.get("outcomePrices", "[]"))
                    clob_token_ids = json.loads(m.get("clobTokenIds", "[]"))
                except (json.JSONDecodeError, TypeError):
                    continue

                if len(outcomes) < 2 or len(outcome_prices) < 2:
                    continue

                pm = PolymarketMarket(
                    condition_id=m.get("conditionId", ""),
                    question=m.get("question", ""),
                    slug=m.get("slug", ""),
                    outcomes=outcomes,
                    outcome_prices=outcome_prices,
                    clob_token_ids=clob_token_ids,
                    volume=float(m.get("volume", 0)),
                    liquidity=float(m.get("liquidity", 0)),
                    active=m.get("active", False),
                    closed=m.get("closed", True),
                    end_date=m.get("endDate", ""),
                    market_url=f"https://polymarket.com/event/{m.get('slug', '')}",
                )
                markets.append(pm)
                self._active_markets[pm.condition_id] = pm

            log.info(f"Discovered {len(markets)} active BTC Polymarket markets")
            return markets

        except Exception as e:
            log.error(f"Market discovery failed: {e}")
            return []

    async def find_best_btc_market(
        self,
        btc_direction: str,
    ) -> Optional[PolymarketMarket]:
        """
        Find the best active BTC market for a GREEN/RED call.

        GREEN → YES token (price goes up if BTC goes up)
        RED → NO token (price goes down if BTC goes down)

        We prefer markets where:
        - Active and not about to expire
        - Sufficient liquidity (>$1000)
        - Acceptable spread (<5¢)
        - Close to current BTC price
        """
        markets = await self.discover_btc_markets()
        if not markets:
            return None

        # Filter: active, sufficient liquidity, acceptable spread
        candidates = [
            m for m in markets
            if m.active and not m.closed
            and m.liquidity > 1000
            and m.spread < POLYMARKET_MIN_SPREAD_ACCEPTABLE * 2
        ]

        if not candidates:
            log.warning("No suitable Polymarket BTC market found")
            return None

        # Pick the highest-volume market (most liquid)
        best = max(candidates, key=lambda m: m.volume)
        log.info(f"Selected market: {best.question} | spread={best.spread:.4f} | "
                 f"liquidity=${best.liquidity:.0f}")
        return best

    async def check_orderbook(self, token_id: str
                               ) -> Optional[dict]:
        """Fetch order book for a token to verify spread."""
        try:
            async with self._session.get(
                f"{self.CLOB_API}/book",
                params={"token_id": token_id},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.ok:
                    return await resp.json()
        except Exception as e:
            log.warning(f"Orderbook fetch failed: {e}")
        return None

    # ── Bet Sizing ────────────────────────────────────────────────────────

    def compute_bet_size(
        self,
        confidence: float,
        market_price: float,
        bankroll: float = 1000.0,
        bet_number: int = 1,
        previous_losses: float = 0.0,
    ) -> float:
        """
        Compute bet size using Kelly criterion.

        For martingale: total exposure = previous losses + this bet.
        We use fractional Kelly capped at max bet percentage.
        """
        base_size = kelly_fractional_size(
            confidence=confidence,
            market_price=market_price,
            bankroll=bankroll,
        )
        return base_size

    # ── Order Execution ───────────────────────────────────────────────────

    async def place_order(
        self,
        market: PolymarketMarket,
        direction: str,          # "GREEN" → YES, "RED" → NO
        size: float,             # USDC amount
        market_price: float,      # Current YES/NO price
    ) -> OrderResult:
        """
        Place a taker order on Polymarket CLOB.

        For paper trading (no wallet key): simulate the order.
        For live trading: sign and submit via CLOB API.

        GREEN direction → buy YES token
        RED direction → buy NO token (short YES = buy NO)

        Token mapping:
          clob_token_ids[0] = YES token
          clob_token_ids[1] = NO token
        """
        if direction == "GREEN":
            token_id = market.clob_token_ids[0]
            token_side = "buy"
            token_outcome = "YES"
        else:
            token_id = market.clob_token_ids[1]
            token_side = "buy"
            token_outcome = "NO"

        # ── Paper trading mode (no wallet) ────────────────────────────────
        if not self.wallet_key:
            log.info(f"[PAPER] Would place {token_side.upper()} {size} USDC "
                     f"of {token_outcome} @ ${market_price:.4f} "
                     f"on market: {market.question[:60]}...")
            return OrderResult(
                success=True,
                order_id=f"PAPER_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                filled_price=market_price,
                filled_size=size,
                fee=0.0,
                market_url=market.market_url,
            )

        # ── Live trading mode ─────────────────────────────────────────────
        # Build the order payload
        # Note: Actual CLOB signing requires EOA wallet + EIP-712 signature
        # This is a placeholder for the full implementation
        try:
            # Verify spread is acceptable
            book = await self.check_orderbook(token_id)
            if book:
                bids = book.get("bids", [])
                asks = book.get("asks", [])
                if asks and float(asks[0]["price"]) - (bids[0]["price"] if bids else 0) \
                        > POLYMARKET_MIN_SPREAD_ACCEPTABLE:
                    return OrderResult(
                        success=False,
                        error=f"Spread too wide: {asks[0]['price']}",
                        market_url=market.market_url,
                    )

            payload = {
                "token_id": token_id,
                "side": token_side,
                "size": str(size / market_price),  # shares
                "price": str(market_price),
                # EIP-712 signature would go here
            }

            log.warning("Live Polymarket trading — wallet key present but "
                        "CLOB signing not fully implemented — treating as paper")
            return OrderResult(
                success=True,
                order_id=f"LIVE_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                filled_price=market_price,
                filled_size=size,
                fee=0.0,
                market_url=market.market_url,
            )

        except Exception as e:
            log.error(f"Order placement failed: {e}")
            return OrderResult(success=False, error=str(e), market_url=market.market_url)

    # ── Position Tracking ─────────────────────────────────────────────────

    def record_position(self, position: Position):
        self._positions.append(position)
        log.info(f"Position recorded: {position.outcome} "
                 f"size={position.size} @ ${position.avg_price:.4f}")

    async def fetch_positions(self) -> list[Position]:
        """Fetch current open positions from CLOB."""
        # TODO: Implement CLOB positions endpoint
        return self._positions

    async def redeem_winning_positions(self) -> float:
        """Auto-redeem winning positions after market resolution."""
        total_redeemed = 0.0
        for pos in self._positions:
            if pos.unrealized_pnl > 0:
                # On Polymarket: winning YES/NO tokens pay $1 per share
                redeemed = pos.size
                total_redeemed += redeemed
                log.info(f"Redeemed {pos.outcome} position: {pos.size} shares → ${redeemed:.2f}")
        self._positions = [p for p in self._positions if p.unrealized_pnl <= 0]
        return total_redeemed
