import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
INTERVALS = ["60", "D"]

INTERVAL_TO_FREQ = {
    "60": "1h",
    "D":  "1D",
}

INTERVAL_LABELS = {
    "60": "1h",
    "D": "1d",
}

DEFAULT_TIMEFRAME = os.getenv("BYBIT_ML_TIMEFRAME", "1h")
TIMEFRAME_TO_BARS_PER_YEAR = {
    "1h": 8760.0,
    "4h": 2190.0,
    "1d": 365.0,
}

# no_funding_oi candidate: keep the same data pipeline, but exclude these
# columns from model training/inference.
MODEL_FEATURE_EXCLUDE_PREFIXES = ("funding_", "oi_")
MODEL_FEATURE_EXCLUDE_COLUMNS = ("funding_rate",)

HISTORY_START = "2020-01-01"

BASE_DIR = Path(__file__).parent
STORAGE_RAW = BASE_DIR / "storage" / "raw"
STORAGE_EXCEL = BASE_DIR / "storage" / "excel"
STORAGE_FEATURES = BASE_DIR / "storage" / "features"
STORAGE_MODELS = BASE_DIR / "storage" / "models"
STORAGE_BACKTEST = BASE_DIR / "storage" / "backtest"
STORAGE_LIVE = BASE_DIR / "storage" / "live"

# ── Live Trading ──────────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Automated order execution. Testnet is the default and both environments
# require an explicit confirmation phrase before any order can be submitted.
BYBIT_TESTNET = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
LIVE_TRADING_CONFIRM = os.getenv("LIVE_TRADING_CONFIRM", "")
BYBIT_CATEGORY = "linear"
BYBIT_POSITION_IDX = 0  # one-way mode
BYBIT_SETTLE_COIN = "USDT"
LIVE_MAX_NOTIONAL_PCT = float(os.getenv("LIVE_MAX_NOTIONAL_PCT", "1.0"))
LIVE_DAILY_INTERVAL_MINUTES = int(os.getenv("LIVE_DAILY_INTERVAL_MINUTES", "15"))
LIVE_MAX_ACTIVE_PER_SYMBOL = int(os.getenv("LIVE_MAX_ACTIVE_PER_SYMBOL", "1"))
LIVE_TARGET  = "target_atr"       # must match model training label
LIVE_SYMBOLS = ["ETHUSDT"]        # BTCUSDT excluded (negative Sharpe in Phase 4.2)

# Live execution constants — shared by run_live.py and show_results.py so the
# displayed simulation matches what the daemon actually does.
INITIAL_EQUITY = 1_000_000.0
RISK_PCT       = 0.02    #每筆下更大，報酬/MDD 都放大
HOLDING_BARS   = 24       # 24h timeout if SL/TP not hit
MAX_CONCURRENT = 3
FEE_PCT        = 0.2      # 0.2% round-trip, matches backtest fee=0.002

# Risk guards — any breach pauses new signal generation
MAX_DRAWDOWN_PCT       = -15.0   # halt if equity drops > 15% from peak
MAX_CONSECUTIVE_LOSSES = 5       # halt after 5 consecutive losing trades
MAX_DAILY_LOSS_PCT     = -5.0    # halt if today's realized loss > 5% of equity

# Shadow threshold — signals between SHADOW and optimal_threshold are logged
# to the ledger (status="shadow") but NOT executed. Used to compare whether
# a lower threshold would have been profitable in live conditions.
SHADOW_THRESHOLD       = 0.70 #進場更少、更嚴格，通常回撤下降，但可能少賺
DUAL_DIRECTION_MARGIN = 0.05  # required prob edge between long and short signals
STRICT_SHORT_THRESHOLD_FLOOR = 0.80

# Research-only long strategy profiles. These are not used by live execution.
LONG_BALANCED_THRESHOLD = 0.73 
LONG_BALANCED_RISK_PCT = 0.08
LONG_BALANCED_MAX_CONCURRENT = 2
LONG_TARGET20_THRESHOLD = 0.73
LONG_TARGET20_RISK_PCT = 0.10
LONG_TARGET20_MAX_CONCURRENT = 2
LITERATURE_LONG_THRESHOLD = 0.70          # 1h 文獻策略進場門檻；調高=更少訊號，調低=更多訊號
LITERATURE_LONG_RISK_PCT = 0.08           # 1h 每筆交易承擔帳戶比例；調高=報酬/回撤都放大
LITERATURE_LONG_MAX_CONCURRENT = 2        # 1h 最多同時持倉數；調高=可疊更多倉，資金波動變大
LITERATURE_LONG_MIN_BULL_SCORE = 4        # 1h 最少多頭確認分數；調高=條件更嚴格、進場變少
LITERATURE_LONG_MAX_RISK_SCORE = 1        # 1h 允許的最高風險分數；調低=避開更多過熱/轉弱訊號
LITERATURE_LONG_DAILY_THRESHOLD = 0.58    # 日K 模型機率進場門檻；目前較佳區間約 0.58~0.59
LITERATURE_LONG_DAILY_RISK_PCT = 0.03     # 日K 每筆交易承擔帳戶比例；0.02~0.04 較保守，0.08 偏積極
LITERATURE_LONG_DAILY_MAX_CONCURRENT = 6  # 日K 最多同時持倉數；近期掃描較佳區間約 5~7
LITERATURE_LONG_DAILY_MIN_BULL_SCORE = 1  # 日K 最少多頭確認分數；近期掃描較佳區間約 1~2
LITERATURE_LONG_DAILY_MAX_RISK_SCORE = 0  # 日K 最高風險分數；0 是最嚴格，要求沒有過熱/轉弱訊號
LITERATURE_LONG_DAILY_HOLDING_BARS = 24   # 日K 最長持倉 24 根，即 24 天

OVERLAP_HOURS = 3   # overlap candles re-fetched to overwrite unclosed candles from previous run
OVERLAP_DAYS = 3
RATE_LIMIT_SLEEP = 0.2
MAX_RETRIES = 3
