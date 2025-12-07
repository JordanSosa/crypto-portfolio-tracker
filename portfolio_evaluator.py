"""
Cryptocurrency Portfolio Evaluator
Analyzes market conditions and provides buy/sell recommendations
"""

import requests
import json
import os
import time
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

try:
    from blockchain_balance_fetcher import BlockchainBalanceFetcher
    BLOCKCHAIN_FETCHER_AVAILABLE = True
except ImportError:
    BLOCKCHAIN_FETCHER_AVAILABLE = False

try:
    from portfolio_database import PortfolioDatabase
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

try:
    from portfolio_rebalancer import PortfolioRebalancer
    REBALANCER_AVAILABLE = True
except ImportError:
    REBALANCER_AVAILABLE = False

try:
    from constants import (
        COINGECKO_BASE_URL,
        COIN_IDS,
        COIN_NAMES,
        API_RETRY_COUNT,
        API_TIMEOUT,
        API_RATE_LIMIT_BACKOFF_BASE,
        DEFAULT_CURRENCY,
        OVER_ALLOCATION_THRESHOLD,
        STRONG_MOMENTUM_THRESHOLD,
        BEARISH_MOMENTUM_THRESHOLD,
        MODERATE_BEARISH_THRESHOLD,
        HIGH_VOLATILITY_THRESHOLD,
        STRONG_PRICE_DROP_THRESHOLD,
        RSI_OVERSOLD,
        RSI_OVERBOUGHT,
        RSI_EXTREME_OVERSOLD,
        RSI_EXTREME_OVERBOUGHT,
        HISTORICAL_PRICE_FETCH_DELAY,
        RATE_LIMIT_SAFE_THRESHOLD,
        MAX_HISTORICAL_FETCHES_PER_RUN
    )
except ImportError:
    # Fallback if constants module not available
    RSI_OVERSOLD = 30.0
    RSI_OVERBOUGHT = 70.0
    RSI_EXTREME_OVERSOLD = 20.0
    RSI_EXTREME_OVERBOUGHT = 80.0
except ImportError:
    # Fallback if constants module not available
    COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
    COIN_IDS = {
        "BTC": "bitcoin", "ETH": "ethereum", "XRP": "ripple",
        "SOL": "solana", "LINK": "chainlink", "BCH": "bitcoin-cash",
        "UNI": "uniswap", "LEO": "leo-token", "WBT": "whitebit",
        "WLFI": "world-liberty-financial"
    }
    COIN_NAMES = {
        "BTC": "Bitcoin", "ETH": "Ethereum", "XRP": "Ripple",
        "SOL": "Solana", "LINK": "Chainlink", "UNI": "Uniswap",
        "BCH": "Bitcoin Cash", "LEO": "LEO Token", "WBT": "WhiteBIT Coin"
    }
    API_RETRY_COUNT = 3
    API_TIMEOUT = 10
    API_RATE_LIMIT_BACKOFF_BASE = 2
    DEFAULT_CURRENCY = "aud"
    OVER_ALLOCATION_THRESHOLD = 45.0
    STRONG_MOMENTUM_THRESHOLD = 2.0
    BEARISH_MOMENTUM_THRESHOLD = -2.0
    MODERATE_BEARISH_THRESHOLD = -1.5
    HIGH_VOLATILITY_THRESHOLD = 20.0
    STRONG_PRICE_DROP_THRESHOLD = -5.0
    RSI_OVERSOLD = 30.0
    RSI_OVERBOUGHT = 70.0
    RSI_EXTREME_OVERSOLD = 20.0
    RSI_EXTREME_OVERBOUGHT = 80.0
    HISTORICAL_PRICE_FETCH_DELAY = 7
    RATE_LIMIT_SAFE_THRESHOLD = 2
    MAX_HISTORICAL_FETCHES_PER_RUN = 3


