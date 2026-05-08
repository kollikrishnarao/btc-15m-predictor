# BTC-15m Direction Predictor — Institutional Grade Architecture

**Version:** 2.0 | **Date:** 2026-05-07
**Status:** Pre-implementation | **Strategy:** Fixed — no changes

---

## 1. Strategy (Fixed, Never Changes)

Every 15 minutes (on Binance candle close):

> **Will ≥2 of the next 3 candles (C2, C3, C4) close GREEN or RED?**

- **GREEN** = candle close > candle open
- **RED** = candle close < candle open
- **Session** = up to 3 bets, win on any 1
- **Enter** only when confidence ≥ 0.55 (0.55–0.69 requires ≥2 signal categories strongly agree)
- **No concurrent sessions**

This is the single source of truth. Nothing overrides this strategy.

---

## 2. Signal Architecture — Multi-Agent Reasoning

```
┌─────────────────────────────────────────────────────────────┐
│  DATA INGESTION LAYER                                       │
│                                                              │
│  Binance WS     → 15m candles, depth, aggTrades, bookTicker │
│  Binance REST   → funding, OI, long/short, klines           │
│  Coinbase WS    → cross-confirmation price feed              │
│  Fear&Greed API → Fear & Greed Index + trend                │
│  CoinGecko API  → BTC dominance, social stats                │
│  Yahoo Finance  → DXY, SP500, VIX, US10Y (15min cache)     │
│  Binance Web3   → Smart Money inflow rank                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ parallel fetch, <60s assembly
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  FEATURE ENGINEERING LAYER                                  │
│                                                              │
│  CANDLESTICK PATTERNS     → Pattern, body%, wick ratios      │
│  VOLUME & ORDERFLOW       → RVOL, VPIN, CVD, OBI, TCR       │
│  TECHNICAL INDICATORS     → RSI, MACD, VWAP, BB, ATR,       │
│                            Supertrend, ADX, EMA, KDJ, Pivots │
│  MARKET MICROSTRUCTURE    → Spread, trade imbalance, OFI     │
│  SMART MONEY             → Funding, OI, long/short ratio,     │
│                            whale signals, perp premium        │
│  SENTIMENT               → Fear&Greed, narratives, hype      │
│  MACRO                   → DXY, SP500, VIX, US10Y            │
│  STRUCTURE               → Higher highs/lows, breaks, sweeps   │
└──────────────────────────┬──────────────────────────────────┘
                           │ enriched feature packet
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PRE-FILTER AGENT          [Rule-based, deterministic]       │
│                                                              │
│  Hard rules — any trigger → immediate SKIP, no LLM call:    │
│                                                              │
│  1. TREND_FILTER: Signal opposing 15m trend → SKIP          │
│     Exception: BTC moved >0.10% against trend               │
│  2. CONSECUTIVE_LOSS: 3 losses → require edge >0.05         │
│  3. NOISE: C1 body <0.1% (doji) → SKIP                    │
│  4. LOW_VOLUME: C1 vol < 0.7x 20-candle avg → SKIP        │
│  5. VPIN_TOXICITY: VPIN > 0.75 → SKIP (extreme uncertainty)│
│  6. ADX_CHOP: ADX < 15 → SKIP (no trend, unpredictable)   │
│  7. EXTREME_FUNDING: funding > 0.15% → SKIP (cascade risk) │
│  8. DOJI_EXHAUSTION: Long wick + small body + high VPIN     │
└──────────────────────────┬──────────────────────────────────┘
                           │ passed pre-filter
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ADVISOR AGENT             [Claude Opus 4.7 — max reasoning] │
│                                                              │
│  Role: Independent deep analysis, cross-checks main engine   │
│  Input: Full feature packet + reflection context             │
│  Output: Advisory call (GREEN/RED/SKIP) + confidence +      │
│          key signals + risk flags + disagreement with main   │
│  Triggered: Every analysis cycle (parallel with main engine) │
│  Max thinking: Enabled                                       │
│                                                              │
│  Produces a separate structured advisory opinion that         │
│  the reasoning engine must reconcile with its own view.       │
└──────────────────────────┬──────────────────────────────────┘
                           │ advisory opinion
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  MAIN REASONING ENGINE      [Me — claude-sonnet-4-6]        │
│                                                              │
│  Role: Final decision authority                              │
│  Input: Feature packet + pre-filter result + advisor opinion │
│         + reflection context                                 │
│  Output: GREEN/RED/SKIP + confidence + 6-dimension scores   │
│          + rationale + risk_factors + conflicts              │
│                                                              │
│  7-Step Analysis:                                            │
│    Step 1: CANDLESTICK & PRICE ACTION                       │
│    Step 2: MOMENTUM (RSI, MACD, EMA cross, price velocity) │
│    Step 3: TREND (Supertrend, ADX, BB position, structure)  │
│    Step 4: ORDERFLOW (CVD, VPIN, OBI, TCR, OFI)           │
│    Step 5: SMART MONEY (funding, OI, whales, perp premium) │
│    Step 6: SENTIMENT (Fear&Greed zone + trend, narratives)│
│    Step 7: MACRO (DXY, SP500, VIX, regime context)        │
│                                                              │
│  Reconciliation: If advisor and engine disagree,              │
│  weight toward the more conservative call unless             │
│  engine has >0.15 higher confidence.                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ final structured decision
          ENTER ───────────┤──────────── SKIP
               │           │               │
               ▼           ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│  SESSION MANAGER                                            │
│  • 3-bet martingale (C2, C3, C4)                         │
│  • Win on any 1 → session profit                          │
│  • State persists to JSON, survives restarts               │
│  • On C2 loss: RECHECK signal — if same direction but      │
│    strong counter-evidence emerged → consider FLIP direction │
│                                                              │
│  DYNAMIC DIRECTION FLIP (on C2/C3 loss):                   │
│  If same direction bet loses AND:                          │
│    - Counter-direction signal has strengthened significantly │
│    - VPIN shows institutional reversal pattern              │
│    - Advisor recommends flip with ≥0.65 confidence         │
│  → Flip to opposite direction for remaining bets           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  POLYMARKET EXECUTOR                                        │
│                                                              │
│  Market Discovery: Gamma API → find active BTC 15m market   │
│  Position Sizing: Fractional Kelly (cap 25% of bankroll)   │
│    f* = 0.5 × (edge / odds) where edge = conf - price     │
│  Execution: CLOB API → place taker order on YES/NO token   │
│  Resolution: Track market expiry, auto-redeem winnings     │
│                                                              │
│  PIPELINE:                                                  │
│    1. Discover active market (Gamma)                       │
│    2. Check orderbook spread (reject if >5¢)               │
│    3. Compute Kelly size                                   │
│    4. Sign + place order (CLOB)                            │
│    5. Track fill + confirm bet ID                          │
│    6. Monitor resolution                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  FEEDBACK LOOP                                              │
│                                                              │
│  After every session resolves (WIN or LOSS):                │
│    1. Log outcome to CSV                                   │
│    2. Update rolling win rate                              │
│    3. Update reflection context (last 20 outcomes)         │
│    4. If 3 consecutive losses → activate circuit breaker   │
│    5. If win rate drops below 45% → pause for human review │
│    6. Inject outcomes into next analysis prompt             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  TELEGRAM ALERTS                                            │
│                                                              │
│  Session started  → Direction, confidence, rationale (brief)│
│  Bet placed       → Candle#, price, size, market URL        │
│  C2/C3 resolved   → Result so far, bets remaining          │
│  Session WIN      → Full P&L, which candle won             │
│  Session LOSS     → Loss amount, reason                     │
│  Circuit breaker  → 3 consecutive losses warning             │
│  /stats          → Win rate, last 20, running P&L          │
│  /session        → Current position, candles remaining      │
│  /export         → CSV file sent to chat                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Feature Engineering — Full Signal Space

### Tier 1: Candlestick & Price Action (C1-C5)

| Feature | Calculation | Signal |
|---|---|---|
| C1 body size % | `abs(close - open) / close × 100` | Conviction |
| C1 close position | `(close - low) / (high - low)` | Who controlled candle |
| C1 upper wick % | `(high - max(open,close)) / range × 100` | Rejection strength |
| C1 lower wick % | `(min(open,close) - low) / range × 100` | Support absorption |
| Body/wick ratio | `body / max(wick, tiny)` | Continuation vs reversal |
| RVOL (C1) | `C1_vol / avg(last_20_vol)` | Move conviction |
| C1 pattern | Pattern name from library | Directional bias |
| C1-C5 momentum | Slope of close over last 5 candles | Short-term direction |
| Price vs VWAP | `price - VWAP` | Value area |
| EMA alignment | EMA7 > EMA25 > EMA99 | Bull/bear structure |
| BB position %B | `(price - BB_lower) / (BB_upper - BB_lower)` | Statistical edge |
| Volume profile | Volume distribution within C1 candle | Informed vs noise |

### Tier 2: Orderflow & Microstructure

| Feature | Calculation | Signal |
|---|---|---|
| **VPIN** | Volume buckets (50), `∑|V_buy - V_sell| / V_total` rolling | Institutional activity → directional move |
| **CVD** | Cumulative `(buy_qty - sell_qty)` over rolling window | Buy/sell pressure accumulation |
| **CVD divergence** | CVD slope vs price slope over same window | Momentum exhaustion |
| **OBI** | `(bid_vol - ask_vol) / (bid_vol + ask_vol)` at L=5 | Order book pressure |
| **TCR** | `(buy_trades - sell_trades) / total_trades` | Aggressor imbalance |
| **OFI** | Tick-level `Δbid_size - Δask_size` weighted | Order flow direction |
| Bid/ask spread bps | `(ask - bid) / mid × 10000` | Liquidity / spread cost |
| Trade size distribution | Mean, median, percentile-95 of trade sizes | Whale vs retail activity |
| Liquidation imbalance | Long liq - short liq over last 6h | Smart money positioning |
| Book pressure gradient | How OBI changes over last 5 depth snapshots | Momentum of orderflow |

### Tier 3: Technical Indicators

| Feature | Config | Signal |
|---|---|---|
| RSI-14 | 14-period on 15m | Overbought/oversold + divergence |
| RSI-4 | 4-period on 15m | Fast momentum |
| MACD | 12/26/9 on 15m | Trend + momentum shift |
| MACD histogram slope | Change in histogram per candle | Momentum acceleration |
| VWAP | Anchored at session start | Value area |
| Bollinger Bands | 20/2 on 15m | Squeeze → breakout, %B position |
| ATR-14 | 14-period on 15m | Volatility, normalize moves |
| Supertrend | 10/3 on 15m | Trend direction |
| ADX | 14-period on 15m | Trend strength (>25 = trending) |
| EMA 7/25/99 cross | On 15m | Trend alignment |
| KDJ | On 15m | Mean reversion signals |
| Pivot R1/S1/R2/S2 | From previous candle high/low/close | Support/resistance zones |
| Ichimoku cloud | Tenkan/Kijun/Span on 15m | Trend + sideways zones |

### Tier 4: Smart Money

| Feature | Source | Signal |
|---|---|---|
| Funding rate | Binance futures | Negative = shorts paying → contrarian bullish |
| Open interest | Binance futures | OI rising + price rising = confirmed; OI spike + divergence = top |
| Long/short ratio | Top traders Binance | >70% long = crowded = reversal risk |
| Perp premium | `perp_price - spot_price` annualized | Contango/backwardation |
| Liquidation clusters | CoinGlass/Sharpe API | Magnetic price levels |
| Whale signals | Binance Web3 API | Smart money inflow rank |
| Top trader bias | Binance top traders | Institutional positioning |

### Tier 5: Sentiment

| Feature | Source | Signal |
|---|---|---|
| Fear & Greed Index | alternative.me | <25 Extreme Fear = buy zone; >75 Extreme Greed = sell zone |
| Fear & Greed trend | Last 3 readings | Rising/Falling/Stable |
| BTC dominance | CoinGecko | Rising = BTC alt rotation; Falling = alt season |
| Social hype | Reddit subs, Twitter activity (CoinGecko) | Narrative momentum |
| News sentiment | CryptoPanic (optional) | Event-driven bias |

### Tier 6: Macro

| Feature | Source | Signal |
|---|---|---|
| DXY (Dollar Index) | Yahoo Finance | DXY up = BTC headwind; DXY down = BTC tailwind |
| S&P 500 | Yahoo Finance | Risk-on/risk-off correlation |
| VIX | Yahoo Finance | VIX > 20 = elevated risk-off |
| US 10Y Yield | Yahoo Finance | Risk appetite, dollar strength |

### Tier 7: Market Structure

| Feature | Calculation | Signal |
|---|---|---|
| Higher high / higher low | Sequential high/low comparison | Uptrend confirmation |
| Break of structure (BOS) | Close above/below key level on rising/falling volume | Momentum continuation |
| Liquidity sweeps | High/low exceeds recent range then reverses | Stop hunt detection |
| Fair value gaps | Gaps in price action | Unfilled zones = future targets |
| Volume profile POC | Point of control from volume histogram | Value area anchor |

---

## 4. Dynamic Direction Flip

**Key innovation over original strategy:** Allow flipping direction on C2/C3 loss.

Original strategy: Lock direction at C1 close, bet same direction on C2, C3, C4 regardless of what happens.

**Enhanced:** After a C2 or C3 loss, if I detect the market has genuinely reversed and my confidence in the original direction has collapsed, I can flip — but only under strict conditions:

```
IF Bet C2 or C3 resolves AGAINST locked direction:
  AND (advisor recommends flip OR counter_signal_strength > original_signal_strength + 0.15)
  AND VPIN shows institutional reversal pattern
  AND new direction passes pre-filter
  AND remaining bets ≥ 1
