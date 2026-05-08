# BTC-15m Multi-Agent Direction Predictor — Institutional Architecture

**Version:** 3.0 | **Date:** 2026-05-08
**Status:** Research-grade design | **Strategy:** Fixed — no changes
**Confidence:** Conviction-based (no hard thresholds) | **Bankroll:** $20

---

## REVISION LOG

| Version | Changes |
|---|---|
| 1.0 | Initial research design |
| 2.0 | Added position sizing, Telegram, session manager |
| 3.0 | Fixed bet progression ($1→$2→$4), $20 bankroll, conviction scoring, PhD-level formulas, pre-C1 analysis, comprehensive feature engineering |

---

## 1. Executive Summary

Every 15 minutes, a BTC/USDT candle closes on Binance. The question: *Will ≥2 of the next 3 candles (C2, C3, C4) close GREEN (close > open) or RED (close < open)?*

We answer via **multi-agent LLM reasoning** on Hermes Agent, running Claude Opus 4.7 as the primary brain. We bet on Polymarket BTC binary markets using a fixed bet progression ($1→$2→$4). Win on any 1 of 3 bets. Start with $20 bankroll.

### Key Clarifications (v3.0)

1. **Position sizing**: Fixed bet progression — $1 base, $2 on loss, $4 on second loss. Max loss $7 per session. No Kelly, no bankroll percentages.
2. **Bankroll**: Start with **$20 only**. Use only profits to increase position. No hard-coded bankroll percentages.
3. **Entry timing**: Analyze using **pre-C1 close data** (1-2 minutes before close) to get near-$0.50 entry. Execute at C2 open.
4. **Conviction scoring**: No hard thresholds (no "≥0.70 = enter"). Use weighted conviction analysis across all dimensions.
5. **Accuracy over profit**: We need to be right 1 of 3 candles. Not about maximizing profit, about winning rate.

### Architecture Overview

```
Hermes Agent (Main Brain)
  ├── Memory: Cross-session learning, regime tracking
  ├── Skills: Trading session, Polymarket execution, flip evaluation
  ├── MCP: Binance WS data, market state
  ├── Cron: 15m analysis cycle
  └── Sub-agents:
        ├── Advisor Agent (Claude Opus 4.7, max reasoning) — parallel cross-validation
        ├── Technical Analyst — candlestick, momentum, trend
        ├── Orderflow Analyst — VPIN, CVD, OBI, smart money
        ├── Macro Analyst — DXY, SP500, VIX, sentiment
        ├── Bull Researcher — argue GREEN case
        ├── Bear Researcher — argue RED case
        ├── Risk Manager — circuit breaker, bet approval
        └── Execution Agent — Polymarket order placement
```

---

## 2. The Strategy (Fixed, Never Changes)

**Core Question:** Will ≥2 of the next 3 candles (C2, C3, C4) close GREEN or RED?

### Candle Numbering

```
Timeline:
  C1: Current candle — we analyze its data (opens 15min ago, closes NOW)
  C2: Next candle — we BET on its direction
  C3: Candle after C2
  C4: Candle after C3

We predict: Will ≥2 of (C2, C3, C4) close GREEN (close > open)?
```

### Pre-C1 Analysis Method

**Critical timing optimization:**
- We analyze **before C1 closes** (1-2 minutes before close)
- This captures live market momentum without the post-close price shift
- We use the **last completed C0 candle** + real-time tick data as our analytical dataset
- Execution happens at C2 open (15 minutes after C1 close)
- This gives us near-$0.50 entry on Polymarket instead of post-shift prices

**Why this matters:**
- If we call GREEN after C1 close, YES token may already be $0.55-$0.70
- At $0.65, a $1 bet returns $1.54 (profit $0.54) — still profitable but reduced
- Pre-C1 analysis gives us entry closer to $0.50, maximizing profit per win

### 3-Bet Fixed Progression (Mark Tingle)

```
Bet 1 (C2): $1 base bet
  C2 GREEN → WIN → Session ends (+$1 profit at $0.50)
  C2 RED   → Loss $1 → Continue to Bet 2

Bet 2 (C3): $2 bet (2x base)
  C3 GREEN → WIN → Session ends (+$2 profit - $1 loss = +$1 total)
  C3 RED   → Loss $2 → Continue to Bet 3

Bet 3 (C4): $4 bet (4x base)
  C4 GREEN → WIN → Session ends (+$4 profit - $3 loss = +$1 total)
  C4 RED   → Loss $4 → Session ends (+$1 - $1 - $2 - $4 = -$7 total)

WE WIN ON ANY 1 OF 3 BETS. Maximum loss = $7. Maximum profit = $1.
```

### Polymarket Entry Pricing

When we call GREEN:
- Buy YES token at current market price
- If price = P, $1 bet returns $1/P shares → if YES resolves, receive $1 per share
- Profit = $1/P - $1 = (1-P)/P
- At P = $0.50: profit = $1.00 per $1 bet
- At P = $0.65: profit = $0.54 per $1 bet
- At P = $0.80: profit = $0.25 per $1 bet

**Acceptable:** Any entry P < $0.90 gives positive expected value if our accuracy > P.

### Dynamic Direction Flip

After a C2 or C3 loss, evaluate flipping direction:

**Conditions for flip:**
1. Counter-signal strength > original signal + 0.15 (conviction gap)
2. VPIN not in toxic zone (≤ 0.60 for flip evaluation)
3. Advisor recommends flip OR ≥2 secondary conditions met:
   - CVD divergence from price
   - Funding rate reversal
   - New technical breakdown confirmed
4. Cannot flip on C4 (no bets remain)
5. Cannot flip during circuit breaker (3 consecutive losses)

**Flip is conservative.** It requires multi-signal consensus and is logged for analysis.

### Conviction Scoring (No Hard Thresholds)

Instead of "confidence ≥ 0.70 = enter", we use **weighted conviction analysis**:

