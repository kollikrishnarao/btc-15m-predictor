# BTC-15m Predictor — God-Tier Architecture v4.0

**Version:** 4.0 | **Date:** 2026-05-11
**Status:** Pre-implementation | **Vision:** Autonomous, self-improving, institutional-grade trading system

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [The Team: 9 Specialized Agent Roles](#2-the-team-9-specialized-agent-roles)
3. [Agent Hierarchy & Communication Protocol](#3-agent-hierarchy--communication-protocol)
4. [The Five Operating Loops](#4-the-five-operating-loops)
5. [MCP Infrastructure Layer](#5-mcp-infrastructure-layer)
6. [Execution Pipeline: Data → Decision → Execution](#6-execution-pipeline-data--decision--execution)
7. [Memory Architecture: 4-Tier Knowledge System](#7-memory-architecture-4-tier-knowledge-system)
8. [Continuous Improvement Engine](#8-continuous-improvement-engine)
9. [Risk Control Framework](#9-risk-control-framework)
10. [Monitoring, Alerting & Observability](#10-monitoring-alerting--observability)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Implementation Phases](#12-implementation-phases)

---

## 1. Executive Summary

### What We're Building

An **autonomous, self-improving trading intelligence** that operates like a world-class quantitative hedge fund — staffed entirely by AI agents, powered by the most capable LLMs (Claude Opus 4.7, Sonnet 4.6, Grok 3), connected to live markets through a purpose-built MCP infrastructure.

The system is **not** a single AI making predictions. It is a **team of specialized agents**, each an expert in their domain, that collaborate, debate, cross-validate, and continuously learn. The team includes:

- **Researchers** who read papers and monitor GitHub daily, finding new techniques
- **Domain Experts** who own specific signal dimensions (orderflow, technicals, macro)
- **Planners** who decide what to improve and when
- **Code Executors** who implement changes with full test coverage
- **Security Reviewers** who audit every change before deployment
- **A Governor** who orchestrates all of this and makes final calls

### The Strategy (Fixed — Never Changes)

Every 15 minutes when C1 candle closes on Binance:
> **Will ≥2 of the next 3 candles (C2, C3, C4) close GREEN or RED?**

- GREEN = candle close > candle open
- RED = candle close < candle open
- 3-bet martingale: $1 → $2 → $4 (max loss $7, win on any 1 of 3)
- Conviction-based entry (no hard thresholds)
- No concurrent sessions
- Max $7 risk per session, $20 initial bankroll

### Why This Architecture is Different

| Traditional Trading Bot | This Architecture |
|---|---|
| Single model, single perspective | 9 specialized agents with distinct expertise |
| Static strategy, no learning | Continuous research → improvement pipeline |
| Hard-coded rules | Conviction-based, adaptive reasoning |
| No memory across sessions | 4-tier memory system with persistent knowledge |
| Manual updates by humans | Autonomous code improvement with validation |
| One pipeline | Parallel pipelines + shadow mode deployment |
| Siloed data | MCP-based unified data layer |

### The Core Innovation: Five Concurrent Loops

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    GOD-TIER OPERATING LAYER                              │
│                                                                         │
│  LOOP 1: TRADING CYCLE (every 15 min)                                  │
│    Data → Pre-Filter → Multi-Agent Analysis → Decision → Execution      │
│                                                                         │
│  LOOP 2: RESEARCH CYCLE (every 24 hours)                               │
│    Read Papers → Monitor GitHub → Scan X/Twitter → Apply Insights       │
│                                                                         │
│  LOOP 3: IMPROVEMENT CYCLE (triggered by Loop 2 or manual)            │
│    Plan → Code → Test → Security Review → Shadow Deploy → Promote      │
│                                                                         │
│  LOOP 4: MONITORING CYCLE (every 5 minutes)                           │
│    Check Health → Validate Performance → Detect Anomalies → Alert     │
│                                                                         │
│  LOOP 5: REFLECTION CYCLE (after every session)                        │
│    Log Outcome → Update Memory → Adjust Weights → Detect Regime Shifts │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The Team: 9 Specialized Agent Roles

### Agent 1: THE GOVERNOR (Chief Orchestrator)

**Model:** Claude Opus 4.7 (max reasoning)
**Tools:** All tools, all other agents, full system access
**Memory:** Full context, all other agents' outputs

```
Responsibilities:
- Owns the TRADING CYCLE (Loop 1)
- Coordinates all other agents
- Makes final trading decisions
- Decides when to activate IMPROVEMENT CYCLE
- Escalates to human when circuit breakers trip
- Reviews all agent outputs for coherence
- Maintains the 4-tier memory system
- Runs the REFLECTION CYCLE after every session

System Prompt Fragment:
"You are THE GOVERNOR of an autonomous trading intelligence.
You coordinate 8 specialist agents. Your role is to:
1. Orchestrate the 15-minute trading cycle with precision
2. Review outputs from all specialists and reconcile conflicts
3. Decide when the system needs self-improvement
4. Maintain institutional-grade discipline — no emotional trading
5. Protect the capital at all costs — the circuit breakers are sacred
6. Keep the memory system current and accurate

You have full system access. You delegate, you review, you decide.
The strategy is fixed: ≥2 of next 3 candles GREEN or RED.
You do not second-guess the strategy. You optimize the execution.
"
```

### Agent 2: THE QUANT (Technical Analysis Expert)

**Model:** Claude Sonnet 4.6 (balanced speed/intelligence)
**Specialty:** Candlestick patterns, technical indicators, momentum
**Triggered:** Every trading cycle + during research reviews
**Memory:** Historical pattern performance database

```
Responsibilities:
- Owns the MOMENTUM and TREND dimensions of conviction scoring
- Analyzes candlestick patterns (C1 and historical)
- Computes technical indicators (RSI, MACD, Bollinger Bands, VWAP, Supertrend, ADX, KDJ)
- Identifies divergences between price and indicators
- Maintains pattern performance history ("hammer patterns win 62% of the time")
- Participates in advisor debates with quantitative backing
- During research: identifies which new TA techniques could improve scoring

Signal Output Format:
{
  "dimension": "technical",
  "momentum_score": 0.72,      # 0-1, 0.5 = neutral
  "trend_score": 0.65,
  "confidence": 0.70,
  "key_signals": ["RSI-14 divergence", "MACD histogram turning positive", "BB squeeze breaking up"],
  "pattern_notes": "C1 is a hammer with 2.1% lower wick — historical win rate for this pattern: 58%",
  "contradictions": ["ADX only 18 — weak trend confirmation"]
}
```

### Agent 3: THE FLOW MASTER (Orderflow & Microstructure Expert)

**Model:** Claude Sonnet 4.6
**Specialty:** VPIN, CVD, OFI, TCR, OBI, market microstructure
**Triggered:** Every trading cycle + research on orderflow literature
**Memory:** Orderflow anomaly patterns, VPIN threshold calibration

```
Responsibilities:
- Owns the ORDERFLOW dimension of conviction scoring
- Computes VPIN (50 volume buckets), CVD (200-trade window), OFI, TCR, OBI
- Analyzes order book imbalance and depth gradient
- Detects institutional activity patterns (smart money traps, liquidity sweeps)
- Identifies CVD divergences from price action
- Monitors trade size distribution (whale vs retail)
- Participates in advisor debates with microstructure evidence

Signal Output Format:
{
  "dimension": "orderflow",
  "score": 0.78,
  "vpin": 0.62,
  "cvd": 234.5,
  "tcr": 0.12,
  "obi": 0.25,
  "institutional_activity": "HIGH",
  "key_signals": ["VPIN > 0.60 — directional move likely", "CVD rising while price flat — hidden accumulation"],
  "whale_alert": false,
  "contradictions": []
}
```

### Agent 4: THE MACRO MONARCH (Macro & Smart Money Expert)

**Model:** Claude Sonnet 4.6
**Specialty:** DXY, S&P 500, VIX, funding rates, OI, long/short ratios
**Triggered:** Every trading cycle + daily macro regime review
**Memory:** Macro regime history, funding rate signal calibration

```
Responsibilities:
- Owns SMART MONEY and MACRO dimensions of conviction scoring
- Analyzes funding rates (Binance futures) for cascade risk
- Monitors open interest changes (OI rising + price rising = confirmed)
- Evaluates long/short ratios from top traders
- Tracks perp premium/discount for basis signals
- Analyzes DXY, S&P 500, VIX for macro regime context
- Detects macro regime shifts (risk-on → risk-off transitions)
- Participates in advisor debates with macro context

Signal Output Format:
{
  "dimension": "macro_smart_money",
  "macro_score": 0.55,
  "smart_money_score": 0.68,
  "funding_rate": 0.0234,
  "oi_trend": "RISING",
  "long_short_ratio": 1.23,
  "dxy_change_pct": 0.12,
  "vix": 18.5,
  "regime": "RISK_ON",
  "key_signals": ["Funding 0.02% — neutral, no cascade risk", "OI rising + BTC flat — accumulation pattern"],
  "macro_warnings": ["DXY pushing toward 107 — watch for BTC headwind"],
  "contradictions": []
}
```

### Agent 5: THE SENTIMENT SCOUT (Market Sentiment & Narrative Analyst)

**Model:** Claude Sonnet 4.6
**Specialty:** Fear & Greed Index, social sentiment, narrative tracking
**Triggered:** Every trading cycle + continuous X/Twitter monitoring
**Memory:** Sentiment signal accuracy, narrative lifecycle patterns

```
Responsibilities:
- Owns SENTIMENT dimension of conviction scoring
- Fetches and interprets Fear & Greed Index
- Monitors X/Twitter for crypto sentiment via MCP integration
- Tracks social volume and narrative momentum
- Analyzes BTC dominance for rotation signals
- Participates in advisor debates with sentiment context
- During research: scans for new sentiment data sources

Signal Output Format:
{
  "dimension": "sentiment",
  "score": 0.48,
  "fear_greed_index": 42,
  "fear_greed_zone": "FEAR",
  "fear_greed_trend": "FALLING",
  "btc_dominance": 54.2,
  "narrative_signal": "cautious",
  "contrarian_opportunity": "EXTREME_FEAR zone — potential bounce setup",
  "key_signals": ["Fear & Greed in FEAR zone", "Narrative turning cautious"],
  "contradictions": []
}
```

### Agent 6: THE ADVISOR (Independent Cross-Validator)

**Model:** Claude Opus 4.7 (max reasoning, max thinking)
**Role:** Independent parallel analysis, debates with other agents
**Triggered:** Every trading cycle (runs parallel to main engine)
**Memory:** Historical advisor accuracy tracking

```
Responsibilities:
- Runs completely independent analysis from the main engine
- Uses all data sources simultaneously (no dimension ownership)
- Provides a "second opinion" that the Governor reconciles
- Engages in structured debates with specialist agents
- Tracks its own accuracy over time
- Escalates when it detects systemic issues

Output Format:
{
  "call": "GREEN | RED | SKIP",
  "confidence": 0.72,
  "strength": "HIGH | MEDIUM | LOW",
  "regime": "TRENDING_UP | TRENDING_DOWN | RANGING | VOLATILE",
  "key_signals": [...],
  "risk_flags": [...],
  "contradiction_flags": [...],
  "advisor_notes": "...",
  "disagreement_with_quant": "..."  // If disagrees with THE QUANT
}
```

### Agent 7: THE RESEARCHER (Daily Intelligence Analyst)

**Model:** Claude Sonnet 4.6
**Role:** Continuous technology and strategy research
**Triggered:** Loop 2 (every 24 hours) + on-demand
**Memory:** Research database, paper summaries, GitHub activity log

```
Daily Routine:
1. SCAN arXiv for new papers on: crypto trading, LLM trading agents, time series prediction, VPIN, market microstructure
2. SCAN GitHub for trending repos in: trading bots, crypto ML, multi-agent systems, MCP servers
3. MONITOR X/Twitter for posts from: @woonomic, @glassnode, @_intoTheblock, @cryptoquant, @nansen_ai, @pombo, @ai_sidekick
4. READ relevant blog posts, Medium articles, Substack posts
5. EVALUATE each finding:
   - Does it apply to our strategy?
   - What's the expected accuracy improvement?
   - What's the implementation complexity?
   - What's the risk of implementation?
6. PRODUCE actionable recommendations
7. UPDATE research database with summaries

Research Agent Output Format:
{
  "date": "2026-05-11",
  "papers_found": [...],
  "github_repos_found": [...],
  "x_insights": [...],
  "recommendations": [
    {
      "type": "NEW_TECHNIQUE | PARAMETER_TUNING | DATA_SOURCE | ARCHITECTURE_CHANGE",
      "title": "...",
      "source": "arXiv paper / GitHub repo / X post",
      "relevance_score": 0.85,
      "expected_improvement": "+2-5% directional accuracy",
      "implementation_effort": "LOW | MEDIUM | HIGH",
      "risk": "LOW | MEDIUM | HIGH",
      "action": "IMPLEMENT_NOW | BACKTEST | EVALUATE | DISCARD"
    }
  ]
}
```

### Agent 8: THE CODER (Implementation Agent)

**Model:** Claude Opus 4.7 (max reasoning)
**Role:** Code changes, refactoring, feature implementation
**Triggered:** Loop 3 (improvement cycle) or manual request
**Memory:** Codebase understanding, change history

```
Responsibilities:
- Implements Governor-approved improvements
- Writes clean, typed, tested Python code
- Maintains backward compatibility
- Updates CLAUDE.md, DESIGN.md, SPEC.md when architecture changes
- Runs full test suite before any deployment
- Produces detailed changelogs
- Implements with the philosophy: "small changes, validated fast"

Change Categories:
1. SIGNAL IMPROVEMENT: New indicators, new data sources, weight adjustments
2. RISK CONTROL: New circuit breakers, position limits, fail-safes
3. EFFICIENCY: Latency improvements, caching, parallelization
4. RELIABILITY: Error handling, retries, fallbacks
5. MONITORING: New metrics, new alerts, better logging

Change Protocol:
1. Governor approves the change (from Researcher's recommendation)
2. Coder implements in isolated branch
3. Coder runs full test suite
4. Coder produces PR with: what changed, why, how tested
5. Security Reviewer audits the PR
6. Governor approves merge
7. Shadow deployment (run new vs old in parallel for 24h)
8. If shadow shows improvement → promote to live
9. If shadow shows regression → rollback
```

### Agent 9: THE SECURITY REVIEWER (Risk & Compliance Officer)

**Model:** Claude Sonnet 4.6
**Role:** Audit all changes, validate risk controls, flag dangerous modifications
**Triggered:** Every code change before deployment + continuous monitoring
**Memory:** Known attack patterns, historical incidents, risk threshold database

```
Responsibilities:
- Reviews every code change before deployment
- Validates that risk controls are not weakened
- Checks for: API key exposure, hardcoded secrets, unsafe deserialization
- Validates: position sizing, circuit breakers, drawdown limits
- Monitors: real-time P&L, error rates, latency anomalies
- Conducts: weekly security audits, penetration tests (automated)
- Maintains: incident response playbook, rollback procedures
- Flags: any change that violates the fixed strategy rules

Security Review Checklist:
□ No hardcoded API keys or secrets
□ All external API calls have timeouts
□ All exceptions are caught and logged
□ No unsafe eval() or exec() calls
□ Position sizing respects max bet limits ($7 per session)
□ Circuit breakers cannot be bypassed
□ All state changes are logged immutably
□ Rollback procedure tested and documented
```

---

## 3. Agent Hierarchy & Communication Protocol

### The Org Chart

```
                    ┌──────────────────────────────┐
                    │         THE GOVERNOR          │
                    │   (Chief Orchestrator)        │
                    │   Claude Opus 4.7            │
                    │   Owns: Loops 1, 5           │
                    └──────────┬───────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
   ┌────▼────┐           ┌────▼─────┐           ┌────▼─────┐
   │  QUANT  │           │   FLOW   │           │  MACRO   │
   │ MASTER  │           │  MASTER  │           │ MONARCH  │
   │ Sonnet  │           │  Sonnet  │           │  Sonnet  │
   └────┬────┘           └────┬─────┘           └────┬─────┘
        │                      │                     │
        └──────────────────────┼─────────────────────┘
                               │
                    ┌──────────▼───────────┐
                    │       ADVISOR        │
                    │   Opus 4.7 (max)     │
                    │  Cross-validator     │
                    └──────────┬───────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
   ┌────▼────┐           ┌────▼─────┐           ┌────▼─────┐
   │SENTIMENT│           │RESEARCHER│           │  CODER   │
   │  SCOUT  │           │  Sonnet  │           │  Opus    │
   │  Sonnet │           │  Loop 2  │           │  Loop 3  │
   └─────────┘           └────┬─────┘           └────┬─────┘
                              │                      │
                              └──────────┬───────────┘
                                         │
                               ┌──────────▼───────────┐
                               │ SECURITY REVIEWER   │
                               │      Sonnet         │
                               │  Loop 3 gatekeeper  │
                               └─────────────────────┘

           ═══════════════════════════════════════════════
                           HUMAN OPERATOR
                    (Receives alerts, can override,
                     reviews weekly performance reports)
           ═══════════════════════════════════════════════
```

### Communication Protocol

**Message Types:**

```python
class AgentMessage:
    """Standard message format between agents."""
    sender: str          # "GOVERNOR", "QUANT", "FLOW_MASTER", etc.
    recipient: str | "BROADCAST"
    message_type: str    # "SIGNAL", "DECISION", "REQUEST", "ALERT", "DEBATE"
    payload: dict        # Structured data (see per-agent output formats)
    timestamp: datetime
    priority: str        # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    requires_response: bool


class AgentSignal(Message):
    """Specialized signal output from dimension agents."""
    dimension: str
    score: float
    confidence: float
    signals: list[str]
    contradictions: list[str]
    regime: str


class GovernorDecision(Message):
    """Final trading decision from Governor."""
    call: str             # "GREEN", "RED", "SKIP"
    confidence: float
    reasoning: str
    specialist_inputs: dict[str, AgentSignal]
    advisor_opinion: dict
    risk_assessment: str
    action: str          # "PLACE_BET", "HOLD", "FLIP", "ABORT"


class DebateTurn(Message):
    """Structured debate between agents."""
    topic: str            # "QUANT vs ADVISOR on momentum direction"
    agent_1_position: str
    agent_2_position: str
    evidence_1: list[str]
    evidence_2: list[str]
    resolution: str        # "AGREED", "DISAGREED — GOVERNOR BREAKS TIE"


class Alert(Message):
    """Alert to human operator."""
    severity: str         # "INFO", "WARNING", "CRITICAL"
    category: str         # "RISK", "ERROR", "IMPROVEMENT", "SECURITY"
    message: str
    action_required: bool
    auto_resolved: bool
```

### Message Flow During Trading Cycle (Loop 1)

```
T-0:02:00 — C1 candle approaching close
    GOVERNOR → BROADCAST: "Analysis cycle beginning. Prepare signals."
    QUANT → GOVERNOR: [SIGNAL] momentum=0.72, trend=0.65
    FLOW_MASTER → GOVERNOR: [SIGNAL] orderflow=0.78, VPIN=0.62
    MACRO_MONARCH → GOVERNOR: [SIGNAL] macro=0.55, smart_money=0.68
    SENTIMENT_SCOUT → GOVERNOR: [SIGNAL] sentiment=0.48

T-0:01:30 — All signals received
    GOVERNOR → ADVISOR: "Analyze independently. Return your call."
    ADVISOR → GOVERNOR: [DECISION] call=GREEN, confidence=0.72, strength=HIGH

T-0:01:00 — Governor reconciles
    GOVERNOR: [Internal deliberation]
    - Pre-filter passed
    - Conviction: 0.68 (GREEN)
    - Advisor agrees (GREEN, 0.72)
    - All dimensions score between 0.48-0.78 (no strong opposing)
    - Decision: ENTER with GREEN, confidence=0.68

T-0:00:30 — Governor places order
    GOVERNOR → EXECUTION_ENGINE: [ACTION] PLACE_BET GREEN @ C2_open

T+0:00:00 — C1 candle closes
    EXECUTION_ENGINE → GOVERNOR: [CONFIRMATION] Bet placed on C2
    GOVERNOR → HUMAN: [ALERT] Session started: GREEN, confidence=0.68

T+0:15:00 — C2 candle closes
    GOVERNOR → EXECUTION_ENGINE: "Resolve C2."
    EXECUTION_ENGINE → GOVERNOR: C2=GREEN, bet=WIN → SESSION WON
    GOVERNOR → HUMAN: [ALERT] Session won on C2, PnL=+$X
    GOVERNOR → ALL: "Run reflection cycle."
    GOVERNOR → RESEARCHER: "Log this outcome in memory."
```

---

## 4. The Five Operating Loops

### Loop 1: Trading Cycle (Every 15 Minutes)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LOOP 1: TRADING CYCLE                                │
│                         (Every 15 minutes)                              │
└─────────────────────────────────────────────────────────────────────────┘

PHASE 1: DATA ASSEMBLY (parallel, <5 seconds)
────────────────────────────────────────────────
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Binance    │ │   Binance    │ │   Binance    │ │   External   │
│  WS: candles │ │  WS: trades  │ │  REST: OI,   │ │   Sources:    │
│  WS: depth   │ │  orderbook    │ │  funding,    │ │ Fear&Greed,  │
│              │ │              │ │  long/short  │ │ DXY, VIX     │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │                │
       └────────────────┴────────────────┴────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │  MarketState     │
                     │  ASSEMBLER       │
                     │  Produces single │
                     │  enriched packet │
                     └────────┬─────────┘
                              │
PHASE 2: PRE-FILTER (<1 second)
────────────────────────────────────────
                              │
                              ▼
              ┌───────────────────────────┐
              │    PRE-FILTER (deterministic rules)   │
              │                           │
              │  • Session active? → SKIP │
              │  • Data stale? → SKIP     │
              │  • C1 doji? → SKIP        │
              │  • RVOL < 0.7x? → SKIP    │
              │  • VPIN > 0.75? → SKIP    │
              │  • ADX < 15? → SKIP       │
              │  • Funding > 0.15%? → SKIP│
              │  • Trend conflict? → SKIP │
              │  • 3 losses + no edge? →SKIP│
              └────────────┬──────────────┘
                           │ PASSED
                           ▼
PHASE 3: PARALLEL ANALYSIS (<30 seconds)
────────────────────────────────────────
              ┌─────────────────────────────┐
              │        GOVERNOR              │
              │  (Orchestrates analysis)     │
              └────────────┬─────────────────┘
                           │
     ┌─────────────────────┼─────────────────────┐
     │                     │                     │
     ▼                     ▼                     ▼
┌─────────┐         ┌───────────┐         ┌──────────┐
│  QUANT  │         │FLOW_MASTER│         │  MACRO   │
│  MASTER │         │           │         │ MONARCH  │
│         │         │           │         │          │
│Output:  │         │Output:    │         │Output:   │
│momentum │         │orderflow  │         │macro +   │
│trend    │         │score      │         │smart_money│
└────┬────┘         └─────┬─────┘         └────┬────┘
     │                     │                     │
     │    ALL SIGNALS ──────┴─────────────────────┤
     │                     │                     │
     │                     ▼                     │
     │              ┌───────────┐                │
     │              │  ADVISOR  │                │
     │              │(Opus 4.7) │                │
     │              │           │                │
     │              │Independent│                │
     │              │analysis   │                │
     │              │Output:    │                │
     │              │GREEN/RED/ │                │
     │              │SKIP       │                │
     │              │confidence │                │
     │              └─────┬─────┘                │
     │                    │                     │
PHASE 4: RECONCILIATION
────────────────────────────────────────────────
     │                    │                     │
     └────────────────────┴──────────────────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │       GOVERNOR        │
                   │                      │
                   │  1. Weight specialist │
                   │     signals by       │
                   │     conviction       │
                   │  2. Reconcile with   │
                   │     Advisor opinion   │
                   │  3. Apply confidence │
                   │     gates            │
                   │  4. Make final call  │
                   └──────────┬───────────┘
                              │
                    ┌─────────┴─────────┐
                    │                  │
                 GREEN/RED           SKIP
                    │                  │
                    ▼                  ▼
PHASE 5: EXECUTION
────────────────────────────────────────────────
              ┌──────────────┐
              │   POLYMARKET │
              │   EXECUTOR   │
              │              │
              │  1. Discover │
              │     market   │
              │  2. Check    │
              │     spread   │
              │  3. Compute  │
              │     bet size │
              │  4. Place    │
              │     order   │
              │  5. Track   │
              └──────┬───────┘
                     │
PHASE 6: RESOLUTION
────────────────────────────────────────────────
                     │
         ┌───────────┴───────────┐
         │                       │
    Bet on C2             Wait for C2
         │              candle close
         ▼                       │
    ┌─────────┐                  │
    │ Wait 15 │                  │
    │  minutes │                  │
    └────┬────┘                  │
         │              ┌───────┴───────┐
         └──────────────►│   RESOLVE     │
                         │ C2/GREEN?     │
                         │ → WIN → END  │
                         │ → LOSS →     │
                         │   Check flip │
                         │   conditions │
                         └──────────────┘

PHASE 7: REFLECTION (Loop 5 triggered)
────────────────────────────────────────────────
              ┌──────────────┐
              │    GOVERNOR   │
              │   runs Loop 5 │
              │  after every  │
              │   session     │
              └──────────────┘
```

### Loop 2: Research Cycle (Every 24 Hours)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LOOP 2: RESEARCH CYCLE                              │
│                         (Every 24 hours)                                │
└─────────────────────────────────────────────────────────────────────────┘

TRIGGER: Cron job at 00:00 UTC (or manual trigger)
────────────────────────────────────────────────────────────

STEP 1: PAPER SCANNING (30 minutes)
─────────────────────────────────────
RESEARCHER → WebSearch:
  Query 1: arXiv cs.AI crypto trading LLM 2026
  Query 2: arXiv q-fin.TR market microstructure prediction
  Query 3: arXiv cs.LG time series binary classification
  Query 4: "VPIN" OR "CVD" OR "order flow imbalance" prediction

For each paper found:
  RESEARCHER → WebFetch: Read paper abstract
  If relevant: RESEARCHER → WebFetch: Read full paper
  RESEARCHER → Memory: Store summary + relevance score

STEP 2: GITHUB MONITORING (20 minutes)
────────────────────────────────────────
RESEARCHER → WebSearch:
  Query 1: site:github.com trending crypto trading bot 2026
  Query 2: site:github.com multi-agent LLM trading
  Query 3: site:github.com BTC prediction ML

For each repo found:
  RESEARCHER → WebFetch: Read README, architecture docs
  If relevant: RESEARCHER → Analyze code patterns
  RESEARCHER → Memory: Store repo summary + applicability

STEP 3: X/TWITTER SENTIMENT (15 minutes)
────────────────────────────────────────
RESEARCHER → MCP: Fetch latest posts from watched accounts
  @woonomic, @glassnode, @_intoTheblock, @cryptoquant,
  @nansen_ai, @ai_sidekick, @pombo, @will_h_o_u_r

For each post:
  RESEARCHER: Extract key insights
  RESEARCHER → Memory: Store with timestamp + source

STEP 4: SYNTHESIS & RECOMMENDATIONS (15 minutes)
─────────────────────────────────────────────────
RESEARCHER: Combines all findings into structured report
RESEARCHER → GOVERNOR: [RESEARCH_REPORT]

GOVERNOR reviews report:
  For each IMPLEMENT_NOW recommendation:
    → Triggers Loop 3 (Improvement Cycle)
  For each BACKTEST recommendation:
    → Schedules backtest, reviews results next day
  For each EVALUATE recommendation:
    → Adds to evaluation queue
  For each DISCARD:
    → Logs reason, ignores

STEP 5: MEMORY UPDATE (10 minutes)
─────────────────────────────────────
RESEARCHER → Memory: Update research database
  - Papers read this cycle
  - Repos monitored
  - X insights collected
  - Recommendations made
  - Recommendations accepted/rejected
```

### Loop 3: Improvement Cycle (Triggered by Loop 2 or Manual)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LOOP 3: IMPROVEMENT CYCLE                            │
│                   (Triggered by Governor or manual)                    │
└─────────────────────────────────────────────────────────────────────────┘

TRIGGER: New research recommendation or Governor-initiated
────────────────────────────────────────────────────────────────────────

STAGE 1: PLANNING (Governor reviews, 10 minutes)
──────────────────────────────────────────────────
GOVERNOR reviews recommendation:
  - What exactly changes?
  - What's the expected improvement?
  - What's the risk?
  - What's the implementation effort?

GOVERNOR decision: APPROVE | REJECT | NEEDS_BACKTEST

If APPROVED:
  GOVERNOR → CODER: "Implement change: [description]"
  GOVERNOR → SECURITY_REVIEWER: "Prepare to review: [description]"

If REJECTED:
  GOVERNOR → Memory: Log rejection reason

If NEEDS_BACKTEST:
  GOVERNOR → CODER: "Run backtest first. Report results."
  [Backtest runs, results reviewed, then decision]

STAGE 2: IMPLEMENTATION (Coder, varies by change size)
─────────────────────────────────────────────────────────
CODER creates isolated branch: feature/[change-name]

CODER implements change:
  - Code changes
  - Unit tests
  - Integration tests
  - Documentation updates

CODER → CODER: Run full test suite
  If tests pass → proceed
  If tests fail → fix, re-run

CODER → GOVERNOR: "Implementation complete. PR ready for review."

STAGE 3: SECURITY REVIEW (Security Reviewer, 20 minutes)
───────────────────────────────────────────────────────────
SECURITY_REVIEWER reads PR diff
SECURITY_REVIEWER runs security checklist
SECURITY_REVIEWER validates risk controls not weakened

If PASSES:
  SECURITY_REVIEWER → GOVERNOR: "Approved for shadow deployment."

If FAILS:
  SECURITY_REVIEWER → CODER: "Security issues found: [list]"
  CODER fixes issues
  Re-review

STAGE 4: SHADOW DEPLOYMENT (24-48 hours)
───────────────────────────────────────────
Governor activates shadow mode:
  - Live system runs current code
  - Shadow system runs new code
  - Both receive same market data
  - Shadow makes decisions but doesn't execute
  - Governor logs both decisions for comparison

After 24 hours:
  Governor compares results:
    If shadow > live by >2%:
      → Promote shadow to live
    If shadow > live by <2%:
      → Continue shadow for 24 more hours
    If shadow < live:
      → Rollback, log lesson learned

STAGE 5: PROMOTION (Governor decision)
────────────────────────────────────────
If shadow outperforms:
  Governor → CODER: "Merge to main. Deploy."
  Governor → Memory: "Log change: [description], improvement: [X%]"
  Governor → HUMAN: "System updated: [change summary]"

If shadow underperforms:
  Governor → CODER: "Rollback. Log regression."
  Governor → Memory: "Log rollback: [description], regression: [X%]"
```

### Loop 4: Monitoring Cycle (Every 5 Minutes)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LOOP 4: MONITORING CYCLE                            │
│                         (Every 5 minutes)                               │
└─────────────────────────────────────────────────────────────────────────┘

MONITOR runs continuously, checking:
─────────────────────────────────────

HEALTH CHECKS:
  □ Is Binance WebSocket connected?
  □ Is Polymarket API responding?
  □ Are all agents healthy (last heartbeat <5 min ago)?
  □ Is the memory system accessible?
  □ Are log files being written?

PERFORMANCE CHECKS:
  □ Win rate over last 20 sessions (flag if <45%)
  □ Consecutive losses (flag at 2, halt at 3)
  □ Average session P&L
  □ Latency of data assembly (flag if >30 seconds)
  □ Latency of agent responses (flag if >60 seconds)

RISK CHECKS:
  □ Current drawdown vs max allowed
  □ Total sessions today (flag if >20)
  □ Bet sizes within limits
  □ No circuit breakers bypassed

ALERT if any metric is anomalous:
  INFO: "Win rate dropped to 47%, still above threshold"
  WARNING: "Win rate dropped to 43%, approaching halt"
  CRITICAL: "3 consecutive losses, session halted"
```

### Loop 5: Reflection Cycle (After Every Session)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LOOP 5: REFLECTION CYCLE                            │
│                     (After Every Trading Session)                       │
└─────────────────────────────────────────────────────────────────────────┘

TRIGGER: Session ends (WIN or LOSS)
─────────────────────────────────────

STEP 1: LOG OUTCOME (automatic)
─────────────────────────────────
  → Log to predictions.csv
  → Log to performance database
  → Update rolling win rate
  → Update consecutive win/loss counters
  → Update reflection context

STEP 2: ANALYZE OUTCOME (Governor, 30 seconds)
────────────────────────────────────────────────
Governor asks:
  - Did we predict correctly?
  - What was the confidence?
  - Did the Advisor agree?
  - Were there any contradictions?
  - Did the flip logic work (if applicable)?
  - What would have improved this prediction?

Governor produces reflection notes:
  - "High confidence GREEN but lost. Momentum signals were misleading here."
  - "Advisor disagreed and was right. Need to weight Advisor higher."
  - "Flip logic correctly detected reversal."

STEP 3: UPDATE MEMORY (automatic)
─────────────────────────────────────
Governor → Memory:
  - Append this session to last_20_outcomes
  - Update rolling win rate
  - Update regime detection
  - Update signal accuracy tracking

Memory entries:
  - Dimension accuracy: "orderflow signals have been right 72% of the time"
  - Advisor accuracy: "Advisor has been right 65% of the time when I was wrong"
  - Pattern performance: "Hammer patterns win 61% of the time in current regime"
  - Regime: "Market shifted from TRENDING_UP to RANGING on 2026-05-10"

STEP 4: ADAPT WEIGHTS (Governor, after 20+ sessions)
─────────────────────────────────────────────────────
After every 20 sessions:
  Governor analyzes which dimensions predicted best:
    If orderflow > momentum:
      → Increase orderflow weight by 0.05
      → Decrease momentum weight by 0.05
    If Advisor accuracy > 70%:
      → Increase Advisor weight in reconciliation
    If flip logic losing more than winning:
      → Tighten flip conditions

  Governor logs weight changes to memory

STEP 5: DETECT REGIME SHIFTS (Governor, continuous)
─────────────────────────────────────────────────────
Governor monitors for regime changes:
  - Win rate shift (trending vs ranging)
  - ADX average changes
  - Funding rate regime changes
  - Macro environment changes

If regime shift detected:
  Governor → HUMAN: "Regime shift detected: [OLD] → [NEW]"
  Governor adjusts conviction thresholds for new regime
  Governor logs regime change to memory
```

---

## 5. MCP Infrastructure Layer

### The MCP Vision

**MCP (Model Context Protocol)** is the standardized way for AI agents to connect to external tools and data sources. We will build a **suite of purpose-built MCP servers** that give every agent in our system access to live market data, research tools, and execution capabilities.

### MCP Server Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENTS (Claude, Grok, etc.)                      │
│                                                                          │
│   Governor ──► Advisor ──► Quant ──► FlowMaster ──► MacroMonarch        │
│       │                                                           │       │
│       │                    (All agents use MCP clients)         │       │
└───────│───────────────────────────────────────────────────────────|───────┘
        │                         │                                  │
        ▼                         ▼                                  ▼
┌───────────────┐      ┌─────────────────┐             ┌──────────────────┐
│  MCP Client   │      │   MCP Client    │             │   MCP Client    │
│ (Python SDK)   │      │   (Python SDK)  │             │   (Python SDK)  │
└───────┬───────┘      └────────┬────────┘             └────────┬─────────┘
        │                       │                                 │
        └───────────────────────┼─────────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
    ┌──────────────────┐ ┌──────────────┐ ┌─────────────────┐
    │   binance-mcp    │ │ polymarket-mcp│ │   news-mcp      │
    │                  │ │              │ │                 │
    │  • get_klines()  │ │ • find_markets()│ │ • fetch_news() │
    │  • get_orderbook │ │ • place_order()│ │ • search_news()│
    │  • get_trades()  │ │ • get_positions│ │ • get_crypto_  │
    │  • get_funding() │ │ • redeem()     │ │   panic()      │
    │  • get_oi()      │ │               │ │                │
    │  • get_ticker()  │ │               │ │                │
    └──────────────────┘ └───────────────┘ └─────────────────┘
              │                 │                 │
              ▼                 ▼                 ▼
    ┌─────────────────────────────────────────────────────────┐
    │              External Data Sources                       │
    │                                                          │
    │  Binance ──► Polymarket ──► Fear&Greed ──► Yahoo ──► X │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
```

### MCP Server 1: binance-mcp

**Purpose:** Connect all agents to Binance market data and execution

```python
# MCP Server: binance-mcp
# Protocol: stdio (local) or HTTP/SSE (remote)
# Auth: API key/secret for authenticated endpoints

@tool
def get_klines(symbol: str, interval: str, limit: int) -> list[dict]:
    """
    Fetch OHLCV candlestick data from Binance.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        interval: Kline interval (e.g., "15m", "1h", "4h", "1d")
        limit: Number of candles (max 1000)

    Returns:
        list of candles: [{open, high, low, close, volume, close_time}, ...]
    """
    # Fetches from Binance REST API
    # Caches results for 5 seconds to avoid rate limits
    pass

@tool
def subscribe_klines(symbol: str, interval: str) -> AsyncIterator[dict]:
    """
    Subscribe to real-time kline stream via WebSocket.

    Yields:
        Real-time candle updates as they occur
    """
    pass

@tool
def get_orderbook(symbol: str, limit: int) -> dict:
    """
    Fetch order book depth.

    Returns:
        {bids: [(price, qty), ...], asks: [(price, qty), ...]}
    """
    pass

@tool
def get_recent_trades(symbol: str, limit: int) -> list[dict]:
    """
    Fetch recent aggregate trades (trade, price, qty, is_buyer_maker).

    Used for: VPIN, CVD, OFI computation
    """
    pass

@tool
def get_funding_rate(symbol: str) -> dict:
    """
    Fetch current funding rate for perpetual futures.

    Returns:
        {rate_pct: float, next_funding_time: datetime}
    """
    pass

@tool
def get_open_interest(symbol: str) -> dict:
    """
    Fetch open interest data.

    Returns:
        {open_interest_btc: float, change_24h: float}
    """
    pass

@tool
def get_ticker(symbol: str) -> dict:
    """
    Fetch 24h ticker statistics.

    Returns:
        {last_price, volume_24h, quote_volume_24h, price_change_pct}
    """
    pass

@tool
def get_long_short_ratio(symbol: str) -> dict:
    """
    Fetch top traders long/short ratio.

    Returns:
        {long_short_ratio: float, long_account_ratio: float}
    """
    pass
```

### MCP Server 2: polymarket-mcp

**Purpose:** Connect all agents to Polymarket markets and execution

```python
# MCP Server: polymarket-mcp
# Protocol: stdio (local) or HTTP/SSE (remote)

@tool
def find_markets(query: str, filter: dict) -> list[dict]:
    """
    Search for prediction markets.

    Args:
        query: Search query (e.g., "BTC 15 minute")
        filter: {active: bool, min_liquidity: float, max_spread: float}

    Returns:
        [{condition_id, question, outcomes, prices, liquidity, end_date}, ...]
    """
    pass

@tool
def get_orderbook(token_id: str) -> dict:
    """
    Get CLOB order book for a specific token.

    Returns:
        {bids: [(price, size, order_id), ...],
         asks: [(price, size, order_id), ...],
         spread: float}
    """
    pass

@tool
def place_order(token_id: str, side: str, size: float, price: float,
                wallet_key: str) -> dict:
    """
    Place an order on Polymarket CLOB.

    Args:
        token_id: CLOB token ID
        side: "BUY" or "SELL"
        size: Number of shares
        price: Price per share (0-1)
        wallet_key: Wallet private key for signing

    Returns:
        {order_id, filled_price, filled_size, fee, status}
    """
    pass

@tool
def get_positions(wallet_address: str) -> list[dict]:
    """
    Get current open positions.

    Returns:
        [{token_id, outcome, size, avg_price, current_price, pnl}, ...]
    """
    pass

@tool
def redeem_position(position_id: str, wallet_key: str) -> dict:
    """
    Redeem a winning position.

    Returns:
        {redeemed_amount: float, fee: float}
    """
    pass

@tool
def get_market_history(condition_id: str) -> list[dict]:
    """
    Get historical resolution data for a market.

    Used for backtesting: what was the actual outcome?
    """
    pass
```

### MCP Server 3: news-mcp

**Purpose:** Connect agents to news, sentiment, and social media data

```python
# MCP Server: news-mcp
# Sources: CryptoPanic, Fear&Greed API, X/Twitter (via RSS alternatives)

@tool
def get_fear_greed_index() -> dict:
    """
    Fetch current Fear & Greed Index.

    Returns:
        {value: int, category: str, trend: str, timestamp: datetime}
    """
    pass

@tool
def search_news(query: str, limit: int) -> list[dict]:
    """
    Search crypto news via CryptoPanic.

    Returns:
        [{title, source, published_at, sentiment, url}, ...]
    """
    pass

@tool
def get_social_sentiment(coin: str) -> dict:
    """
    Fetch social sentiment for a coin.

    Returns:
        {twitter_sentiment, reddit_sentiment, social_volume, trend}
    """
    pass

@tool
def fetch_x_feed(username: str) -> list[dict]:
    """
    Fetch recent posts from an X account.

    Uses RSS alternatives (xcancel, nitter instances) or X API.

    Returns:
        [{content, published_at, likes, retweets, url}, ...]
    """
    pass
```

### MCP Server 4: memory-mcp

**Purpose:** Persistent knowledge graph and memory for all agents

```python
# MCP Server: memory-mcp
# Backend: PostgreSQL + Redis + Vector DB (Chroma)

@tool
def store_fact(key: str, value: dict, ttl: int) -> bool:
    """
    Store a fact in the knowledge graph.

    Args:
        key: Unique key (e.g., "signal_accuracy/orderflow/2026-05")
        value: {fact, confidence, source, timestamp}
        ttl: Time to live in seconds (0 = forever)
    """
    pass

@tool
def recall_facts(query: str, limit: int) -> list[dict]:
    """
    Semantic recall of stored facts.

    Args:
        query: Natural language query
        limit: Max results

    Returns:
        [{key, fact, relevance_score, timestamp}, ...]
    """
    pass

@tool
def append_to_sequence(key: str, item: dict) -> int:
    """
    Append an item to a sequence (e.g., last_20_outcomes).

    Maintains max length, evicts oldest when full.
    """
    pass

@tool
def get_sequence(key: str) -> list[dict]:
    """
    Get a full sequence (e.g., last_20_outcomes).
    """
    pass

@tool
def update_counter(key: str, delta: int) -> int:
    """
    Atomically increment/decrement a counter.
    Used for: consecutive_wins, consecutive_losses, total_sessions
    """
    pass
```

---

## 6. Execution Pipeline: Data → Decision → Execution

### End-to-End Flow

```
T-2:00 ────────────────────────────────────────────────────────────────── T+0:00 ── T+0:15 ── T+0:30 ── T+0:45 ──
   │                                                                                      │
   ▼                                                                                      │
┌─────────────────────────────────────────────────────────────────────────┐               │
│                     DATA ASSEMBLY PHASE                                  │               │
│                                                                                              │
│  Parallel fetch (target: <5 seconds):                                             │
│    • Binance WS: klines, aggTrades, orderbook depth                                  │
│    • Binance REST: funding, OI, long/short, ticker                                   │
│    • Fear & Greed API                                                                  │
│    • Yahoo Finance: DXY, SP500, VIX                                                    │
│                                                                                          │
│  Output: MarketState packet — single enriched data object                            │
└──────────────────────────────────────┬──────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     PRE-FILTER PHASE                                     │
│                                                                              │
│  Deterministic rules (target: <1 second):                                   │
│    1. Session active? → SKIP immediately                                    │
│    2. Data stale (>60s)? → SKIP                                            │
│    3. C1 doji (body <0.1%)? → SKIP                                         │
│    4. Low volume (RVOL <0.7x)? → SKIP                                      │
│    5. VPIN toxic (>0.75)? → SKIP                                           │
│    6. No trend (ADX <15)? → SKIP                                           │
│    7. Extreme funding (>0.15%)? → SKIP                                     │
│    8. Trend conflict? → SKIP                                               │
│    9. 3 losses + no edge? → SKIP                                           │
│                                                                              │
│  Output: PASS/FAIL with reason                                             │
└──────────────────────────────────────┬────────────────────────────────────┘
                                       │ PASSED
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     PARALLEL ANALYSIS PHASE                               │
│                      (target: <30 seconds)                                │
│                                                                              │
│  QUANT ─────────┐                                                         │
│  (Sonet)        │                                                         │
│  • RSI, MACD    │                                                         │
│  • Patterns     │                                                         │
│  • Momentum     │                                                         │
│  • Trend        │                                                         │
│                 │                                                         │
│  FLOW_MASTER ───┼──► SPECIALIST                                           │
│  (Sonnet)       │    SIGNALS                                             │
│  • VPIN, CVD    │    ─────────────► GOVERNOR ◄───────────── ADVISOR      │
│  • OFI, TCR     │           (Opus 4.7, max reasoning)                      │
│  • Orderbook    │                                                         │
│                 │                                                         │
│  MACRO_MONARCH ├─► Combine + reconcile                                    │
│  (Sonnet)       │    • Weighted conviction score                          │
│  • Funding      │    • Advisor reconciliation                             │
│  • OI, LS ratio │    • Confidence bucket determination                    │
│  • DXY, VIX     │                                                         │
│                 │                                                         │
│  SENTIMENT_SCOUT┘                                                         │
│  (Sonnet)       │                                                         │
│  • Fear&Greed   │                                                         │
│  • Social       │                                                         │
│  • BTC dominance│                                                         │
│                                                                              │
│  ADVISOR ───────┘                                                         │
│  (Opus 4.7)                                                               │
│  • Independent                                                             │
│    analysis                                                               │
│  • Full context                                                           │
│  • Debate-ready                                                           │
│                                                                              │
│  GOVERNOR (Opus 4.7):                                                     │
│    1. Aggregate specialist signals                                        │
│    2. Compute weighted conviction                                         │
│    3. Reconcile with Advisor                                              │
│    4. Apply confidence gates                                              │
│    5. Make final call: GREEN / RED / SKIP                                 │
└──────────────────────────────────────┬────────────────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │                                     │
                 GREEN/RED                            SKIP
                    │                                     │
                    ▼                                     ▼
┌────────────────────────────────────────┐  ┌────────────────────────────┐
│           EXECUTION PHASE               │  │         IDLE                │
│                                          │  │                             │
│  Governor → Polymarket MCP:             │  │  Wait for next C1 close    │
│    • Discover BTC market                │  │  (next 15-minute cycle)    │
│    • Check orderbook spread             │  │                             │
│    • Compute Kelly bet size             │  │                             │
│    • Sign + place order                 │  │                             │
│                                          │  │                             │
│  Governor → Telegram:                   │  │                             │
│    "Session started: GREEN @ 0.68 conf  │  │                             │
│     Bet placed: C2, $X @ market price"  │  │                             │
│                                          │  │                             │
│  Governor → Memory:                      │  │                             │
│    Log session start, expected outcome   │  │                             │
└─────────────────────────────────────────┘  └─────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     RESOLUTION PHASE                                     │
│                     (15-45 minutes later)                               │
│                                                                         │
│  C2 candle closes ──► Governor resolves bet ──► WIN or LOSS             │
│                                                                         │
│  If WIN:                                                               │
│    • Log session WON                                                   │
│    • Calculate P&L                                                     │
│    • Alert Telegram                                                    │
│    • Trigger Reflection Cycle                                          │
│    • Return to idle                                                    │
│                                                                         │
│  If LOSS:                                                              │
│    • Log loss                                                          │
│    • Check remaining bets                                              │
│    • If bet_remaining > 0:                                             │
│        • Evaluate flip conditions                                      │
│        • If flip conditions met: FLIP direction                        │
│        • Place next bet (C3 or C4)                                     │
│    • If bet_remaining == 0:                                            │
│        • Log session LOST                                              │
│        • Alert Telegram (CRITICAL if 3 losses)                         │
│        • Trigger Reflection Cycle                                       │
│        • Check circuit breaker                                         │
│        • Return to idle                                                │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   REFLECTION PHASE (Loop 5)                             │
│                     (~30 seconds)                                       │
│                                                                         │
│  Governor:                                                              │
│    • Log session outcome to CSV                                        │
│    • Update rolling win rate                                           │
│    • Update consecutive win/loss counters                              │
│    • Update reflection context (injected next cycle)                   │
│    • Analyze what signals were right/wrong                            │
│    • Detect regime shifts                                              │
│    • Adjust weights if 20+ sessions accumulated                        │
│    • Update memory system                                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Memory Architecture: 4-Tier Knowledge System

### Tier Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    4-TIER MEMORY ARCHITECTURE                           │
└─────────────────────────────────────────────────────────────────────────┘

TIER 1: WORKING MEMORY (Redis, TTL: 15 minutes)
─────────────────────────────────────────────────
What's here:
  • Current MarketState packet
  • Active session state
  • Last 3 trading decisions
  • Current conviction scores

Who writes: Governor (automatically)
Who reads: All agents during trading cycle
Persistence: In-memory, lost on restart
Purpose: Fast access during decision-making

Example:
{
  "current_candle": {...},
  "active_session": {direction: "GREEN", bets_placed: 1},
  "last_decision": {call: "GREEN", confidence: 0.68, advisor: "GREEN"},
  "current_scores": {momentum: 0.72, orderflow: 0.78, macro: 0.55}
}


TIER 2: EPISODIC MEMORY (PostgreSQL, unlimited)
─────────────────────────────────────────────────
What's here:
  • Every trading session (outcome, decision, reasoning)
  • Every research finding
  • Every improvement implemented
  • Every anomaly detected

Schema:
  Table: trading_sessions
    - id, timestamp, direction, confidence, outcome
    - specialist_signals, advisor_opinion, pnl
    - flip_occurred, regime, market_conditions

  Table: research_findings
    - id, date, source, title, summary
    - relevance_score, action_taken, result

  Table: code_changes
    - id, date, change_type, description
    - expected_improvement, actual_improvement, rollback?

Who writes: Governor, Coder (automatically)
Who reads: Governor (during reflection), Research Agent (during synthesis)
Persistence: Permanent, survives restarts
Purpose: Pattern recognition across time


TIER 3: SEMANTIC MEMORY (Vector DB, unlimited)
─────────────────────────────────────────────────
What's here:
  • Paper summaries (arXiv papers read)
  • GitHub repo analyses
  • X/Twitter insights from watched accounts
  • Strategy principles and their justifications
  • Known patterns and their performance

Schema (Chroma collection: "knowledge"):
  {
    "id": "paper/vpin_theory_2024",
    "document": "VPIN theory paper... key formula: VPIN = (1/M) × Σ|Vb-Vs|/Vb...",
    "metadata": {source: "arXiv", date: "2024-03", topic: "market_microstructure"},
    "embedding": [0.123, -0.456, ...]
  }

  {
    "id": "signal_accuracy/orderflow/may_2026",
    "document": "Orderflow signals have been right 72% of the time in May 2026...",
    "metadata": {dimension: "orderflow", period: "2026-05"},
    "embedding": [...]
  }

Who writes: Research Agent, Governor (during synthesis)
Who reads: All agents (semantic search)
Persistence: Permanent
Purpose: "What did we learn about X?" — instant recall


TIER 4: PROCEDURAL MEMORY (Files + Memory, persistent)
────────────────────────────────────────────────────────
What's here:
  • System architecture (CLAUDE.md, DESIGN.md)
  • Strategy rules (SPEC.md) — the sacred text
  • Code patterns and conventions
  • MCP tool definitions
  • Agent system prompts

Who writes: Coder (when architecture changes), Human (strategy updates)
Who reads: All agents (at startup + on-demand)
Persistence: Git-tracked files + Claude Code memory
Purpose: "How do we do things here?"
```

### Memory Update Protocol

```
When a session ends (WIN or LOSS):
────────────────────────────
1. Governor → Working Memory: Clear current session
2. Governor → Episodic Memory: INSERT trading_session row
3. Governor → Semantic Memory: UPDATE signal accuracy (upsert)
4. Governor → Semantic Memory: APPEND if regime shift detected

When research cycle runs:
─────────────────────────────
1. Research Agent → Semantic Memory: INSERT paper summaries
2. Research Agent → Semantic Memory: INSERT repo analyses
3. Research Agent → Episodic Memory: INSERT research_finding
4. Research Agent → Governor: [RECOMMENDATIONS]

When improvement deployed:
────────────────────────────
1. Coder → Episodic Memory: INSERT code_change row
2. Governor → Procedural Memory: UPDATE relevant docs
3. Governor → Semantic Memory: UPSERT "what changed" summary
```

---

## 8. Continuous Improvement Engine

### The Self-Improvement Loop

```
┌─────────────────────────────────────────────────────────────────────────┐
│              CONTINUOUS IMPROVEMENT ENGINE                               │
│                                                                         │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐          │
│   │  RESEARCH    │────►│   GOVERNOR   │────►│    CODER     │          │
│   │   AGENT      │     │   DECIDES    │     │ IMPLEMENTS   │          │
│   │ (daily scan) │     │ (accept/reject│    │(isolated branch)│      │
│   └──────┬───────┘     └──────┬───────┘     └──────┬───────┘          │
│          │                    │                    │                   │
│          │ findings +         │ approval +         │ code + tests     │
│          │ recommendations     │ security_review    │                  │
│          ▼                    ▼                    ▼                   │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐          │
│   │   MEMORY     │◄────│   SHADOW     │◄────│  SECURITY    │          │
│   │   UPDATE     │     │  DEPLOYMENT  │     │   REVIEW     │          │
│   │ (log what we │     │ (24-48 hours │     │  (validate   │          │
│   │   learned)   │     │  parallel)   │     │  safety)     │          │
│   └──────────────┘     └──────┬───────┘     └──────────────┘          │
│                               │                                        │
│                               ▼                                        │
│                        ┌──────────────┐                                 │
│                        │  PROMOTE    │                                 │
│                        │  OR ROLLBACK│                                 │
│                        └─────────────┘                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

### Categories of Improvement

```
IMPROVEMENT TYPE 1: Signal Enhancement
────────────────────────────────────────
Example: "Research found that KDJ divergence improves momentum scoring"
Change: Add KDJ indicator to Quant agent's analysis
Expected: +2-3% momentum accuracy
Risk: LOW (additive, no existing logic removed)

IMPROVEMENT TYPE 2: Weight Optimization
────────────────────────────────────────
Example: "Historical analysis shows orderflow has 15% better accuracy than momentum"
Change: Increase orderflow weight from 0.20 → 0.25, decrease momentum from 0.25 → 0.20
Expected: Better conviction scoring
Risk: LOW (weight shift, validated by backtest)

IMPROVEMENT TYPE 3: New Data Source
────────────────────────────────────
Example: "X/Twitter sentiment via MCP gives additional edge"
Change: Add SentimentScout agent + MCP integration
Expected: +3-5% overall accuracy
Risk: MEDIUM (new dependency, data quality variance)

IMPROVEMENT TYPE 4: Strategy Enhancement
─────────────────────────────────────────
Example: "Flip conditions should be tighter to avoid bad flips"
Change: Require VPIN < 0.60 (was < 0.70) for flip
Expected: Fewer losing flips
Risk: MEDIUM (changes risk control behavior)

IMPROVEMENT TYPE 5: Architecture Change
────────────────────────────────────────
Example: "Add a 4th specialist agent for volume profile analysis"
Change: New agent, new MCP connection, new dimension in conviction
Expected: +5-8% overall accuracy
Risk: HIGH (significant change, must validate all interactions)

IMPROVEMENT TYPE 6: Risk Control Addition
──────────────────────────────────────────
Example: "Add daily loss limit of $50"
Change: If daily loss > $50, halt trading until next day
Expected: Better capital protection
Risk: NONE (pure risk control)
```

### Validation Protocol

```
Before ANY change is deployed to live:
────────────────────────────────────────

1. UNIT TESTS: All existing tests pass
2. INTEGRATION TESTS: New functionality tested end-to-end
3. BACKTEST: Run on last 90 days of historical data
   - Must show > 2% improvement OR be risk control (auto-approve)
   - Must not show > 1% regression
4. SHADOW DEPLOYMENT: 24-48 hours in parallel with live
   - Governor compares live vs shadow decisions
   - If shadow consistently better → promote
   - If shadow worse → rollback
5. HUMAN NOTIFICATION: Governor alerts human of any change
```

---

## 9. Risk Control Framework

### Three Layers of Defense

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    THREE-LAYER RISK CONTROL                             │
└─────────────────────────────────────────────────────────────────────────┘

LAYER 1: PRE-TRADE RISK (before any bet is placed)
──────────────────────────────────────────────────
□ Pre-filter hard rules (10 deterministic checks)
□ Conviction threshold gates (HIGH/MEDIUM/LOW)
□ Advisor disagreement override
□ Max bet size check ($7 per session, $20 bankroll)
□ VPIN toxicity check (>0.75 = skip)
□ Circuit breaker check (3 losses + no edge = skip)

LAYER 2: REAL-TIME RISK (while session is active)
──────────────────────────────────────────────────
□ Max session exposure: $7 total loss
□ Dynamic flip conditions (strict, requires multiple confirmations)
□ 15-minute max wait between bets
□ Circuit breaker: 3 consecutive losses = pause
□ Daily loss limit: $50 = pause until next day
□ Max daily sessions: 20

LAYER 3: SYSTEMIC RISK (protects against system failure)
────────────────────────────────────────────────────────
□ Dead man's switch: If no heartbeat in 5 minutes, alert human
□ Database corruption detection: Verify data integrity every hour
□ API failure fallback: If Binance fails, pause trading
□ Polymarket failure: If Polymarket fails, pause trading
□ Max drawdown circuit: If drawdown > 20%, pause + review
□ Human override: Human can halt at any time via Telegram
```

### Circuit Breaker Matrix

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CIRCUIT BREAKER MATRIX                               │
├─────────────────────┬───────────────────────────────────────────────────┤
│     Condition       │              Action                               │
├─────────────────────┼───────────────────────────────────────────────────┤
│ 3 consecutive losses│ • Halt auto-trading                              │
│ (no flip possible)  │ • Alert human                                    │
│                     │ • Resume only after human confirmation           │
├─────────────────────┼───────────────────────────────────────────────────┤
│ 3 losses, flip also │ • Review flip conditions                          │
│ loses               │ • Tighten flip conditions                         │
│                     │ • Alert human                                    │
├─────────────────────┼───────────────────────────────────────────────────┤
│ Win rate < 45%      │ • Pause for backtest review                       │
│ over 20 sessions    │ • Alert human                                    │
│                     │ • Resume only if human approves new conditions   │
├─────────────────────┼───────────────────────────────────────────────────┤
│ Daily loss > $50    │ • Halt trading for rest of day                   │
│                     │ • Alert human                                    │
│                     │ • Resume next day automatically                   │
├─────────────────────┼───────────────────────────────────────────────────┤
│ Total drawdown > 20%│ • Halt all trading                              │
│                     │ • Alert human (CRITICAL)                         │
│                     │ • Resume only after human review                 │
├─────────────────────┼───────────────────────────────────────────────────┤
│ System error rate   │ • Switch to degraded mode (manual approve only)  │
│ > 10% per hour      │ • Alert human                                    │
├─────────────────────┼───────────────────────────────────────────────────┤
│ API latency > 60s   │ • Pause trading                                  │
│                     │ • Alert human                                    │
│                     │ • Resume when latency normalizes                 │
└─────────────────────┴───────────────────────────────────────────────────┘
```

---

## 10. Monitoring, Alerting & Observability

### Metrics Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      METRICS DASHBOARD (Grafana)                        │
└─────────────────────────────────────────────────────────────────────────┘

PANEL 1: Trading Performance
────────────────────────────────
  • Win rate (rolling 20 sessions)
  • Total P&L (daily, weekly, all-time)
  • Average session length
  • Confidence calibration (predicted vs actual)

PANEL 2: Agent Health
────────────────────────────────
  • Last heartbeat from each agent
  • Average response time per agent
  • Error rate per agent
  • Memory usage per agent

PANEL 3: Market Data Quality
────────────────────────────────
  • Data freshness (seconds old)
  • Binance WS connection status
  • Polymarket API latency
  • VPIN computation latency

PANEL 4: Risk Metrics
────────────────────────────────
  • Current drawdown
  • Consecutive wins/losses
  • Daily loss/profit
  • Max exposure in flight

PANEL 5: System Performance
────────────────────────────────
  • Total cycle time (data → decision)
  • MCP server latency
  • Database query times
  • Log volume per hour
```

### Alert Levels

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ALERT LEVELS                                   │
├───────────┬─────────────────────────────────────────────────────────────┤
│  LEVEL    │  WHEN & WHAT                                                │
├───────────┼─────────────────────────────────────────────────────────────┤
│  INFO     │  Session started/ended (Green/Red, P&L)                     │
│           │  Research cycle completed                                   │
│           │  Code change deployed                                       │
├───────────┼─────────────────────────────────────────────────────────────┤
│  WARNING  │  Win rate approaching threshold (<50%)                      │
│           │  2 consecutive losses (warning before 3rd)                 │
│           │  Data freshness > 30 seconds                                │
│           │  Agent response time > 45 seconds                          │
│           │  Daily loss approaching $50 limit                         │
├───────────┼─────────────────────────────────────────────────────────────┤
│  CRITICAL │  3 consecutive losses (circuit breaker triggered)         │
│           │  Win rate < 45% over 20 sessions                            │
│           │  Daily loss > $50                                          │
│           │  Drawdown > 20%                                             │
│           │  API failure / data source down                            │
│           │  System error rate > 10%                                   │
├───────────┼─────────────────────────────────────────────────────────────┤
│  EMERGENCY│  Total drawdown > 30%                                       │
│           │  Security breach detected                                   │
│           │  Unauthorized trade detected                                │
│           │  Dead man's switch triggered (no heartbeat > 5 min)         │
└───────────┴─────────────────────────────────────────────────────────────┘
```

### Telegram Alert Menu

```
/start         — Show bot status
/stats         — Win rate, P&L, recent sessions
/session       — Current active session status
/export        — Export full history CSV
/halt          — Emergency stop (requires confirmation)
/resume        — Resume after halt (requires confirmation)
/config        — Show current settings
/performance   — Detailed performance breakdown
/health        — System health check
/help          — Show all commands
```

---

## 11. Deployment Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      DEPLOYMENT ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────┐
                        │    Human Ops     │
                        │  (Telegram Bot)  │
                        └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
             ┌──────▼──────┐          ┌───────▼──────┐
             │   Hermes     │          │   Grafana    │
             │   Agent      │          │   Dashboard  │
             │  (Governor)  │          │              │
             └──────┬──────┘          └───────▲──────┘
                    │                         │
        ┌───────────┼─────────────────────────┼───────────┐
        │           │                         │           │
   ┌────▼────┐  ┌────▼────┐             ┌──────▼──────┐    │
   │ Cronjob │  │  MCP    │             │ Prometheus   │    │
   │ (Loop 2)│  │ Servers │             │  + Alertmgr  │    │
   └────┬────┘  └────┬────┘             └─────────────┘    │
        │           │                                           │
        │    ┌──────┴──────┐                                   │
        │    │             │                                   │
   ┌────▼────▼──┐  ┌──────▼──────┐                            │
   │   binance   │  │  polymarket  │                            │
   │    -mcp     │  │    -mcp     │                            │
   └────┬────┬───┘  └──────┬──────┘                            │
        │    │              │                                   │
        └────┼──────────────┼───────────────────────────────────┘
             │              │
    ┌────────▼─────────┐    │
    │    Binance       │    │
    │   (Markets)      │    │
    └──────────────────┘    │
                           ┌▼──────────────┐
                           │  Polymarket   │
                           │    (CLOB)     │
                           └───────────────┘

DATA STORAGE:
─────────────────────────────────────────────────────────────────────────
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  PostgreSQL     │  │     Redis       │  │   Chroma DB     │
│                 │  │                 │  │                 │
│  • sessions     │  │  • working mem  │  │  • embeddings   │
│  • outcomes     │  │  • cache        │  │  • knowledge    │
│  • research     │  │  • pub/sub      │  │                 │
│  • changes      │  │                │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘

DEPLOYMENT: Docker Compose (single node) or Kubernetes (multi-node)
─────────────────────────────────────────────────────────────────────────
Docker services:
  • btc-predictor (main trading bot)
  • postgres (data store)
  • redis (cache + pub/sub)
  • chroma (vector DB)
  • prometheus (metrics)
  • grafana (dashboards)
  • alertmanager (alerts)
  • nginx (reverse proxy for Grafana)

All services configured with:
  • Health checks
  • Auto-restart on failure
  • Log rotation
  • Backup schedules
```

---

## 12. Implementation Phases

### Phase 1: Foundation (Week 1-2)

```
□ Set up project structure with proper directories
□ Implement MCP servers:
  □ binance-mcp (basic: klines, ticker, funding, OI)
  □ polymarket-mcp (basic: find markets, place orders)
  □ memory-mcp (basic: store/recall facts)
□ Implement data layer:
  □ Binance client (WS + REST, parallel fetch)
  □ MarketState assembler
  □ All indicators (VPIN, CVD, OFI, TCR, OBI)
□ Implement pre-filter with all 10 rules
□ Implement session manager (JSON persistence)
□ Implement Telegram alerts (basic)
□ Write CLAUDE.md, DESIGN.md, SPEC.md

Deliverable: Can run a complete trading cycle (data → decision) in paper mode
```

### Phase 2: Multi-Agent (Week 3-4)

```
□ Implement Governor agent (Claude Opus 4.7)
□ Implement specialist agents:
  □ Quant Master
  □ Flow Master
  □ Macro Monarch
  □ Sentiment Scout
□ Implement Advisor agent (Opus 4.7, max reasoning)
□ Implement inter-agent communication protocol
□ Implement Governor reconciliation logic
□ Implement execution engine (Polymarket)
□ Implement 4-tier memory system
□ Implement Reflection Cycle (Loop 5)

Deliverable: Full multi-agent trading cycle working with paper trading
```

### Phase 3: Research & Improvement (Week 5-6)

```
□ Implement Research Agent
□ Implement X/Twitter MCP integration
□ Implement arXiv/GitHub monitoring
□ Implement daily research cycle (Loop 2)
□ Implement Coder agent
□ Implement Security Reviewer agent
□ Implement shadow deployment system
□ Implement continuous improvement pipeline (Loop 3)

Deliverable: System can research, implement, and validate its own improvements
```

### Phase 4: Monitoring & Hardening (Week 7-8)

```
□ Implement Grafana dashboards
□ Implement Prometheus metrics
□ Implement all circuit breakers
□ Implement monitoring cycle (Loop 4)
□ Implement automated backtesting framework
□ Implement rollback procedures
□ Security audit (all code, all MCP connections)
□ Load testing (simulate 1000 trading cycles)

Deliverable: Institutional-grade reliability and observability
```

### Phase 5: Live Trading (Week 9+)

```
□ Live Polymarket trading with small amounts ($1-2 bets)
□ Monitor performance vs paper trading
□ Gradual bet size increase as confidence builds
□ Weekly human review of system performance
□ Monthly architecture reviews
□ Quarterly strategy re-evaluation

Deliverable: Production system generating real P&L
```

---

## Key Differences from Current v2.0 Architecture

| Aspect | v2.0 (Current) | v4.0 (God-Tier) |
|---|---|---|
| Agents | 1 (advisor) + 1 (reasoning) | 9 specialized agents |
| Research | Manual | Daily automated (Research Agent) |
| Code changes | Human-only | Autonomous (Coder + Security Reviewer) |
| Memory | 1 file (reflection) | 4-tier (Working, Episodic, Semantic, Procedural) |
| Improvement | Never | Continuous (Loop 3: research → implement → validate) |
| Monitoring | Telegram alerts | Full Grafana + Prometheus |
| MCP | None | 4 purpose-built MCP servers |
| Data flow | Sequential | Parallel + orchestrated |
| X/Twitter | Not integrated | Integrated via MCP |
| Backtesting | Manual | Automated, continuous |
| Deployment | Single script | Docker Compose + Kubernetes-ready |
| Testing | Basic pytest | Full CI/CD with shadow deployment |

---

## Appendix: Agent System Prompts Summary

### Governor System Prompt (Key Principles)

```
You are THE GOVERNOR of an autonomous BTC 15-minute trading intelligence.

Your team:
- QUANT: Technical analysis (momentum, patterns, trend)
- FLOW_MASTER: Orderflow and microstructure (VPIN, CVD, OFI)
- MACRO_MONARCH: Macro + smart money (DXY, funding, OI)
- SENTIMENT_SCOUT: Fear&Greed, social, narratives
- ADVISOR: Independent cross-validation (Opus 4.7 max)
- RESEARCHER: Daily research (papers, GitHub, X)
- CODER: Implementation of approved changes
- SECURITY_REVIEWER: Audit and risk validation

Your operating loops:
1. TRADING (every 15 min): Data → Filter → Analyze → Decide → Execute
2. RESEARCH (every 24h): Scan → Synthesize → Recommend
3. IMPROVE (triggered): Plan → Code → Test → Review → Deploy
4. MONITOR (every 5 min): Health → Performance → Alert
5. REFLECT (after every session): Log → Analyze → Adapt

Your decision process:
1. Receive signals from all specialists
2. Receive independent opinion from ADVISOR
3. Reconcile and weigh
4. Apply confidence gates
5. Make final call: GREEN / RED / SKIP
6. Execute if GREEN/RED
7. Reflect after outcome

The strategy is sacred and never changes:
- Predict ≥2 of next 3 candles GREEN or RED
- 3-bet martingale: $1 → $2 → $4
- Win on any 1 of 3
- Max loss: $7 per session

Your priorities (in order):
1. PROTECT CAPITAL — never lose more than $7 per session
2. MAINTAIN DISCIPLINE — follow the strategy without deviation
3. IMPROVE CONTINUOUSLY — learn from every outcome
4. STAY INSTITUTIONAL — no emotion, no FOMO, no revenge trading

When in doubt, SKIP. Patience is the edge.
```

---

**Document Version:** 4.0
**Author:** Claude Opus 4.7 (with research from TradingAgents, MCP, LangChain ecosystems)
**Status:** Ready for Human Review
**Next Step:** Human reviews architecture → suggests changes → iterate → approve → implement Phase 1
