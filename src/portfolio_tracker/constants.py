"""
Constants and configuration for the cryptocurrency portfolio tracker
"""

# CoinGecko API endpoint
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# Coin ID mapping (CoinGecko uses different IDs than symbols)
COIN_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "XRP": "ripple",
    "SOL": "solana",
    "LINK": "chainlink",
    "BCH": "bitcoin-cash",
    "UNI": "uniswap",
    "LEO": "leo-token",
    "WBT": "whitebit",
    "WLFI": "world-liberty-financial"
}

# Coin name mapping (symbol -> full name)
COIN_NAMES = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "XRP": "Ripple",
    "SOL": "Solana",
    "LINK": "Chainlink",
    "UNI": "Uniswap",
    "BCH": "Bitcoin Cash",
    "LEO": "LEO Token",
    "WBT": "WhiteBIT Coin",
    "WLFI": "World Liberty Financial"
}

# Default target allocations
DEFAULT_TARGET_ALLOCATIONS = {
    "BTC": 50.0,
    "ETH": 20.0,
    "XRP": 15.0,
    "SOL": 10.0,
    "LINK": 5.0
}

# Analysis thresholds
OVER_ALLOCATION_THRESHOLD = 45.0  # Percentage above which asset is considered over-allocated
REBALANCE_THRESHOLD = 2.0  # Minimum allocation difference (%) to trigger rebalancing
STRONG_MOMENTUM_THRESHOLD = 2.0  # Risk-adjusted momentum threshold for strong signals
BEARISH_MOMENTUM_THRESHOLD = -2.0  # Risk-adjusted momentum threshold for bearish signals
MODERATE_BEARISH_THRESHOLD = -1.5  # Risk-adjusted momentum threshold for moderate bearish
HIGH_VOLATILITY_THRESHOLD = 20.0  # Volatility percentage threshold
STRONG_PRICE_DROP_THRESHOLD = -5.0  # 24h price change threshold for strong bearish

# API configuration
API_RETRY_COUNT = 3
API_TIMEOUT = 10
API_RATE_LIMIT_BACKOFF_BASE = 2  # Base seconds for exponential backoff

# Rate limiting configuration for historical price fetching
HISTORICAL_PRICE_FETCH_DELAY = 7  # Seconds between historical price fetches
RATE_LIMIT_SAFE_THRESHOLD = 2  # Stop fetching if remaining requests < this
MAX_HISTORICAL_FETCHES_PER_RUN = 3  # Limit number of fetches per run to avoid rate limits

# Currency
DEFAULT_CURRENCY = "aud"

# DCA Strategy Configuration
DCA_BASE_MULTIPLIER = 1.0  # Standard DCA amount multiplier
DCA_INCREASE_MULTIPLIER = 1.5  # Increase DCA when oversold
DCA_DECREASE_MULTIPLIER = 0.5  # Decrease DCA when overbought
DCA_PAUSE_THRESHOLD = 80.0  # RSI above which to pause DCA

# Technical Indicator Thresholds
RSI_OVERSOLD = 30.0
RSI_OVERBOUGHT = 70.0
RSI_EXTREME_OVERSOLD = 20.0
RSI_EXTREME_OVERBOUGHT = 80.0

# Moving Average Periods
SMA_SHORT_PERIOD = 50
SMA_LONG_PERIOD = 200
EMA_SHORT_PERIOD = 12
EMA_LONG_PERIOD = 26

