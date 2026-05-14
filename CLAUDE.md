# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: BTC-15m Direction Predictor — Institutional Grade Trading System

Location: `/tmp/btc-predictor-v2/`

## Strategy (FIXED — never change)

Every 15 minutes: predict whether ≥2 of the next 3 candles (C2, C3, C4) will close GREEN or RED.

**Pre-C1 analysis method:** Analyze 1-2 minutes BEFORE C1 close using C0 (last completed candle) + live tick data. Execute bet at C2 open (≈15 min later) to get near-$0.50 Polymarket entry.

- GREEN = candle close > candle open
- RED = candle close < candle open
- 3-bet martingale: $1 → $2 → $4 (max loss $7, max profit $1)
- Win on any 1 of 3 bets

## Bet Sizing (FIXED — No Kelly)

```
Base bet: $1
On loss: $2 (2x base)
On second loss: $4 (4x base)

Bankroll: Start with $20. Use only profits for future bets. Never exceed $7 per session.
```

## Entry Decision (Conviction-Based — No Hard Thresholds)

```
ENTER if ALL of:
  1. Weighted conviction > 0.50
  2. ≥2 dimensions score > 0.65 OR < 0.35 (extreme supporting signals)
  3. No dimension score < 0.25 (no strong opposing signals)
  4. Pre-filter hard rules PASS
  5. VPIN < 0.70
  6. Advisor agrees OR confidence gap > 0.10

SKIP if ANY:
  - Conviction < 0.50
  - Only 1 dimension extreme, rest neutral
  - Strong opposing signal (dimension < 0.25)
  - VPIN > 0.70
```

## Six-Dimension Conviction Scoring

Each dimension scored 0–1 (0.5 = neutral):

| Dimension | Weight | Components |
|---|---|---|
| momentum | 0.25 | RSI, MACD histogram, price velocity |
| trend | 0.20 | Supertrend, ADX, BB position, EMA alignment |
| orderflow | 0.20 | VPIN, CVD, OFI, TCR, OBI |
| smart_money | 0.15 | funding rate, OI change, long/short ratio |
| sentiment | 0.10 | Fear&Greed zone, BTC dominance |
| macro | 0.10 | DXY, S&P 500, VIX |

```
Conviction = Σ (dimension_score × weight)
dimension_score = 0.5 + 0.5 × tanh(oscillator_value)
```

## Key Formulas (PhD-Level)

### VPIN
```
VPIN = (1/M) × Σ_{b=1}^{M} |V_b - V_s| / V_b
M = 50 (volume buckets). Higher = more institutional activity.
>0.50 = directional move likely. >0.70 = skip (too uncertain).
```

### CVD (Cumulative Volume Delta)
```
CVD = Σ (V_buy - V_sell) over 200 trades rolling
CVD divergence = price_slope opposite to CVD_slope = hidden pressure
```

### OFI (Order Flow Imbalance)
```
OFI = Σ (ΔBid_l - ΔAsk_l) × exp(-(l-1)/λ), L=5, λ=2
Normalized with tanh(OFI / σ_OFI)
```

### TCR (Trade Count Ratio)
```
TCR = (N_buy - N_sell) / (N_buy + N_sell)
>0.15 = strong buy aggression, <-0.15 = strong sell aggression
```

### OBI (Order Book Imbalance)
```
OBI = (Bid_total - Ask_total) / (Bid_total + Ask_total)
>0.25 = strong bid pressure, <-0.25 = strong ask pressure
```

## Architecture

### Agent System

```
src/agents/base/base_agent.py              — Agent ABC (call_llm, parse_signal_json)
src/agents/specialists/quant_master.py     — Momentum + Trend (hybrid code+LLM)
src/agents/specialists/flow_master.py      — Orderflow (hybrid code+LLM)
src/agents/specialists/macro_monarch.py    — Smart Money + Macro (hybrid code+LLM)
src/agents/specialists/sentiment_scout.py  — Sentiment (hybrid code+LLM)
src/agents/advisor.py                      — Independent cross-validator (Opus 4.7 + thinking)
src/agents/governor/governor.py            — Final decision: arithmetic + LLM synthesis
src/data_quality.py                        — Data quality gate (validates MarketState)
```

