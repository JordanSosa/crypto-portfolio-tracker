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

try:
    from transaction_tracker import TransactionTracker, TransactionType, AccountingMethod
    TRANSACTION_TRACKER_AVAILABLE = True
except ImportError:
    TRANSACTION_TRACKER_AVAILABLE = False

app = Flask(__name__, static_folder='dashboard/static', static_url_path='/static')
CORS(app)  # Enable CORS for development

# Global cache for portfolio data with timestamp
_portfolio_cache = None
_analyses_cache = None
_market_data_cache = None
_cache_timestamp = None
CACHE_DURATION_SECONDS = 300  # Cache for 5 minutes to avoid rate limits


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


def load_portfolio_data(force_refresh: bool = False):
    """Load portfolio data and cache it"""
    global _portfolio_cache, _analyses_cache, _market_data_cache, _cache_timestamp
    
    # Check if we have valid cached data
    if not force_refresh and _portfolio_cache is not None and _cache_timestamp is not None:
        cache_age = (datetime.now() - _cache_timestamp).total_seconds()
        if cache_age < CACHE_DURATION_SECONDS:
            # Return cached data
            return _portfolio_cache, _analyses_cache, _market_data_cache
    
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
        
        # Cache the results with timestamp
        _portfolio_cache = portfolio
        _analyses_cache = analyses
        _market_data_cache = evaluator.market_data
        _cache_timestamp = datetime.now()
        
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
    """Get performance metrics including advanced metrics"""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        db = PortfolioDatabase()
        returns = db.calculate_returns()
        snapshot_count = db.get_snapshot_count()
        
        # Get advanced metrics
        sharpe = db.calculate_sharpe_ratio(days=365)
        sortino = db.calculate_sortino_ratio(days=365)
        drawdown = db.calculate_max_drawdown(days=365)
        # Note: benchmark comparison removed per user request
        
        db.close()
        
        # Format drawdown dates for JSON serialization
        drawdown_formatted = None
        if drawdown:
            drawdown_formatted = {
                'max_drawdown_pct': drawdown['max_drawdown_pct'],
                'max_drawdown_value': drawdown['max_drawdown_value'],
                'peak_date': drawdown['peak_date'].strftime('%Y-%m-%d') if drawdown.get('peak_date') else None,
                'trough_date': drawdown['trough_date'].strftime('%Y-%m-%d') if drawdown.get('trough_date') else None,
                'recovery_date': drawdown['recovery_date'].strftime('%Y-%m-%d') if drawdown.get('recovery_date') else None,
                'days_to_recover': drawdown.get('days_to_recover')
            }
        
        return jsonify({
            'returns': returns,
            'snapshot_count': snapshot_count,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'max_drawdown': drawdown_formatted
            # Note: benchmark_comparison removed per user request
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


@app.route('/api/portfolio/deposit-allocation')
def get_deposit_allocation():
    """Calculate deposit allocation plan"""
    deposit_amount = request.args.get('amount', type=float)
    
    if not deposit_amount or deposit_amount <= 0:
        return jsonify({'error': 'Invalid deposit amount'}), 400
    
    if not REBALANCER_AVAILABLE:
        return jsonify({'error': 'Rebalancer not available'}), 500
    
    portfolio, analyses, market_data = load_portfolio_data()
    
    if portfolio is None:
        return jsonify({'error': 'Could not load portfolio data'}), 500
    
    try:
        rebalancer = PortfolioRebalancer()
        
        # Extract DCA priorities from analyses
        dca_priorities = {}
        for analysis in analyses:
            if analysis.dca_priority > 0:
                dca_priorities[analysis.symbol] = analysis.dca_priority
        
        allocations = rebalancer.calculate_deposit_allocation(
            portfolio,
            deposit_amount,
            market_data=market_data,
            dca_priorities=dca_priorities if dca_priorities else None
        )
        
        current_total = sum(asset.value for asset in portfolio.values())
        new_total = current_total + deposit_amount
        
        # Convert allocations to list format for easier frontend handling
        allocations_list = []
        for symbol, details in allocations.items():
            allocations_list.append({
                'symbol': symbol,
                **details
            })
        
        # Calculate projected allocations for all assets
        projected_allocations = []
        for symbol, asset in portfolio.items():
            if symbol in allocations:
                new_allocation = allocations[symbol]["new_allocation"]
            else:
                new_allocation = (asset.value / new_total) * 100
            
            target = rebalancer.target_allocations.get(symbol, 0.0)
            diff = new_allocation - target
            
            if abs(diff) < 2.0:
                status = "on_target"
            elif diff > 0:
                status = "over_target"
            else:
                status = "under_target"
            
            projected_allocations.append({
                'symbol': symbol,
                'name': asset.name,
                'current': asset.allocation_percent,
                'after': new_allocation,
                'target': target,
                'status': status
            })
        
        # Add assets in target but not in portfolio
        for symbol, target_pct in rebalancer.target_allocations.items():
            if symbol not in [a['symbol'] for a in projected_allocations]:
                if symbol in allocations:
                    new_allocation = allocations[symbol]["new_allocation"]
                else:
                    new_allocation = 0.0
                
                diff = new_allocation - target_pct
                if abs(diff) < 2.0:
                    status = "on_target"
                elif diff > 0:
                    status = "over_target"
                else:
                    status = "under_target"
                
                projected_allocations.append({
                    'symbol': symbol,
                    'name': allocations.get(symbol, {}).get('name', symbol),
                    'current': 0.0,
                    'after': new_allocation,
                    'target': target_pct,
                    'status': status
                })
        
        total_allocated = sum(a['deposit_allocation'] for a in allocations_list)
        
        return jsonify({
            'deposit_amount': deposit_amount,
            'current_total': current_total,
            'new_total': new_total,
            'allocations': allocations_list,
            'projected_allocations': projected_allocations,
            'total_allocated': total_allocated,
            'remaining': deposit_amount - total_allocated
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolio/refresh')
def refresh_portfolio_data():
    """Force refresh of portfolio data (bypasses cache)"""
    portfolio, analyses, market_data = load_portfolio_data(force_refresh=True)
    
    if portfolio is None:
        return jsonify({'error': 'Could not load portfolio data'}), 500
    
    return jsonify({
        'message': 'Portfolio data refreshed successfully',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/transactions/pnl')
def get_transaction_pnl():
    """Get P&L summary from transaction tracker"""
    if not TRANSACTION_TRACKER_AVAILABLE:
        return jsonify({'error': 'Transaction tracker not available'}), 500
    
    try:
        db = PortfolioDatabase()
        tracker = db.transaction_tracker
        
        # Get portfolio P&L summary with automatic price fetching
        summary = tracker.get_portfolio_pnl_summary()
        
        # Format unrealized P&L for JSON
        unrealized_formatted = {}
        for symbol, pnl in summary['unrealized_pnl'].items():
            unrealized_formatted[symbol] = {
                'symbol': pnl.symbol,
                'current_amount': pnl.current_amount,
                'average_cost_basis': pnl.average_cost_basis,
                'current_price': pnl.current_price,
                'total_cost_basis': pnl.total_cost_basis,
                'current_value': pnl.current_value,
                'unrealized_gain_loss': pnl.unrealized_gain_loss,
                'unrealized_gain_loss_pct': pnl.unrealized_gain_loss_pct
            }
        
        prices_failed = summary.get('prices_failed', False)
        error_message = None
        if prices_failed:
            error_message = "Unable to fetch current prices from CoinGecko API. This may be due to rate limits. Cost basis data is shown, but current values and P&L cannot be calculated. Please wait a minute and refresh the page."
        
        db.close()
        tracker.close()
        
        return jsonify({
            'unrealized_pnl': unrealized_formatted,
            'realized_pnl': summary['realized_pnl'],
            'total_unrealized_gain_loss': summary['total_unrealized_gain_loss'],
            'total_realized_gain_loss': summary['total_realized_gain_loss'],
            'total_gain_loss': summary['total_gain_loss'],
            'total_cost_basis': summary['total_cost_basis'],
            'total_current_value': summary['total_current_value'],
            'total_return_pct': summary['total_return_pct'],
            'prices_failed': prices_failed,
            'error': error_message
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/transactions/history')
def get_transaction_history():
    """Get transaction history"""
    if not TRANSACTION_TRACKER_AVAILABLE:
        return jsonify({'error': 'Transaction tracker not available'}), 500
    
    symbol = request.args.get('symbol')
    limit = int(request.args.get('limit', 50))
    
    try:
        db = PortfolioDatabase()
        tracker = db.transaction_tracker
        
        # Get transaction history
        transactions = tracker.get_transaction_history(symbol=symbol.upper() if symbol else None)
        
        # Limit results
        transactions = transactions[:limit]
        
        # Format for JSON
        transactions_formatted = []
        for trans in transactions:
            transactions_formatted.append({
                'id': trans.id,
                'timestamp': trans.timestamp.isoformat() if trans.timestamp else None,
                'symbol': trans.symbol,
                'transaction_type': trans.transaction_type.value,
                'amount': trans.amount,
                'price_per_unit': trans.price_per_unit,
                'total_value': trans.total_value,
                'fee': trans.fee,
                'fee_currency': trans.fee_currency,
                'exchange': trans.exchange,
                'notes': trans.notes
            })
        
        db.close()
        tracker.close()
        
        return jsonify(transactions_formatted)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/transactions/cost-basis')
def get_cost_basis():
    """Get cost basis summary for all assets"""
    if not TRANSACTION_TRACKER_AVAILABLE:
        return jsonify({'error': 'Transaction tracker not available'}), 500
    
    try:
        db = PortfolioDatabase()
        tracker = db.transaction_tracker
        
        cost_basis = tracker.get_portfolio_cost_basis()
        
        db.close()
        tracker.close()
        
        return jsonify(cost_basis)
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