THEN:
  FLIP direction for remaining bets
  Log flip reason explicitly
  Alert on Telegram with flip rationale
```

This is NOT martingale doubling — it's a **directional correction** based on new market evidence. The flip is conservative, requires consensus from multiple signals, and is logged for post-hoc analysis.

---

## 5. Reflection Context (Injected Every Analysis)

```python
reflection_context = {
    "last_20_outcomes": [("GREEN", True), ("RED", False), ...],  # direction + won
    "rolling_win_rate_20": 0.65,
    "consecutive_losses": 2,
    "consecutive_wins": 0,
    "last_flip": {"candle": "C3", "from": "GREEN", "to": "RED", "reason": "..."},
    "regime": "TRENDING_UP" | "TRENDING_DOWN" | "RANGING" | "VOLATILE",
    "avg_session_length": 1.8,  # candles until win (efficiency)
    "strongest_signal_category": "orderflow",
    "weakest_signal_category": "macro",
}
```

---

## 6. Confidence Scoring (Weighted, Not Average)

```
weighted_confidence = (
    momentum_score     × 0.25 +
    trend_score       × 0.20 +
    orderflow_score   × 0.20 +
    smart_money_score × 0.15 +
    sentiment_score   × 0.10 +
    macro_score       × 0.10
)
```

Each dimension scores 0.0–1.0:
- 0.0 = strongly bearish
- 0.5 = neutral
- 1.0 = strongly bullish

---

## 7. Entry Thresholds

| Weighted Confidence | Bucket | Action |
|---|---|---|
| ≥ 0.70 | HIGH | Enter session immediately |
| 0.55–0.69 | MEDIUM | Enter only if ≥2 sub-scores are extreme (≤0.3 or ≥0.7) |
| < 0.55 | LOW | SKIP |

---

## 8. Polymarket Integration

- **Market discovery:** Gamma API → active BTC 15m markets
- **Order book:** CLOB API → verify spread ≤ 5¢ before placing
- **Position sizing:** Fractional Kelly (half-Kelly, cap at 25% bankroll)
- **Edge calculation:** `edge = predicted_probability - market_price`
- **Bet placement:** Taker order on YES token (GREEN) or NO token (RED)
- **Resolution tracking:** Monitor market close, auto-redeem winning positions

---

## 9. Metrics & Evaluation

- **Primary:** Directional win rate (not RMSE or price accuracy)
- **Session win rate:** % of sessions won (≥2/3 candles correct)
- **Per-candle accuracy:** % of individual C2/C3/C4 directions correct
- **Confidence calibration:** Did high-confidence calls win more than low-confidence?
- **Signal attribution:** Which feature category predicted best?
- **Flip analysis:** Did flips improve or hurt outcomes?
- **Regime breakdown:** Win rate by market regime

---

## 10. Non-Functional Requirements

- All data < 60 seconds old at analysis time
- OHLCV from WS < 15 seconds old
- Order book < 5 seconds old
- Session state persisted to JSON (survives restart)
- CSV append-only (outcomes back-filled)
- Telegram alerts at every session lifecycle event
- Paper trading first, live trading only after ≥53% win rate over 100 sessions
