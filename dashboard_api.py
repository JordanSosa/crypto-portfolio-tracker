"""
Dashboard API Backend
Flask API server for portfolio dashboard
"""

from flask import Flask, jsonify, send_from_directory, request, render_template
from flask_cors import CORS
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import sys
import json

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

try:
    from ai_advisor import AIAdvisor
    AI_ADVISOR_AVAILABLE = True
except ImportError:
    AI_ADVISOR_AVAILABLE = False

try:
    from blockchain_transaction_importer import import_from_wallet_config
    IMPORTER_AVAILABLE = True
except ImportError:
    IMPORTER_AVAILABLE = False

app = Flask(__name__, 
            static_folder='dashboard/static', 
            static_url_path='/static',
            template_folder='dashboard/templates')
CORS(app)  # Enable CORS for development

import pickle

# Global cache for portfolio data with timestamp
_portfolio_cache = None
_analyses_cache = None
_market_data_cache = None
_cache_timestamp = None
CACHE_DURATION_SECONDS = 14400  # Cache for 4 hours
CACHE_FILE = "portfolio_cache.pkl"


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
    
    # Check if we have valid memory cache
    if not force_refresh and _portfolio_cache is not None and _cache_timestamp is not None:
        cache_age = (datetime.now() - _cache_timestamp).total_seconds()
        if cache_age < CACHE_DURATION_SECONDS:
            return _portfolio_cache, _analyses_cache, _market_data_cache

    # Check for file-based cache if memory cache is empty or expired
    if not force_refresh:
        try:
            if os.path.exists(CACHE_FILE):
                # Check file modification time
                file_mod_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
                if (datetime.now() - file_mod_time).total_seconds() < CACHE_DURATION_SECONDS:
                    print("Loading portfolio data from disk cache...")
                    with open(CACHE_FILE, 'rb') as f:
                        cache_data = pickle.load(f)
                        _portfolio_cache = cache_data.get('portfolio')
                        _analyses_cache = cache_data.get('analyses')
                        _market_data_cache = cache_data.get('market_data')
                        _cache_timestamp = cache_data.get('timestamp')
                        return _portfolio_cache, _analyses_cache, _market_data_cache
        except Exception as e:
            print(f"Error loading cache from disk: {e}")
            # Continue to fetch fresh data
    
    if not EVALUATOR_AVAILABLE:
        return None, None, None
    
    try:
        print("Fetching fresh portfolio data from APIs...")
        # Try to load from wallet, but disable prompts for API use
        # It will use btc_balance from config if available
        portfolio, market_data = load_portfolio_from_wallet(prompt_for_btc=False)
        
        # If wallet loading fails and no portfolio is returned, stop here
        if portfolio is None:
            return None, None, None
        
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

        # Save to disk cache
        try:
            with open(CACHE_FILE, 'wb') as f:
                pickle.dump({
                    'portfolio': _portfolio_cache,
                    'analyses': _analyses_cache,
                    'market_data': _market_data_cache,
                    'timestamp': _cache_timestamp
                }, f)
            print(f"Saved portfolio data to cache file: {CACHE_FILE}")
        except Exception as e:
            print(f"Error saving cache to disk: {e}")
        
        return portfolio, analyses, evaluator.market_data
        
    except Exception as e:
        print(f"Error loading portfolio data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None, None, None


def get_ai_summary(portfolio, analyses):
    """
    Get executive summary from AI Advisor or return None if not available/configured.
    """
    if not AI_ADVISOR_AVAILABLE:
        return None
        
    try:
        # Load config to get API Key
        config_path = 'wallet_config.json'
        api_key = None
        model_name = "gemini-3-pro-preview" # Default per user request
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                try:
                    config = json.load(f)
                    api_key = config.get('gemini_api_key')
                    model_name = config.get('gemini_model', "gemini-3-pro-preview")
                except:
                    pass
        
        if not api_key:
            return None
            
        advisor = AIAdvisor(api_key=api_key, model_name=model_name)
        
        # Create a lookup for analysis data
        analysis_map = {a.symbol: a for a in analyses} if analyses else {}
        
        # Calculate approx 24h PnL
        total_24h_pnl = 0
        for s, a in portfolio.items():
            if s in analysis_map and analysis_map[s].price_change_24h:
                # Value / (1 + pct/100) = value_yesterday
                # PnL = Value - value_yesterday
                pct = analysis_map[s].price_change_24h
                val_yesterday = a.value / (1 + pct/100)
                total_24h_pnl += (a.value - val_yesterday)

        # Prepare context data
        portfolio_context = {
            'total_value': sum(a.value for a in portfolio.values()),
            'total_pnl': total_24h_pnl,
            'assets': [
                {
                    'symbol': s,
                    'value': a.value,
                    'allocation': a.allocation_percent,
                    'change_24h': analysis_map[s].price_change_24h if s in analysis_map else 0.0
                }
                for s, a in portfolio.items()
            ]
        }
        
        analysis_context = [
            analysis_to_dict(a) for a in analyses
        ]
        
        return advisor.generate_portfolio_summary(portfolio_context, analysis_context)
        
    except Exception as e:
        print(f"Error getting AI summary: {e}")
        return None


def get_portfolio_history_data(days: int = 30):
    """Fetch portfolio history from DB and format for charts"""
    labels = []
    values = []
    
    if not DATABASE_AVAILABLE:
        return labels, values
        
    try:
        db = PortfolioDatabase()
        # Get simple value history (list of (datetime, value) tuples)
        history = db.get_portfolio_value_history(days=days)
        db.close()
        
        for dt, value in history:
            # dt is already a datetime object from get_portfolio_value_history
            formatted_date = dt.strftime("%b %d %H:%M") # e.g. "Dec 10 14:30"
            
            labels.append(formatted_date)
            # Ensure value is a float
            values.append(float(value))
            
        return labels, values
    except Exception as e:
        print(f"Error fetching history: {e}")
        # Print stack trace for debugging
        import traceback
        traceback.print_exc()
        return [], []
    except Exception as e:
        print(f"Error fetching history: {e}")
        return [], []


@app.route('/')
def index():
    """Serve the dashboard HTML"""
    # Use render_template to process Jinja2 tags
    portfolio, market_data, _ = load_portfolio_data()
    
    # Calculate some summary stats for the template
    total_value = sum(asset.value for asset in portfolio.values()) if portfolio else 0.0
    
    # Get 7-day history for the sparkline chart
    hist_labels, hist_values = get_portfolio_history_data(days=7)
    
    # Generate executive summary
    executive_summary = None
    if market_data and EVALUATOR_AVAILABLE:
        try:
             # Try AI first
             executive_summary = get_ai_summary(portfolio, market_data)
             
             if not executive_summary:
                 # Fallback to rule-based
                 temp_evaluator = PortfolioEvaluator(portfolio)
                 executive_summary = temp_evaluator.generate_executive_summary(market_data)
        except Exception as e:
            print(f"Error generating summary for template: {e}")

    # Calculate Unrealized P&L (Copy of logic for template render)
    unrealized_pnl = {}
    total_unrealized_pnl = 0.0
    try:
        from transaction_tracker import TransactionTracker
        tracker = TransactionTracker()
        cost_basis_data = tracker.get_portfolio_cost_basis()
        
        for symbol, asset in portfolio.items():
            if symbol in cost_basis_data:
                basis = cost_basis_data[symbol].get('total_cost_basis', 0.0)
                # Check for alternative key if needed or just be safe
                if basis is None: 
                    basis = 0.0
                
                # Debug individual asset
                # print(f"DEBUG: {symbol} - Basis: {basis}, Value: {asset.value}")

                pnl = asset.value - basis
                pnl_percent = (pnl / basis * 100) if basis > 0 else 0
                
                unrealized_pnl[symbol] = {
                    'pnl': pnl, 
                    'pnl_percent': pnl_percent,
                    'cost_basis': basis
                }
                total_unrealized_pnl += pnl
            else:
                unrealized_pnl[symbol] = {'pnl': 0, 'pnl_percent': 0, 'cost_basis': 0}
        
        print(f"DEBUG: P&L Calculated for {len(unrealized_pnl)} assets. Total: {total_unrealized_pnl}")
        print(f"DEBUG: Sample P&L: {list(unrealized_pnl.items())[:1]}")

    except Exception as e:
        print(f"Error calculating P&L for template: {e}")
        import traceback
        traceback.print_exc()
        unrealized_pnl = {s: {'pnl': 0, 'pnl_percent': 0} for s in portfolio}

    # Calculate Rebalancing Plan
    rebalancing_plan = []
    if REBALANCER_AVAILABLE and EVALUATOR_AVAILABLE:
        try:
             rebalancer = PortfolioRebalancer()
             actions = rebalancer.calculate_rebalancing(
                portfolio, 
                rebalance_threshold=1.0, 
                market_data=market_data
             )
             for action in actions:
                if action.action == "HOLD": continue
                rebalancing_plan.append({
                    'symbol': action.symbol,
                    'action': action.action,
                    'amount_diff': action.amount_diff,
                    'value_diff': action.value_diff,
                    'target_allocation': action.target_allocation,
                    'current_allocation': action.current_allocation,
                    'reason': f"Target: {action.target_allocation}%"
                })
        except Exception as e:
             print(f"Error calculating rebalancing for template: {e}")

    return render_template('index.html', 
                           portfolio=portfolio or {}, 
                           total_value=total_value,
                           analyses=market_data,
                           executive_summary=executive_summary,
                           unrealized_pnl=unrealized_pnl,
                           total_unrealized_pnl=total_unrealized_pnl,
                           rebalancing_plan=rebalancing_plan,
                           hist_labels=hist_labels,
                           hist_values=hist_values,
                           active_page='dashboard')


@app.route('/refresh')
def refresh_data():
    """Force refresh of data"""
    global _portfolio_cache
    _portfolio_cache = None
    
    # Clear disk cache
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            print("Disk cache cleared")
    except Exception as e:
        print(f"Error clearing disk cache: {e}")
        
    return '<script>window.location.href="/";</script>'  # Redirect to home


@app.route('/performance')
def performance():
    """Performance page"""
    portfolio, market_data, _ = load_portfolio_data()
    
    # Get longer history for performance page
    hist_labels, hist_values = get_portfolio_history_data(days=365)
    
    return render_template('performance.html', 
                           active_page='performance',
                           hist_labels=hist_labels,
                           hist_values=hist_values)


@app.route('/assets')
def assets():
    """Assets page"""
    portfolio, market_data, _ = load_portfolio_data()
    return render_template('assets.html', portfolio=portfolio or {}, active_page='assets')


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page"""
    config_path = 'wallet_config.json'
    message = None
    
    if request.method == 'POST':
        try:
            new_config = request.form.get('config_json')
            api_key = request.form.get('gemini_api_key')
            model_name = request.form.get('gemini_model')
            
            # Validate JSON
            json_obj = json.loads(new_config)
            
            # Update AI settings if provided (or if empty string to clear)
            if api_key is not None:
                json_obj['gemini_api_key'] = api_key
            if model_name is not None:
                json_obj['gemini_model'] = model_name
                
            # Save to file
            with open(config_path, 'w') as f:
                f.write(json.dumps(json_obj, indent=4))
            message = "Configuration saved successfully!"
        except Exception as e:
            message = f"Error saving config: {e}"
            
    # Load current config
    gemini_api_key = ""
    gemini_model = "gemini-3-pro-preview"
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config_dump = f.read()
                # Also decode to get specific fields
                try:
                    data = json.loads(config_dump)
                    gemini_api_key = data.get('gemini_api_key', '')
                    gemini_model = data.get('gemini_model', 'gemini-3-pro-preview')
                except:
                    pass
        else:
            config_dump = "{}"
    except:
        config_dump = "{}"
        
    return render_template('settings.html', 
                          config_dump=config_dump, 
                          gemini_api_key=gemini_api_key,
                          gemini_model=gemini_model,
                          message=message, 
                          active_page='settings')


@app.route('/pnl')
def pnl():
    """Profit & Loss Analysis page"""
    if not DATABASE_AVAILABLE or not TRANSACTION_TRACKER_AVAILABLE:
        return render_template('pnl.html', error="Transaction tracking not available", active_page='pnl')
        
    try:
        db = PortfolioDatabase()
        # Initialize tracker if not already done in DB (DB usually handles it but let's be safe)
        if not hasattr(db, 'transaction_tracker'):
             tracker = TransactionTracker()
        else:
             tracker = db.transaction_tracker
             
        # Get P&L summary
        summary = tracker.get_portfolio_pnl_summary()
        
        # Also need current portfolio for context
        portfolio, _, _ = load_portfolio_data()
        
        db.close()
        # tracker.close() # DB closes connection usually
        
        return render_template('pnl.html', 
                               summary=summary, 
                               portfolio=portfolio,
                               active_page='pnl')
    except Exception as e:
        print(f"Error loading PnL: {e}")
        return render_template('pnl.html', error=str(e), active_page='pnl')


@app.route('/api/portfolio/current')
def get_current_portfolio():
    """Get current portfolio state"""
    portfolio, analyses, market_data = load_portfolio_data()
    
    if portfolio is None:
        return jsonify({'error': 'Could not load portfolio data'}), 500
    
    total_value = sum(asset.value for asset in portfolio.values())
    
    today_summary = None
    if analyses and EVALUATOR_AVAILABLE:
        try:
             # Try AI first
             today_summary = get_ai_summary(portfolio, analyses)
             
             if not today_summary:
                 temp_evaluator = PortfolioEvaluator(portfolio)
                 today_summary = temp_evaluator.generate_executive_summary(analyses)
        except Exception as e:
            print(f"Error generating summary: {e}")

    # Calculate Rebalancing Plan
    rebalancing_plan = []
    if REBALANCER_AVAILABLE and EVALUATOR_AVAILABLE:
        try:
            # We need risk-adjusted limits from Evaluator
            # Since we didn't keep the evaluator instance, let's create one or get limits
            if not today_summary: # If summary failed, try init evaluator again
                 temp_evaluator = PortfolioEvaluator(portfolio)
            else:
                 # Re-init evaluator just to be sure we have clean state or use existing
                 temp_evaluator = PortfolioEvaluator(portfolio)
            
            # Extract risk limits - assuming this method exists or we can calculate them
            # Looking at PortfolioEvaluator, it likely has '_calculate_risk_adjusted_limits' or similar
            # If not exposed publicly, we might need to modify it or just trust the rebalancer's default
            
            # Actually, let's check PortfolioEvaluator for public methods for limits
            # For now, we will pass None for limits and let rebalancer use standard targets
            # UNLESS we find safe_exposure_limits
            
            risk_limits = None
            # Check if we can get limits
            # temp_evaluator._calculate_risk_metrics() usually sets internal state
            
            rebalancer = PortfolioRebalancer()
            # Use market data for prices of assets we don't own if needed (though portfolio has current prices)
            
            actions = rebalancer.calculate_rebalancing(
                portfolio, 
                rebalance_threshold=1.0, # Tighter threshold for "exact" figures
                market_data=market_data
            )
            
            # Format for API
            for action in actions:
                if action.action == "HOLD": continue
                
                rebalancing_plan.append({
                    'symbol': action.symbol,
                    'action': action.action,
                    'amount_diff': action.amount_diff,
                    'value_diff': action.value_diff, # Positive for Buy, Negative for Sell
                    'target_allocation': action.target_allocation,
                    'current_allocation': action.current_allocation,
                    'reason': f"Target: {action.target_allocation}%"
                })
                
        except Exception as e:
            print(f"Error calculating rebalancing: {e}")

    # Calculate Unrealized P&L
    unrealized_pnl = {}
    total_unrealized_pnl = 0.0
    try:
        from transaction_tracker import TransactionTracker
        tracker = TransactionTracker()
        # Calculate P&L for all assets. 
        # Note: calculate_unrealized_pnl_with_prices might fail if API limit reached, 
        # so we fallback to manual calculation if needed or just use what we have.
        # Since we already have current prices in 'portfolio' objects, we can optimize.
        
        # We'll use the tracker to get cost basis, then calculate against current portfolio values
        # This is more efficient than re-fetching prices
        cost_basis_data = tracker.get_portfolio_cost_basis()
        
        for symbol, asset in portfolio.items():
            if symbol in cost_basis_data:
                # Calculate P&L: Current Value - Cost Basis
                # Note: This assumes cost_basis_data matches current holdings. 
                # If transactions are missing, this might be off.
                basis = cost_basis_data[symbol].get('total_cost_basis', 0.0)
                if basis is None: basis = 0.0

                # Scale basis to current holding amount if needed (e.g. if we sold some)
                # But get_portfolio_cost_basis should return remaining cost basis for open lots.
                
                # Let's verify against asset.value which is (amount * current_price)
                pnl = asset.value - basis
                pnl_percent = (pnl / basis * 100) if basis > 0 else 0
                
                unrealized_pnl[symbol] = {
                    'pnl': pnl,
                    'pnl_percent': pnl_percent,
                    'cost_basis': basis
                }
                total_unrealized_pnl += pnl
            else:
                unrealized_pnl[symbol] = {'pnl': 0, 'pnl_percent': 0, 'cost_basis': 0}

    except Exception as e:
        print(f"Error calculating P&L: {e}")
        unrealized_pnl = {s: {'pnl': 0, 'pnl_percent': 0} for s in portfolio}
    
    return jsonify({
        'portfolio': [asset_to_dict(asset) for asset in portfolio.values()],
        'analyses': [analysis_to_dict(analysis) for analysis in analyses] if analyses else [],
        'executive_summary': today_summary,
        'unrealized_pnl': unrealized_pnl,
        'total_unrealized_pnl': total_unrealized_pnl,
        'rebalancing_plan': rebalancing_plan,
        'total_value': total_value,
        'asset_count': len(portfolio),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/portfolio/sync-transactions', methods=['POST'])
def sync_transactions():
    """Trigger transaction import from blockchain"""
    if not IMPORTER_AVAILABLE:
        return jsonify({'error': 'Transaction importer module not found'}), 501
    
    try:
        # Clear cache to ensure fresh data after import
        global _portfolio_cache, _analyses_cache, _market_data_cache, _cache_timestamp
        _portfolio_cache = None
        _analyses_cache = None
        _market_data_cache = None
        _cache_timestamp = None
        if os.path.exists(CACHE_FILE):
            try:
                os.remove(CACHE_FILE)
            except:
                pass

        # Run import
        stats = import_from_wallet_config(limit_per_address=50) # Limit to 50 for speed
        
        return jsonify({
            'status': 'success',
            'message': 'Transaction import completed',
            'stats': stats
        })
    except Exception as e:
        print(f"Import error: {e}")
        return jsonify({'error': str(e)}), 500

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



@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat with the AI Advisor about the portfolio"""
    if not AI_ADVISOR_AVAILABLE:
        return jsonify({'error': 'AI Advisor not available'}), 503
        
    try:
        data = request.json
        user_message = data.get('message', '')
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
            
        # Load portfolio context
        portfolio, analyses, market_data = load_portfolio_data()
        
        # Load config to get API Key (reused logic)
        config_path = 'wallet_config.json'
        api_key = None
        model_name = "gemini-3-pro-preview" 
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                try:
                    config = json.load(f)
                    api_key = config.get('gemini_api_key')
                    model_name = config.get('gemini_model', "gemini-3-pro-preview")
                except:
                    pass
        
        if not api_key:
            return jsonify({'response': "Please configure your Gemini API Key in Settings first."})

        # Initialize advisor
        advisor = AIAdvisor(api_key=api_key, model_name=model_name)
        
        # Prepare context (reusing logic from get_ai_summary, improved with analysis_map)
        analysis_map = {a.symbol: a for a in analyses} if analyses else {}
        total_24h_pnl = 0
        for s, a in portfolio.items():
            if s in analysis_map and analysis_map[s].price_change_24h:
                pct = analysis_map[s].price_change_24h
                val_yesterday = a.value / (1 + pct/100)
                total_24h_pnl += (a.value - val_yesterday)

        portfolio_context = {
            'total_value': sum(a.value for a in portfolio.values()),
            'total_pnl': total_24h_pnl,
            'assets': [
                {
                    'symbol': s,
                    'value': a.value,
                    'allocation': a.allocation_percent,
                    'change_24h': analysis_map[s].price_change_24h if s in analysis_map else 0.0,
                    'price': a.current_price
                }
                for s, a in portfolio.items()
            ]
        }
        
        market_analysis_context = [
            {
                'symbol': a.symbol,
                'trend': a.trend,
                'rsi': a.technical_indicators.rsi if a.technical_indicators else None,
                'action': a.suggested_action
            }
            for a in analyses
        ] if analyses else []

        # Get response
        response_text = advisor.get_chat_response(user_message, portfolio_context, market_analysis_context)
        
        return jsonify({'response': response_text})
        
    except Exception as e:
        print(f"Chat error: {e}")
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
    
    app.run(debug=False, host='127.0.0.1', port=5000)

