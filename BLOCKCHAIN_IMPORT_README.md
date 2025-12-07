# Blockchain Transaction Import

This feature automatically imports transaction history from your blockchain addresses and calculates cost basis using historical prices.

## How It Works

1. **Fetches Transaction History**: Uses BlockCypher (Bitcoin) and Etherscan (Ethereum) APIs to get all transactions from your addresses
2. **Identifies Buys/Sells**: 
   - Incoming transactions = BUY (you received crypto)
   - Outgoing transactions = SELL (you sent crypto)
3. **Gets Historical Prices**: Fetches the price of the asset on the transaction date from CoinGecko
4. **Records Transactions**: Automatically creates cost basis lots and records transactions in the transaction tracker

## Usage

### Quick Start - Import from Wallet Config

The easiest way is to import from your existing `wallet_config.json`:

```python
from blockchain_transaction_importer import import_from_wallet_config

# Import all transactions from addresses in wallet_config.json
results = import_from_wallet_config(
    wallet_config_path="wallet_config.json",
    limit_per_address=100  # Max transactions per address
)

print(f"Imported {results['total_imported']} transactions")
```

Or run the script directly:

```bash
python blockchain_transaction_importer.py
```

### Manual Import

You can also import from specific addresses:

```python
from blockchain_transaction_importer import (
    import_bitcoin_transactions,
    import_ethereum_transactions
)
from blockchain_balance_fetcher import BlockchainBalanceFetcher
from transaction_tracker import TransactionTracker

# Initialize
balance_fetcher = BlockchainBalanceFetcher(etherscan_api_key="YOUR_KEY")
tracker = TransactionTracker("portfolio_history.db")

# Import Bitcoin transactions
import_bitcoin_transactions(
    address="bc1q...",
    tracker=tracker,
    balance_fetcher=balance_fetcher,
    symbol="BTC",
    limit=100
)

# Import Ethereum transactions
import_ethereum_transactions(
    address="0x...",
    tracker=tracker,
    balance_fetcher=balance_fetcher,
    symbol="ETH",
    limit=100
)
```

## Important Notes

### Limitations

1. **Exchange Transactions**: If you bought crypto on an exchange and then withdrew it, the on-chain transaction only shows the withdrawal, not the purchase. The system will treat this as a "buy" at the withdrawal date price, which may not be accurate.

2. **Self-Transfers**: Transfers between your own addresses will be counted as buys/sells. You may need to manually adjust these.

3. **Historical Price Accuracy**: CoinGecko's historical price API may not have exact prices for very old transactions. The system uses daily prices, so intraday price movements aren't captured.

4. **Rate Limits**: The import process makes many API calls (one per transaction for historical prices). This can be slow and may hit rate limits. The script includes delays to help with this.

### What Gets Imported

- **Bitcoin**: All transactions from addresses (or xpub-derived addresses)
- **Ethereum**: All ETH transactions from your address
- **ERC-20 Tokens**: Not yet supported (would need additional Etherscan API calls)

### Transaction Types

- **Incoming transactions** → Recorded as BUY transactions
- **Outgoing transactions** → Recorded as SELL transactions

The system automatically:
- Calculates cost basis from historical prices
- Includes transaction fees
- Creates cost basis lots for tracking
- Links transactions to their blockchain transaction hashes

## After Import

Once imported, you can:
- View transaction history in the dashboard
- See cost basis and P&L calculations
- Generate tax reports
- Track realized and unrealized gains/losses

## Troubleshooting

**"No transactions found"**
- Check that the address has transaction history
- Verify the address format is correct
- For Bitcoin xpub, make sure addresses with balances are being checked

**"Could not fetch price"**
- CoinGecko may not have historical data for very old dates
- Check your internet connection
- Wait a moment and retry (rate limiting)

**"Rate limit exceeded"**
- The import process makes many API calls
- Wait a few minutes and try again
- Consider importing in smaller batches (lower `limit` parameter)

## Future Enhancements

Potential improvements:
- Support for ERC-20 token transactions
- Better handling of exchange deposits/withdrawals
- Detection of self-transfers
- Batch historical price fetching (more efficient)
- Support for more blockchains (Solana, XRP, etc.)

