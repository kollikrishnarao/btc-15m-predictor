# BTC-15m Predictor

**Institutional-grade BTC 15-minute direction predictor powered by multi-agent LLM reasoning.**

Predict whether ≥2 of the next 3 BTC candles will close GREEN or RED, using a team of specialized AI agents with conviction-based decision making.

## Strategy

Every 15 minutes when a Binance candle closes:
- **Question:** Will ≥2 of the next 3 candles (C2, C3, C4) close GREEN or RED?
- **GREEN** = candle close > candle open | **RED** = candle close < candle open
- **3-bet martingale:** $1 → $2 → $4 (max loss $7, win on any 1 of 3)
- **Conviction-based entry** — no hard thresholds, weighted multi-dimensional scoring
- **No concurrent sessions**

## Architecture

The system uses a **9-agent multi-agent architecture** powered by Claude (Opus 4.7, Sonnet 4.6) via OpenMAX:

- **Governor** — Chief orchestrator, final decision authority
- **Quant Master** — Technical analysis (RSI, MACD, patterns, trend)
- **Flow Master** — Orderflow & microstructure (VPIN, CVD, OFI, TCR, OBI)
- **Macro Monarch** — Macro + smart money (DXY, funding, OI)
- **Sentiment Scout** — Fear & Greed, social, narratives
- **Advisor** — Independent cross-validation (Opus 4.7 max reasoning)
- **Researcher** — Daily research (papers, GitHub, X)
- **Coder** — Implementation of approved improvements
- **Security Reviewer** — Audit and risk validation

See [GOD_TIER_ARCHITECTURE.md](./GOD_TIER_ARCHITECTURE.md) for the full architecture design.

## Key Docs

| File | Purpose |
|------|---------|
| [SPEC.md](./SPEC.md) | Strategy source of truth — never changes |
| [DESIGN.md](./DESIGN.md) | Full v3.0 architectural design |
| [GOD_TIER_ARCHITECTURE.md](./GOD_TIER_ARCHITECTURE.md) | v4.0 god-tier architecture with 9 agents, 5 operating loops, MCP infrastructure |
| [CLAUDE.md](./CLAUDE.md) | Development guide for Claude Code |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env

# Run (paper trading)
python -m src.main

# Run with live trading
python -m src.main --live

# Run tests
pytest tests/ -v
```

## MCP Infrastructure

Purpose-built MCP servers connect agents to live data:
- **binance-mcp** — Klines, orderbook, trades, funding, OI
- **polymarket-mcp** — Market discovery, order placement, position tracking
- **news-mcp** — Fear & Greed, CryptoPanic, X/Twitter
- **memory-mcp** — Persistent knowledge graph for all agents

## Five Operating Loops

1. **Trading** (every 15 min) — Data → Filter → 6 specialists + Advisor → Governor → Polymarket
2. **Research** (every 24h) — arXiv, GitHub, X → Synthesize → Recommendations
3. **Improve** (triggered) — Plan → Code → Security review → Shadow deploy → Promote
4. **Monitor** (every 5 min) — Health, performance, risk → Alert
5. **Reflect** (after every session) — Log → Update memory → Adapt

## Risk Controls

- Pre-filter hard rules (10 deterministic checks before any LLM call)
- Conviction threshold gates (HIGH/MEDIUM/LOW confidence buckets)
- Max $7 loss per session, $50 daily loss limit
- Circuit breakers at 3 consecutive losses
- 20% drawdown halt

## License

MIT