```
Conviction Score = Σ(dimension_score × dimension_weight)

Dimension weights (adjusted by regime):
  momentum:      0.25  — RSI, MACD, price velocity
  trend:         0.20  — Supertrend, ADX, BB position
  orderflow:     0.20  — VPIN, CVD, OBI
  smart_money:   0.15  — funding, OI, long/short
  sentiment:     0.10  — Fear&Greed zone
  macro:        0.10  — DXY, SP500, VIX

ENTRY RULE: Enter if:
  - Weighted conviction > 0.55 (soft floor, not hard cutoff)
  - AND ≥2 dimensions score > 0.65 OR < 0.35 (extreme signals)
  - AND no dimension score < 0.20 (no strongly opposing signals)
  - AND VPIN < 0.70 (not toxic)
  - AND pre-filter hard rules pass
```

**The key change:** We don't have a hard "≥0.70 = enter, <0.55 = skip" binary. We analyze all dimensions holistically. If conviction is medium-high with multiple extreme supporting signals, we enter. If conviction is medium but one dimension is strongly conflicting, we skip.

---

## 3. PhD-Level Mathematical Framework

This section provides the exact mathematical formulations for all signal computations. These are not approximations — they are the derivations used by professional quant researchers.

### 3.1 VPIN (Volume-Synchronized Probability of Informed Trading)

**Original paper:** Easley, López de Prado, O'Hara — "The Volume同步 Probability of Informed Trading" (VPIN)

**Concept:** VPIN measures the probability that a randomly selected trade is informed. High VPIN = institutional activity = directional move likely.

**For crypto (adapted from original equities formula):**

**Step 1 — Classify trades as buy or sell:**
Using the **tick rule** (Lee & Ready, 1987):
```
If ΔP > 0: classify as BUY
If ΔP < 0: classify as SELL
If ΔP = 0: use previous classification
```

**Step 2 — Compute volume buckets:**
Divide the trade stream into M equal-volume buckets (M = 50 for 15m candles):
```
V_b = volume of buys in bucket b
V_s = volume of sells in bucket b
V_b = volume of bucket b
```

**Step 3 — VPIN formula:**
```
VPIN = (1/M) × Σ_{b=1}^{M} |V_b - V_s| / V_b

Or equivalently:
VPIN = Σ |V_buy - V_sell| / Σ V_total   [over rolling M buckets]
```

**Rolling VPIN for real-time:**
```
VPIN_t = (1/M) × Σ_{i=t-M+1}^{t} |V_buy(i) - V_sell(i)| / V_total(i)
```

Where the window slides as each new bucket is formed.

**Implementation parameters for BTC 15m:**
- Bucket size: Volume equivalent to ~12 seconds of average BTC trading (~50 BTC)
- M = 50 buckets (covers roughly the last 10 minutes of trade data)
- Classification: tick rule on aggTrades price delta

**VPIN interpretation:**
| VPIN Range | Signal | Action |
|---|---|---|
| < 0.30 | Normal retail activity | Standard analysis |
| 0.30–0.50 | Elevated activity | Weight signals more heavily |
| 0.50–0.70 | High institutional activity | Strong directional signal likely |
| > 0.70 | Extreme — skip | Too uncertain, high risk |

### 3.2 CVD (Cumulative Volume Delta)

**Concept:** Accumulated difference between buy volume and sell volume. CVD divergence from price = hidden institutional pressure.

**Base formula:**
```
CVD_t = Σ_{i=1}^{t} (V_buy(i) - V_sell(i))

Rolling CVD (last N trades):
CVD_window = Σ_{i=t-N+1}^{t} (V_buy(i) - V_sell(i))
```

**For BTC 15m:**
- Window: 200 trades (rolling)
- Positive CVD = net buy pressure (bullish)
- Negative CVD = net sell pressure (bearish)
- CVD magnitude indicates conviction of the pressure

**CVD divergence detection:**
```
price_slope = (P_t - P_{t-N}) / P_{t-N}   [N = same period as CVD]
cvd_slope   = (CVD_t - CVD_{t-N}) / |CVD_{t-N}|

Divergence = sign(price_slope) ≠ sign(cvd_slope)
```

**Divergence patterns:**
| Pattern | Interpretation |
|---|---|
| Price rising + CVD flat | Rally without buy support → reversal likely |
| Price rising + CVD falling | Hidden sell pressure → reversal likely |
| Price falling + CVD rising | Hidden buy pressure → reversal likely |
| Price falling + CVD flat | Drop without sell support → reversal likely |

**CVD score for reasoning (normalized 0–1):**
```
CVD_score = 0.5 + (CVD_window / (2 × max_CVD_seen))
```

### 3.3 OFI (Order Flow Imbalance)

**Concept:** Change in order book depth, measuring bid vs ask pressure at each price level.

**Formula:**
```
OFI = Σ_{l=1}^{L} [ΔBid_qty(l) - ΔAsk_qty(l)] × weight(l)

Where:
ΔBid_qty(l) = bid_qty(l, t) - bid_qty(l, t-1)
ΔAsk_qty(l) = ask_qty(l, t) - ask_qty(l, t-1)
weight(l) = e^{-(l-1)/λ}  [exponential decay, λ = depth parameter]

For L = 5 levels, λ = 2:
OFI = ΔBid_1 - ΔAsk_1 + 0.61×(ΔBid_2 - ΔAsk_2) + 0.37×(ΔBid_3 - ΔAsk_3) + ...
```

**Simplified 3-level OFI for real-time:**
```
OFI = (Bid_qty_L1 - Ask_qty_L1) + 0.5×(Bid_qty_L2 - Ask_qty_L2) + 0.25×(Bid_qty_L3 - Ask_qty_L3)
```

**OFI normalization:**
```
OFI_score = tanh(OFI / σ_OFI)   [tanh normalizes to [-1, 1]]
```
Where σ_OFI is the rolling standard deviation of OFI over last 20 periods.

### 3.4 TCR (Trade Count Ratio)

**Concept:** Ratio of buy trades to sell trades (not volume-weighted).

**Formula:**
```
TCR = (N_buy - N_sell) / (N_buy + N_sell)

Rolling TCR (last N trades):
TCR_window = (Σ I_buy - Σ I_sell) / N
Where I_buy = 1 if trade classified as buy, 0 otherwise
```

