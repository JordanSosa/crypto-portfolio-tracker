# Cryptocurrency Portfolio Tracker

An automated cryptocurrency portfolio tracker that fetches balances from blockchain addresses, analyzes market conditions, and provides buy/sell recommendations with historical performance tracking.

## Features

### Current Features
- **Multi-blockchain Support**: Fetches balances from Bitcoin, Ethereum, XRP, Solana, and ERC-20 tokens
- **Automated Balance Fetching**: Supports wallet addresses and Bitcoin xpub keys
- **Market Analysis**: Real-time price data from CoinGecko API
- **Trading Recommendations**: Automated buy/sell/hold suggestions based on:
  - Portfolio allocation percentages
  - Price momentum (24h, 7d, 30d)
  - Volatility analysis
  - Risk-adjusted momentum
  - Trend detection
- **Historical Tracking**: 
  - Automatic portfolio snapshots (daily/weekly)
  - Performance metrics (daily, weekly, monthly, YTD, all-time returns)
  - Portfolio value history
  - Asset-level historical tracking

## Installation

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Set up wallet configuration:
   - Copy `wallet_config.json.example` to `wallet_config.json`
   - Add your wallet addresses and API keys
   - Get a free Etherscan API key at https://etherscan.io/apis

## Usage

### Basic Portfolio Evaluation

Run the portfolio evaluator to get current analysis and recommendations:

```bash
python portfolio_evaluator.py
```

This will:
- Fetch current balances from your configured wallets (or use manual portfolio)
- Get latest market prices
- Analyze portfolio allocation and market conditions
- Generate buy/sell/hold recommendations
- Save a snapshot to the database
- Display performance metrics

### View Historical Data

View portfolio value history for the last N days:

```bash
python portfolio_evaluator.py --history 30
```

This displays a table showing:
- Date and time of each snapshot
- Portfolio value in AUD
- Value change from previous snapshot
- Percentage change

### Skip Saving Snapshot

If you want to run analysis without saving to database:

```bash
python portfolio_evaluator.py --no-save
```

## Configuration

### Wallet Configuration (`wallet_config.json`)

```json
{
  "etherscan_api_key": "YOUR_ETHERSCAN_API_KEY_HERE",
  "btc_xpub": "your_bitcoin_xpub_key",
  "btc_address": "your_bitcoin_address",
  "eth_address": "your_ethereum_address",
  "xrp_address": "your_xrp_address",
  "sol_address": "your_solana_address",
  "erc20_tokens": [
    {
      "symbol": "LINK",
      "contract": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
      "decimals": 18
    }
  ]
}
```

## Database

The tool uses SQLite to store historical portfolio data in `portfolio_history.db`. The database includes:

- **portfolio_snapshots**: Timestamped portfolio value snapshots
- **asset_holdings**: Individual asset holdings for each snapshot
- **market_analysis**: Market analysis data and recommendations for each snapshot

### Database Features

- Automatic snapshot saving on each run
- Performance metrics calculation (returns, Sharpe ratio, etc.)
- Historical data queries
- Asset-level history tracking
- Automatic cleanup of old snapshots (keeps one per day for data older than 1 year)

## Recommendation Logic

The tool generates recommendations based on multiple factors:

1. **Over-allocation**: Assets >45% allocation may trigger sell recommendations
2. **Bearish momentum**: Strong negative momentum with significant declines
3. **Bullish momentum**: Strong positive momentum with low allocation
4. **High volatility**: High volatility combined with bearish trends
5. **Consistent performance**: Strong performance across multiple timeframes
6. **Under-allocation**: Low allocation with positive/neutral trends
7. **Rebalancing**: Taking profits after strong 30-day gains

## Performance Metrics

The tool calculates and displays:

- **24h Return**: Portfolio value change in the last 24 hours
- **7d Return**: Portfolio value change in the last 7 days
- **30d Return**: Portfolio value change in the last 30 days
- **YTD Return**: Year-to-date return (from January 1st)
- **All-Time Return**: Return since first snapshot

## File Structure

```
.
├── portfolio_evaluator.py      # Main portfolio analysis and evaluation
├── portfolio_rebalancer.py     # Target allocation and rebalancing calculator
├── blockchain_balance_fetcher.py  # Blockchain balance fetching
├── portfolio_database.py       # Database operations for historical tracking
├── constants.py                # Shared constants and configuration
├── wallet_config.json          # Wallet addresses and API keys (create from example)
├── wallet_config.json.example  # Example configuration file
├── portfolio_history.db        # SQLite database (created automatically)
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Future Enhancements

See `FUTURE_UPDATES.md` for planned features including:
- Technical indicators (RSI, MACD, moving averages)
- Risk management (position sizing, stop-loss suggestions)
- Alert system (price alerts, allocation alerts)
- Portfolio optimization (target allocations, rebalancing calculator)
- Advanced analytics (Sharpe ratio, correlation analysis)
- And more...

## Disclaimer

⚠️ **This is an automated analysis tool for informational purposes only. Always do your own research and consider your risk tolerance before making trading decisions. Past performance does not guarantee future results.**

## License

This project is provided as-is for personal use.
