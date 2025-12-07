# Transaction Tracking System

This document explains how to use the Transaction Tracking feature for logging trades, calculating P&L, and generating tax reports.

## Overview

The Transaction Tracking system provides:
- **Trade History**: Log all buy/sell transactions
- **P&L Tracking**: Calculate realized and unrealized gains/losses
- **Tax Reporting**: Generate tax reports using FIFO, LIFO, or Average Cost methods
- **Fee Tracking**: Account for trading fees in cost basis and P&L calculations

## Files

- `transaction_models.py`: Data models (Transaction, CostBasisLot, RealizedPnL, UnrealizedPnL)
- `transaction_tracker.py`: Main TransactionTracker class with all functionality
- `transaction_tracking_example.py`: Example usage scripts

## Quick Start

### 1. Basic Transaction Recording

```python
from transaction_tracker import TransactionTracker, TransactionType, AccountingMethod

# Initialize tracker
tracker = TransactionTracker("portfolio_history.db")

# Record a buy transaction
tracker.record_transaction(
    symbol="BTC",
    transaction_type=TransactionType.BUY,
    amount=0.5,
    price_per_unit=50000.0,
    fee=25.0,
    exchange="Coinbase",
    notes="Initial purchase"
)

# Record a sell transaction (automatically calculates realized P&L)
tracker.record_transaction(
    symbol="BTC",
    transaction_type=TransactionType.SELL,
    amount=0.2,
    price_per_unit=60000.0,
    fee=12.0,
    exchange="Coinbase",
    accounting_method=AccountingMethod.FIFO
)
```

### 2. Calculate P&L

**Method 1: Manual price (original way)**
```python
# Unrealized P&L (current holdings) - you provide the price
unrealized = tracker.calculate_unrealized_pnl("BTC", current_price=55000.0)
print(f"Unrealized P&L: ${unrealized.unrealized_gain_loss:,.2f}")
```

**Method 2: Automatic price fetching (NEW!)**
```python
# Automatically fetches current prices from CoinGecko
unrealized_all = tracker.calculate_unrealized_pnl_with_prices()
for symbol, pnl in unrealized_all.items():
    print(f"{symbol}: ${pnl.unrealized_gain_loss:,.2f}")

# Or get complete portfolio summary
summary = tracker.get_portfolio_pnl_summary()
print(f"Total Gain/Loss: ${summary['total_gain_loss']:,.2f}")
```

**Realized P&L (closed positions)**
```python
realized = tracker.calculate_realized_pnl(symbol="BTC")
print(f"Total Realized P&L: ${realized['total_realized_pnl']:,.2f}")
```

### 3. Generate Tax Report

```python
from datetime import datetime

# Generate tax report for a year
tax_report = tracker.generate_tax_report(2024, AccountingMethod.FIFO)
print(f"Net Gain/Loss: ${tax_report['net_gain_loss']:,.2f}")
print(f"Total Gains: ${tax_report['total_gains']:,.2f}")
print(f"Total Losses: ${tax_report['total_losses']:,.2f}")
```

### 4. Integration with Portfolio Database

```python
from portfolio_database import PortfolioDatabase

# PortfolioDatabase now includes transaction tracker
db = PortfolioDatabase("portfolio_history.db")
tracker = db.transaction_tracker  # Access via property

# Use tracker as normal
tracker.record_transaction(...)
```

### 5. Integration with Rebalancer

```python
from portfolio_rebalancer import PortfolioRebalancer
from portfolio_database import PortfolioDatabase

db = PortfolioDatabase("portfolio_history.db")
tracker = db.transaction_tracker
rebalancer = PortfolioRebalancer()

# Calculate rebalancing actions
actions = rebalancer.calculate_rebalancing(portfolio)

# Log transactions when executing rebalancing
transaction_ids = rebalancer.log_rebalancing_transactions(
    actions=actions,
    transaction_tracker=tracker,
    fee_percentage=0.1,  # 0.1% trading fee
    exchange="Coinbase"
)
```

## Accounting Methods

The system supports three accounting methods:

### FIFO (First In, First Out)
- Matches oldest purchases with sales
- Default method
- Often results in higher taxes in rising markets

```python
tracker.record_transaction(
    ...,
    accounting_method=AccountingMethod.FIFO
)
```

### LIFO (Last In, First Out)
- Matches newest purchases with sales
- May result in lower taxes in rising markets

```python
tracker.record_transaction(
    ...,
    accounting_method=AccountingMethod.LIFO
)
```

### Average Cost
- Uses weighted average of all purchases
- Simplifies calculations

```python
tracker.record_transaction(
    ...,
    accounting_method=AccountingMethod.AVERAGE_COST
)
```

## Database Schema

The system creates three main tables:

### `transactions`
Stores all buy/sell transactions:
- `id`: Primary key
- `timestamp`: Transaction date/time
- `symbol`: Asset symbol
- `transaction_type`: BUY or SELL
- `amount`: Amount of asset
- `price_per_unit`: Price per unit
- `total_value`: Total transaction value
- `fee`: Trading fee
- `exchange`: Exchange/platform
- `notes`: Optional notes

### `cost_basis_lots`
Tracks purchase lots for cost basis calculation:
- `id`: Primary key
- `transaction_id`: Link to buy transaction
- `symbol`: Asset symbol
- `amount`: Amount in lot
- `cost_per_unit`: Cost per unit (including fees)
- `total_cost`: Total cost of lot
- `is_closed`: Whether lot has been fully sold
- `purchase_date`: Date of purchase