**Thresholds:**
| TCR | Signal |
|---|---|
| > +0.15 | Strong buy aggression |
| +0.05 to +0.15 | Moderate buy pressure |
| -0.05 to +0.05 | Neutral |
| -0.15 to -0.05 | Moderate sell pressure |
| < -0.15 | Strong sell aggression |

### 3.5 Order Book Imbalance (OBI)

**Formula:**
```
OBI_L = (Σ_{l=1}^{L} Bid_qty(l) - Σ_{l=1}^{L} Ask_qty(l)) / (Σ_{l=1}^{L} Bid_qty(l) + Σ_{l=1}^{L} Ask_qty(l))

For L = 5:
OBI = (Bid_total - Ask_total) / (Bid_total + Ask_total)
```

**Thresholds:**
| OBI | Signal |
|---|---|
| > +0.25 | Strong bid pressure |
| +0.10 to +0.25 | Moderate bid pressure |
| -0.10 to +0.10 | Balanced |
| -0.25 to -0.10 | Moderate ask pressure |
| < -0.25 | Strong ask pressure |

### 3.6 Smart Money Indicators

#### Funding Rate Analysis

**Formula:**
```
Funding_8h = rate from Binance (paid every 8 hours)
Annualized_funding = Funding_8h × 3 × 365  [3 funding periods per day]

Signal:
  Positive high funding (> 0.03% per 8h = ~33% annualized): 
    → Bullish but dangerous — bulls paying shorts → reversal risk
  Negative funding (< -0.03% per 8h):
    → Bearish — shorts paying bulls → continuation
```

**For our 15m analysis:**
```
Funding_score = -1 × tanh(Funding_8h × 50)   [negative because positive funding = bearish signal]
```

#### Open Interest (OI) Analysis

**Key relationship:**
```
OI_rising + Price_rising = CONFIRMED trend (healthy)
OI_falling + Price_rising = BEARISH divergence (trend weakening)
OI_rising + Price_falling = BEARISH confirmation
OI_falling + Price_falling = BULLISH divergence (reversal potential)
```

**OI change formula:**
```
OI_change_pct = (OI_t - OI_{t-1}) / OI_{t-1} × 100
OI_signal = +1 if OI_change_pct > 2% and price rising
          = -1 if OI_change_pct > 2% and price falling
          = +0.5 if OI_change_pct > 1% (moderate)
          = 0 otherwise
```

#### Long/Short Ratio (Top Traders)

**Formula:**
```
LS_ratio = Long_accounts / Short_accounts   [from Binance top traders]
LS_ratio_score = LS_ratio - 1.0  [centered at 0]
```

**Thresholds:**
| Long Account % | Signal | Score impact |
|---|---|---|
| > 65% | Crowded long = reversal risk | -0.15 to bullish signal |
| 55–65% | Slight bullish | +0.05 |
| 45–55% | Neutral | 0 |
| 35–45% | Slight bearish | +0.05 to bearish signal |
| < 35% | Crowded short = reversal risk | +0.15 to bullish signal |

### 3.7 Market Microstructure Score

**Combined orderflow score:**
```
Microstructure_Score = w1×VPIN_score + w2×CVD_score + w3×OFI_score + w4×TCR_score + w5×OBI_score

Where:
VPIN_score = VPIN (0-1, higher = more institutional activity)
CVD_score  = normalized CVD (0-1, 0.5 = neutral)
OFI_score  = tanh(OFI/σ) (-1 to 1, normalized to 0-1)
TCR_score  = (TCR + 1) / 2 (0-1)
OBI_score  = (OBI + 1) / 2 (0-1)

w1=0.25, w2=0.25, w3=0.20, w4=0.15, w5=0.15

Microstructure_Score interpretation:
  > 0.65: Strong institutional flow in one direction
  0.55–0.65: Moderate flow
  0.45–0.55: Neutral
  < 0.45: Ambiguous orderflow
```

### 3.8 Multi-Timeframe Confluence

**The key insight:** A signal confirmed across multiple timeframes is more reliable.

```
TF_alignment_score = 
  0.20 × candle_1h_trend_aligned +   [1h EMA alignment with our direction]
  0.15 × candle_4h_trend_aligned +   [4h trend confirmation]
  0.15 × candle_1d_structure +      [Daily structure — higher high/low?]
  0.25 × candle_15m_momentum +      [Our primary 15m momentum]
  0.25 × candle_5m_imbalance         [Very short-term orderflow]

Where each component is 1 if aligned with our call, 0 if against, 0.5 if neutral.
```

**Confluence zones:**
- 4+ timeframes aligned: Very high conviction
- 3 timeframes aligned: High conviction
- 2 timeframes aligned: Medium conviction
- 1 timeframe aligned: Low conviction
- 0 timeframes aligned: Skip

### 3.9 Volume Profile Analysis

**Point of Control (POC):** The price level with highest volume traded.

**Value Area High/Low (VAH/VAL):** Price levels containing 70% of volume.

**Formula:**
```
POC = argmax_p Σ V(p)  [price with max volume]
VAH = price at 85th percentile of volume distribution
VAL = price at 15th percentile of volume distribution
```

**Signal interpretation:**
| Price vs POC/VAH/VAL | Signal |
|---|---|
| Price above VAH | Bullish — trading at premium to value |
| Price between VAH and POC | Slight bullish |
| Price at POC | Neutral |
| Price between POC and VAL | Slight bearish |
| Price below VAL | Bearish — trading at discount to value |

**For our 15m analysis:**
- Build volume profile from C-5 to C-1 (last 5 candles)
- Use tick-level data for precision
- Compare C1 close to POC: above POC = bullish continuation, below = bearish

### 3.10 Momentum Scoring System

**Composite momentum formula:**
```
RSI_score = (RSI_14 - 50) / 50   [normalized: -1 to +1, 0 = neutral]
MACD_score = sign(MACD_histogram) × tanh(|MACD_histogram| / ATR_14)
Velocity_score = tanh(price_velocity_5 / ATR_14)

Momentum_Score = 0.40×RSI_score + 0.35×MACD_score + 0.25×Velocity_score
```

**RSI divergence detection:**
```
RSI_div = RSI_14 < 30 and price_at_support → BULLISH DIVERGENCE
RSI_div = RSI_14 > 70 and price_at_resistance → BEARISH DIVERGENCE
```