**Phase 2 changes:**
- Each specialist returns `dict[str, AgentSignal]` (one per dimension owned)
- Governor uses regime-adaptive weight profiles (`REGIME_WEIGHT_PROFILES`)
- Governor adds interaction terms: confirmation bonus, divergence penalty, consensus floor
- Governor LLM synthesis step calls Sonnet 4.6 for final judgment (10s timeout, falls back to arithmetic)

### Data Layer

```
src/data_sources/binance_client.py    — Binance WS + REST (SOCKS5 proxy supported)
src/features/market_state.py          — MarketStateAssembler
src/features/technical_indicators.py  — RSI, MACD, VWAP, BB, ATR, Supertrend, ADX, EMA
src/pre_filter.py                     — Hard rules (runs BEFORE agents)
src/session.py                         — 3-bet state machine, JSON persistence
src/dynamic_flip.py                    — Flip evaluation after C2/C3 loss
src/event_loop.py                     — Main orchestrator (15m cycle)
src/execution/polymarket_client.py    — Polymarket CLOB API
src/prediction_logger.py              — CSV logger + rolling stats + reflection
src/alerts/telegram_alerts.py         — Telegram bot
config/constants.py                    — All thresholds, API keys, paths
tests/                                — 79 tests (all passing)
```

### Conviction Scoring (Regime-Adaptive)

Default weights: momentum=0.25, trend=0.20, orderflow=0.20, smart_money=0.15, sentiment=0.10, macro=0.10

Profiles by regime (TRENDING_UP, RANGING, VOLATILE, RISK_ON, RISK_OFF, UNKNOWN):
- TRENDING: momentum + trend get higher weight
- RANGING: orderflow + smart_money get higher weight
- VOLATILE: orderflow + smart_money get higher weight

Interaction terms:
- Confirmation bonus: orderflow + momentum agree → +0.05 max
- Divergence penalty: any dimension gap > 0.30 → penalty
- Consensus bonus: all dims loosely agree → bonus

## Key Docs

- `SPEC.md` — Strategy source of truth
- `DESIGN.md` — Full architectural design (v3.0, PhD-level math, pre-C1 method)
- `CLAUDE.md` — This file

## Common Commands

```bash
# Run tests
pytest tests/ -v

# Run the predictor (paper trading)
python -m src.main

# Run with live trading
python -m src.main --live

# Run backtest
python src/backtest.py

# Quick analysis check
python -c "from src.features.market_state import MarketStateAssembler; from src.data_sources.binance_client import BinanceClient; ..."
```

## Pre-Filter Hard Rules

These run BEFORE any LLM call. Any trigger = SKIP:

1. **Session active** — wait for resolution
2. **Data stale** — > 60 seconds old
3. **No C0 candle** — no candle data available
4. **C0 doji** — body < 0.05% (no signal)
5. **C0 low volume** — RVOL < 0.7x
6. **VPIN toxic** — > 0.70 (institutional uncertainty)
7. **No trend** — ADX < 15
8. **Extreme funding** — > 0.15% (cascade risk)
9. **Signal vs trend conflict** — no counter-move exception
10. **Circuit breaker** — 3 consecutive losses + no edge

## Pre-C1 Analysis Timing

```
T-2:00  Begin analysis (C0 + live tick data)
T-0:30  Final conviction call + Polymarket order
T-0:00  C1 closes (order already placed at ≈C2 open price)
T+15:00 C2 closes → resolve bet
```

## Dynamic Flip

After C2/C3 loss, flip direction if ALL:
- Counter-signal > original + 0.15
- VPIN ≤ 0.60
- Advisor recommends (≥ 0.60 conf)
- ≥1 secondary: CVD divergence, funding reversal, technical breakdown

Cannot flip on C4 or during circuit breaker.

## Environment Variables

```
ANTHROPIC_API_KEY           — Main reasoning (Opus 4.7)
ANTHROPIC_ADVISOR_KEY       — Advisor Agent (Opus 4.7 max)
ANTHROPIC_BASE_URL          — API base (e.g., https://api.opusmax.pro)
POLYMARKET_WALLET_KEY       — For live trading
TELEGRAM_BOT_TOKEN          — Telegram bot
TELEGRAM_CHAT_ID            — Telegram chat
BINANCE_API_KEY/SECRET      — Binance (optional)
```

## Data Freshness Requirements

- Live trades (aggTrades): < 5 seconds
- Order book: < 5 seconds
- Funding rate: < 5 minutes (cached)
- Macro (Yahoo): < 15 minutes (cached)
- Fear & Greed: < 30 minutes (cached)