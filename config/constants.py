# BTC-15m Predictor — Configuration
import os
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

SESSION_STATE_FILE = DATA_DIR / ".session_state.json"
PERFORMANCE_LOG_FILE = DATA_DIR / ".performance_log.json"
PREDICTIONS_CSV = DATA_DIR / "predictions.csv"
REFLECTION_CACHE = DATA_DIR / ".reflection_cache.json"

# ── API Keys ─────────────────────────────────────────────────────────────────
# REQUIRED:
#   ANTHROPIC_API_KEY      — Main reasoning engine (me — claude-sonnet-4-6)
#   ANTHROPIC_ADVISOR_KEY  — Advisor Agent (Claude Opus 4.7)
#
# OPTIONAL:
#   TELEGRAM_BOT_TOKEN     — Telegram bot for alerts
#   POLYMARKET_WALLET_KEY   — Wallet private key for Polymarket
#   POLYMARKET_API_KEY      — Polymarket API key
#   CMC_API_KEY             — CoinMarketCap for on-chain metrics

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_ADVISOR_KEY = os.getenv("ANTHROPIC_ADVISOR_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
POLYMARKET_WALLET_KEY = os.getenv("POLYMARKET_WALLET_KEY", "")
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")

# ── Model Config ─────────────────────────────────────────────────────────────
BRAINS = {
    "advisor": {
        "model": os.getenv("ANTHROPIC_ADVISOR_MODEL", "claude-opus-4-7"),
        "max_tokens": 4096,
        "temperature": 0.2,
        "thinking": {"type": "enabled", "budget_tokens": 2048},
    },
    "reasoning": {
        "model": "claude-sonnet-4-6",
        "max_tokens": 2048,
        "temperature": 0.3,
    },
}

# ── Confidence Thresholds ─────────────────────────────────────────────────────
CONFIDENCE_HIGH = 0.70   # Enter session immediately
CONFIDENCE_MEDIUM = 0.55  # Enter only if ≥2 signal categories are extreme
CONFIDENCE_LOW = 0.00     # Skip

# Extreme score threshold for MEDIUM confidence entry
EXTREME_SCORE_THRESHOLD = 0.15  # Score must be ≤0.30 or ≥0.70 to count as "extreme"
REQUIRED_EXTREME_CATEGORIES = 2  # Need ≥2 extreme categories for MEDIUM entry

# ── Pre-Filter Hard Rules ─────────────────────────────────────────────────────
MIN_CANDLE_BODY_PCT = 0.10     # C1 body must be >0.1% or SKIP
MIN_VOLUME_RATIO = 0.70         # C1 vol must be >0.7x 20-candle avg or SKIP
MAX_VPIN_TOXICITY = 0.75        # VPIN >0.75 → SKIP (extreme uncertainty)
MIN_VPIN_TOXICITY = 0.75        # Alias for pre-filter (reads MAX but same threshold)
MIN_ADX_TREND = 15.0            # ADX <15 → SKIP (no trend, choppy)
MAX_FUNDING_RATE_PCT = 0.15     # Funding >0.15% → SKIP (cascade liquidation risk)
EXTREME_FUNDING_PCT = 0.10      # Funding >0.10% → note as risk factor
TREND_REVERSAL_BTC_MOVE_PCT = 0.10  # BTC must move >0.10% against trend for exception
MIN_EDGE_FOR_CIRCUIT_BREAKER = 0.05  # After 3 losses, need edge >5¢

# ── Binance ──────────────────────────────────────────────────────────────────
BINANCE_SPOT_BASE = "https://api.binance.com/api/v3"
BINANCE_FUTURES_BASE = "https://fapi.binance.com/fapi/v1"
BINANCE_WS_BASE = "wss://stream.binance.com:9443/stream"
BINANCE_WS_COMBINED = "wss://stream.binance.com:9443/stream"
SYMBOL_SPOT = "BTCUSDT"
SYMBOL_FUTURES = "BTCUSDT"
KLINE_INTERVAL = "15m"
KLINE_LIMIT = 100   # Candles for indicator computation

# ── Coinbase (cross-confirmation) ────────────────────────────────────────────
COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"
COINBASE_REST_BASE = "https://api.exchange.coinbase.com"

# ── Data Source URLs ──────────────────────────────────────────────────────────
FEAR_GREED_API = "https://api.alternative.me/fng/"
COINGECKO_API = "https://api.coingecko.com/api/v3"
BINANCE_WEB3_SMART_MONEY = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/tracker/wallet/token/inflow/rank/query/ai"

# ── Polymarket ────────────────────────────────────────────────────────────────
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
POLYMARKET_BET_MAX_PCT = 0.25   # Max 25% of bankroll per bet (Kelly cap)
POLYMARKET_MIN_SPREAD_ACCEPTABLE = 0.05  # Reject if spread > 5¢

# ── VPIN Config ──────────────────────────────────────────────────────────────
VPIN_NUM_BUCKETS = 50            # Volume buckets for VPIN computation
VPIN_ROLLING_WINDOW = 200        # Trades in rolling window
CVD_WINDOW = 200                # Trades for CVD

# ── Analysis Timing ───────────────────────────────────────────────────────────
ANALYSIS_TIMEOUT_SECONDS = 60
BRAIN_TIMEOUT_SECONDS = 30
ADVISOR_TIMEOUT_SECONDS = 45

# ── Session / Martingale ──────────────────────────────────────────────────────
MAX_BETS_PER_SESSION = 3
FLIP_ALLOWED = True              # Allow dynamic direction flip on C2/C3 loss
FLIP_CONFIDENCE_GAP = 0.15      # Counter-signal must exceed original by this

# ── Reflection Loop ───────────────────────────────────────────────────────────
REFLECTION_OUTCOMES_COUNT = 20   # Last N outcomes injected into prompt
MIN_SESSIONS_FOR_REVIEW = 50    # Pause for human review if win rate < 45% over N sessions

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
