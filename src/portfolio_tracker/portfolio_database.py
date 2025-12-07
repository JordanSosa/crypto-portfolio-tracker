"""
Portfolio Database Module
Handles SQLite database operations for storing historical portfolio data
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class PortfolioSnapshot:
    """Represents a single portfolio snapshot at a point in time"""
    timestamp: datetime
    total_value: float
    assets: Dict[str, Dict]  # symbol -> {amount, price, value, allocation_percent}


class PortfolioDatabase:
    """Manages SQLite database for portfolio historical data"""
    
    def __init__(self, db_path: str = None):
        """
        Initialize database connection and create tables if needed
        
        Args:
            db_path: Path to SQLite database file (defaults to data/portfolio_history.db)
        """
        if db_path is None:
            # Default to data directory if it exists, otherwise root
            if os.path.exists('data'):
                self.db_path = os.path.join('data', 'portfolio_history.db')
            else:
                self.db_path = 'portfolio_history.db'
        else:
            self.db_path = db_path
        self.conn = None
        self._initialize_database()
        # Initialize transaction tracker (lazy import to avoid circular dependencies)
        self._transaction_tracker = None
    
    def _initialize_database(self):
        """Create database tables if they don't exist"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        
        cursor = self.conn.cursor()
        
        # Table for portfolio snapshots (daily/weekly summaries)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL UNIQUE,
                total_value REAL NOT NULL,
                asset_count INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table for individual asset holdings in each snapshot
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asset_holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                amount REAL NOT NULL,
                price REAL NOT NULL,
                value REAL NOT NULL,
                allocation_percent REAL NOT NULL,
                FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE CASCADE,
                UNIQUE(snapshot_id, symbol)
            )
        """)
        
        # Table for market analysis data (recommendations, trends, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                price_change_24h REAL,
                price_change_7d REAL,
                price_change_30d REAL,
                volatility REAL,
                momentum REAL,
                risk_adjusted_momentum REAL,
                trend TEXT,
                recommendation TEXT,
                reason TEXT,
                suggested_action TEXT,
                FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE CASCADE,
                UNIQUE(snapshot_id, symbol)
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp 
            ON portfolio_snapshots(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_holdings_snapshot 
            ON asset_holdings(snapshot_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_holdings_symbol 
            ON asset_holdings(symbol)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_snapshot 
            ON market_analysis(snapshot_id)
        """)
        
        # Table for historical daily prices (for technical indicators)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                price REAL NOT NULL,
                volume_24h REAL,
                market_cap REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date)
            )
        """)
        
        # Create indexes for historical prices
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_historical_prices_symbol_date 
            ON historical_prices(symbol, date DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_historical_prices_symbol 
            ON historical_prices(symbol)
        """)
        
        self.conn.commit()
    
    def save_snapshot(
        self, 
        portfolio: Dict[str, any], 
        market_analyses: Optional[List[any]] = None,
        timestamp: Optional[datetime] = None
    ) -> int:
        """
        Save a portfolio snapshot to the database
        
        Args:
            portfolio: Dictionary mapping asset symbols to Asset objects
            market_analyses: Optional list of MarketAnalysis objects
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            snapshot_id: The ID of the created snapshot
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate total portfolio value
        total_value = sum(asset.value for asset in portfolio.values())
        asset_count = len(portfolio)
        
        cursor = self.conn.cursor()
        
        # Insert or replace snapshot (use INSERT OR REPLACE for same-day snapshots)
        cursor.execute("""
            INSERT OR REPLACE INTO portfolio_snapshots 
            (timestamp, total_value, asset_count)
            VALUES (?, ?, ?)
        """, (timestamp_str, total_value, asset_count))
        
        snapshot_id = cursor.lastrowid
        
        # If snapshot already existed, get its ID
        if snapshot_id == 0:
            cursor.execute("""
                SELECT id FROM portfolio_snapshots WHERE timestamp = ?
            """, (timestamp_str,))
            row = cursor.fetchone()
            if row:
                snapshot_id = row['id']
                # Delete old asset holdings and analysis for this snapshot
                cursor.execute("DELETE FROM asset_holdings WHERE snapshot_id = ?", (snapshot_id,))
                cursor.execute("DELETE FROM market_analysis WHERE snapshot_id = ?", (snapshot_id,))
        
        # Insert asset holdings
        for symbol, asset in portfolio.items():
            cursor.execute("""
                INSERT INTO asset_holdings 
                (snapshot_id, symbol, name, amount, price, value, allocation_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot_id,
                asset.symbol,
                asset.name,
                asset.amount,
                asset.current_price,
                asset.value,
                asset.allocation_percent
            ))
        
        # Insert market analysis if provided
        if market_analyses:
            for analysis in market_analyses:
                cursor.execute("""
                    INSERT INTO market_analysis
                    (snapshot_id, symbol, price_change_24h, price_change_7d, price_change_30d,
                     volatility, momentum, risk_adjusted_momentum, trend, recommendation,
                     reason, suggested_action)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    snapshot_id,
                    analysis.symbol,
                    analysis.price_change_24h,
                    analysis.price_change_7d,
                    analysis.price_change_30d,
                    analysis.volatility,
                    analysis.momentum,
                    analysis.risk_adjusted_momentum,
                    analysis.trend,
                    analysis.recommendation.value if hasattr(analysis.recommendation, 'value') else str(analysis.recommendation),
                    analysis.reason,
                    analysis.suggested_action
                ))
        
        self.conn.commit()
        return snapshot_id
    
    def get_latest_snapshot(self) -> Optional[PortfolioSnapshot]:
        """Get the most recent portfolio snapshot"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, total_value 
            FROM portfolio_snapshots 
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if not row:
            return None
        
        snapshot_id = row['id']
        timestamp = datetime.strptime(row['timestamp'], "%Y-%m-%d %H:%M:%S")
        
        # Get asset holdings
        cursor.execute("""
            SELECT symbol, name, amount, price, value, allocation_percent
            FROM asset_holdings
            WHERE snapshot_id = ?
        """, (snapshot_id,))
        
        assets = {}
        for asset_row in cursor.fetchall():
            assets[asset_row['symbol']] = {
                'name': asset_row['name'],
                'amount': asset_row['amount'],
                'price': asset_row['price'],
                'value': asset_row['value'],
                'allocation_percent': asset_row['allocation_percent']
            }
        
        return PortfolioSnapshot(
            timestamp=timestamp,
            total_value=row['total_value'],
            assets=assets
        )
    
    def get_portfolio_history(
        self, 
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[PortfolioSnapshot]:
        """
        Get portfolio history within a date range
        
        Args:
            days: Number of days back from now (if specified)
            start_date: Start date for query
            end_date: End date for query
            
        Returns:
            List of PortfolioSnapshot objects
        """
        cursor = self.conn.cursor()
        
        if days:
            start_date = datetime.now() - timedelta(days=days)
            end_date = datetime.now()
        
        if start_date and end_date:
            start_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
            end_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                SELECT id, timestamp, total_value 
                FROM portfolio_snapshots 
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            """, (start_str, end_str))
        else:
            cursor.execute("""
                SELECT id, timestamp, total_value 
                FROM portfolio_snapshots 
                ORDER BY timestamp ASC
            """)
        
        snapshots = []
        for row in cursor.fetchall():
            snapshot_id = row['id']
            timestamp = datetime.strptime(row['timestamp'], "%Y-%m-%d %H:%M:%S")
            
            # Get asset holdings for this snapshot
            cursor.execute("""
                SELECT symbol, name, amount, price, value, allocation_percent
                FROM asset_holdings
                WHERE snapshot_id = ?
            """, (snapshot_id,))
            
            assets = {}
            for asset_row in cursor.fetchall():
                assets[asset_row['symbol']] = {
                    'name': asset_row['name'],
                    'amount': asset_row['amount'],
                    'price': asset_row['price'],
                    'value': asset_row['value'],
                    'allocation_percent': asset_row['allocation_percent']
                }
            
            snapshots.append(PortfolioSnapshot(
                timestamp=timestamp,
                total_value=row['total_value'],
                assets=assets
            ))
        
        return snapshots
    
    def get_portfolio_value_history(
        self,
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Tuple[datetime, float]]:
        """
        Get simplified portfolio value history (timestamp, value pairs)
        
        Returns:
            List of (datetime, total_value) tuples
        """
        cursor = self.conn.cursor()
        
        if days:
            start_date = datetime.now() - timedelta(days=days)
            end_date = datetime.now()
        
        if start_date and end_date:
            start_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
            end_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                SELECT timestamp, total_value 
                FROM portfolio_snapshots 
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            """, (start_str, end_str))
        else:
            cursor.execute("""
                SELECT timestamp, total_value 
                FROM portfolio_snapshots 
                ORDER BY timestamp ASC
            """)
        
        return [
            (datetime.strptime(row['timestamp'], "%Y-%m-%d %H:%M:%S"), row['total_value'])
            for row in cursor.fetchall()
        ]
    
    def get_asset_history(
        self,
        symbol: str,
        days: Optional[int] = None
    ) -> List[Tuple[datetime, float, float, float]]:
        """
        Get historical data for a specific asset
        
        Args:
            symbol: Asset symbol (e.g., 'BTC', 'ETH')
            days: Number of days back from now
            
        Returns:
            List of (timestamp, amount, price, value) tuples
        """
        cursor = self.conn.cursor()
        
        if days:
            start_date = datetime.now() - timedelta(days=days)
            start_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                SELECT ps.timestamp, ah.amount, ah.price, ah.value
                FROM asset_holdings ah
                JOIN portfolio_snapshots ps ON ah.snapshot_id = ps.id
                WHERE ah.symbol = ? AND ps.timestamp >= ?
                ORDER BY ps.timestamp ASC
            """, (symbol, start_str))
        else:
            cursor.execute("""
                SELECT ps.timestamp, ah.amount, ah.price, ah.value
                FROM asset_holdings ah
                JOIN portfolio_snapshots ps ON ah.snapshot_id = ps.id
                WHERE ah.symbol = ?
                ORDER BY ps.timestamp ASC
            """, (symbol,))
        
        return [
            (
                datetime.strptime(row['timestamp'], "%Y-%m-%d %H:%M:%S"),
                row['amount'],
                row['price'],
                row['value']
            )
            for row in cursor.fetchall()
        ]
    
    def calculate_returns(
        self,
        days: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Calculate portfolio returns over different time periods
        
        Args:
            days: Number of days to look back (default: all available)
            
        Returns:
            Dictionary with return metrics
        """
        latest = self.get_latest_snapshot()
        if not latest:
            return {}
        
        current_value = latest.total_value
        returns = {}
        
        # Get historical snapshots
        history = self.get_portfolio_value_history(days=days)
        if len(history) < 2:
            return {}
        
        # Find snapshots at different time intervals
        now = datetime.now()
        
        # Daily return
        one_day_ago = now - timedelta(days=1)
        daily_snapshot = self._find_closest_snapshot(history, one_day_ago)
        if daily_snapshot:
            returns['daily'] = ((current_value - daily_snapshot[1]) / daily_snapshot[1]) * 100
        
        # Weekly return
        one_week_ago = now - timedelta(days=7)
        weekly_snapshot = self._find_closest_snapshot(history, one_week_ago)
        if weekly_snapshot:
            returns['weekly'] = ((current_value - weekly_snapshot[1]) / weekly_snapshot[1]) * 100
        
        # Monthly return
        one_month_ago = now - timedelta(days=30)
        monthly_snapshot = self._find_closest_snapshot(history, one_month_ago)
        if monthly_snapshot:
            returns['monthly'] = ((current_value - monthly_snapshot[1]) / monthly_snapshot[1]) * 100
        
        # YTD return (from January 1st)
        year_start = datetime(now.year, 1, 1)
        ytd_snapshot = self._find_closest_snapshot(history, year_start)
        if ytd_snapshot:
            returns['ytd'] = ((current_value - ytd_snapshot[1]) / ytd_snapshot[1]) * 100
        
        # All-time return (from first snapshot)
        if history:
            first_snapshot = history[0]
            returns['all_time'] = ((current_value - first_snapshot[1]) / first_snapshot[1]) * 100
        
        return returns
    
    def calculate_sharpe_ratio(
        self,
        days: int = 365,
        risk_free_rate: float = 0.0
    ) -> Optional[float]:
        """
        Calculate Sharpe ratio for the portfolio (risk-adjusted return)
        
        Args:
            days: Number of days to analyze
            risk_free_rate: Annual risk-free rate (default 0% for crypto)
            
        Returns:
            Sharpe ratio (annualized) or None if insufficient data
        """
        history = self.get_portfolio_value_history(days=days)
        
        if len(history) < 2:
            return None
        
        # Calculate daily returns
        daily_returns = []
        for i in range(1, len(history)):
            prev_value = history[i-1][1]
            curr_value = history[i][1]
            if prev_value > 0:
                daily_return = (curr_value - prev_value) / prev_value
                daily_returns.append(daily_return)
        
        if len(daily_returns) < 2:
            return None
        
        # Calculate mean and std dev of daily returns
        mean_daily_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_daily_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return None
        
        # Annualize (assuming 365 trading days)
        annualized_return = mean_daily_return * 365
        annualized_volatility = std_dev * (365 ** 0.5)
        
        # Calculate Sharpe ratio
        sharpe = (annualized_return - risk_free_rate) / annualized_volatility
        return sharpe
    
    def calculate_sortino_ratio(
        self,
        days: int = 365,
        risk_free_rate: float = 0.0
    ) -> Optional[float]:
        """
        Calculate Sortino ratio (only penalizes downside volatility)
        
        Args:
            days: Number of days to analyze
            risk_free_rate: Annual risk-free rate (default 0% for crypto)
            
        Returns:
            Sortino ratio (annualized) or None if insufficient data
        """
        history = self.get_portfolio_value_history(days=days)
        
        if len(history) < 2:
            return None
        
        # Calculate daily returns
        daily_returns = []
        for i in range(1, len(history)):
            prev_value = history[i-1][1]
            curr_value = history[i][1]
            if prev_value > 0:
                daily_return = (curr_value - prev_value) / prev_value
                daily_returns.append(daily_return)
        
        if len(daily_returns) < 2:
            return None
        
        mean_daily_return = sum(daily_returns) / len(daily_returns)
        
        # Only count negative returns (downside deviation)
        downside_returns = [r for r in daily_returns if r < 0]
        if not downside_returns:
            # No downside = perfect (return a high value)
            return 999.0
        
        downside_variance = sum(r ** 2 for r in downside_returns) / len(daily_returns)
        downside_deviation = downside_variance ** 0.5
        
        if downside_deviation == 0:
            return None
        
        # Annualize
        annualized_return = mean_daily_return * 365
        annualized_downside_dev = downside_deviation * (365 ** 0.5)
        
        # Calculate Sortino ratio
        sortino = (annualized_return - risk_free_rate) / annualized_downside_dev
        return sortino
    
    def calculate_max_drawdown(
        self,
        days: int = 365
    ) -> Optional[Dict[str, any]]:
        """
        Calculate maximum drawdown (largest peak-to-trough decline)
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with drawdown metrics or None if insufficient data
        """
        history = self.get_portfolio_value_history(days=days)
        
        if len(history) < 2:
            return None
        
        peak_value = history[0][1]
        peak_date = history[0][0]
        max_drawdown_pct = 0.0
        max_drawdown_value = 0.0
        trough_date = None
        recovery_date = None
        current_peak_value = peak_value
        current_peak_date = peak_date
        
        for date, value in history:
            # Update peak if we hit a new high
            if value > current_peak_value:
                current_peak_value = value
                current_peak_date = date
                # Check if we've recovered from previous drawdown
                if recovery_date is None and trough_date is not None:
                    if value >= peak_value:
                        recovery_date = date
            
            # Calculate drawdown from current peak
            if current_peak_value > 0:
                drawdown = (current_peak_value - value) / current_peak_value
                if drawdown > max_drawdown_pct:
                    max_drawdown_pct = drawdown
                    max_drawdown_value = current_peak_value - value
                    trough_date = date
                    peak_date = current_peak_date
        
        # Calculate days to recover if recovered
        days_to_recover = None
        if recovery_date and trough_date:
            days_to_recover = (recovery_date - trough_date).days
        
        return {
            'max_drawdown_pct': max_drawdown_pct * 100,  # As percentage
            'max_drawdown_value': max_drawdown_value,
            'peak_date': peak_date,
            'trough_date': trough_date,
            'recovery_date': recovery_date,
            'days_to_recover': days_to_recover
        }
    
    def calculate_benchmark_comparison(
        self,
        benchmark_symbol: str = "BTC",
        days: int = 365
    ) -> Optional[Dict[str, float]]:
        """
        Compare portfolio performance against a benchmark (e.g., BTC)
        
        Args:
            benchmark_symbol: Symbol of benchmark asset (default: BTC)
            days: Number of days to analyze
            
        Returns:
            Dictionary with comparison metrics or None if insufficient data
        """
        portfolio_history = self.get_portfolio_value_history(days=days)
        
        if len(portfolio_history) < 2:
            return None
        
        # Calculate portfolio total return
        first_value = portfolio_history[0][1]
        last_value = portfolio_history[-1][1]
        if first_value == 0:
            return None
        
        portfolio_return = ((last_value - first_value) / first_value) * 100
        
        # Get benchmark price history
        # We need to fetch this from CoinGecko or use historical_prices table
        try:
            benchmark_history = self.get_historical_prices(benchmark_symbol, days=days)
            if not benchmark_history or len(benchmark_history) < 2:
                return None
            
            first_benchmark_price = benchmark_history[0][1]
            last_benchmark_price = benchmark_history[-1][1]
            if first_benchmark_price == 0:
                return None
            
            benchmark_return = ((last_benchmark_price - first_benchmark_price) / first_benchmark_price) * 100
            
            # Calculate relative performance
            excess_return = portfolio_return - benchmark_return
            
            # Calculate beta (simplified - correlation * (portfolio_vol / benchmark_vol))
            portfolio_returns = []
            benchmark_returns = []
            
            # Align dates and calculate returns
            portfolio_dict = {date: value for date, value in portfolio_history}
            benchmark_dict = {date: price for date, price in benchmark_history}
            
            # Get common dates
            common_dates = sorted(set(portfolio_dict.keys()) & set(benchmark_dict.keys()))
            if len(common_dates) < 2:
                return {
                    'portfolio_return': portfolio_return,
                    'benchmark_return': benchmark_return,
                    'excess_return': excess_return,
                    'outperformance_pct': excess_return,
                    'beta': None,
                    'alpha': excess_return
                }
            
            # Calculate returns for common dates
            prev_portfolio_value = portfolio_dict[common_dates[0]]
            prev_benchmark_price = benchmark_dict[common_dates[0]]
            
            for date in common_dates[1:]:
                portfolio_value = portfolio_dict[date]
                benchmark_price = benchmark_dict[date]
                
                if prev_portfolio_value > 0 and prev_benchmark_price > 0:
                    portfolio_ret = (portfolio_value - prev_portfolio_value) / prev_portfolio_value
                    benchmark_ret = (benchmark_price - prev_benchmark_price) / prev_benchmark_price
                    portfolio_returns.append(portfolio_ret)
                    benchmark_returns.append(benchmark_ret)
                
                prev_portfolio_value = portfolio_value
                prev_benchmark_price = benchmark_price
            
            # Calculate beta if we have enough data
            beta = None
            if len(portfolio_returns) >= 2 and len(benchmark_returns) >= 2:
                # Calculate covariance and variance
                mean_portfolio_ret = sum(portfolio_returns) / len(portfolio_returns)
                mean_benchmark_ret = sum(benchmark_returns) / len(benchmark_returns)
                
                covariance = sum((portfolio_returns[i] - mean_portfolio_ret) * 
                                (benchmark_returns[i] - mean_benchmark_ret) 
                                for i in range(len(portfolio_returns))) / len(portfolio_returns)
                
                benchmark_variance = sum((r - mean_benchmark_ret) ** 2 for r in benchmark_returns) / len(benchmark_returns)
                
                if benchmark_variance > 0:
                    beta = covariance / benchmark_variance
            
            return {
                'portfolio_return': portfolio_return,
                'benchmark_return': benchmark_return,
                'excess_return': excess_return,
                'outperformance_pct': excess_return,
                'beta': beta,
                'alpha': excess_return  # Simplified alpha (excess return)
            }
            
        except Exception as e:
            # If benchmark data unavailable, return basic comparison
            return {
                'portfolio_return': portfolio_return,
                'benchmark_return': None,
                'excess_return': None,
                'outperformance_pct': None,
                'beta': None,
                'alpha': None,
                'error': f'Could not fetch benchmark data: {str(e)}'
            }
    
    def calculate_advanced_metrics(
        self,
        days: int = 365,
        benchmark_symbol: str = "BTC",
        risk_free_rate: float = 0.0
    ) -> Dict[str, any]:
        """
        Calculate all advanced performance metrics
        
        Args:
            days: Number of days to analyze
            benchmark_symbol: Symbol for benchmark comparison
            risk_free_rate: Annual risk-free rate
            
        Returns:
            Dictionary with all performance metrics
        """
        metrics = {
            'returns': self.calculate_returns(days=days),
            'sharpe_ratio': self.calculate_sharpe_ratio(days=days, risk_free_rate=risk_free_rate),
            'sortino_ratio': self.calculate_sortino_ratio(days=days, risk_free_rate=risk_free_rate),
            'max_drawdown': self.calculate_max_drawdown(days=days),
            'benchmark_comparison': self.calculate_benchmark_comparison(benchmark_symbol=benchmark_symbol, days=days)
        }
        
        return metrics
    
    def _find_closest_snapshot(
        self,
        history: List[Tuple[datetime, float]],
        target_date: datetime
    ) -> Optional[Tuple[datetime, float]]:
        """Find the closest snapshot to a target date"""
        if not history:
            return None
        
        closest = None
        min_diff = None
        
        for snapshot in history:
            diff = abs((snapshot[0] - target_date).total_seconds())
            if min_diff is None or diff < min_diff:
                min_diff = diff
                closest = snapshot
        
        # Only return if within 2 days of target
        if closest and abs((closest[0] - target_date).total_seconds()) < 2 * 24 * 3600:
            return closest
        
        return None
    
    def get_snapshot_count(self) -> int:
        """Get total number of snapshots in database"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM portfolio_snapshots")
        row = cursor.fetchone()
        return row['count'] if row else 0
    
    def cleanup_old_snapshots(self, keep_days: int = 365):
        """
        Remove snapshots older than specified days (keep only one per day for old data)
        
        Args:
            keep_days: Keep all snapshots from the last N days
        """
        cursor = self.conn.cursor()
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
        
        # For old snapshots, keep only one per day (the latest one)
        cursor.execute("""
            DELETE FROM portfolio_snapshots
            WHERE timestamp < ? 
            AND id NOT IN (
                SELECT MAX(id)
                FROM portfolio_snapshots
                WHERE timestamp < ?
                GROUP BY DATE(timestamp)
            )
        """, (cutoff_str, cutoff_str))
        
        self.conn.commit()
        return cursor.rowcount
    
    def save_historical_prices(
        self,
        symbol: str,
        prices: List[Tuple[str, float, Optional[float], Optional[float]]]
    ):
        """
        Save historical prices for an asset
        
        Args:
            symbol: Asset symbol (e.g., 'BTC')
            prices: List of tuples (date_str, price, volume_24h, market_cap)
                   date_str format: 'YYYY-MM-DD'
        """
        cursor = self.conn.cursor()
        
        for date_str, price, volume_24h, market_cap in prices:
            cursor.execute("""
                INSERT OR REPLACE INTO historical_prices 
                (symbol, date, price, volume_24h, market_cap)
                VALUES (?, ?, ?, ?, ?)
            """, (symbol, date_str, price, volume_24h, market_cap))
        
        self.conn.commit()
    
    def get_historical_prices(
        self,
        symbol: str,
        days: int = 200
    ) -> List[Tuple[datetime, float]]:
        """
        Get historical prices for an asset
        
        Args:
            symbol: Asset symbol
            days: Number of days of history to retrieve
            
        Returns:
            List of tuples (datetime, price) sorted by date (oldest first)
        """
        cursor = self.conn.cursor()
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT date, price 
            FROM historical_prices
            WHERE symbol = ? AND date >= ?
            ORDER BY date ASC
        """, (symbol, cutoff_str))
        
        results = []
        for row in cursor.fetchall():
            try:
                date_obj = datetime.strptime(row['date'], "%Y-%m-%d")
                results.append((date_obj, row['price']))
            except ValueError:
                continue
        
        return results
    
    def get_latest_price_date(self, symbol: str) -> Optional[datetime]:
        """
        Get the date of the most recent price data for an asset
        
        Args:
            symbol: Asset symbol
            
        Returns:
            Datetime of latest price or None if no data exists
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT MAX(date) as max_date
            FROM historical_prices
            WHERE symbol = ?
        """, (symbol,))
        
        row = cursor.fetchone()
        if row and row['max_date']:
            try:
                return datetime.strptime(row['max_date'], "%Y-%m-%d")
            except ValueError:
                return None
        return None
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    @property
    def transaction_tracker(self):
        """Lazy-load transaction tracker"""
        if self._transaction_tracker is None:
            try:
                from .transaction_tracker import TransactionTracker
                self._transaction_tracker = TransactionTracker(self.db_path)
            except ImportError:
                raise ImportError(
                    "transaction_tracker module not found. "
                    "Make sure transaction_tracker.py is in the same directory."
                )
        return self._transaction_tracker

