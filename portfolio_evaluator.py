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


class Recommendation(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Asset:
    symbol: str
    name: str
    amount: float
    current_price: float
    allocation_percent: float
    value: float


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


class PortfolioEvaluator:
    """Evaluates cryptocurrency portfolio and provides trading recommendations"""
    
    # CoinGecko API endpoint (free, no API key required)
    BASE_URL = "https://api.coingecko.com/api/v3"
    
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
    
    def __init__(self, portfolio: Dict[str, Asset]):
        """
        Initialize evaluator with portfolio data
        
        Args:
            portfolio: Dictionary mapping asset symbols to Asset objects
        """
        self.portfolio = portfolio
        self.market_data = {}
        
    def fetch_market_data(self, symbols: List[str], retry_count: int = 3) -> Dict:
        """
        Fetch current market data for given symbols with retry logic for rate limits
        
        Args:
            symbols: List of asset symbols to fetch
            retry_count: Number of retry attempts for rate limit errors
        """
        coin_ids = [self.COIN_IDS.get(symbol.upper()) for symbol in symbols 
                   if symbol.upper() in self.COIN_IDS]
        
        if not coin_ids:
            return {}
        
        # Fetch price data with 24h, 7d, 30d changes
        url = f"{self.BASE_URL}/coins/markets"
        params = {
            "vs_currency": "aud",
            "ids": ",".join(coin_ids),
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": False,
            "price_change_percentage": "24h,7d,30d"
        }
        
        for attempt in range(retry_count):
            try:
                response = requests.get(url, params=params, timeout=10)
                
                # Handle rate limiting (429 Too Many Requests)
                if response.status_code == 429:
                    if attempt < retry_count - 1:
                        wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s, 6s
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
                    wait_time = (attempt + 1) * 2
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
            symbol = next((s for s, cid in self.COIN_IDS.items() 
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
    
    def calculate_volatility(self, price_changes: List[float]) -> float:
        """Calculate volatility from price changes"""
        if not price_changes:
            return 0.0
        
        mean = sum(price_changes) / len(price_changes)
        variance = sum((x - mean) ** 2 for x in price_changes) / len(price_changes)
        return variance ** 0.5
    
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
                suggested_action="No action - data unavailable"
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
        
        # Generate recommendation based on multiple factors
        recommendation, reason, action = self._generate_recommendation(
            asset, price_change_24h, price_change_7d, price_change_30d, 
            momentum, risk_adjusted_momentum, volatility, trend
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
            suggested_action=action
        )
    
    def _generate_recommendation(
        self, asset: Asset, change_24h: float, change_7d: float, 
        change_30d: float, momentum: float, risk_adjusted_momentum: float, 
        volatility: float, trend: str
    ) -> Tuple[Recommendation, str, str]:
        """Generate buy/sell/hold recommendation with reasoning"""
        
        reasons = []
        action_parts = []
        
        # Factor 1: Over-allocation check (if > 45%, consider rebalancing)
        if asset.allocation_percent > 45:
            reasons.append(f"Over-allocated at {asset.allocation_percent:.2f}%")
            # Use risk-adjusted momentum for more accurate signal detection
            if trend == "bearish" or risk_adjusted_momentum < -1.5:
                return (
                    Recommendation.SELL,
                    f"Over-allocated ({asset.allocation_percent:.2f}%) and showing bearish signals",
                    f"Consider selling {min(10, asset.allocation_percent - 35):.1f}% to rebalance"
                )
        
        # Factor 2: Strong bearish momentum (using risk-adjusted)
        # -2.0 means 2 standard deviations below mean - very significant for any asset
        if risk_adjusted_momentum < -2.0 and change_24h < -5:
            reasons.append("Strong bearish momentum detected")
            if asset.allocation_percent > 20:
                return (
                    Recommendation.SELL,
                    "Strong bearish momentum with significant recent decline",
                    f"Consider selling 10-20% to reduce exposure"
                )
        
        # Factor 3: Strong bullish momentum with low allocation (using risk-adjusted)
        # +2.0 means 2 standard deviations above mean - very significant for any asset
        if risk_adjusted_momentum > 2.0 and asset.allocation_percent < 10:
            reasons.append("Strong bullish momentum with low allocation")
            return (
                Recommendation.BUY,
                "Strong bullish momentum and under-allocated position",
                f"Consider increasing allocation to 10-15%"
            )
        
        # Factor 4: High volatility with over-allocation
        if volatility > 20 and asset.allocation_percent > 30:
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
        
        print(f"Successfully fetched data for {len(market_data)} assets\n")
        
        analyses = []
        for symbol, asset in self.portfolio.items():
            analysis = self.analyze_asset(asset, market_data)
            analyses.append(analysis)
        
        return analyses
    
    def print_report(self, analyses: List[MarketAnalysis], show_history: bool = False):
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
                    if 'daily' in returns:
                        print(f"24h Return: {returns['daily']:+.2f}%")
                    if 'weekly' in returns:
                        print(f"7d Return: {returns['weekly']:+.2f}%")
                    if 'monthly' in returns:
                        print(f"30d Return: {returns['monthly']:+.2f}%")
                    if 'ytd' in returns:
                        print(f"YTD Return: {returns['ytd']:+.2f}%")
                    if 'all_time' in returns:
                        print(f"All-Time Return: {returns['all_time']:+.2f}%")
                    snapshot_count = db.get_snapshot_count()
                    print(f"Historical Snapshots: {snapshot_count}")
                db.close()
            except Exception as e:
                print(f"\nNote: Could not load historical data: {e}")
        
        print()
        
        # Group by recommendation
        buy_assets = [a for a in analyses if a.recommendation == Recommendation.BUY]
        sell_assets = [a for a in analyses if a.recommendation == Recommendation.SELL]
        hold_assets = [a for a in analyses if a.recommendation == Recommendation.HOLD]
        
        # Print recommendations
        if sell_assets:
            print("[SELL] SELL RECOMMENDATIONS")
            print("-" * 80)
            for analysis in sell_assets:
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
                print(f"  Reason: {analysis.reason}")
                print(f"  Action: {analysis.suggested_action}")
            print()
        
        if buy_assets:
            print("[BUY] BUY RECOMMENDATIONS")
            print("-" * 80)
            for analysis in buy_assets:
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
                print(f"  Reason: {analysis.reason}")
                print(f"  Action: {analysis.suggested_action}")
            print()
        
        if hold_assets:
            print("[HOLD] HOLD RECOMMENDATIONS")
            print("-" * 80)
            for analysis in hold_assets:
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
                print(f"  Reason: {analysis.reason}")
            print()
        
        # Summary
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Assets to Sell: {len(sell_assets)}")
        print(f"Assets to Buy: {len(buy_assets)}")
        print(f"Assets to Hold: {len(hold_assets)}")
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
    coin_names = {
        "BTC": "Bitcoin",
        "ETH": "Ethereum",
        "XRP": "Ripple",
        "SOL": "Solana",
        "LINK": "Chainlink",
        "UNI": "Uniswap",
        "BCH": "Bitcoin Cash",
        "LEO": "LEO Token",
        "WBT": "WhiteBIT Coin"
    }
    
    for symbol, amount in balances.items():
        if symbol in market_data:
            price = market_data[symbol]["current_price"]
            value = asset_values[symbol]
            allocation = (value / total_value * 100) if total_value > 0 else 0
            
            portfolio[symbol] = Asset(
                symbol=symbol,
                name=coin_names.get(symbol, symbol),
                amount=amount,
                current_price=price,
                allocation_percent=allocation,
                value=value
            )
    
    return portfolio


def load_portfolio_from_wallet(wallet_config_path: str = "wallet_config.json") -> Tuple[Optional[Dict[str, Asset]], Optional[Dict]]:
    """
    Load portfolio automatically from wallet addresses
    
    Args:
        wallet_config_path: Path to wallet configuration file
        
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
    
    # Fetch balances
    balances = fetcher.fetch_all_balances(wallet_config)
    
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


def main(save_snapshot: bool = True):
    """
    Main function - initialize portfolio and run evaluation
    
    Args:
        save_snapshot: Whether to save portfolio snapshot to database (default: True)
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
    
    if analyses:
        # Save snapshot to database (unless disabled)
        save_portfolio_snapshot(portfolio, analyses, enabled=save_snapshot)
        
        # Print report with historical data
        evaluator.print_report(analyses, show_history=True)
        
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
    
    args = parser.parse_args()
    
    # If --history is specified, show history and exit
    if args.history:
        print_portfolio_history(days=args.history)
        sys.exit(0)
    
    # Otherwise, run normal evaluation
    main(save_snapshot=not args.no_save)