### 3.11 Conviction Weight Formula

**Final conviction score (all dimensions combined):**

```
Conviction = (
  momentum_score     × w_m +
  trend_score        × w_t +
  orderflow_score    × w_of +
  smart_money_score  × w_sm +
  sentiment_score    × w_se +
  macro_score        × w_ma
)

Where w_m=0.25, w_t=0.20, w_of=0.20, w_sm=0.15, w_se=0.10, w_ma=0.10

Each dimension score is from 0 to 1:
  0.0 = strongly bearish
  0.5 = neutral
  1.0 = strongly bullish
```

**Dimension scores computed as:**

```
momentum_score = 0.5 + 0.5 × tanh(RSI_osc + MACD_osc + velocity_osc)

trend_score = 0.5 + 0.5 × tanh(ADX_osc + BB_position_osc + EMA_cross_osc)

orderflow_score = 0.5 + 0.5 × tanh(VPIN_osc + CVD_osc + OFI_osc + TCR_osc)

smart_money_score = 0.5 + 0.5 × tanh(funding_osc + OI_osc + LS_ratio_osc)

sentiment_score = 0.5 + 0.5 × tanh(FG_normalized + dominance_osc)

macro_score = 0.5 + 0.5 × tanh(DXY_osc + SP500_osc + VIX_osc)
```

Where each `_osc` component is the normalized deviation from neutral.

---

## 4. Complete Feature Engineering

### Tier 1: Candlestick & Price Action (Primary Signal Source)

| Feature | Formula | Range | Signal |
|---|---|---|---|
| C1 body size % | `abs(close - open) / close × 100` | 0–∞ | >0.5% = conviction |
| C1 close position | `(close - low) / (high - low)` | 0–1 | >0.7 = bullish control |
| C1 upper wick % | `(high - max(open,close)) / range × 100` | 0–100 | >30% = rejection |
| C1 lower wick % | `(min(open,close) - low) / range × 100` | 0–100 | >30% = support absorption |
| Body/wick ratio | `body / max(wick, tiny)` | 0–∞ | >1.0 = body dominates |
| C1 direction | `close > open ? GREEN : RED` | {GREEN, RED} | Primary signal |
| RVOL (C1) | `C1_vol / avg(last_20_vol)` | 0–∞ | >1.5 = high conviction |
| C1 volume | `C1_vol (BTC)` | 0–∞ | Absolute volume |
| Price velocity (5c) | `(C1_close - C-5_close) / C-5_close × 100` | -∞ to +∞ | Momentum |
| VWAP deviation % | `(price - VWAP) / VWAP × 100` | -∞ to +∞ | Value area |
| EMA alignment | EMA7 > EMA21 > EMA99 vs opposite | {BULL, NEUT, BEAR} | Trend structure |

### Tier 2: Orderflow & Microstructure

| Feature | Formula | Range | Signal |
|---|---|---|---|
| **VPIN** | `Σ|Vb-Vs|/ΣV over M=50 volume buckets` | 0–1 | >0.50 = directional move |
| **CVD** | `Σ(V_buy - V_sell)` over 200 trades | -∞ to +∞ | CVD divergence = reversal |
| **CVD divergence** | `sign(price_slope) ≠ sign(CVD_slope)` | {T, F} | Hidden pressure |
| **OFI** | `Σ(ΔBid - ΔAsk) × exp_weight` | -∞ to +∞ | Order book pressure |
| **OBI** | `(Bid_total - Ask_total) / (Bid + Ask)` | -1 to +1 | Book imbalance |
| **TCR** | `(N_buy - N_sell) / N_total` | -1 to +1 | Trade aggression |
| **Spread bps** | `(ask - bid) / mid × 10000` | 0–∞ | Liquidity |
| **Book pressure gradient** | `OFI_t - OFI_{t-5}` | -∞ to +∞ | Momentum of orderflow |
| **Trade size mean** | `avg(trade_qty)` | 0–∞ | Whale vs retail |
| **Large trade %** | `N_trades_qty>1BTC / N_total_trades` | 0–1 | Institutional activity |

### Tier 3: Technical Indicators

| Feature | Config | Formula | Signal |
|---|---|---|---|
| RSI-14 | 14-period on 15m | `100 - 100/(1+RS)` | <30 oversold, >70 overbought |
| RSI-4 | 4-period on 15m | Same | Fast momentum |
| RSI divergence | C1 vs C-5 | price_low + RSI_low pattern | Reversal signal |
| MACD line | 12/26 on 15m | EMA12 - EMA26 | Trend |
| MACD signal | 9-period | EMA(MACD_line, 9) | Crossover signal |
| MACD histogram | MACD - signal | Current momentum | Slope = acceleration |
| MACD histogram slope | diff per candle | `hist_t - hist_{t-1}` | Momentum change |
| VWAP | Anchored at session | `Σ(P×V)/ΣV` | Value area |
| Bollinger Bands | 20/2 | ±2σ from SMA | %B position |
| BB width | 20/2 | `(UB - LB) / mid × 100` | Volatility |
| ATR-14 | 14-period | `Σ(TR) / 14` | Volatility |
| Supertrend | 10/3 | `close > ST_up ? UP : DOWN` | Trend direction |
| ADX | 14-period | `100 × avg(PlusDM) / ATR` | Trend strength (>25 = trending) |
| EMA7/21/99 | On 15m | Standard EMA | Alignment = trend health |
| KDJ | 9/3/3 | `K = 2/3×K_prev + 1/3×rsv` | Overbought/oversold |
| Pivot points | R1, S1, PP, R2, S2 | From prev candle | Support/resistance |
| VWAP vs price | Anchored | `(price - VWAP) / VWAP` | Above/below value |

### Tier 4: Smart Money

