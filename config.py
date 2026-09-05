# config.py
# ==========================================
# EDIT THESE VALUES WITH YOUR DELTA DETAILS
# ==========================================

# === DELTA EXCHANGE (TESTNET-INDIA) ===
DELTA_BASE_URL = "https://cdn-ind.testnet.deltaex.org"
DELTA_API_KEY = ""      # <-- PASTE YOUR KEY
DELTA_API_SECRET = "" # <-- PASTE YOUR SECRET

# === ETH FUTURES SYMBOL ===
ETH_FUTURES_SYMBOL = "ETHUSD"

# === OPTIONS PARAMETERS ===
OPTIONS_EXPIRY_HOURS = 72   # Choose between 48 to 120
OPTIONS_TRADE_SIZE = 1      # 1 contract (testnet only)
OPTIONS_ORDER_TYPE = "limit"

# === STRATEGY RULES ===
SAR_ACCELERATION = 0.02
SAR_MAXIMUM = 0.20
ADX_THRESHOLD = 6          # Filter signals in sideways markets
CONFIRMATION_BARS = 1       # Wait for 1 candles before acting

# === RISK ===
MAX_POSITION_SIZE = 5
STOP_LOSS_PCT = 0.15        # 15% stop-loss
TAKE_PROFIT_PCT = 0.30   # 30% profit target (close trade when option rises 30%)
FLIP_ON_REVERSAL = True  # True = Sell old position when new opposite signal comes
# === OPTIONS EXPIRY SELECTION ===
OPTION_TARGET_DAYS = 3   # We want the option expiring closest to 3 days from now