### `realized_pnl`
Records realized gains/losses when positions are closed:
- `id`: Primary key
- `sell_transaction_id`: Link to sell transaction
- `lot_id`: Link to cost basis lot
- `symbol`: Asset symbol
- `amount`: Amount sold
- `cost_basis`: Cost basis of sold amount
- `sale_price`: Sale price per unit
- `sale_value`: Total sale proceeds
- `realized_gain_loss`: Calculated gain/loss
- `accounting_method`: Method used (FIFO/LIFO/etc.)

## API Reference

### TransactionTracker Methods

#### `record_transaction(...)`
Record a buy or sell transaction.

**Parameters:**
- `symbol` (str): Asset symbol
- `transaction_type` (TransactionType): BUY or SELL
- `amount` (float): Amount of asset
- `price_per_unit` (float): Price per unit
- `fee` (float, optional): Trading fee (default: 0.0)
- `fee_currency` (str, optional): Currency of fee (default: "AUD")
- `exchange` (str, optional): Exchange/platform name
- `transaction_id` (str, optional): External transaction ID
- `notes` (str, optional): Optional notes
- `timestamp` (datetime, optional): Transaction timestamp (defaults to now)
- `accounting_method` (AccountingMethod, optional): Method for sells (defaults to FIFO)

**Returns:** Transaction ID (int)

#### `get_transaction_history(...)`
Get transaction history with optional filters.

**Parameters:**
- `symbol` (str, optional): Filter by symbol
- `start_date` (datetime, optional): Start date filter
- `end_date` (datetime, optional): End date filter
- `transaction_type` (TransactionType, optional): Filter by type

**Returns:** List of Transaction objects

#### `calculate_unrealized_pnl(symbol, current_price)`
Calculate unrealized P&L for an asset (manual price).

**Parameters:**
- `symbol` (str): Asset symbol
- `current_price` (float): Current market price

**Returns:** UnrealizedPnL object or None

#### `fetch_current_prices(symbols, retry_count)`
Fetch current market prices from CoinGecko API.

**Parameters:**
- `symbols` (List[str]): List of asset symbols to fetch prices for
- `retry_count` (int, optional): Number of retry attempts (default: 3)

**Returns:** Dictionary mapping symbol to current price

#### `calculate_unrealized_pnl_with_prices(symbols, retry_count)`
Calculate unrealized P&L for assets, automatically fetching current prices.

**Parameters:**
- `symbols` (List[str], optional): List of symbols to calculate P&L for. If None, uses all assets with open positions
- `retry_count` (int, optional): Number of retry attempts for price fetching (default: 3)

**Returns:** Dictionary mapping symbol to UnrealizedPnL object

#### `get_portfolio_pnl_summary(symbols, retry_count)`
Get a complete P&L summary for the portfolio with automatic price fetching.

**Parameters:**
- `symbols` (List[str], optional): List of symbols to include. If None, uses all assets with open positions
- `retry_count` (int, optional): Number of retry attempts for price fetching (default: 3)

**Returns:** Dictionary with portfolio P&L summary including:
- `unrealized_pnl`: Dict of UnrealizedPnL objects
- `realized_pnl`: Dict with total realized P&L
- `total_unrealized_gain_loss`: Total unrealized gain/loss
- `total_realized_gain_loss`: Total realized gain/loss
- `total_gain_loss`: Combined total
- `total_cost_basis`: Total cost basis
- `total_current_value`: Total current value
- `total_return_pct`: Total return percentage

#### `calculate_realized_pnl(...)`
Calculate total realized P&L.

**Parameters:**
- `symbol` (str, optional): Filter by symbol
- `start_date` (datetime, optional): Start date filter
- `end_date` (datetime, optional): End date filter

**Returns:** Dictionary with `total_realized_pnl` and `trade_count`

#### `generate_tax_report(year, accounting_method)`
Generate tax report for a given year.

**Parameters:**
- `year` (int): Tax year
- `accounting_method` (AccountingMethod, optional): Method to use (defaults to FIFO)

**Returns:** Dictionary with tax report data

#### `get_portfolio_cost_basis()`
Get cost basis summary for all assets.

**Returns:** Dictionary mapping symbols to cost basis data

## Examples

See `transaction_tracking_example.py` for complete working examples including:
- Basic transaction recording
- P&L calculations
- Tax reporting
- Rebalancing integration
- Accounting method comparison

## Notes

- **Fees**: Trading fees are automatically included in cost basis for buy transactions
- **Partial Sales**: The system handles partial lot sales correctly
- **Multiple Lots**: Supports multiple purchase lots per asset
- **Database**: Uses the same database as PortfolioDatabase for integration
- **Thread Safety**: Not thread-safe; use separate tracker instances for concurrent access
- **Price Fetching**: Automatic price fetching uses CoinGecko API (same as your existing portfolio evaluator)
- **Rate Limiting**: Price fetching includes retry logic for CoinGecko rate limits

## Future Enhancements

Potential improvements:
- Support for transfers between wallets/exchanges
- Support for staking rewards and airdrops
- Support for margin trading and futures
- Export to CSV/Excel for tax software
- Integration with exchange APIs for automatic import
- Support for multiple currencies
- Wash sale detection

