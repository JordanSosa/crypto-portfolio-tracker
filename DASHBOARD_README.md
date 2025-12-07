# Portfolio Dashboard

A web-based dashboard for visualizing your cryptocurrency portfolio with interactive charts and real-time recommendations.

## Features

- **Portfolio Overview**: View total portfolio value with performance metrics (24h, 7d, 30d returns)
- **Portfolio Value Chart**: Interactive line chart showing portfolio value over time
- **Asset Allocation**: Visual pie chart and table showing current asset allocations
- **Recommendations**: Color-coded recommendations with priority levels
- **Rebalancing**: Detailed rebalancing suggestions with buy/sell amounts
- **Auto-refresh**: Dashboard automatically refreshes every 5 minutes

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

This will install Flask and flask-cors along with other dependencies.

## Usage

### Starting the Dashboard

You can start the dashboard in two ways:

#### Option 1: Using the main script
```bash
python portfolio_evaluator.py --dashboard
```

#### Option 2: Direct API server
```bash
python dashboard_api.py
```

The dashboard will be available at: **http://localhost:5000**

Open your web browser and navigate to that URL to view the dashboard.

### Stopping the Dashboard

Press `Ctrl+C` in the terminal where the server is running.

## Dashboard Sections

### Portfolio Overview
- Total portfolio value in AUD
- Performance metrics (24h, 7d, 30d returns)
- Portfolio value history chart (last 30 days)

### Asset Allocation
- Interactive doughnut chart showing allocation percentages
- Detailed table with:
  - Asset symbols and names
  - Current allocation percentages
  - Asset values
  - 24-hour price changes
  - Market trends (bullish/bearish/neutral)

### Recommendations
- Color-coded recommendation cards:
  - **Red (High Priority)**: Urgent actions needed
  - **Yellow (Medium Priority)**: Moderate priority actions
  - **Green (Low Priority)**: Standard recommendations
- Each card shows:
  - Recommendation type (DCA_INCREASE, DCA_DECREASE, etc.)
  - Asset symbol
  - Priority level (0-10)
  - Reasoning
  - Suggested action

### Rebalancing
- Buy recommendations: Assets to purchase with exact amounts
- Sell recommendations: Assets to sell with exact amounts
- Shows current vs target allocations
- Displays both value and quantity to buy/sell

## Technical Details

### Backend API

The dashboard uses a Flask REST API with the following endpoints:

- `GET /api/portfolio/current` - Current portfolio state and analyses
- `GET /api/portfolio/history?days=30` - Portfolio value history
- `GET /api/portfolio/performance` - Performance metrics
- `GET /api/portfolio/rebalancing` - Rebalancing recommendations
- `GET /api/asset/<symbol>/history?days=30` - Individual asset history

### Frontend

- **HTML5** with semantic markup
- **Chart.js** for interactive charts
- **Vanilla JavaScript** (no framework dependencies)
- **Responsive CSS** with modern design
- **Auto-refresh** every 5 minutes

## Troubleshooting

### Dashboard won't start

1. **Check Flask installation**:
   ```bash
   pip install flask flask-cors
   ```

2. **Check if port 5000 is available**:
   - The dashboard uses port 5000 by default
   - If it's in use, you can modify `dashboard_api.py` to use a different port

3. **Check for errors in the terminal**:
   - The server will display error messages if there are issues loading portfolio data

### No data showing

1. **Ensure portfolio data exists**:
   - Run `python portfolio_evaluator.py` first to generate portfolio data
   - Make sure `wallet_config.json` is configured or the manual portfolio is set up

2. **Check database**:
   - Historical data requires the SQLite database (`portfolio_history.db`)
   - Run the evaluator at least once to create snapshots

3. **Check browser console**:
   - Open browser developer tools (F12) and check for JavaScript errors
   - Check the Network tab to see if API calls are failing

### Charts not displaying

1. **Check internet connection**:
   - Chart.js is loaded from a CDN
   - Ensure you have internet access

2. **Check browser compatibility**:
   - Modern browsers (Chrome, Firefox, Safari, Edge) are supported
   - JavaScript must be enabled

## Future Enhancements

Planned improvements:
- Real-time WebSocket updates
- More chart types (candlestick, volume, etc.)
- Export functionality (PDF, CSV)
- Customizable date ranges
- Dark mode
- Mobile app version
- Alert notifications

## Security Note

The dashboard runs on `127.0.0.1` (localhost) by default, making it only accessible from your local machine. This is intentional for security. If you need remote access, consider:

1. Using a reverse proxy (nginx, Apache)
2. Adding authentication
3. Using HTTPS
4. Restricting access with firewall rules

**Never expose the dashboard to the public internet without proper security measures.**

