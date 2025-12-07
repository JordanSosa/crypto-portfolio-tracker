"""
Portfolio Tracker Package
Cryptocurrency portfolio analysis and tracking tools
"""

__version__ = "1.0.0"

from .portfolio_evaluator import (
    PortfolioEvaluator,
    Asset,
    MarketAnalysis,
    Recommendation,
    load_portfolio_from_wallet
)

from .portfolio_rebalancer import (
    PortfolioRebalancer,
    RebalancingAction
)

from .portfolio_database import (
    PortfolioDatabase,
    PortfolioSnapshot
)

from .blockchain_balance_fetcher import BlockchainBalanceFetcher

from .technical_indicators import TechnicalIndicators

try:
    from .transaction_tracker import TransactionTracker
    from .transaction_models import (
        Transaction, TransactionType, CostBasisLot, RealizedPnL,
        UnrealizedPnL, AccountingMethod
    )
    TRANSACTION_TRACKING_AVAILABLE = True
except ImportError:
    TRANSACTION_TRACKING_AVAILABLE = False

__all__ = [
    'PortfolioEvaluator',
    'Asset',
    'MarketAnalysis',
    'Recommendation',
    'load_portfolio_from_wallet',
    'PortfolioRebalancer',
    'RebalancingAction',
    'PortfolioDatabase',
    'PortfolioSnapshot',
    'BlockchainBalanceFetcher',
    'TechnicalIndicators'
]

if TRANSACTION_TRACKING_AVAILABLE:
    __all__.extend([
        'TransactionTracker',
        'Transaction',
        'TransactionType',
        'CostBasisLot',
        'RealizedPnL',
        'UnrealizedPnL',
        'AccountingMethod'
    ])

