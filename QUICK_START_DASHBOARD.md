# Quick Start: Portfolio Dashboard

## 🚀 Get Started in 3 Steps

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Start the Dashboard
```bash
python portfolio_evaluator.py --dashboard
```

### Step 3: Open Your Browser
Navigate to: **http://localhost:5000**

That's it! Your dashboard is now running.

## 📊 What You'll See

- **Portfolio Overview**: Total value and performance metrics
- **Value Chart**: Interactive chart showing portfolio value over time
- **Asset Allocation**: Visual breakdown of your holdings
- **Recommendations**: Actionable trading recommendations
- **Rebalancing**: Buy/sell suggestions to reach target allocations

## 🔄 Auto-Refresh

The dashboard automatically refreshes every 5 minutes to show the latest data.

## 🛑 Stopping the Dashboard

Press `Ctrl+C` in the terminal where the server is running.

## ❓ Troubleshooting

**Dashboard won't start?**
- Make sure Flask is installed: `pip install flask flask-cors`
- Check if port 5000 is available

**No data showing?**
- Run `python portfolio_evaluator.py` first to generate portfolio data
- Ensure your `wallet_config.json` is configured (or the manual portfolio is set up)

For more details, see `DASHBOARD_README.md`