| Feature | Source | Formula | Signal |
|---|---|---|---|
| Funding rate | Binance `/fapi/v1/fundingRate` | Rate % per 8h | >0.03% = reversal risk |
| Funding rate annualized | Rate × 3 × 365 | % per year | Extreme readings |
| OI change % | Binance `/fapi/v1/openInterest` | `(OI_now - OI_prev) / OI_prev × 100` | OI spike + divergence |
| Long/Short ratio | Binance `/fapi/v1/ratio` | Long / Short | >1.3 = crowded long |
| Long account % | Binance top traders | `Long_accounts / Total` | Extreme = reversal |
| Perp premium | `perp_price - spot_price` | `(diff / spot) × 10000` bps | Contango/backwardation |
| Liquidation clusters | CoinGlass API | Price levels | Magnetic levels |
| Whale inflow rank | Binance Web3 | Portfolio flow | Smart money positioning |

### Tier 5: Sentiment

| Feature | Source | Formula | Signal |
|---|---|---|---|
| Fear & Greed Index | alternative.me API | 0–100 | <25 extreme fear, >75 extreme greed |
| Fear & Greed trend | Last 3 readings | Direction | Rising/falling |
| Fear & Greed zone | Classification | {EF, F, N, G, EG} | Zone-based signal |
| BTC Dominance | CoinGecko | % | Rising = BTC rotation |
| Social hype | CoinGecko social stats | Score 0–1 | Narrative momentum |
| News sentiment | Optional: CryptoPanic | Score | Event-driven |

### Tier 6: Macro

| Feature | Source | Formula | Signal |
|---|---|---|---|
| DXY | Yahoo Finance `DX-Y.NYB` | Index value | DXY up = BTC headwind |
| DXY change % | Daily change | `(DXY_now - DXY_prev) / DXY_prev × 100` | Trend |
| S&P 500 | Yahoo Finance `^GSPC` | Index value | Risk-on/risk-off |
| SP500 change % | Daily change | Same pattern | Correlation |
| VIX | Yahoo Finance `^VIX` | Index value | >20 = risk-off |
| VIX change % | Daily change | Pattern | Sentiment shift |
| US 10Y Yield | Yahoo Finance `^TNX` | Yield % | Risk appetite |
| Correlation matrix | Rolling 20-day | `corr(BTC, SP500)` | Regime indicator |

### Tier 7: Market Structure

| Feature | Formula | Signal |
|---|---|---|
| HH/HL (5-candle) | `H_t > H_{t-1} and L_t > L_{t-1}` | Uptrend confirmation |
| LH/LL (5-candle) | `H_t < H_{t-1} and L_t < L_{t-1}` | Downtrend confirmation |
| Break of structure | `close > HH or close < LL` | Momentum continuation |
| Liquidity sweep | `high > HH + 0.5×ATR then reversal` | Stop hunt detection |
| Fair value gap | Gap in price action | Unfilled zone = target |
| Volume POC | `argmax_p volume(p)` | Value anchor |
| Volume profile VAH/VAL | 70% volume area | Support/resistance |

---

## 5. Pre-C1 Analysis Method (Timing Optimization)

### The Problem

Current approach: analyze after C1 close.
- By the time we analyze and execute, Polymarket prices have shifted
- GREEN call after bullish C1 → YES token already > $0.50
- Reduced profit per win

### The Solution: Pre-C1 Close Analysis

**Timeline:**
```
T-2:00  Begin analysis using C0 (last completed) + live tick data
T-0:30  Final conviction call and bet sizing decision
T-0:00  C1 closes
T+0:01  Place bet on Polymarket (at C2 open price, near $0.50)
T+15:00 C2 closes → resolve first bet
```

**Data used in pre-C1 analysis:**
- C0 (last completed candle) — full OHLCV data
- Live aggTrades stream — real-time VPIN, CVD, OFI, TCR
- Live order book depth — current OBI, spread
- REST data (funding, OI, long/short) — cached, refreshed every 5 minutes
- Macro data — 15-minute cache (Yahoo Finance)
- Fear & Greed — 30-minute cache

**Why this works:**
- C0 gives us the most recent completed candle (15 minutes ago)
- Live tick data gives us the current orderflow and momentum
- We don't need C1 to close to know what's happening — we see it forming in real-time
- At T-1 minute, we know 14 minutes of the current candle — enough for momentum signal

**Pre-C1 momentum score:**
```
Pre_C1_momentum = 
  0.4 × live_price_velocity (first 14min of C1) +
  0.3 × CVD_rolling (live trades) +
  0.3 × OFI_current (live orderbook)

If Pre_C1_momentum > threshold and pre-filter passes:
  → Proceed with analysis using C0 + live data
  → Execute bet at C2 open (15min later)
```

### Pre-C1 Pre-Filter Rules

Same hard rules as post-close, plus:
- **C0 body must exist**: C0 body > 0.05% (not a doji)
- **Live data sufficient**: ≥100 trades in last 5 minutes for VPIN/CVD
- **Order book stable**: Spread < 20 bps, no extreme imbalance

---

## 6. Agent Architecture

### 6.1 Hermes Agent as Main Brain

Hermes is the persistent orchestrating layer. It runs continuously, managing the 15m analysis cycle via cron, orchestrating sub-agents, and maintaining memory.

**Memory (MEMORY.md):**
```markdown
## Current Regime
regime: TRENDING_UP
win_rate_20: 0.65
strongest_signal: orderflow (68% accuracy)
weakest_signal: macro (48% accuracy)
last_outcome: WON on C3
consecutive_losses: 0

## Performance Tracking
total_sessions: 147
win_rate: 0.544
avg_profit: $0.43/session
total_profit: $63.21
bankroll: $20 base + $63.21 profits = $83.21

## Regime History
- 2026-05-07: TRENDING_UP → 72% (12 sessions)
- 2026-05-06: RANGING → 45% (8 sessions)

## Signal Attribution (last 50 sessions)
orderflow: 68% accuracy
momentum: 62% accuracy
trend: 58% accuracy
smart_money: 52% accuracy
macro: 48% accuracy
```

**Skills (SKILL.md):**
- `SKILL_trading_session.md` — Complete session workflow
- `SKILL_pre_c1_analysis.md` — Pre-C1 analysis method
- `SKILL_flip_evaluation.md` — Dynamic flip logic
- `SKILL_polymarket_execution.md` — Order placement
- `SKILL_market_state_assembly.md` — Data fetching

