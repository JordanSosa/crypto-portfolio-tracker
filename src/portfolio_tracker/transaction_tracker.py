"""
Transaction Tracking Module
Handles buy/sell transaction logging, cost basis tracking, and P&L calculations
"""

import sqlite3
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

try:
    from .transaction_models import (
        Transaction, TransactionType, CostBasisLot, RealizedPnL, 
        UnrealizedPnL, AccountingMethod
    )
except ImportError:
    from transaction_models import (
        Transaction, TransactionType, CostBasisLot, RealizedPnL, 
        UnrealizedPnL, AccountingMethod
    )

# Try to import constants, fallback if not available
try:
    from .constants import (
        COINGECKO_BASE_URL, COIN_IDS, DEFAULT_CURRENCY,
        API_RETRY_COUNT, API_TIMEOUT, API_RATE_LIMIT_BACKOFF_BASE
    )
except ImportError:
    try:
        from constants import (
            COINGECKO_BASE_URL, COIN_IDS, DEFAULT_CURRENCY,
            API_RETRY_COUNT, API_TIMEOUT, API_RATE_LIMIT_BACKOFF_BASE
        )
    except ImportError:
        COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
        COIN_IDS = {
            "BTC": "bitcoin", "ETH": "ethereum", "XRP": "ripple",
            "SOL": "solana", "LINK": "chainlink", "BCH": "bitcoin-cash",
            "UNI": "uniswap", "LEO": "leo-token", "WBT": "whitebit",
            "WLFI": "world-liberty-financial"
        }
        DEFAULT_CURRENCY = "aud"
        API_RETRY_COUNT = 3
        API_TIMEOUT = 10
        API_RATE_LIMIT_BACKOFF_BASE = 2