class Recommendation(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    # DCA Strategy Recommendations
    DCA_INCREASE = "DCA_INCREASE"  # Increase DCA amount
    DCA_STANDARD = "DCA_STANDARD"  # Continue standard DCA
    DCA_DECREASE = "DCA_DECREASE"  # Decrease DCA amount
    DCA_PAUSE = "DCA_PAUSE"  # Pause DCA temporarily
    DCA_OUT_START = "DCA_OUT_START"  # Begin DCA out strategy
    DCA_OUT_ACCELERATE = "DCA_OUT_ACCELERATE"  # Accelerate DCA out


@dataclass
class Asset:
    symbol: str
    name: str
    amount: float
    current_price: float
    allocation_percent: float
    value: float


@dataclass
class TechnicalIndicatorsData:
    """Technical indicators for an asset"""
    rsi: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    macd: Optional[Dict[str, float]] = None
    bollinger_bands: Optional[Dict[str, float]] = None
    price_vs_ma_position: Optional[str] = None  # "above", "below", "near"
    price_vs_bands_position: Optional[str] = None


@dataclass
class MarketAnalysis:
    symbol: str
    price_change_24h: float
    price_change_7d: float
    price_change_30d: float
    volatility: float
    momentum: float
    risk_adjusted_momentum: float  # Momentum normalized by volatility
    trend: str  # "bullish", "bearish", "neutral"
    recommendation: Recommendation
    reason: str
    suggested_action: str
    # New fields for technical indicators
    technical_indicators: Optional[TechnicalIndicatorsData] = None
    dca_multiplier: float = 1.0  # Suggested DCA amount multiplier
    dca_priority: int = 0  # Priority for DCA (higher = more important)


class PortfolioEvaluator:
    """Evaluates cryptocurrency portfolio and provides trading recommendations"""
    
    def __init__(self, portfolio: Dict[str, Asset]):
        """
        Initialize evaluator with portfolio data
        
        Args:
            portfolio: Dictionary mapping asset symbols to Asset objects
        """
        self.portfolio = portfolio
        self.market_data = {}
        
    def fetch_market_data(self, symbols: List[str], retry_count: int = API_RETRY_COUNT) -> Dict:
        """
        Fetch current market data for given symbols with retry logic for rate limits
        
        Args:
            symbols: List of asset symbols to fetch
            retry_count: Number of retry attempts for rate limit errors
        """
        coin_ids = [COIN_IDS.get(symbol.upper()) for symbol in symbols 
                   if symbol.upper() in COIN_IDS]
        
        if not coin_ids:
            return {}
        
        # Fetch price data with 24h, 7d, 30d changes
        url = f"{COINGECKO_BASE_URL}/coins/markets"
        params = {
            "vs_currency": DEFAULT_CURRENCY,
            "ids": ",".join(coin_ids),
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": False,
            "price_change_percentage": "24h,7d,30d"
        }
        
        for attempt in range(retry_count):
            try:
                response = requests.get(url, params=params, timeout=API_TIMEOUT)
                
                # Handle rate limiting (429 Too Many Requests)
                if response.status_code == 429:
                    if attempt < retry_count - 1:
                        wait_time = (attempt + 1) * API_RATE_LIMIT_BACKOFF_BASE
                        print(f"    Rate limit hit. Waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print("    Error: Rate limit exceeded. Please wait a minute and try again.")
                        return {}
                
                response.raise_for_status()
                data = response.json()
                break  # Success, exit retry loop
                
            except requests.exceptions.RequestException as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * API_RATE_LIMIT_BACKOFF_BASE
                    print(f"    Request error: {e}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Error fetching market data after {retry_count} attempts: {e}")
                    return {}
        else:
            # This shouldn't happen, but just in case
            return {}
        
        # Organize data by symbol
        market_data = {}
        for coin in data:
            symbol = next((s for s, cid in COIN_IDS.items() 
                          if cid == coin["id"]), None)
            if symbol:
                market_data[symbol] = {
                    "current_price": coin["current_price"],
                    "price_change_24h": coin.get("price_change_percentage_24h_in_currency", 0),
                    "price_change_7d": coin.get("price_change_percentage_7d_in_currency", 0),
                    "price_change_30d": coin.get("price_change_percentage_30d_in_currency", 0),
                    "market_cap": coin.get("market_cap", 0),
                    "volume_24h": coin.get("total_volume", 0)
                }
        
        return market_data
    
    def fetch_historical_prices(
        self, 
        symbol: str, 
        days: int = 200,
        retry_count: int = API_RETRY_COUNT
    ) -> Optional[List[Tuple[datetime, float]]]:
        """
        Fetch historical daily prices from CoinGecko API
        
        Args:
            symbol: Asset symbol (e.g., 'BTC')
            days: Number of days of history to fetch (max 365)
            retry_count: Number of retry attempts
            
        Returns:
            List of tuples (datetime, price) sorted by date (oldest first), or None on error
        """
        if symbol.upper() not in COIN_IDS:
            return None
        
        coin_id = COIN_IDS[symbol.upper()]
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart"
        params = {
            "vs_currency": DEFAULT_CURRENCY,
            "days": min(days, 365),  # CoinGecko max is 365 days
            "interval": "daily"
        }
        
        for attempt in range(retry_count):
            try:
                response = requests.get(url, params=params, timeout=API_TIMEOUT)
                
                # Check rate limit headers before processing response
                rate_limit_remaining = response.headers.get('X-RateLimit-Remaining')
                rate_limit_reset = response.headers.get('X-RateLimit-Reset')
                
                if rate_limit_remaining:
                    try:
                        remaining = int(rate_limit_remaining)
                        if remaining < RATE_LIMIT_SAFE_THRESHOLD:
                            if rate_limit_reset:
                                try:
                                    reset_time = int(rate_limit_reset)
                                    current_time = int(time.time())
                                    wait_time = max(reset_time - current_time, 60)
                                    if wait_time > 0:
                                        print(f"    Rate limit nearly exhausted ({remaining} remaining). Waiting {wait_time} seconds...")
                                        time.sleep(wait_time)
                                except (ValueError, TypeError):
                                    pass
                    except (ValueError, TypeError):
                        pass
                
                if response.status_code == 429:
                    # Check Retry-After header if available
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                        except (ValueError, TypeError):
                            wait_time = (attempt + 1) * API_RATE_LIMIT_BACKOFF_BASE * 5  # Longer wait
                    else:
                        wait_time = (attempt + 1) * API_RATE_LIMIT_BACKOFF_BASE * 5  # Longer wait
                    
                    if attempt < retry_count - 1:
                        print(f"    Rate limit hit. Waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print("    Error: Rate limit exceeded. Please wait a minute and try again.")
                        return None
                
                response.raise_for_status()
                data = response.json()
                
                # Extract prices from the response
                # CoinGecko returns: {"prices": [[timestamp_ms, price], ...], ...}
                prices = []
                if "prices" in data:
                    for entry in data["prices"]:
                        timestamp_ms = entry[0]
                        price = entry[1]
                        # Convert milliseconds to datetime
                        date_obj = datetime.fromtimestamp(timestamp_ms / 1000)
                        prices.append((date_obj, price))
                    
                    # Sort by date (oldest first)
                    prices.sort(key=lambda x: x[0])
                    return prices
                
                return None
                
            except requests.exceptions.RequestException as e:
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * API_RATE_LIMIT_BACKOFF_BASE * 3  # Longer wait
                    print(f"    Request error: {e}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Error fetching historical prices for {symbol} after {retry_count} attempts: {e}")
                    return None
        
        return None
    
    def fetch_missing_historical_prices(
        self,
        symbol: str,
        latest_date: Optional[datetime]
    ) -> Optional[List[Tuple[datetime, float]]]:
        """
        Fetch only missing historical prices (incremental update)
        
        Args:
            symbol: Asset symbol
            latest_date: Date of latest price in database (None if no data)
            
        Returns:
            List of new price data or None
        """
        if latest_date is None:
            # No data exists, fetch full history
            return self.fetch_historical_prices(symbol, days=200)
        
        # Calculate days since last update
        days_since_update = (datetime.now() - latest_date).days
        
        if days_since_update <= 2:
            # Data is fresh, no need to fetch
            return None
        
        # Only fetch the missing days (plus a few extra for safety)
        days_to_fetch = min(days_since_update + 5, 365)
        return self.fetch_historical_prices(symbol, days=days_to_fetch)
    
    def calculate_volatility(self, price_changes: List[float]) -> float:
        """Calculate volatility from price changes"""
        if not price_changes:
            return 0.0
        
        mean = sum(price_changes) / len(price_changes)
        variance = sum((x - mean) ** 2 for x in price_changes) / len(price_changes)
        return variance ** 0.5
    
    def calculate_technical_indicators(
        self, 
        symbol: str, 
        current_price: float,
        market_data: Dict
    ) -> Optional[TechnicalIndicatorsData]:
        """
        Calculate technical indicators for an asset using historical price data
        
        Args:
            symbol: Asset symbol
            current_price: Current price of the asset
            market_data: Market data dictionary
            
        Returns:
            TechnicalIndicatorsData object or None if insufficient data
        """
        try:
            from technical_indicators import TechnicalIndicators
        except ImportError:
            return None
        
        # Try to get historical prices from database first
        historical_prices = None
        if DATABASE_AVAILABLE:
            try:
                db = PortfolioDatabase()
                historical_prices = db.get_historical_prices(symbol, days=200)
                db.close()
                
                # Check if we have enough data and if it's recent
                if historical_prices:
                    latest_date = historical_prices[-1][0] if historical_prices else None
                    days_old = (datetime.now() - latest_date).days if latest_date else 999
                    
                    # If data is more than 2 days old, fetch fresh data
                    if days_old > 2 or len(historical_prices) < 50:
                        historical_prices = None
            except Exception as e:
                # If database fails, fall back to API
                historical_prices = None
        
        # Fetch from API if database doesn't have recent data
        if not historical_prices or len(historical_prices) < 50:
            historical_prices = self.fetch_historical_prices(symbol, days=200)
            
            # Save to database if we got data
            if historical_prices and DATABASE_AVAILABLE:
                try:
                    db = PortfolioDatabase()
                    # Convert to format for database storage
                    price_data = [
                        (date.strftime("%Y-%m-%d"), price, None, None)
                        for date, price in historical_prices
                    ]
                    db.save_historical_prices(symbol, price_data)
                    db.close()
                except Exception:
                    pass  # Don't fail if database save fails
        
        if not historical_prices or len(historical_prices) < 14:
            # Not enough data for indicators
            return None
        
        # Extract just the prices (oldest to newest)
        prices = [price for _, price in historical_prices]
        
        # Add current price if not already included
        if len(prices) == 0 or prices[-1] != current_price:
            prices.append(current_price)
        
        # Calculate indicators
        rsi = TechnicalIndicators.calculate_rsi(prices, period=14)
        sma_50 = TechnicalIndicators.calculate_sma(prices, period=50) if len(prices) >= 50 else None
        sma_200 = TechnicalIndicators.calculate_sma(prices, period=200) if len(prices) >= 200 else None
        ema_12 = TechnicalIndicators.calculate_ema(prices, period=12) if len(prices) >= 12 else None
        ema_26 = TechnicalIndicators.calculate_ema(prices, period=26) if len(prices) >= 26 else None
        
        # Calculate MACD with proper history
        macd = None
        if len(prices) >= 26:
            macd = TechnicalIndicators.calculate_macd_with_history(prices)
        
        # Calculate Bollinger Bands
        bollinger_bands = TechnicalIndicators.calculate_bollinger_bands(prices, period=20) if len(prices) >= 20 else None
        
        # Determine price position relative to moving averages
        price_vs_ma_position = None
        if sma_200 and current_price > 0:
            distance_pct = ((current_price - sma_200) / sma_200) * 100
            if distance_pct > 5:
                price_vs_ma_position = "above"
            elif distance_pct < -5:
                price_vs_ma_position = "below"
            else:
                price_vs_ma_position = "near"
        
        # Determine price position relative to Bollinger Bands
        price_vs_bands_position = TechnicalIndicators.get_price_position_in_bands(
            current_price, bollinger_bands
        )
        
        return TechnicalIndicatorsData(
            rsi=rsi,
            sma_50=sma_50,
            sma_200=sma_200,
            ema_12=ema_12,
            ema_26=ema_26,
            macd=macd,
            bollinger_bands=bollinger_bands,
            price_vs_ma_position=price_vs_ma_position,
            price_vs_bands_position=price_vs_bands_position
        )
    
    def _generate_dca_recommendation(
        self,
        asset: Asset,
        change_24h: float,
        change_7d: float,
        change_30d: float,
        momentum: float,
        risk_adjusted_momentum: float,
        volatility: float,
        trend: str,
        technical_indicators: Optional[TechnicalIndicatorsData]
    ) -> Tuple[Recommendation, str, str, float, int]:
        """
        Generate DCA-based recommendation
        
        Returns:
            Tuple of (recommendation, reason, action, dca_multiplier, priority)
        """
        reasons = []
        dca_multiplier = 1.0
        priority = 0
        
        # Use technical indicators if available
        rsi = technical_indicators.rsi if technical_indicators else None
        sma_200 = technical_indicators.sma_200 if technical_indicators else None
        price_vs_ma = technical_indicators.price_vs_ma_position if technical_indicators else None
        
        # Factor 1: RSI-based DCA adjustments
        if rsi is not None:
            if rsi < RSI_EXTREME_OVERSOLD:  # Very oversold
                dca_multiplier = 2.0
                priority = 10
                reasons.append(f"Extremely oversold (RSI: {rsi:.1f})")
                return (
                    Recommendation.DCA_INCREASE,
                    f"Extremely oversold conditions (RSI: {rsi:.1f}) - excellent buying opportunity",
                    f"Increase DCA amount by 2.0x this period",
                    dca_multiplier,
                    priority
                )
            elif rsi < RSI_OVERSOLD:  # Oversold
                dca_multiplier = 1.5
                priority = 7
                reasons.append(f"Oversold (RSI: {rsi:.1f})")
                return (
                    Recommendation.DCA_INCREASE,
                    f"Oversold conditions (RSI: {rsi:.1f}) - good buying opportunity",
                    f"Increase DCA amount by 1.5x this period",
                    dca_multiplier,
                    priority
                )
            elif rsi > RSI_EXTREME_OVERBOUGHT:  # Very overbought
                reasons.append(f"Extremely overbought (RSI: {rsi:.1f})")
                # Check if we should DCA out for profit-taking
                # If allocation is above target and extremely overbought, suggest DCA out
                if asset.allocation_percent > 10:  # Has meaningful position
                    # Check if we have target allocation info
                    try:
                        from portfolio_rebalancer import PortfolioRebalancer
                        rebalancer = PortfolioRebalancer()
                        target_allocation = rebalancer.target_allocations.get(asset.symbol, 0)
                        if asset.allocation_percent > target_allocation:
                            return (
                                Recommendation.DCA_OUT_START,
                                f"Extremely overbought (RSI: {rsi:.1f}) and above target allocation ({asset.allocation_percent:.1f}% vs {target_allocation:.1f}%) - profit-taking opportunity",
                                "Begin DCA out strategy to take profits",
                                0.0,
                                8
                            )
                    except:
                        pass
                # Otherwise just pause
                return (
                    Recommendation.DCA_PAUSE,
                    f"Extremely overbought (RSI: {rsi:.1f}) - consider pausing DCA",
                    "Pause DCA temporarily or begin DCA out strategy",
                    0.0,
                    5
                )
            elif rsi > RSI_OVERBOUGHT:  # Overbought
                dca_multiplier = 0.5
                priority = 3
                reasons.append(f"Overbought (RSI: {rsi:.1f})")
                return (
                    Recommendation.DCA_DECREASE,
                    f"Overbought conditions (RSI: {rsi:.1f}) - reduce DCA amount",
                    f"Reduce DCA amount by 0.5x this period",
                    dca_multiplier,
                    priority
                )
        
        # Factor 2: Moving Average context
        if sma_200 is not None and asset.current_price > 0:
            price_above_200ma = asset.current_price > sma_200
            price_distance_from_200ma = abs((asset.current_price - sma_200) / sma_200) * 100
            
            if not price_above_200ma and price_distance_from_200ma > 10:
                # Price significantly below 200-day MA - accumulation zone
                dca_multiplier = max(dca_multiplier, 1.3)
                priority = max(priority, 6)
                reasons.append(f"Price {price_distance_from_200ma:.1f}% below 200-day MA (accumulation zone)")
            elif price_above_200ma and price_distance_from_200ma > 20:
                # Price far above 200-day MA - be cautious or take profits
                # Check if we should DCA out for profit-taking
                if asset.allocation_percent > 10:  # Has meaningful position
                    # Check if allocation is above target and we have strong gains
                    try:
                        from portfolio_rebalancer import PortfolioRebalancer
                        rebalancer = PortfolioRebalancer()
                        target_allocation = rebalancer.target_allocations.get(asset.symbol, 0)
                        # If above target and price is far above MA, suggest DCA out
                        if asset.allocation_percent > target_allocation and change_30d > 20:
                            return (
                                Recommendation.DCA_OUT_START,
                                f"Price {price_distance_from_200ma:.1f}% above 200-day MA with strong 30d gains ({change_30d:.1f}%) and above target allocation - profit-taking opportunity",
                                "Begin DCA out strategy to lock in gains",
                                0.0,
                                7
                            )
                    except:
                        pass
                # Otherwise just reduce DCA
                dca_multiplier = min(dca_multiplier, 0.7)
                priority = max(priority, 4)
                reasons.append(f"Price {price_distance_from_200ma:.1f}% above 200-day MA")
        
        # Factor 3: Allocation-based adjustments
        if asset.allocation_percent < 5 and trend != "bearish":
            # Under-allocated - increase priority
            priority = max(priority, 8)
            reasons.append("Under-allocated position")
            dca_multiplier = max(dca_multiplier, 1.2)
        elif asset.allocation_percent > OVER_ALLOCATION_THRESHOLD:
            # Over-allocated - reduce or pause
            if trend == "bearish" or risk_adjusted_momentum < MODERATE_BEARISH_THRESHOLD:
                return (
                    Recommendation.DCA_OUT_START,
                    f"Over-allocated ({asset.allocation_percent:.1f}%) with bearish signals",
                    "Begin DCA out strategy to reduce exposure",
                    0.0,
                    9
                )
            else:
                dca_multiplier = 0.0  # Pause buying
                priority = 2
                reasons.append(f"Over-allocated ({asset.allocation_percent:.1f}%)")
        
        # Factor 4: Strong bearish momentum - pause or reduce
        if risk_adjusted_momentum < BEARISH_MOMENTUM_THRESHOLD and change_24h < STRONG_PRICE_DROP_THRESHOLD:
            if asset.allocation_percent > 20:
                return (
                    Recommendation.DCA_PAUSE,
                    "Strong bearish momentum detected - pause DCA",
                    "Pause DCA until trend stabilizes",
                    0.0,
                    6
                )
            else:
                dca_multiplier = 0.5
                priority = 4
                reasons.append("Bearish momentum - reduce DCA")
        
        # Factor 5: Strong bullish momentum with low allocation
        if risk_adjusted_momentum > STRONG_MOMENTUM_THRESHOLD and asset.allocation_percent < 10:
            dca_multiplier = max(dca_multiplier, 1.3)
            priority = max(priority, 7)
            reasons.append("Strong bullish momentum with low allocation")
        
        # Factor 6: High volatility - be cautious
        if volatility > HIGH_VOLATILITY_THRESHOLD:
            dca_multiplier = min(dca_multiplier, 0.8)
            priority = max(priority, 3)
            reasons.append(f"High volatility ({volatility:.1f}%)")
        
        # Factor 7: MACD bearish divergence + overbought conditions (profit-taking signal)
        if technical_indicators and technical_indicators.macd:
            macd = technical_indicators.macd
            # Check for bearish MACD signal (histogram negative or MACD below signal)
            if macd['histogram'] < 0 and rsi and rsi > RSI_OVERBOUGHT:
                # Bearish MACD with overbought RSI - potential reversal
                if asset.allocation_percent > 10:  # Has meaningful position
                    try:
                        from portfolio_rebalancer import PortfolioRebalancer
                        rebalancer = PortfolioRebalancer()
                        target_allocation = rebalancer.target_allocations.get(asset.symbol, 0)
                        # If above target, suggest DCA out
                        if asset.allocation_percent > target_allocation:
                            return (
                                Recommendation.DCA_OUT_START,
                                f"Bearish MACD divergence (histogram: {macd['histogram']:.2f}) with overbought RSI ({rsi:.1f}) and above target allocation - potential reversal signal",
                                "Begin DCA out strategy to protect gains",
                                0.0,
                                7
                            )
                    except:
                        pass
        
        # Determine final recommendation based on multiplier
        if dca_multiplier == 0.0:
            recommendation = Recommendation.DCA_PAUSE
            action = "Pause DCA temporarily"
        elif dca_multiplier >= 1.3:
            recommendation = Recommendation.DCA_INCREASE
            action = f"Increase DCA amount by {dca_multiplier:.1f}x this period"
        elif dca_multiplier <= 0.7:
            recommendation = Recommendation.DCA_DECREASE
            action = f"Reduce DCA amount by {dca_multiplier:.1f}x this period"
        else:
            recommendation = Recommendation.DCA_STANDARD
            action = "Continue standard DCA schedule"
        
        reason_text = "; ".join(reasons) if reasons else "Normal market conditions"
        return (recommendation, reason_text, action, dca_multiplier, priority)
    
    def analyze_asset(self, asset: Asset, market_data: Dict) -> MarketAnalysis:
        """Analyze individual asset and generate recommendation"""
        symbol = asset.symbol
        
        if symbol not in market_data:
            return MarketAnalysis(
                symbol=symbol,
                price_change_24h=0,
                price_change_7d=0,
                price_change_30d=0,
                volatility=0,
                momentum=0,
                risk_adjusted_momentum=0,
                trend="neutral",
                recommendation=Recommendation.HOLD,
                reason="Market data unavailable",
                suggested_action="No action - data unavailable",
                technical_indicators=None,
                dca_multiplier=1.0,
                dca_priority=0
            )
        
        data = market_data[symbol]
        price_change_24h = data["price_change_24h"] or 0
        price_change_7d = data["price_change_7d"] or 0
        price_change_30d = data["price_change_30d"] or 0
        
        # Calculate volatility from price changes
        price_changes = [abs(price_change_24h), abs(price_change_7d), abs(price_change_30d)]
        volatility = self.calculate_volatility(price_changes)
        
        # Calculate raw momentum (weighted average of recent changes)
        momentum = (price_change_24h * 0.5 + price_change_7d * 0.3 + price_change_30d * 0.2)
        
        # Calculate risk-adjusted momentum (normalize by volatility)
        # This makes momentum comparable across assets with different volatility levels
        if volatility > 0:
            risk_adjusted_momentum = momentum / volatility
        else:
            risk_adjusted_momentum = momentum if momentum != 0 else 0
        
        # Determine trend using risk-adjusted momentum
        # Thresholds are now in terms of standard deviations (more statistically meaningful)
        if risk_adjusted_momentum > 1.0:  # More than 1 std dev above mean
            trend = "bullish"
        elif risk_adjusted_momentum < -1.0:  # More than 1 std dev below mean
            trend = "bearish"
        else:
            trend = "neutral"
        
        # Calculate technical indicators (if historical data available)
        technical_indicators = self.calculate_technical_indicators(
            symbol, asset.current_price, market_data
        )
        
        # Generate DCA-based recommendation
        recommendation, reason, action, dca_multiplier, priority = self._generate_dca_recommendation(
            asset, price_change_24h, price_change_7d, price_change_30d,
            momentum, risk_adjusted_momentum, volatility, trend, technical_indicators
        )
        
        return MarketAnalysis(
            symbol=symbol,
            price_change_24h=price_change_24h,
            price_change_7d=price_change_7d,
            price_change_30d=price_change_30d,
            volatility=volatility,
            momentum=momentum,
            risk_adjusted_momentum=risk_adjusted_momentum,
            trend=trend,
            recommendation=recommendation,
            reason=reason,
            suggested_action=action,
            technical_indicators=technical_indicators,
            dca_multiplier=dca_multiplier,
            dca_priority=priority
        )
    
    def _generate_recommendation(
        self, asset: Asset, change_24h: float, change_7d: float, 
        change_30d: float, momentum: float, risk_adjusted_momentum: float, 
        volatility: float, trend: str
    ) -> Tuple[Recommendation, str, str]:
        """Generate buy/sell/hold recommendation with reasoning"""
        
        reasons = []
        action_parts = []
        
        # Factor 1: Over-allocation check
        if asset.allocation_percent > OVER_ALLOCATION_THRESHOLD:
            reasons.append(f"Over-allocated at {asset.allocation_percent:.2f}%")
            # Use risk-adjusted momentum for more accurate signal detection
            if trend == "bearish" or risk_adjusted_momentum < MODERATE_BEARISH_THRESHOLD:
                return (
                    Recommendation.SELL,
                    f"Over-allocated ({asset.allocation_percent:.2f}%) and showing bearish signals",
                    f"Consider selling {min(10, asset.allocation_percent - 35):.1f}% to rebalance"
                )
        
        # Factor 2: Strong bearish momentum (using risk-adjusted)
        # BEARISH_MOMENTUM_THRESHOLD means 2 standard deviations below mean - very significant
        if risk_adjusted_momentum < BEARISH_MOMENTUM_THRESHOLD and change_24h < STRONG_PRICE_DROP_THRESHOLD:
            reasons.append("Strong bearish momentum detected")
            if asset.allocation_percent > 20:
                return (
                    Recommendation.SELL,
                    "Strong bearish momentum with significant recent decline",
                    f"Consider selling 10-20% to reduce exposure"
                )
        
        # Factor 3: Strong bullish momentum with low allocation (using risk-adjusted)
        # STRONG_MOMENTUM_THRESHOLD means 2 standard deviations above mean - very significant
        if risk_adjusted_momentum > STRONG_MOMENTUM_THRESHOLD and asset.allocation_percent < 10:
            reasons.append("Strong bullish momentum with low allocation")
            return (
                Recommendation.BUY,
                "Strong bullish momentum and under-allocated position",
                f"Consider increasing allocation to 10-15%"
            )
        
        # Factor 4: High volatility with over-allocation
        if volatility > HIGH_VOLATILITY_THRESHOLD and asset.allocation_percent > 30:
            reasons.append(f"High volatility ({volatility:.1f}%) with large position")
            if trend == "bearish":
                return (
                    Recommendation.SELL,
                    "High volatility combined with bearish trend",
                    "Consider reducing position by 5-10% to manage risk"
                )
        
        # Factor 5: Consistent positive momentum
        if change_7d > 10 and change_30d > 20 and asset.allocation_percent < 15:
            reasons.append("Consistent strong performance")
            return (
                Recommendation.BUY,
                "Consistent strong performance over multiple timeframes",
                "Consider adding to position if it fits your risk profile"
            )
        
        # Factor 6: Under-allocation with neutral/positive trend
        if asset.allocation_percent < 5 and trend != "bearish":
            reasons.append("Under-allocated with positive/neutral trend")
            return (
                Recommendation.BUY,
                "Under-allocated position with neutral or positive trend",
                "Consider increasing to 5-10% for better diversification"
            )
        
        # Factor 7: Rebalancing opportunity (moderate allocation, strong performance)
        if 10 <= asset.allocation_percent <= 30:
            if change_30d > 25:
                reasons.append("Strong 30-day performance suggests taking profits")
                return (
                    Recommendation.SELL,
                    "Strong 30-day gains suggest taking some profits",
                    "Consider selling 5-10% to lock in gains"
                )
        
        # Default: Hold
        reason_text = "; ".join(reasons) if reasons else "No strong signals detected"
        return (
            Recommendation.HOLD,
            reason_text or "Portfolio allocation and market conditions are balanced",
            "Maintain current position"
        )
    
    def ensure_historical_prices(self, symbols: List[str], force_refresh: bool = False, max_fetches: Optional[int] = None):
        """
        Ensure historical prices are available in database for all symbols
        
        Args:
            symbols: List of asset symbols
            force_refresh: If True, fetch fresh data even if recent data exists
            max_fetches: Maximum number of symbols to fetch in this run (defaults to MAX_HISTORICAL_FETCHES_PER_RUN)
        """
        if not DATABASE_AVAILABLE:
            return
        
        if max_fetches is None:
            max_fetches = MAX_HISTORICAL_FETCHES_PER_RUN
        
        try:
            db = PortfolioDatabase()
            symbols_to_fetch = []
            symbols_with_dates = {}  # Store latest dates for incremental updates
            
            for symbol in symbols:
                if symbol.upper() not in COIN_IDS:
                    continue
                
                if force_refresh:
                    symbols_to_fetch.append(symbol)
                    symbols_with_dates[symbol] = None
                else:
                    # Check if we have recent data
                    latest_date = db.get_latest_price_date(symbol)
                    if latest_date is None:
                        symbols_to_fetch.append(symbol)
                        symbols_with_dates[symbol] = None
                    else:
                        days_old = (datetime.now() - latest_date).days
                        if days_old > 2:
                            symbols_to_fetch.append(symbol)
                            symbols_with_dates[symbol] = latest_date
            
            db.close()
            
            # Limit number of fetches per run to avoid rate limits
            if len(symbols_to_fetch) > max_fetches:
                print(f"  Limiting to {max_fetches} fetches this run to avoid rate limits.")
                print(f"  Remaining {len(symbols_to_fetch) - max_fetches} symbols will be fetched on subsequent runs.")
                symbols_to_fetch = symbols_to_fetch[:max_fetches]
            
            # Fetch historical prices for symbols that need it
            if symbols_to_fetch:
                print(f"Fetching historical price data for {len(symbols_to_fetch)} assets...")
                print("(Adding delays between requests to respect rate limits)")
                
                for i, symbol in enumerate(symbols_to_fetch):
                    try:
                        # Add delay between requests (except for first one)
                        if i > 0:
                            delay = HISTORICAL_PRICE_FETCH_DELAY
                            print(f"  Waiting {delay} seconds before next request...")
                            time.sleep(delay)
                        
                        # Use incremental update if we have existing data
                        latest_date = symbols_with_dates.get(symbol)
                        if latest_date is not None and not force_refresh:
                            historical_prices = self.fetch_missing_historical_prices(symbol, latest_date)
                        else:
                            historical_prices = self.fetch_historical_prices(symbol, days=200)
                        
                        if historical_prices:
                            db = PortfolioDatabase()
                            price_data = [
                                (date.strftime("%Y-%m-%d"), price, None, None)
                                for date, price in historical_prices
                            ]
                            db.save_historical_prices(symbol, price_data)
                            db.close()
                            print(f"  ✓ {symbol}: {len(historical_prices)} days of price data")
                        else:
                            print(f"  ✗ {symbol}: Failed to fetch historical prices")
                            # If we hit rate limit, stop fetching remaining symbols
                            # to avoid further rate limit issues
                            if i < len(symbols_to_fetch) - 1:
                                print(f"  Stopping further fetches to avoid rate limits.")
                                print(f"  Remaining symbols will be fetched on next run.")
                                break
                    except Exception as e:
                        error_msg = str(e).lower()
                        print(f"  ✗ {symbol}: Error - {e}")
                        # Check if it's a rate limit error
                        if "rate limit" in error_msg or "429" in error_msg:
                            print(f"  Rate limit detected. Stopping further fetches.")
                            if i < len(symbols_to_fetch) - 1:
                                print(f"  Remaining {len(symbols_to_fetch) - i - 1} symbols will be fetched on next run.")
                            break
        except Exception as e:
            print(f"Warning: Could not ensure historical prices: {e}")
    
    def evaluate_portfolio(self, market_data: Optional[Dict] = None) -> List[MarketAnalysis]:
        """
        Evaluate entire portfolio and return recommendations
        
        Args:
            market_data: Optional pre-fetched market data. If None, will fetch it.
        """
        symbols = list(self.portfolio.keys())
        
        # Use provided market_data or fetch it
        if market_data is None:
            print(f"Fetching market data for {len(symbols)} assets...")
            market_data = self.fetch_market_data(symbols)
            
            if not market_data:
                print("Warning: Could not fetch market data. Using placeholder data.")
                return []
        else:
            print(f"Using pre-fetched market data for {len(symbols)} assets...")
        
        # Store market_data for use in rebalancing calculations
        self.market_data = market_data
        
        print(f"Successfully fetched data for {len(market_data)} assets")
        
        # Ensure historical prices are available for technical indicators
        # This will check database first and only fetch if needed
        self.ensure_historical_prices(symbols, force_refresh=False)
        print()
        
        analyses = []
        for symbol, asset in self.portfolio.items():
            analysis = self.analyze_asset(asset, market_data)
            analyses.append(analysis)
        
        return analyses
    
    def _print_recommendation_section(
        self, 
        action_type: str, 
        section_title: str, 
        analyses: List[MarketAnalysis],
        show_action: bool = True
    ):
        """Helper method to print a section of recommendations"""
        print(f"[{action_type}] {section_title}")
        print("-" * 80)
        for analysis in analyses:
            asset = self.portfolio[analysis.symbol]
            print(f"\n{asset.name} ({analysis.symbol})")
            print(f"  Current Allocation: {asset.allocation_percent:.2f}%")
            print(f"  Current Value: AU${asset.value:,.2f}")
            print(f"  24h Change: {analysis.price_change_24h:+.2f}%")
            print(f"  7d Change: {analysis.price_change_7d:+.2f}%")
            print(f"  30d Change: {analysis.price_change_30d:+.2f}%")
            print(f"  Momentum: {analysis.momentum:+.2f}%")
            print(f"  Risk-Adjusted Momentum: {analysis.risk_adjusted_momentum:+.2f} std dev")
            print(f"  Trend: {analysis.trend.upper()}")
            
            # Show technical indicators if available
            if analysis.technical_indicators:
                ti = analysis.technical_indicators
                if ti.rsi is not None:
                    rsi_status = ""
                    if ti.rsi < 30:
                        rsi_status = " (Oversold)"
                    elif ti.rsi > 70:
                        rsi_status = " (Overbought)"
                    print(f"  RSI: {ti.rsi:.1f}{rsi_status}")
                
                if ti.sma_50 is not None:
                    print(f"  50-day SMA: AU${ti.sma_50:,.2f}")
                
                if ti.sma_200 is not None:
                    print(f"  200-day SMA: AU${ti.sma_200:,.2f}")
                    if asset.current_price > 0:
                        ma_distance = ((asset.current_price - ti.sma_200) / ti.sma_200) * 100
                        print(f"  Price vs 200-day MA: {ma_distance:+.1f}%")
                
                if ti.macd is not None:
                    macd = ti.macd
                    macd_signal = "Bullish" if macd['histogram'] > 0 else "Bearish"
                    print(f"  MACD: {macd['macd']:.2f} | Signal: {macd['signal']:.2f} | Histogram: {macd['histogram']:.2f} ({macd_signal})")
                
                if ti.bollinger_bands is not None:
                    bb = ti.bollinger_bands
                    if ti.price_vs_bands_position:
                        position_map = {
                            'above_upper': 'Above Upper Band',
                            'upper_half': 'Upper Half',
                            'lower_half': 'Lower Half',
                            'below_lower': 'Below Lower Band'
                        }
                        position_str = position_map.get(ti.price_vs_bands_position, ti.price_vs_bands_position)
                        print(f"  Bollinger Bands: {position_str} (Upper: AU${bb['upper']:,.2f}, Lower: AU${bb['lower']:,.2f})")
            
            # Show DCA information for DCA recommendations
            if analysis.recommendation in [
                Recommendation.DCA_INCREASE, 
                Recommendation.DCA_STANDARD, 
                Recommendation.DCA_DECREASE,
                Recommendation.DCA_PAUSE,
                Recommendation.DCA_OUT_START,
                Recommendation.DCA_OUT_ACCELERATE
            ]:
                print(f"  DCA Multiplier: {analysis.dca_multiplier:.2f}x")
                print(f"  DCA Priority: {analysis.dca_priority}/10")
            
            print(f"  Reason: {analysis.reason}")
            if show_action:
                print(f"  Action: {analysis.suggested_action}")
        print()
    
    def print_report(self, analyses: List[MarketAnalysis], show_history: bool = False, show_rebalancing: bool = True):
        """Print formatted evaluation report"""
        print("=" * 80)
        print("PORTFOLIO EVALUATION REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()
        
        # Calculate total portfolio value
        total_value = sum(asset.value for asset in self.portfolio.values())
        
        print(f"Total Portfolio Value: AU${total_value:,.2f}")
        print(f"Number of Assets: {len(self.portfolio)}")
        
        # Show historical performance if requested and database is available
        if show_history and DATABASE_AVAILABLE:
            try:
                db = PortfolioDatabase()
                returns = db.calculate_returns()
                if returns:
                    print("\n" + "-" * 80)
                    print("PERFORMANCE METRICS")
                    print("-" * 80)
                    print("Returns:")
                    if 'daily' in returns:
                        print(f"  24h Return: {returns['daily']:+.2f}%")
                    if 'weekly' in returns:
                        print(f"  7d Return: {returns['weekly']:+.2f}%")
                    if 'monthly' in returns:
                        print(f"  30d Return: {returns['monthly']:+.2f}%")
                    if 'ytd' in returns:
                        print(f"  YTD Return: {returns['ytd']:+.2f}%")
                    if 'all_time' in returns:
                        print(f"  All-Time Return: {returns['all_time']:+.2f}%")
                    
                    # Advanced metrics
                    print("\nRisk-Adjusted Metrics:")
                    sharpe = db.calculate_sharpe_ratio(days=365)
                    if sharpe is not None:
                        sharpe_rating = "Excellent" if sharpe > 3 else "Very Good" if sharpe > 2 else "Good" if sharpe > 1 else "Below Average"
                        print(f"  Sharpe Ratio: {sharpe:.2f} ({sharpe_rating})")
                    
                    sortino = db.calculate_sortino_ratio(days=365)
                    if sortino is not None:
                        if sortino < 999:
                            sortino_rating = "Excellent" if sortino > 3 else "Very Good" if sortino > 2 else "Good" if sortino > 1 else "Below Average"
                            print(f"  Sortino Ratio: {sortino:.2f} ({sortino_rating})")
                        else:
                            print(f"  Sortino Ratio: Perfect (no downside volatility)")
                    
                    # Maximum Drawdown
                    drawdown = db.calculate_max_drawdown(days=365)
                    if drawdown:
                        print(f"\nMaximum Drawdown:")
                        print(f"  Drawdown: {drawdown['max_drawdown_pct']:.2f}% (AU${drawdown['max_drawdown_value']:,.2f})")
                        if drawdown['peak_date']:
                            print(f"  Peak Date: {drawdown['peak_date'].strftime('%Y-%m-%d')}")
                        if drawdown['trough_date']:
                            print(f"  Trough Date: {drawdown['trough_date'].strftime('%Y-%m-%d')}")
                        if drawdown['recovery_date']:
                            print(f"  Recovery Date: {drawdown['recovery_date'].strftime('%Y-%m-%d')}")
                            if drawdown['days_to_recover']:
                                print(f"  Days to Recover: {drawdown['days_to_recover']}")
                        elif drawdown['trough_date']:
                            print(f"  Status: Not yet recovered")
                    
                    # Benchmark Comparison
                    benchmark = db.calculate_benchmark_comparison(benchmark_symbol="BTC", days=365)
                    if benchmark and 'error' not in benchmark:
                        print(f"\nBenchmark Comparison (vs BTC):")
                        if benchmark.get('portfolio_return') is not None:
                            print(f"  Portfolio Return: {benchmark['portfolio_return']:+.2f}%")
                        if benchmark.get('benchmark_return') is not None:
                            print(f"  BTC Return: {benchmark['benchmark_return']:+.2f}%")
                        if benchmark.get('excess_return') is not None:
                            outperformance = benchmark['excess_return']
                            status = "Outperforming" if outperformance > 0 else "Underperforming"
                            print(f"  Excess Return: {outperformance:+.2f}% ({status})")
                        if benchmark.get('beta') is not None:
                            beta = benchmark['beta']
                            beta_desc = "More volatile" if beta > 1 else "Less volatile" if beta < 1 else "Similar volatility"
                            print(f"  Beta: {beta:.2f} ({beta_desc} than BTC)")
                    elif benchmark and 'error' in benchmark:
                        print(f"\nBenchmark Comparison: {benchmark['error']}")
                    
                    snapshot_count = db.get_snapshot_count()
                    print(f"\nHistorical Snapshots: {snapshot_count}")
                db.close()
            except Exception as e:
                print(f"\nNote: Could not load historical data: {e}")
                import traceback
                traceback.print_exc()
        
        # Get rebalancing actions for summary (calculate once, use multiple times)
        rebalancing_actions = []
        if show_rebalancing and REBALANCER_AVAILABLE:
            try:
                rebalancer = PortfolioRebalancer()
                # Get market data for assets not in portfolio (if available)
                market_data = getattr(self, 'market_data', None)
                rebalancing_actions = rebalancer.calculate_rebalancing(
                    self.portfolio, 
                    market_data=market_data
                )
                if rebalancing_actions:
                    print("\n")
                    rebalancer.print_rebalancing_report(rebalancing_actions, total_value, show_hold=False)
                    
                    # Check if there are sell actions - if so, offer deposit-based alternative
                    sell_actions = [a for a in rebalancing_actions if a.action == "SELL"]
                    buy_actions = [a for a in rebalancing_actions if a.action == "BUY"]
                    
                    if sell_actions or buy_actions:
                        print("\n" + "=" * 100)
                        print("DEPOSIT-BASED REBALANCING OPTION")
                        print("=" * 100)
                        print("Instead of selling assets, you can rebalance using new deposits.")
                        print("This avoids capital gains taxes and keeps your portfolio growing.")
                        print()
                        
                        # Calculate minimum deposit needed to fully rebalance
                        total_buy_needed = sum(a.value_diff for a in buy_actions if a.value_diff > 0)
                        if total_buy_needed > 0:
                            print(f"Minimum deposit to fully rebalance: AU${total_buy_needed:,.2f}")
                            print("(You can deposit any amount - smaller deposits will partially rebalance)")
                            print()
                        
                        try:
                            deposit_input = input("Enter deposit amount (AUD) to see allocation plan (or press Enter to skip): ").strip()
                            if deposit_input:
                                deposit_amount = float(deposit_input)
                                if deposit_amount > 0:
                                    # Extract DCA priorities from analyses
                                    dca_priorities = {}
                                    for analysis in analyses:
                                        if analysis.dca_priority > 0:
                                            dca_priorities[analysis.symbol] = analysis.dca_priority
                                    
                                    rebalancer.print_deposit_allocation_report(
                                        self.portfolio,
                                        deposit_amount,
                                        market_data=market_data,
                                        dca_priorities=dca_priorities if dca_priorities else None
                                    )
                                else:
                                    print("Deposit amount must be greater than 0.")
                        except (ValueError, EOFError, KeyboardInterrupt):
                            # Handle invalid input or non-interactive mode
                            pass
            except Exception as e:
                print(f"\nNote: Could not generate rebalancing report: {e}")
                rebalancing_actions = []
        
        print()
        
        # Calculate rebalancing counts for summary
        rebalancing_buy_count = len([a for a in rebalancing_actions if a.action == "BUY"]) if rebalancing_actions else 0
        rebalancing_sell_count = len([a for a in rebalancing_actions if a.action == "SELL"]) if rebalancing_actions else 0
        rebalancing_hold_count = len([a for a in rebalancing_actions if a.action == "HOLD"]) if rebalancing_actions else 0
        
        # Group DCA recommendations
        dca_increase = [a for a in analyses if a.recommendation == Recommendation.DCA_INCREASE]
        dca_standard = [a for a in analyses if a.recommendation == Recommendation.DCA_STANDARD]
        dca_decrease = [a for a in analyses if a.recommendation == Recommendation.DCA_DECREASE]
        dca_pause = [a for a in analyses if a.recommendation == Recommendation.DCA_PAUSE]
        dca_out = [a for a in analyses if a.recommendation in [
            Recommendation.DCA_OUT_START, 
            Recommendation.DCA_OUT_ACCELERATE
        ]]
        
        # Print DCA recommendations first (if any)
        if dca_increase:
            # Sort by priority
            dca_increase.sort(key=lambda x: x.dca_priority, reverse=True)
            self._print_recommendation_section("DCA", "INCREASE DCA AMOUNT", dca_increase, show_action=True)
        
        if dca_standard:
            self._print_recommendation_section("DCA", "STANDARD DCA SCHEDULE", dca_standard, show_action=True)
        
        if dca_decrease:
            self._print_recommendation_section("DCA", "REDUCE DCA AMOUNT", dca_decrease, show_action=True)
        
        if dca_pause:
            self._print_recommendation_section("DCA", "PAUSE DCA", dca_pause, show_action=True)
        
        if dca_out:
            self._print_recommendation_section("DCA", "DCA OUT STRATEGY", dca_out, show_action=True)
        
        # Summary
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"DCA Increase: {len(dca_increase)}")
        print(f"DCA Standard: {len(dca_standard)}")
        print(f"DCA Decrease: {len(dca_decrease)}")
        print(f"DCA Pause: {len(dca_pause)}")
        print(f"DCA Out: {len(dca_out)}")
        print(f"Rebalancing - Assets to Sell: {rebalancing_sell_count}")
        print(f"Rebalancing - Assets to Buy: {rebalancing_buy_count}")
        print(f"Rebalancing - Assets to Hold: {rebalancing_hold_count}")
        print()
        print("[!] DISCLAIMER: This is an automated analysis tool. Always do your own")
        print("   research and consider your risk tolerance before making trading decisions.")
        print("=" * 80)


def load_portfolio_from_balances(balances: Dict[str, float], market_data: Dict) -> Dict[str, Asset]:
    """
    Build portfolio Asset objects from blockchain balances and market prices
    
    Args:
        balances: Dictionary mapping asset symbols to amounts
        market_data: Market data from CoinGecko API
        
    Returns:
        Dictionary of Asset objects
    """
    portfolio = {}
    total_value = 0.0
    
    # First pass: calculate values
    asset_values = {}
    for symbol, amount in balances.items():
        if symbol in market_data:
            price = market_data[symbol]["current_price"]
            value = amount * price
            asset_values[symbol] = value
            total_value += value
    
    # Second pass: create Asset objects with allocations
    for symbol, amount in balances.items():
        if symbol in market_data:
            price = market_data[symbol]["current_price"]
            value = asset_values[symbol]
            allocation = (value / total_value * 100) if total_value > 0 else 0
            
            portfolio[symbol] = Asset(
                symbol=symbol,
                name=COIN_NAMES.get(symbol, symbol),
                amount=amount,
                current_price=price,
                allocation_percent=allocation,
                value=value
            )
    
    return portfolio


def load_portfolio_from_wallet(wallet_config_path: str = "wallet_config.json", prompt_for_btc: bool = True) -> Tuple[Optional[Dict[str, Asset]], Optional[Dict]]:
    """
    Load portfolio automatically from wallet addresses
    
    Args:
        wallet_config_path: Path to wallet configuration file
        prompt_for_btc: Whether to prompt for Bitcoin balance if not in config (default: True)
                       Set to False for non-interactive use (e.g., API servers)
        
    Returns:
        Tuple of (Dictionary of Asset objects, market_data Dict) or (None, None) if loading fails
    """
    if not BLOCKCHAIN_FETCHER_AVAILABLE:
        print("Error: blockchain_balance_fetcher module not available")
        return None, None
    
    if not os.path.exists(wallet_config_path):
        print(f"Wallet config file not found: {wallet_config_path}")
        print("Please create wallet_config.json (see wallet_config.json.example)")
        return None, None
    
    try:
        with open(wallet_config_path, 'r') as f:
            wallet_config = json.load(f)
    except Exception as e:
        print(f"Error reading wallet config: {e}")
        return None, None
    
    # Initialize balance fetcher
    etherscan_key = wallet_config.get("etherscan_api_key")
    if not etherscan_key or etherscan_key == "YOUR_ETHERSCAN_API_KEY_HERE":
        print("Warning: Etherscan API key not configured. Ethereum/ERC-20 balances will not be fetched.")
        print("Get a free API key at https://etherscan.io/apis")
        etherscan_key = None
    
    fetcher = BlockchainBalanceFetcher(etherscan_api_key=etherscan_key)
    
    # Fetch balances - pass prompt_for_btc parameter
    balances = fetcher.fetch_all_balances(wallet_config, prompt_for_btc=prompt_for_btc)
    
    if not balances:
        print("No balances found. Please check your wallet addresses.")
        return None, None
    
    # Fetch market prices for all assets
    print("Fetching current market prices...")
    # Create temporary evaluator to use its fetch_market_data method
    temp_portfolio = {symbol: Asset(symbol=symbol, name=symbol, amount=0, current_price=0, allocation_percent=0, value=0) 
                     for symbol in balances.keys()}
    evaluator = PortfolioEvaluator(temp_portfolio)
    market_data = evaluator.fetch_market_data(list(balances.keys()))
    
    if not market_data:
        print("Error: Could not fetch market prices")
        return None, None
    
    # Build portfolio from balances and prices
    portfolio = load_portfolio_from_balances(balances, market_data)
    
    return portfolio, market_data


def save_portfolio_snapshot(portfolio: Dict[str, Asset], analyses: List[MarketAnalysis], enabled: bool = True):
    """
    Save current portfolio state to database
    
    Args:
        portfolio: Dictionary of Asset objects
        analyses: List of MarketAnalysis objects
        enabled: Whether to save snapshot (default: True)
    """
    if not enabled or not DATABASE_AVAILABLE:
        return
    
    try:
        db = PortfolioDatabase()
        snapshot_id = db.save_snapshot(portfolio, analyses)
        db.close()
        print(f"\n[✓] Portfolio snapshot saved (ID: {snapshot_id})")
    except Exception as e:
        print(f"\n[!] Warning: Could not save portfolio snapshot: {e}")


def print_portfolio_history(days: int = 30):
    """
    Print portfolio value history
    
    Args:
        days: Number of days to display
    """
    if not DATABASE_AVAILABLE:
        print("Database not available. Historical tracking requires portfolio_database module.")
        return
    
    try:
        db = PortfolioDatabase()
        history = db.get_portfolio_value_history(days=days)
        db.close()
        
        if not history:
            print(f"No historical data found for the last {days} days.")
            return
        
        print("=" * 80)
        print(f"PORTFOLIO VALUE HISTORY (Last {days} days)")
        print("=" * 80)
        print(f"{'Date':<20} {'Value (AUD)':<20} {'Change':<15} {'Change %':<15}")
        print("-" * 80)
        
        prev_value = None
        for timestamp, value in history:
            change_str = ""
            change_pct_str = ""
            if prev_value is not None:
                change = value - prev_value
                change_pct = (change / prev_value) * 100
                change_str = f"AU${change:+,.2f}"
                change_pct_str = f"{change_pct:+.2f}%"
            
            date_str = timestamp.strftime("%Y-%m-%d %H:%M")
            print(f"{date_str:<20} AU${value:>15,.2f} {change_str:>15} {change_pct_str:>15}")
            prev_value = value
        
        print("=" * 80)
        
    except Exception as e:
        print(f"Error loading portfolio history: {e}")


def main(save_snapshot: bool = True, show_rebalancing: bool = True):
    """
    Main function - initialize portfolio and run evaluation
    
    Args:
        save_snapshot: Whether to save portfolio snapshot to database (default: True)
        show_rebalancing: Whether to show rebalancing recommendations (default: True)
    """
    
    # Try to load portfolio from wallet addresses first
    portfolio, market_data = load_portfolio_from_wallet()
    
    # Fall back to manual portfolio if wallet loading fails
    if portfolio is None:
        market_data = None  # Will need to fetch it
        print("\nUsing manual portfolio configuration...")
        print("(To use automatic wallet syncing, set up wallet_config.json)\n")
        
        # Initialize portfolio based on the dashboard data
        portfolio = {
            "XRP": Asset(
                symbol="XRP",
                name="Ripple",
                amount=295.843,
                current_price=3.08,
                allocation_percent=44.81,
                value=913.09
            ),
            "BTC": Asset(
                symbol="BTC",
                name="Bitcoin",
                amount=0.00622109,
                current_price=134840.44,
                allocation_percent=41.16,
                value=838.85
            ),
            "ETH": Asset(
                symbol="ETH",
                name="Ethereum",
                amount=0.028903,
                current_price=4585.27,
                allocation_percent=6.5,
                value=132.52
            ),
            "SOL": Asset(
                symbol="SOL",
                name="Solana",
                amount=0.432648,
                current_price=199.96,
                allocation_percent=4.24,
                value=86.51
            ),
            "LINK": Asset(
                symbol="LINK",
                name="Chainlink",
                amount=3.17046,
                current_price=21.01,
                allocation_percent=3.27,
                value=66.63
            )
        }
    
    # Create evaluator and run analysis
    # Pass market_data if we already have it to avoid duplicate API calls
    evaluator = PortfolioEvaluator(portfolio)
    analyses = evaluator.evaluate_portfolio(market_data=market_data)
    
    # Ensure we have market data for all target allocation assets (for rebalancing)
    if REBALANCER_AVAILABLE and analyses:
        rebalancer = PortfolioRebalancer()
        target_symbols = list(rebalancer.target_allocations.keys())
        missing_symbols = [s for s in target_symbols if s not in evaluator.market_data]
        if missing_symbols:
            # Fetch prices for assets in target allocation but not in portfolio
            print(f"Fetching prices for target allocation assets: {', '.join(missing_symbols)}")
            additional_market_data = evaluator.fetch_market_data(missing_symbols)
            evaluator.market_data.update(additional_market_data)
    
    if analyses:
        # Save snapshot to database (unless disabled)
        save_portfolio_snapshot(portfolio, analyses, enabled=save_snapshot)
        
        # Print report with historical data and rebalancing recommendations
        evaluator.print_report(analyses, show_history=True, show_rebalancing=show_rebalancing)
        
        # Show brief history summary
        if DATABASE_AVAILABLE:
            print("\n" + "=" * 80)
            print("TIP: Use 'python portfolio_evaluator.py --history 30' to view detailed history")
            print("=" * 80)
    else:
        print("Error: Could not generate portfolio analysis.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cryptocurrency Portfolio Evaluator with Historical Tracking"
    )
    parser.add_argument(
        "--history",
        type=int,
        metavar="DAYS",
        help="Display portfolio value history for the last N days"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip saving portfolio snapshot to database"
    )
    parser.add_argument(
        "--no-rebalancing",
        action="store_true",
        help="Skip rebalancing recommendations"
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Start the web dashboard server"
    )
    
    args = parser.parse_args()
    
    # If --dashboard is specified, start the dashboard server
    if args.dashboard:
        try:
            from dashboard_api import app
            print("=" * 80)
            print("Starting Portfolio Dashboard...")
            print("=" * 80)
            print("Dashboard will be available at: http://localhost:5000")
            print("Press Ctrl+C to stop the server")
            print("=" * 80)
            app.run(debug=False, host='127.0.0.1', port=5000)
        except ImportError:
            print("Error: Could not import dashboard_api module.")
            print("Please ensure dashboard_api.py exists and Flask is installed.")
            print("Install Flask with: pip install flask flask-cors")
            sys.exit(1)
        except Exception as e:
            print(f"Error starting dashboard: {e}")
            sys.exit(1)
        sys.exit(0)
    
    # If --history is specified, show history and exit
    if args.history:
        print_portfolio_history(days=args.history)
        sys.exit(0)
    
    # Otherwise, run normal evaluation
    main(save_snapshot=not args.no_save, show_rebalancing=not args.no_rebalancing)