**MCP Integration:**
- Binance WS: `wss://fstream.binance.com/ws/btcusdt@aggTrade` — live trades
- Binance WS: `wss://fstream.binance.com/ws/btcusdt@depth20@100ms` — order book
- Binance WS: `wss://fstream.binance.com/ws/btcusdt@kline_15m` — candle stream
- Binance REST: funding rate, OI, long/short ratio (cached, refresh every 5min)
- Fear & Greed API: `https://api.alternative.me/fng/` (cached 30min)
- Yahoo Finance: macro data (cached 15min)

### 6.2 Agent Roles

| Agent | Model | Purpose |
|---|---|---|
| **Data Agent** | Haiku/CLI | Pre-fetch, parallel assembly of market state |
| **Technical Analyst** | Sonnet 4.6 | C1 candlestick, RSI/MACD/VWAP, momentum, trend |
| **Orderflow Analyst** | Sonnet 4.6 | VPIN, CVD, OBI, TCR, OFI, smart money |
| **Macro Analyst** | Sonnet 4.6 | DXY, SP500, VIX, Fear&Greed |
| **Bull Researcher** | Opus 4.7 | Argue GREEN, find supporting signals |
| **Bear Researcher** | Opus 4.7 | Argue RED, find opposing signals |
| **Facilitator** | Sonnet 4.6 | Judge debate, select prevailing view |
| **Advisor Agent** | Opus 4.7 max | Independent parallel cross-validation |
| **Main Reasoner** | Opus 4.7 | Final call (on Hermes) |
| **Risk Manager** | Sonnet 4.6 | Circuit breaker, bankroll check |
| **Execution Agent** | Haiku/CLI | Polymarket order placement |
| **Reflection Agent** | Sonnet 4.6 | Log outcomes, update memory |

### 6.3 Communication Protocol

```
Pre-C1 (T-2:00 to T-0:30):
  Live data stream → Data Agent → Market State Packet
  Market State → Pre-Filter (hard rules)
  Passed → Parallel: Advisor + Main Reasoner + Analyst trio

Parallel Analysis (T-0:30):
  ├─ Technical Analyst: candlestick + momentum + trend → report
  ├─ Orderflow Analyst: VPIN + CVD + OBI + smart money → report
  ├─ Macro Analyst: DXY + SP500 + VIX + sentiment → report
  │
  ├─ Bull Researcher: argue GREEN from analyst reports
  ├─ Bear Researcher: argue RED from analyst reports
  └─ Facilitator: judge debate → verdict

  All → Main Reasoner (synthesizes + final call)
  
  Advisor Agent (parallel on Opus 4.7, max thinking) → independent opinion
  Main Reasoner reconciles → final call

T-0:30 → Execute bet on Polymarket (at C2 open price)

Post-C1 (T+15:00):
  C2 closes → resolve bet
    WIN → session ends, log, alert
    LOSS → evaluate flip → place next bet or skip
```

---

## 7. Position Sizing & Bankroll

### 7.1 Fixed Bet Progression

**Mark Tingle Progression:**
```
Base bet: $1
On loss: multiply by 2
On second loss: multiply by 4
Maximum 3 bets per session

Total max exposure: $1 + $2 + $4 = $7
```

### 7.2 Bankroll Management

**Starting bankroll: $20**

**Rules:**
1. Only use starting $20 for base bets ($1)
2. Use **only profits** for future base bets
3. After each session: if won, increase bankroll tracking
4. **Never use more than $7 per session** (max loss cap)
5. **Circuit breaker**: After 3 consecutive losses, require conviction > 0.60 before next bet

**Bankroll tracking:**
```
Starting: $20 (base)
Session 1: Bet $1 → WIN → +$1 → Bankroll = $21
Session 2: Bet $1 → WIN → +$1 → Bankroll = $22
Session 3: Bet $1 → LOSS → -$1 → Bankroll = $21
Session 4: Bet $1 → LOSS → Bet $2 → WIN → +$1 → Bankroll = $22
...
```

**Note:** The bankroll is our tracking number. The actual Polymarket bets use the fixed progression ($1→$2→$4) regardless of bankroll size. We don't increase bet sizes based on profits.

### 7.3 Profit Reinvestment

- After each winning session, the profit is added to tracked bankroll
- Next session's base bet is still $1 (we don't compound)
- The bankroll number is used for:
  - Circuit breaker check (if bankroll drops below $15, increase caution)
  - Statistics and performance tracking
  - Telegram alerts showing growth

---

## 8. Polymarket Execution Layer

### 8.1 Entry Timing

**Pre-C1 execution:**
- Analysis completes at T-0:30 (30 seconds before C1 close)
- We place the Polymarket order at C2 open price
- C2 open = C1 close + ~1 second (execution latency)
- Expected entry: within 2 seconds of C1 close price

**Entry price expectation:**
- C1 close → Polymarket market updates immediately
- At T-0:30 analysis, YES/NO tokens reflect current market state
- By T+1 (C2 open), we execute at the market price at that moment
- **Target:** Entry between $0.45 and $0.70 (acceptable range)
- **Acceptable:** Any entry below $0.90 (positive expected value if accuracy > entry price)

### 8.2 Market Discovery

```python
async def find_btc_market():
    # 1. Gamma API for active BTC markets
    markets = await gamma_client.get_markets(
        active=True, closed=False,
        question_contains=["btc", "bitcoin"],
        order_by="volume"
    )
    
    # 2. Filter: liquidity > $500, spread < $0.10
    candidates = [m for m in markets 
                 if m.liquidity > 500 and m.spread < 0.10]
    
    # 3. Pick highest volume
    return max(candidates, key=lambda m: m.volume)
```

### 8.3 Order Placement

```python
async def place_bet(direction, market, size):
    token = market.yes_token if direction == "GREEN" else market.no_token
    current_price = market.get_price(token)  # At C2 open
    
    order = client.create_order(
        token_id=token,
        side="buy",
        size=size / current_price,  # Shares
        price=current_price
    )
    
    # Sign with wallet key
    signed = sign_order(order)
    
    # Submit to CLOB
    result = await client.submit(signed)
    return result
```

### 8.4 Position Tracking