class TransactionTracker:
    """Manages transaction tracking, cost basis, and P&L calculations"""
    
    def __init__(self, db_path: str = "portfolio_history.db"):
        """
        Initialize transaction tracker
        
        Args:
            db_path: Path to SQLite database (should match PortfolioDatabase)
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.default_accounting_method = AccountingMethod.FIFO
        self._initialize_tables()
    
    def _initialize_tables(self):
        """Create transaction tracking tables if they don't exist"""
        cursor = self.conn.cursor()
        
        # Table for transactions (buy/sell trades)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                transaction_type TEXT NOT NULL CHECK(transaction_type IN ('BUY', 'SELL')),
                amount REAL NOT NULL,
                price_per_unit REAL NOT NULL,
                total_value REAL NOT NULL,
                fee REAL DEFAULT 0.0,
                fee_currency TEXT DEFAULT 'AUD',
                exchange TEXT,
                transaction_id TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table for cost basis lots (tracks purchase lots for FIFO/LIFO)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cost_basis_lots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                amount REAL NOT NULL,
                cost_per_unit REAL NOT NULL,
                total_cost REAL NOT NULL,
                fee REAL DEFAULT 0.0,
                purchase_date TEXT NOT NULL,
                is_closed INTEGER DEFAULT 0,
                closed_date TEXT,
                FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
            )
        """)
        
        # Table for realized gains/losses (when lots are closed)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS realized_pnl (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sell_transaction_id INTEGER NOT NULL,
                lot_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                amount REAL NOT NULL,
                cost_basis REAL NOT NULL,
                sale_price REAL NOT NULL,
                sale_value REAL NOT NULL,
                realized_gain_loss REAL NOT NULL,
                accounting_method TEXT NOT NULL,
                sale_date TEXT NOT NULL,
                FOREIGN KEY (sell_transaction_id) REFERENCES transactions(id),
                FOREIGN KEY (lot_id) REFERENCES cost_basis_lots(id)
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_symbol 
            ON transactions(symbol)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_timestamp 
            ON transactions(timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_type 
            ON transactions(transaction_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cost_basis_lots_symbol 
            ON cost_basis_lots(symbol)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cost_basis_lots_closed 
            ON cost_basis_lots(is_closed, symbol)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_realized_pnl_date 
            ON realized_pnl(sale_date DESC)
        """)
        
        self.conn.commit()
    
    def record_transaction(
        self,
        symbol: str,
        transaction_type: TransactionType,
        amount: float,
        price_per_unit: float,
        fee: float = 0.0,
        fee_currency: str = "AUD",
        exchange: Optional[str] = None,
        transaction_id: Optional[str] = None,
        notes: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        accounting_method: Optional[AccountingMethod] = None
    ) -> int:
        """
        Record a buy or sell transaction
        
        Args:
            symbol: Asset symbol (e.g., 'BTC')
            transaction_type: BUY or SELL
            amount: Amount of asset
            price_per_unit: Price per unit at time of transaction
            fee: Trading fee
            fee_currency: Currency of fee (default: AUD)
            exchange: Exchange/platform name
            transaction_id: External transaction ID
            notes: Optional notes
            timestamp: Transaction timestamp (defaults to now)
            accounting_method: Accounting method for sells (defaults to FIFO)
            
        Returns:
            transaction_id: ID of created transaction
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        total_value = amount * price_per_unit
        
        cursor = self.conn.cursor()
        
        # Insert transaction
        cursor.execute("""
            INSERT INTO transactions 
            (timestamp, symbol, transaction_type, amount, price_per_unit, 
             total_value, fee, fee_currency, exchange, transaction_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp_str, symbol, transaction_type.value, amount, 
            price_per_unit, total_value, fee, fee_currency, exchange, 
            transaction_id, notes
        ))
        
        trans_id = cursor.lastrowid
        
        # For BUY transactions, create cost basis lot
        if transaction_type == TransactionType.BUY:
            cost_per_unit = (total_value + fee) / amount if amount > 0 else 0  # Include fee in cost basis
            cursor.execute("""
                INSERT INTO cost_basis_lots
                (transaction_id, symbol, amount, cost_per_unit, total_cost, 
                 fee, purchase_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                trans_id, symbol, amount, cost_per_unit, 
                total_value + fee, fee, timestamp_str
            ))
        
        # For SELL transactions, match with cost basis lots and calculate realized P&L
        elif transaction_type == TransactionType.SELL:
            method = accounting_method or self.default_accounting_method
            self._process_sell_transaction(trans_id, symbol, amount, 
                                         price_per_unit, fee, timestamp_str, method)
        
        self.conn.commit()
        return trans_id
    
    def _process_sell_transaction(
        self,
        sell_transaction_id: int,
        symbol: str,
        sell_amount: float,
        sell_price: float,
        sell_fee: float,
        sell_date: str,
        accounting_method: AccountingMethod
    ):
        """Process a sell transaction by matching with cost basis lots"""
        remaining_to_sell = sell_amount
        sale_value = sell_amount * sell_price
        
        cursor = self.conn.cursor()
        
        # Get open lots based on accounting method
        if accounting_method == AccountingMethod.FIFO:
            lots = self._get_open_lots_fifo(symbol)
        elif accounting_method == AccountingMethod.LIFO:
            lots = self._get_open_lots_lifo(symbol)
        elif accounting_method == AccountingMethod.AVERAGE_COST:
            lots = self._get_open_lots_average_cost(symbol)
        else:
            lots = self._get_open_lots_fifo(symbol)  # Default to FIFO
        
        # Match sell amount with lots
        for lot in lots:
            if remaining_to_sell <= 0:
                break
            
            lot_amount = lot['amount']
            lot_cost_per_unit = lot['cost_per_unit']
            lot_id = lot['id']
            
            # Determine how much of this lot to use
            amount_to_close = min(remaining_to_sell, lot_amount)
            
            # Calculate realized gain/loss
            cost_basis = amount_to_close * lot_cost_per_unit
            sale_proceeds = amount_to_close * sell_price
            # Allocate fee proportionally
            fee_allocation = sell_fee * (amount_to_close / sell_amount) if sell_amount > 0 else 0
            realized_gain_loss = sale_proceeds - cost_basis - fee_allocation
            
            # Record realized P&L
            cursor.execute("""
                INSERT INTO realized_pnl
                (sell_transaction_id, lot_id, symbol, amount, cost_basis,
                 sale_price, sale_value, realized_gain_loss, accounting_method, sale_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sell_transaction_id, lot_id, symbol, amount_to_close,
                cost_basis, sell_price, sale_proceeds, realized_gain_loss,
                accounting_method.value, sell_date
            ))
            
            # Update or close the lot
            if amount_to_close >= lot_amount:
                # Close entire lot
                cursor.execute("""
                    UPDATE cost_basis_lots
                    SET is_closed = 1, closed_date = ?
                    WHERE id = ?
                """, (sell_date, lot_id))
            else:
                # Partially close lot
                new_amount = lot_amount - amount_to_close
                new_total_cost = new_amount * lot_cost_per_unit
                cursor.execute("""
                    UPDATE cost_basis_lots
                    SET amount = ?, total_cost = ?
                    WHERE id = ?
                """, (new_amount, new_total_cost, lot_id))
            
            remaining_to_sell -= amount_to_close
        
        if remaining_to_sell > 0:
            # Warn about selling more than owned
            print(f"Warning: Sold {remaining_to_sell} more {symbol} than available in cost basis lots")
    
    def _get_open_lots_fifo(self, symbol: str) -> List[Dict]:
        """Get open lots in FIFO order (oldest first)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, amount, cost_per_unit, total_cost, purchase_date
            FROM cost_basis_lots
            WHERE symbol = ? AND is_closed = 0
            ORDER BY purchase_date ASC, id ASC
        """, (symbol,))
        return [dict(row) for row in cursor.fetchall()]
    
    def _get_open_lots_lifo(self, symbol: str) -> List[Dict]:
        """Get open lots in LIFO order (newest first)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, amount, cost_per_unit, total_cost, purchase_date
            FROM cost_basis_lots
            WHERE symbol = ? AND is_closed = 0
            ORDER BY purchase_date DESC, id DESC
        """, (symbol,))
        return [dict(row) for row in cursor.fetchall()]
    
    def _get_open_lots_average_cost(self, symbol: str) -> List[Dict]:
        """Get open lots for average cost calculation"""
        # For average cost, we calculate weighted average and treat as single lot
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                SUM(amount) as total_amount,
                SUM(total_cost) as total_cost,
                CASE 
                    WHEN SUM(amount) > 0 THEN SUM(total_cost) / SUM(amount)
                    ELSE 0
                END as avg_cost_per_unit
            FROM cost_basis_lots
            WHERE symbol = ? AND is_closed = 0
        """, (symbol,))
        
        row = cursor.fetchone()
        if row and row['total_amount'] and row['total_amount'] > 0:
            # Return as single "virtual" lot
            return [{
                'id': 0,  # Special ID for average cost
                'amount': row['total_amount'],
                'cost_per_unit': row['avg_cost_per_unit'],
                'total_cost': row['total_cost'],
                'purchase_date': None
            }]
        return []
    
    def transaction_exists(self, transaction_id: str) -> bool:
        """
        Check if a transaction with the given transaction_id already exists
        
        Args:
            transaction_id: External transaction ID (e.g., blockchain tx hash)
            
        Returns:
            True if transaction exists, False otherwise
        """
        if not transaction_id:
            return False
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM transactions
            WHERE transaction_id = ?
        """, (transaction_id,))
        
        row = cursor.fetchone()
        return row['count'] > 0 if row else False
    
    def get_transaction_history(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[TransactionType] = None
    ) -> List[Transaction]:
        """Get transaction history with optional filters"""
        cursor = self.conn.cursor()
        
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.strftime("%Y-%m-%d %H:%M:%S"))
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.strftime("%Y-%m-%d %H:%M:%S"))
        
        if transaction_type:
            query += " AND transaction_type = ?"
            params.append(transaction_type.value)
        
        query += " ORDER BY timestamp DESC"
        
        cursor.execute(query, params)
        
        transactions = []
        for row in cursor.fetchall():
            transactions.append(Transaction(
                id=row['id'],
                timestamp=datetime.strptime(row['timestamp'], "%Y-%m-%d %H:%M:%S"),
                symbol=row['symbol'],
                transaction_type=TransactionType(row['transaction_type']),
                amount=row['amount'],
                price_per_unit=row['price_per_unit'],
                total_value=row['total_value'],
                fee=row['fee'],
                fee_currency=row['fee_currency'],
                exchange=row['exchange'],
                transaction_id=row['transaction_id'],
                notes=row['notes']
            ))
        
        return transactions
    
    def calculate_unrealized_pnl(
        self,
        symbol: str,
        current_price: float
    ) -> Optional[UnrealizedPnL]:
        """Calculate unrealized P&L for an asset"""
        cursor = self.conn.cursor()
        
        # Get all open lots
        cursor.execute("""
            SELECT SUM(amount) as total_amount, SUM(total_cost) as total_cost
            FROM cost_basis_lots
            WHERE symbol = ? AND is_closed = 0
        """, (symbol,))
        
        row = cursor.fetchone()
        if not row or not row['total_amount'] or row['total_amount'] == 0:
            return None
        
        current_amount = row['total_amount']
        total_cost_basis = row['total_cost']
        average_cost_basis = total_cost_basis / current_amount if current_amount > 0 else 0
        current_value = current_amount * current_price
        unrealized_gain_loss = current_value - total_cost_basis
        unrealized_gain_loss_pct = (unrealized_gain_loss / total_cost_basis * 100) if total_cost_basis > 0 else 0
        
        return UnrealizedPnL(
            symbol=symbol,
            current_amount=current_amount,
            average_cost_basis=average_cost_basis,
            current_price=current_price,
            total_cost_basis=total_cost_basis,
            current_value=current_value,
            unrealized_gain_loss=unrealized_gain_loss,
            unrealized_gain_loss_pct=unrealized_gain_loss_pct
        )
    
    def calculate_realized_pnl(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Calculate total realized P&L with optional filters"""
        cursor = self.conn.cursor()
        
        query = "SELECT SUM(realized_gain_loss) as total_pnl, COUNT(*) as trade_count FROM realized_pnl WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if start_date:
            query += " AND sale_date >= ?"
            params.append(start_date.strftime("%Y-%m-%d %H:%M:%S"))
        
        if end_date:
            query += " AND sale_date <= ?"
            params.append(end_date.strftime("%Y-%m-%d %H:%M:%S"))
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        return {
            'total_realized_pnl': row['total_pnl'] or 0.0,
            'trade_count': row['trade_count'] or 0
        }
    
    def generate_tax_report(
        self,
        year: int,
        accounting_method: Optional[AccountingMethod] = None
    ) -> Dict:
        """Generate tax report for a given year"""
        method = accounting_method or self.default_accounting_method
        
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)
        
        cursor = self.conn.cursor()
        
        # Get all realized P&L for the year
        cursor.execute("""
            SELECT 
                symbol,
                SUM(amount) as total_amount,
                SUM(cost_basis) as total_cost_basis,
                SUM(sale_value) as total_sale_value,
                SUM(realized_gain_loss) as total_gain_loss,
                COUNT(*) as trade_count
            FROM realized_pnl
            WHERE sale_date >= ? AND sale_date <= ? AND accounting_method = ?
            GROUP BY symbol
            ORDER BY symbol
        """, (
            start_date.strftime("%Y-%m-%d %H:%M:%S"),
            end_date.strftime("%Y-%m-%d %H:%M:%S"),
            method.value
        ))
        
        trades = []
        total_gains = 0.0
        total_losses = 0.0
        
        for row in cursor.fetchall():
            gain_loss = row['total_gain_loss']
            if gain_loss > 0:
                total_gains += gain_loss
            else:
                total_losses += abs(gain_loss)
            
            trades.append({
                'symbol': row['symbol'],
                'amount_sold': row['total_amount'],
                'cost_basis': row['total_cost_basis'],
                'sale_proceeds': row['total_sale_value'],
                'gain_loss': gain_loss,
                'trade_count': row['trade_count']
            })
        
        net_gain_loss = total_gains - total_losses
        
        return {
            'year': year,
            'accounting_method': method.value,
            'trades': trades,
            'total_gains': total_gains,
            'total_losses': total_losses,
            'net_gain_loss': net_gain_loss,
            'total_trades': sum(t['trade_count'] for t in trades)
        }
    
    def get_portfolio_cost_basis(self) -> Dict[str, Dict]:
        """Get cost basis summary for all assets"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                symbol,
                SUM(amount) as total_amount,
                SUM(total_cost) as total_cost_basis,
                CASE 
                    WHEN SUM(amount) > 0 THEN SUM(total_cost) / SUM(amount)
                    ELSE 0
                END as avg_cost_per_unit
            FROM cost_basis_lots
            WHERE is_closed = 0
            GROUP BY symbol
        """)
        
        cost_basis = {}
        for row in cursor.fetchall():
            cost_basis[row['symbol']] = {
                'amount': row['total_amount'],
                'total_cost_basis': row['total_cost_basis'],
                'average_cost_per_unit': row['avg_cost_per_unit']
            }
        
        return cost_basis
    
    def get_open_lots(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open cost basis lots"""
        cursor = self.conn.cursor()
        
        if symbol:
            cursor.execute("""
                SELECT * FROM cost_basis_lots
                WHERE symbol = ? AND is_closed = 0
                ORDER BY purchase_date ASC
            """, (symbol,))
        else:
            cursor.execute("""
                SELECT * FROM cost_basis_lots
                WHERE is_closed = 0
                ORDER BY symbol, purchase_date ASC
            """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def fetch_current_prices(
        self,
        symbols: List[str],
        retry_count: int = API_RETRY_COUNT
    ) -> Dict[str, float]:
        """
        Fetch current market prices from CoinGecko API
        
        Args:
            symbols: List of asset symbols to fetch prices for
            retry_count: Number of retry attempts for rate limit errors
            
        Returns:
            Dictionary mapping symbol to current price
        """
        coin_ids = [COIN_IDS.get(symbol.upper()) for symbol in symbols 
                   if symbol.upper() in COIN_IDS]
        
        if not coin_ids:
            return {}
        
        # Fetch price data
        url = f"{COINGECKO_BASE_URL}/coins/markets"
        params = {
            "vs_currency": DEFAULT_CURRENCY,
            "ids": ",".join(coin_ids),
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": False
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
                    print(f"Error fetching prices after {retry_count} attempts: {e}")
                    return {}
        else:
            # This shouldn't happen, but just in case
            return {}
        
        # Organize data by symbol
        prices = {}
        for coin in data:
            symbol = next((s for s, cid in COIN_IDS.items() 
                          if cid == coin["id"]), None)
            if symbol:
                prices[symbol] = coin["current_price"]
        
        return prices
    
    def calculate_unrealized_pnl_with_prices(
        self,
        symbols: Optional[List[str]] = None,
        retry_count: int = API_RETRY_COUNT
    ) -> Dict[str, UnrealizedPnL]:
        """
        Calculate unrealized P&L for assets, automatically fetching current prices
        
        Args:
            symbols: List of symbols to calculate P&L for. If None, uses all assets with open positions
            retry_count: Number of retry attempts for price fetching
            
        Returns:
            Dictionary mapping symbol to UnrealizedPnL object
        """
        cursor = self.conn.cursor()
        
        # Get all assets with open positions
        if symbols is None:
            cursor.execute("""
                SELECT DISTINCT symbol
                FROM cost_basis_lots
                WHERE is_closed = 0
            """)
            symbols = [row['symbol'] for row in cursor.fetchall()]
        
        if not symbols:
            return {}
        
        # Fetch current prices
        prices = self.fetch_current_prices(symbols, retry_count)
        
        # Calculate unrealized P&L for each asset
        results = {}
        for symbol in symbols:
            if symbol in prices:
                unrealized = self.calculate_unrealized_pnl(symbol, prices[symbol])
                if unrealized:
                    results[symbol] = unrealized
        
        return results
    
    def get_portfolio_pnl_summary(
        self,
        symbols: Optional[List[str]] = None,
        retry_count: int = API_RETRY_COUNT
    ) -> Dict:
        """
        Get a complete P&L summary for the portfolio with automatic price fetching
        
        Args:
            symbols: List of symbols to include. If None, uses all assets with open positions
            retry_count: Number of retry attempts for price fetching
            
        Returns:
            Dictionary with portfolio P&L summary
        """
        # Get unrealized P&L with automatic price fetching
        unrealized_pnl = self.calculate_unrealized_pnl_with_prices(symbols, retry_count)
        
        # Get realized P&L
        realized_pnl = self.calculate_realized_pnl()
        
        # Calculate totals
        total_unrealized_gain_loss = sum(pnl.unrealized_gain_loss for pnl in unrealized_pnl.values())
        total_cost_basis = sum(pnl.total_cost_basis for pnl in unrealized_pnl.values())
        total_current_value = sum(pnl.current_value for pnl in unrealized_pnl.values())
        
        return {
            'unrealized_pnl': unrealized_pnl,
            'realized_pnl': realized_pnl,
            'total_unrealized_gain_loss': total_unrealized_gain_loss,
            'total_realized_gain_loss': realized_pnl['total_realized_pnl'],
            'total_gain_loss': total_unrealized_gain_loss + realized_pnl['total_realized_pnl'],
            'total_cost_basis': total_cost_basis,
            'total_current_value': total_current_value,
            'total_return_pct': ((total_current_value - total_cost_basis) / total_cost_basis * 100) if total_cost_basis > 0 else 0
        }
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

