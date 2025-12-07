"""
Example usage of Transaction Tracking system

This script demonstrates how to use the transaction tracking features
for logging trades, calculating P&L, and generating tax reports.
"""

from datetime import datetime
from transaction_tracker import TransactionTracker, TransactionType, AccountingMethod
from portfolio_database import PortfolioDatabase
from portfolio_rebalancer import PortfolioRebalancer
from portfolio_evaluator import Asset


def example_basic_transactions():
    """Example: Record basic buy and sell transactions"""
    print("=" * 80)
    print("EXAMPLE 1: Basic Transaction Recording")
    print("=" * 80)
    
    # Initialize tracker
    tracker = TransactionTracker("portfolio_history.db")
    
    # Record a buy transaction
    print("\n1. Recording a BUY transaction...")
    buy_id = tracker.record_transaction(
        symbol="BTC",
        transaction_type=TransactionType.BUY,
        amount=0.5,
        price_per_unit=50000.0,
        fee=25.0,
        exchange="Coinbase",
        notes="Initial purchase"
    )
    print(f"   Buy transaction recorded with ID: {buy_id}")
    
    # Record another buy at different price
    print("\n2. Recording another BUY transaction...")
    buy_id2 = tracker.record_transaction(
        symbol="BTC",
        transaction_type=TransactionType.BUY,
        amount=0.3,
        price_per_unit=45000.0,
        fee=15.0,
        exchange="Coinbase",
        notes="DCA purchase"
    )
    print(f"   Buy transaction recorded with ID: {buy_id2}")
    
    # Record a sell transaction (will automatically calculate realized P&L)
    print("\n3. Recording a SELL transaction...")
    sell_id = tracker.record_transaction(
        symbol="BTC",
        transaction_type=TransactionType.SELL,
        amount=0.2,
        price_per_unit=60000.0,
        fee=12.0,
        exchange="Coinbase",
        accounting_method=AccountingMethod.FIFO,
        notes="Profit taking"
    )
    print(f"   Sell transaction recorded with ID: {sell_id}")
    
    # Get transaction history
    print("\n4. Transaction History:")
    history = tracker.get_transaction_history(symbol="BTC")
    for trans in history:
        print(f"   {trans.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | "
              f"{trans.transaction_type.value:4s} | "
              f"{trans.amount:8.4f} BTC @ ${trans.price_per_unit:,.2f} | "
              f"Fee: ${trans.fee:.2f}")
    
    tracker.close()


def example_pnl_calculations():
    """Example: Calculate realized and unrealized P&L"""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: P&L Calculations")
    print("=" * 80)
    
    tracker = TransactionTracker("portfolio_history.db")
    
    # Method 1: Manual price (original way)
    print("\n1. Unrealized P&L with manual price:")
    current_price = 55000.0
    unrealized = tracker.calculate_unrealized_pnl("BTC", current_price)
    
    if unrealized:
        print(f"   Symbol: {unrealized.symbol}")
        print(f"   Current Amount: {unrealized.current_amount:.4f} BTC")
        print(f"   Average Cost Basis: ${unrealized.average_cost_basis:,.2f}")
        print(f"   Current Price: ${unrealized.current_price:,.2f}")
        print(f"   Total Cost Basis: ${unrealized.total_cost_basis:,.2f}")
        print(f"   Current Value: ${unrealized.current_value:,.2f}")
        print(f"   Unrealized Gain/Loss: ${unrealized.unrealized_gain_loss:,.2f} "
              f"({unrealized.unrealized_gain_loss_pct:+.2f}%)")
    else:
        print("   No open positions found")
    
    # Method 2: Automatic price fetching (NEW!)
    print("\n2. Unrealized P&L with automatic price fetching:")
    print("   Fetching current prices from CoinGecko...")
    unrealized_all = tracker.calculate_unrealized_pnl_with_prices()
    
    if unrealized_all:
        for symbol, unrealized in unrealized_all.items():
            print(f"\n   {symbol}:")
            print(f"     Current Amount: {unrealized.current_amount:.4f}")
            print(f"     Average Cost Basis: ${unrealized.average_cost_basis:,.2f}")
            print(f"     Current Price: ${unrealized.current_price:,.2f}")
            print(f"     Total Cost Basis: ${unrealized.total_cost_basis:,.2f}")
            print(f"     Current Value: ${unrealized.current_value:,.2f}")
            print(f"     Unrealized Gain/Loss: ${unrealized.unrealized_gain_loss:,.2f} "
                  f"({unrealized.unrealized_gain_loss_pct:+.2f}%)")
    else:
        print("   No open positions found")
    
    # Calculate realized P&L
    print("\n3. Realized P&L (closed positions):")
    realized = tracker.calculate_realized_pnl(symbol="BTC")
    print(f"   Total Realized P&L: ${realized['total_realized_pnl']:,.2f}")
    print(f"   Number of Trades: {realized['trade_count']}")
    
    # Get cost basis summary
    print("\n4. Cost Basis Summary:")
    cost_basis = tracker.get_portfolio_cost_basis()
    for symbol, data in cost_basis.items():
        print(f"   {symbol}: {data['amount']:.4f} @ avg ${data['average_cost_per_unit']:,.2f} "
              f"(Total cost: ${data['total_cost_basis']:,.2f})")
    
    tracker.close()