- Track all open positions with entry price and size
- Monitor market resolution timing
- Auto-redeem winning positions after market expiry
- Log all trades for analysis

---

## 9. Conviction-Based Decision Framework

### 9.1 No Hard Thresholds — Conviction Analysis

**Old approach (v2):**
```
if confidence >= 0.70: ENTER
elif confidence >= 0.55 and extreme_signals >= 2: ENTER  
else: SKIP
```

**New approach (v3) — conviction analysis:**

```
ENTER if ALL of:
  1. Weighted conviction > 0.50 (soft floor)
  2. ≥2 dimensions score > 0.65 OR < 0.35 (extreme supporting signals)
  3. No dimension score < 0.25 (no strong opposing signals)
  4. Pre-filter hard rules PASS
  5. VPIN < 0.70 (not toxic)
  6. Advisor agrees OR confidence gap > 0.10

SKIP if ANY of:
  - Weighted conviction < 0.50
  - Only 1 dimension extreme, rest neutral
  - Strong opposing signal (dimension < 0.25)
  - VPIN > 0.70
  - Pre-filter fails
  - Advisor strongly disagrees (opposite call with high confidence)
```

### 9.2 Dimension Score Matrix

| Dimension | Score | Meaning |
|---|---|---|
| momentum | 0.0–1.0 | RSI/MACD/velocity composite |
| trend | 0.0–1.0 | Supertrend/ADX/BB/structure |
| orderflow | 0.0–1.0 | VPIN/CVD/OBI/TCR/OFI |
| smart_money | 0.0–1.0 | funding/OI/long-short ratio |
| sentiment | 0.0–1.0 | Fear&Greed/dominance |
| macro | 0.0–1.0 | DXY/SP500/VIX |

**Score interpretation:**
- 0.0–0.30: Bearish signal
- 0.30–0.45: Slight bearish
- 0.45–0.55: Neutral
- 0.55–0.70: Slight bullish
- 0.70–1.0: Bullish signal

### 9.3 Example Conviction Analysis

```
Dimension        Score    Signal         Weight
momentum:        0.82    Strong bullish   0.25
trend:           0.71    Slight bullish  0.20
orderflow:       0.78    Bullish          0.20
smart_money:     0.55    Neutral          0.15
sentiment:       0.62    Slight bullish   0.10
macro:           0.48    Neutral          0.10

Weighted conviction = 0.82×0.25 + 0.71×0.20 + 0.78×0.20 + 0.55×0.15 + 0.62×0.10 + 0.48×0.10
                    = 0.205 + 0.142 + 0.156 + 0.083 + 0.062 + 0.048
                    = 0.696

Extreme signals: momentum (0.82 > 0.65) ✓, orderflow (0.78 > 0.65) ✓ → 2 extremes
No opposing signal: all scores > 0.25 ✓

→ ENTER: GREEN with conviction 0.70
```

---

## 10. Dynamic Flip Logic

### Flip Conditions (Revised)

After C2 or C3 loss, evaluate flip:

**Required (ALL must be true):**
1. Counter-signal conviction > original signal + 0.15
2. VPIN ≤ 0.60 (not toxic)
3. Advisor recommends flip (≥ 0.60 confidence)
4. At least 1 of 3 secondary conditions met:
   - CVD divergence confirmed
   - Funding rate reversal (>0.02% change)
   - New technical breakdown (ADX dropped >5 points, or new lower low)

**Forbidden:**
- Cannot flip on C4 (no bets remain)
- Cannot flip during circuit breaker (3 consecutive losses)

**Flip execution:**
```
If flip conditions met:
  flip_direction = opposite(original_direction)
  Log: "FLIP: {original} → {flip_direction} | reason: {reason}"
  Alert on Telegram
  Place next bet in flip direction
```

---

## 11. Telegram Alert System

### Alert Events

| Event | Content |
|---|---|
| Pre-C1 analysis started | Regime, live data snapshot |
| Session entered | Direction, conviction score, market URL |
| Bet placed | Candle, size, entry price |
| Bet resolved (WIN) | Candle result, profit, remaining bets |
| Bet resolved (LOSS) | Candle result, remaining bets |
| Session WIN | Full P&L, winning candle |
| Session LOSS | Total loss, all bet outcomes |
| Direction flip | From → To, flip reason |
| Circuit breaker | 3 consecutive losses warning |
| /stats | Win rate, last 20, total profit, bankroll |
| /export | CSV file |

### Alert Format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 BTC 15m — PRE-C1 ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🕐 Time: {timestamp}
📍 Regime: {regime}

SIGNAL BREAKDOWN
  Momentum:    {score}/1.0 ██████████████░░
  Trend:       {score}/1.0 ████████████░░░░
  Orderflow:   {score}/1.0 █████████████░░░
  Smart Money: {score}/1.0 █████████░░░░░░░
  Macro:       {score}/1.0 ██████░░░░░░░░░░

⚖️ Conviction: {conviction:.2f}
🔮 Call: {direction} 🟢/🔴
👤 Advisor: {advisor_call} @ {advisor_conf:.2f}

🎯 ACTION: BET PLACED
   C2 @ ${price} | Size: ${size}
   Market: {url}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 12. Self-Improving Loop (Karpathy Pattern)

### The Improvement Cycle

```
Every session:
  1. Log: direction, conviction, outcome, all dimension scores
  2. Update: rolling win rate, consecutive counters

Every 20 sessions:
  3. Signal attribution: which dimensions predicted best?
  4. Regime detection: trending / ranging / volatile
  5. Adjust: if a dimension consistently wrong → reduce its weight
  6. Report: morning cron → Hermes generates analysis → MEMORY.md

If win rate < 0.40 over last 20:
  7. Circuit breaker → require edge > 0.05
  8. Alert: "Regime shift detected — manual review needed"
```

### Signal Attribution Formula

```
For each dimension D over last N sessions:
  high_D_sessions = [s for s in last_N where dim_score(D) > 0.65]
  if len(high_D_sessions) >= 5:
    accuracy(D) = sum(1 for s in high_D_sessions if s.outcome == WIN) / len(high_D_sessions)
  else:
    accuracy(D) = None (not enough data)

Dimension weight adjustment:
  if accuracy(D) > 0.60: weight(D) += 0.02
  if accuracy(D) < 0.45: weight(D) -= 0.02
  weight(D) = max(0.05, min(0.40, weight(D)))  # Clamp [5%, 40%]
```

