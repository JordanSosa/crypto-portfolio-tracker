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

# Currency
DEFAULT_CURRENCY = "aud"

