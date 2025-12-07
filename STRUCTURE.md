# Project Structure

This document describes the organized folder structure of the cryptocurrency portfolio tracker.

## Directory Structure

```
.
├── src/
│   └── portfolio_tracker/          # Main Python package
│       ├── __init__.py             # Package initialization
│       ├── blockchain_balance_fetcher.py  # Blockchain balance fetching
│       ├── constants.py            # Shared constants and configuration
│       ├── portfolio_database.py   # Database operations
│       ├── portfolio_evaluator.py  # Portfolio analysis and evaluation
│       ├── portfolio_rebalancer.py # Rebalancing calculator
│       └── technical_indicators.py # Technical indicator calculations
│
├── web/                            # Web dashboard
│   ├── dashboard_api.py           # Flask API server
│   └── dashboard/                 # Frontend files
│       ├── index.html             # Main dashboard page
│       └── static/
│           ├── css/
│           │   └── dashboard.css  # Dashboard styles
│           └── js/
│               └── dashboard.js   # Dashboard JavaScript
│
├── config/                         # Configuration files
│   └── wallet_config.json.example # Example wallet configuration
│
├── docs/                           # Documentation
│   ├── DASHBOARD_README.md        # Dashboard documentation
│   ├── QUICK_START_DASHBOARD.md   # Quick start guide
│   └── FUTURE_UPDATES.md          # Planned features
│
├── data/                           # Data files (gitignored)
│   └── portfolio_history.db       # SQLite database
│
├── portfolio_evaluator.py         # CLI entry point
├── requirements.txt               # Python dependencies
├── README.md                      # Main documentation
├── STRUCTURE.md                   # This file
└── .gitignore                     # Git ignore rules
```

## Module Organization

### `src/portfolio_tracker/`
Core portfolio tracking functionality:
- **blockchain_balance_fetcher.py**: Fetches balances from blockchain addresses
- **constants.py**: Shared constants (API endpoints, thresholds, coin mappings)
- **portfolio_database.py**: SQLite database operations for historical data
- **portfolio_evaluator.py**: Main analysis engine with recommendations
- **portfolio_rebalancer.py**: Rebalancing calculations
- **technical_indicators.py**: Technical analysis indicators (RSI, MACD, etc.)

### `web/`
Web dashboard application:
- **dashboard_api.py**: Flask REST API server
- **dashboard/**: Frontend HTML, CSS, and JavaScript

### `config/`
Configuration templates and examples:
- **wallet_config.json.example**: Template for wallet configuration

### `docs/`
Documentation files:
- **DASHBOARD_README.md**: Dashboard usage and features
- **QUICK_START_DASHBOARD.md**: Quick start guide
- **FUTURE_UPDATES.md**: Planned enhancements

### `data/`
Runtime data (gitignored):
- **portfolio_history.db**: SQLite database with historical snapshots

## Entry Points

### CLI Entry Point
- **portfolio_evaluator.py** (root): Command-line interface entry point
  - Usage: `python portfolio_evaluator.py [options]`
  - Options: `--dashboard`, `--history`, `--no-save`, `--no-rebalancing`, `--config`

### Dashboard Entry Point
- **web/dashboard_api.py**: Flask API server
  - Can be run directly: `python web/dashboard_api.py`
  - Or via CLI: `python portfolio_evaluator.py --dashboard`

## Import Paths

The package uses relative imports within `src/portfolio_tracker/` and absolute imports from the package root:

```python
# Within package (relative imports)
from .constants import COIN_NAMES
from .portfolio_rebalancer import PortfolioRebalancer

# From outside package (absolute imports)
from src.portfolio_tracker.portfolio_evaluator import PortfolioEvaluator
```

## Configuration Files

- **wallet_config.json**: User's wallet configuration (gitignored, stored in root or config/)
- **wallet_config.json.example**: Template file (in config/)

## Database

- **portfolio_history.db**: SQLite database (stored in data/ directory)
- Automatically created on first run
- Contains historical snapshots, asset holdings, and market analysis data

## Benefits of This Structure

1. **Separation of Concerns**: Core logic, web interface, and configuration are separated
2. **Maintainability**: Easy to find and modify specific components
3. **Scalability**: Easy to add new features without cluttering the root
4. **Package Structure**: Proper Python package organization for potential distribution
5. **Documentation**: Centralized documentation in docs/
6. **Configuration**: Config files separated from code
7. **Data Isolation**: Runtime data in separate directory (gitignored)