---

## 13. Component Inventory

| Component | File | Purpose |
|---|---|---|
| Data Ingestion | `src/data_sources/binance_client.py` | Binance WS + REST |
| Feature Engineering | `src/features/market_state.py` | MarketStateAssembler |
| Technical Indicators | `src/features/technical_indicators.py` | TA computations |
| Pre-Filter | `src/pre_filter.py` | Hard rules before LLM |
| Advisor Agent | `src/agents/advisor.py` | Opus 4.7 cross-validation |
| Reasoning Engine | `src/reasoning_prompt.py` | Main prompt + output parsing |
| Session Manager | `src/session.py` | State machine, persistence |
| Dynamic Flip | `src/dynamic_flip.py` | Flip evaluation |
| Polymarket Client | `src/execution/polymarket_client.py` | Order placement |
| Prediction Logger | `src/prediction_logger.py` | CSV logging + stats |
| Telegram Alerts | `src/alerts/telegram_alerts.py` | All notifications |
| Event Loop | `src/event_loop.py` | Main orchestrator |
| Config | `config/constants.py` | Thresholds, API keys |

---

## 14. Data Flow (Pre-C1 Method)

```
T-2:00  Cron trigger → Hermes begins analysis
          │
          ▼
T-1:55  Parallel data fetch:
          ├─ Binance WS: aggTrades stream (live)
          ├─ Binance WS: depth stream (live)
          ├─ Binance WS: kline_15m stream (watching C1 form)
          ├─ Binance REST: funding, OI, long/short (cached 5min)
          ├─ Fear & Greed API (cached 30min)
          └─ Yahoo Finance: macro (cached 15min)
          │
          ▼ (target: < 20 seconds)
T-1:35  Market state assembled → Pre-filter run
          │
          ├─ FAIL → Log skip, wait for next cycle
          └─ PASS → Continue
          │
          ▼
T-1:30  Parallel analysis:
          ├─ Technical Analyst (Sonnet) → candlestick + momentum report
          ├─ Orderflow Analyst (Sonnet) → VPIN + CVD + OBI report
          ├─ Macro Analyst (Sonnet) → DXY + SP500 + sentiment report
          │
          ├─ Bull Researcher (Opus) → argue GREEN
          ├─ Bear Researcher (Opus) → argue RED
          └─ Facilitator (Sonnet) → debate verdict
          │
          ├─ Advisor Agent (Opus 4.7 max) → independent opinion
          └─ Main Reasoner (Opus) → final conviction call
          │
          ▼ (target: < 60 seconds total)
T-0:30  Final call: GREEN/RED/SKIP + conviction score
          │
          ├─ SKIP → Log analysis, wait for next cycle
          └─ ENTER →
              │
              ▼
T-0:30  Polymarket order placement (at current price ≈ C2 open)
          │
          ▼
T-0:28  Order confirmed → Log bet, alert Telegram
          │
          ▼
T-0:00  C1 candle closes (bet already placed at ~C2 open price)
          │
          ▼
T+15:00 C2 candle closes → resolve bet
          │
          ├─ WIN → Session ends, log, alert, reset
          ├─ LOSS + bets remain → flip evaluation → place bet or hold
          └─ LOSS + no bets → Session ends, log, alert, reset
          │
          ▼
(Repeat for C3 and C4 as needed)
```

---

## 15. Key Reference Formulas

### VPIN
```
VPIN = (1/M) × Σ_{b=1}^{M} |V_b - V_s| / V_b
Where M = 50 (volume buckets), V_b = bucket volume, V_s = sell volume in bucket
```

### CVD
```
CVD = Σ (V_buy - V_sell)  [rolling N trades, N = 200]
CVD_divergence = sign(price_slope) ≠ sign(CVD_slope)
```

### OFI
```
OFI = Σ_{l=1}^{L} (ΔBid_l - ΔAsk_l) × exp(-(l-1)/λ)
For L = 5, λ = 2
```

### OBI
```
OBI = (Bid_total - Ask_total) / (Bid_total + Ask_total)
```

### TCR
```
TCR = (N_buy - N_sell) / (N_buy + N_sell)
```

### Conviction Score
```
Conviction = Σ (dimension_score × dimension_weight)
dimension_score = 0.5 + 0.5 × tanh(oscillator_value)
```

### Kelly (Not Used — for reference only)
```
f* = (b×p - q) / b
Where p = probability, q = 1-p, b = odds - 1
```

---

## 16. Failure Modes & Recovery

| Failure | Detection | Recovery |
|---|---|---|
| WS disconnect | aggTrades stream timeout | Reconnect with backoff, skip cycle if > 5min |
| Pre-C1 data insufficient | < 100 trades in 5min | SKIP, wait for next cycle |
| Order book unstable | Spread > 20 bps | SKIP, wait for next cycle |
| Polymarket order fails | API error | SKIP, alert, do not open session |
| Session active, missed candle | C2/C3/C4 close detection gap | Check session state, resolve any pending bets |
| CSV write fails | IO error | Retry, alert on repeated failure |
| Memory update fails | Write error | Log warning, continue |

---

## 17. Implementation Priority

### Phase 1: Core (Current)
- Pre-C1 analysis method implementation
- Fixed bet progression ($1→$2→$4)
- Conviction-based scoring (no hard thresholds)
- VPIN, CVD, OFI, OBI, TCR computation
- Telegram alerts

### Phase 2: Multi-Agent Expansion
- Technical/Orderflow/Macro Analyst agents
- Bull/Bear researcher debate
- Facilitator verdict system
- Advisor Agent integration

### Phase 3: Self-Improvement
- Signal attribution tracking
- Dimension weight adjustment
- Regime detection
- Morning report generation

### Phase 4: Production
- Live Polymarket trading
- Backtest framework
- Performance dashboard

---

*Design v3.0 — PhD-level mathematical framework, pre-C1 analysis, fixed bet progression, $20 bankroll, conviction-based entry.*