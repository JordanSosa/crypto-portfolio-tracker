"""
Dashboard API Backend
Flask API server for portfolio dashboard
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import sys

# Import portfolio modules
try:
    from portfolio_evaluator import (
        PortfolioEvaluator, 
        load_portfolio_from_wallet,
        Asset,
        MarketAnalysis,
        Recommendation
    )
    EVALUATOR_AVAILABLE = True
except ImportError:
    EVALUATOR_AVAILABLE = False

try:
    from portfolio_database import PortfolioDatabase
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

try:
    from portfolio_rebalancer import PortfolioRebalancer
    REBALANCER_AVAILABLE = True
except ImportError:
    REBALANCER_AVAILABLE = False

app = Flask(__name__, static_folder='dashboard/static', static_url_path='/static')
CORS(app)  # Enable CORS for development

# Global cache for portfolio data (refresh on each request for now)
_portfolio_cache = None
_analyses_cache = None
_market_data_cache = None


def asset_to_dict(asset: Asset) -> Dict:
    """Convert Asset object to dictionary"""
    return {
        'symbol': asset.symbol,
        'name': asset.name,
        'amount': asset.amount,
        'current_price': asset.current_price,
        'allocation_percent': asset.allocation_percent,
        'value': asset.value
    }


def analysis_to_dict(analysis: MarketAnalysis) -> Dict:
    """Convert MarketAnalysis object to dictionary"""
    result = {
        'symbol': analysis.symbol,
        'price_change_24h': analysis.price_change_24h,
        'price_change_7d': analysis.price_change_7d,
        'price_change_30d': analysis.price_change_30d,
        'volatility': analysis.volatility,
        'momentum': analysis.momentum,
        'risk_adjusted_momentum': analysis.risk_adjusted_momentum,
        'trend': analysis.trend,
        'recommendation': analysis.recommendation.value if hasattr(analysis.recommendation, 'value') else str(analysis.recommendation),
        'reason': analysis.reason,
        'suggested_action': analysis.suggested_action,
        'dca_multiplier': analysis.dca_multiplier,
        'dca_priority': analysis.dca_priority
    }
    
    # Add technical indicators if available
    if analysis.technical_indicators:
        ti = analysis.technical_indicators
        result['technical_indicators'] = {
            'rsi': ti.rsi,
            'sma_50': ti.sma_50,
            'sma_200': ti.sma_200,
            'ema_12': ti.ema_12,
            'ema_26': ti.ema_26,
            'macd': ti.macd,
            'bollinger_bands': ti.bollinger_bands,
            'price_vs_ma_position': ti.price_vs_ma_position,
            'price_vs_bands_position': ti.price_vs_bands_position
        }
    else:
        result['technical_indicators'] = None
    
    return result


def load_portfolio_data():
    """Load portfolio data and cache it"""
    global _portfolio_cache, _analyses_cache, _market_data_cache
    
    if not EVALUATOR_AVAILABLE:
        return None, None, None
    
    try:
        # Try to load from wallet, but disable prompts for API use
        # It will use btc_balance from config if available
        portfolio, market_data = load_portfolio_from_wallet(prompt_for_btc=False)
        
        # Fall back to manual portfolio if wallet loading fails
        if portfolio is None:
            # Use the manual portfolio from portfolio_evaluator.py
            from portfolio_evaluator import COIN_NAMES
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
            market_data = None
        
        # Create evaluator and run analysis
        evaluator = PortfolioEvaluator(portfolio)
        analyses = evaluator.evaluate_portfolio(market_data=market_data)
        
        # Store market data in evaluator for rebalancing
        evaluator.market_data = market_data or evaluator.market_data
        
        # Cache the results
        _portfolio_cache = portfolio
        _analyses_cache = analyses
        _market_data_cache = evaluator.market_data
        
        return portfolio, analyses, evaluator.market_data
        
    except Exception as e:
        print(f"Error loading portfolio data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None, None, None


@app.route('/')
def index():
    """Serve the dashboard HTML"""
    return send_from_directory('dashboard', 'index.html')


@app.route('/api/portfolio/current')
def get_current_portfolio():
    """Get current portfolio state"""
    portfolio, analyses, market_data = load_portfolio_data()
    
    if portfolio is None:
        return jsonify({'error': 'Could not load portfolio data'}), 500
    
    total_value = sum(asset.value for asset in portfolio.values())
    
    return jsonify({
        'portfolio': [asset_to_dict(asset) for asset in portfolio.values()],
        'analyses': [analysis_to_dict(analysis) for analysis in analyses] if analyses else [],
        'total_value': total_value,
        'asset_count': len(portfolio),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/portfolio/history')
def get_portfolio_history():
    """Get portfolio value history"""
    days = int(request.args.get('days', 30))
    
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        db = PortfolioDatabase()
        history = db.get_portfolio_value_history(days=days)
        db.close()
        
        return jsonify([
            {
                'date': timestamp.isoformat(),
                'value': value
            }
            for timestamp, value in history
        ])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolio/performance')
def get_performance_metrics():
    """Get performance metrics"""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        db = PortfolioDatabase()
        returns = db.calculate_returns()
        snapshot_count = db.get_snapshot_count()
        db.close()
        
        return jsonify({
            'returns': returns,
            'snapshot_count': snapshot_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolio/rebalancing')
def get_rebalancing():
    """Get rebalancing recommendations"""
    if not REBALANCER_AVAILABLE:
        return jsonify({'error': 'Rebalancer not available'}), 500
    
    portfolio, analyses, market_data = load_portfolio_data()
    
    if portfolio is None:
        return jsonify({'error': 'Could not load portfolio data'}), 500
    
    try:
        rebalancer = PortfolioRebalancer()
        actions = rebalancer.calculate_rebalancing(
            portfolio,
            market_data=market_data
        )
        
        # Convert actions to dictionaries
        actions_dict = []
        for action in actions:
            actions_dict.append({
                'symbol': action.symbol,
                'name': action.name,
                'current_allocation': action.current_allocation,
                'target_allocation': action.target_allocation,
                'allocation_diff': action.allocation_diff,
                'current_value': action.current_value,
                'target_value': action.target_value,
                'value_diff': action.value_diff,
                'current_amount': action.current_amount,
                'target_amount': action.target_amount,
                'amount_diff': action.amount_diff,
                'action': action.action,
                'current_price': action.current_price
            })
        
        total_value = sum(asset.value for asset in portfolio.values())
        summary = rebalancer.get_rebalancing_summary(actions)
        
        return jsonify({
            'actions': actions_dict,
            'summary': summary,
            'total_value': total_value
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/asset/<symbol>/history')
def get_asset_history(symbol: str):
    """Get historical data for a specific asset"""
    days = int(request.args.get('days', 30))
    
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        db = PortfolioDatabase()
        history = db.get_asset_history(symbol.upper(), days=days)
        db.close()
        
        return jsonify([
            {
                'date': timestamp.isoformat(),
                'amount': amount,
                'price': price,
                'value': value
            }
            for timestamp, amount, price, value in history
        ])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Check if dashboard directory exists
    if not os.path.exists('dashboard'):
        os.makedirs('dashboard')
        os.makedirs('dashboard/static')
        os.makedirs('dashboard/static/css')
        os.makedirs('dashboard/static/js')
    
    print("Starting Portfolio Dashboard API...")
    print("Dashboard will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    
    app.run(debug=True, host='127.0.0.1', port=5000)