def example_tax_reporting():
    """Example: Generate tax reports"""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Tax Reporting")
    print("=" * 80)
    
    tracker = TransactionTracker("portfolio_history.db")
    
    # Generate tax report for current year
    current_year = datetime.now().year
    print(f"\n1. Tax Report for {current_year} (FIFO method):")
    tax_report = tracker.generate_tax_report(current_year, AccountingMethod.FIFO)
    
    print(f"   Accounting Method: {tax_report['accounting_method']}")
    print(f"   Total Trades: {tax_report['total_trades']}")
    print(f"   Total Gains: ${tax_report['total_gains']:,.2f}")
    print(f"   Total Losses: ${tax_report['total_losses']:,.2f}")
    print(f"   Net Gain/Loss: ${tax_report['net_gain_loss']:,.2f}")
    
    if tax_report['trades']:
        print("\n   Breakdown by Asset:")
        for trade in tax_report['trades']:
            print(f"     {trade['symbol']}:")
            print(f"       Amount Sold: {trade['amount_sold']:.4f}")
            print(f"       Cost Basis: ${trade['cost_basis']:,.2f}")
            print(f"       Sale Proceeds: ${trade['sale_proceeds']:,.2f}")
            print(f"       Gain/Loss: ${trade['gain_loss']:,.2f}")
            print(f"       Trades: {trade['trade_count']}")
    else:
        print("   No trades found for this year")
    
    tracker.close()


def example_rebalancing_integration():
    """Example: Integrate transaction tracking with rebalancing"""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Rebalancing Integration")
    print("=" * 80)
    
    # Initialize components
    db = PortfolioDatabase("portfolio_history.db")
    tracker = db.transaction_tracker
    rebalancer = PortfolioRebalancer()
    
    # Create a sample portfolio
    portfolio = {
        "BTC": Asset(
            symbol="BTC",
            name="Bitcoin",
            amount=0.5,
            current_price=50000.0,
            allocation_percent=60.0,
            value=25000.0
        ),
        "ETH": Asset(
            symbol="ETH",
            name="Ethereum",
            amount=10.0,
            current_price=3000.0,
            allocation_percent=40.0,
            value=30000.0
        )
    }
    
    # Calculate rebalancing actions
    print("\n1. Calculating rebalancing actions...")
    actions = rebalancer.calculate_rebalancing(portfolio)
    
    # Log transactions for rebalancing
    print("\n2. Logging rebalancing transactions...")
    transaction_ids = rebalancer.log_rebalancing_transactions(
        actions=actions,
        transaction_tracker=tracker,
        fee_percentage=0.1,  # 0.1% fee
        exchange="Coinbase"
    )
    
    print(f"   Logged {len(transaction_ids)} transactions")
    for trans_id in transaction_ids:
        print(f"   Transaction ID: {trans_id}")
    
    # Show transaction history
    print("\n3. Recent transactions:")
    recent = tracker.get_transaction_history()
    for trans in recent[:5]:  # Show last 5
        print(f"   {trans.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | "
              f"{trans.symbol} | {trans.transaction_type.value} | "
              f"{trans.amount:.4f} @ ${trans.price_per_unit:,.2f}")
    
    db.close()
    tracker.close()


def example_portfolio_pnl_summary():
    """Example: Get complete portfolio P&L summary with automatic price fetching"""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Complete Portfolio P&L Summary")
    print("=" * 80)
    
    tracker = TransactionTracker("portfolio_history.db")
    
    print("\nFetching current prices and calculating P&L...")
    summary = tracker.get_portfolio_pnl_summary()
    
    print("\n" + "=" * 80)
    print("PORTFOLIO P&L SUMMARY")
    print("=" * 80)
    
    print(f"\nTotal Cost Basis: ${summary['total_cost_basis']:,.2f}")
    print(f"Total Current Value: ${summary['total_current_value']:,.2f}")
    print(f"Total Return: {summary['total_return_pct']:+.2f}%")
    
    print(f"\nUnrealized Gain/Loss: ${summary['total_unrealized_gain_loss']:,.2f}")
    print(f"Realized Gain/Loss: ${summary['total_realized_gain_loss']:,.2f}")
    print(f"Total Gain/Loss: ${summary['total_gain_loss']:,.2f}")
    
    if summary['unrealized_pnl']:
        print("\nUnrealized P&L by Asset:")
        for symbol, pnl in summary['unrealized_pnl'].items():
            print(f"  {symbol}: ${pnl.unrealized_gain_loss:,.2f} ({pnl.unrealized_gain_loss_pct:+.2f}%)")
    
    tracker.close()


def example_multiple_accounting_methods():
    """Example: Compare different accounting methods"""
    print("\n" + "=" * 80)
    print("EXAMPLE 6: Accounting Method Comparison")
    print("=" * 80)
    
    # Note: This is a simplified example
    # In practice, you'd need separate databases or reset between methods
    print("\nNote: Different accounting methods (FIFO, LIFO, Average Cost)")
    print("      will produce different realized P&L calculations.")
    print("\nFIFO (First In, First Out):")
    print("  - Matches oldest purchases with sales")
    print("  - Often results in higher taxes in rising markets")
    print("\nLIFO (Last In, First Out):")
    print("  - Matches newest purchases with sales")
    print("  - May result in lower taxes in rising markets")
    print("\nAverage Cost:")
    print("  - Uses weighted average of all purchases")
    print("  - Simplifies calculations but may not be tax-optimal")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("TRANSACTION TRACKING EXAMPLES")
    print("=" * 80)
    
    try:
        # Run examples
        example_basic_transactions()
        example_pnl_calculations()
        example_tax_reporting()
        example_rebalancing_integration()
        example_portfolio_pnl_summary()
        example_multiple_accounting_methods()
        
        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()

