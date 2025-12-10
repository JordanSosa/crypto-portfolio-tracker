"""
Risk Management Module
Calculates position sizing, stop-losses, correlation, and risk-adjusted limits
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math

class RiskTolerance(Enum):
    CONSERVATIVE = "conservative"  # Lower risk, smaller positions
    MODERATE = "moderate"         # Balanced risk
    AGGRESSIVE = "aggressive"     # Higher risk tolerance


@dataclass
class RiskMetrics:
    """Risk metrics for a single asset"""
    symbol: str
    volatility_annualized: float  # Annualized volatility as percentage
    atr: Optional[float]  # Average True Range
    risk_score: float  # Calculated risk score (0-100)
    max_allocation_pct: float  # Maximum recommended allocation percentage
    suggested_position_size: float  # Suggested position size in portfolio value


@dataclass
class CorrelationMatrix:
    """Correlation data between assets"""
    correlations: Dict[Tuple[str, str], float]  # (asset1, asset2) -> correlation
    high_correlations: List[Tuple[str, str, float]]  # Pairs with correlation > 0.7
    diversification_score: float  # Portfolio diversification score (0-100)


@dataclass
class StopLossSuggestion:
    """Stop-loss suggestion for long-term strategy"""
    symbol: str
    current_price: float
    entry_price: Optional[float]  # Average entry price if available
    gain_pct: Optional[float]  # Current gain percentage
    emergency_stop: Optional[float]  # Wide emergency stop (50-70% below entry)
    trailing_stop: Optional[float]  # Trailing stop for profit protection
    trailing_stop_pct: Optional[float]  # Percentage below peak
    recommendation: str  # "HOLD", "SET_TRAILING", "PROTECT_PROFITS"


@dataclass
class PortfolioRiskAnalysis:
    """Overall portfolio risk analysis"""
    total_risk_score: float
    concentration_risk: float  # Risk from over-concentration
    correlation_risk: float  # Risk from high correlations
    diversification_score: float
    risk_adjusted_allocations: Dict[str, float]  # Suggested max allocations
    warnings: List[str]  # Risk warnings


class RiskManager:
    """Manages risk calculations for long-term investment strategy"""
    
    def __init__(self, risk_tolerance: RiskTolerance = RiskTolerance.MODERATE):
        """
        Initialize risk manager
        
        Args:
            risk_tolerance: User's risk tolerance level
        """
        self.risk_tolerance = risk_tolerance
        
        # Risk tolerance multipliers for position sizing
        self.risk_multipliers = {
            RiskTolerance.CONSERVATIVE: 0.5,  # More conservative positions
            RiskTolerance.MODERATE: 1.0,      # Standard positions
            RiskTolerance.AGGRESSIVE: 1.5     # Larger positions (but still risk-adjusted)
        }
    
    def calculate_risk_metrics(
        self,
        symbol: str,
        prices: List[float],
        current_price: float
    ) -> Optional[RiskMetrics]:
        """
        Calculate risk metrics for an asset
        
        Args:
            symbol: Asset symbol
            prices: Historical prices (oldest to newest)
            current_price: Current price
            
        Returns:
            RiskMetrics object or None if insufficient data
        """
        from technical_indicators import TechnicalIndicators
        
        # Calculate volatility
        volatility = TechnicalIndicators.calculate_volatility_annualized(prices, period=30)
        if volatility is None:
            # Fallback to shorter period
            volatility = TechnicalIndicators.calculate_volatility_annualized(prices, period=14)
        
        if volatility is None:
            return None
        
        # Calculate ATR
        atr = TechnicalIndicators.calculate_atr(prices, period=14)
        
        # Calculate risk score (0-100, higher = riskier)
        # Based on volatility: 0-20% = low risk, 20-40% = medium, 40%+ = high
        risk_score = min(100, volatility * 2)  # Scale volatility to 0-100
        
        # Calculate max allocation based on risk
        # Formula: max_allocation = base_limit / (1 + risk_score/50)
        # Conservative: base_limit = 30%, Moderate: 50%, Aggressive: 70%
        base_limits = {
            RiskTolerance.CONSERVATIVE: 30.0,
            RiskTolerance.MODERATE: 50.0,
            RiskTolerance.AGGRESSIVE: 70.0
        }
        base_limit = base_limits[self.risk_tolerance]
        max_allocation = base_limit / (1 + risk_score / 50)
        
        # Ensure minimum allocation for diversification
        max_allocation = max(5.0, min(max_allocation, base_limit))
        
        return RiskMetrics(
            symbol=symbol,
            volatility_annualized=volatility,
            atr=atr,
            risk_score=risk_score,
            max_allocation_pct=max_allocation,
            suggested_position_size=0.0  # Will be calculated with portfolio context
        )
    
    def calculate_correlation_matrix(
        self,
        asset_prices: Dict[str, List[float]],
        period: int = 30
    ) -> CorrelationMatrix:
        """
        Calculate correlation matrix for all asset pairs
        
        Args:
            asset_prices: Dictionary mapping symbols to price lists
            period: Period for correlation calculation
            
        Returns:
            CorrelationMatrix object
        """
        from technical_indicators import TechnicalIndicators
        
        correlations = {}
        high_correlations = []
        symbols = list(asset_prices.keys())
        
        # Calculate correlations for all pairs
        for i, symbol1 in enumerate(symbols):
            for symbol2 in symbols[i+1:]:
                prices1 = asset_prices[symbol1]
                prices2 = asset_prices[symbol2]
                
                # Ensure same length (use minimum length)
                min_len = min(len(prices1), len(prices2))
                if min_len < period:
                    continue
                
                corr = TechnicalIndicators.calculate_correlation(
                    prices1[-min_len:],
                    prices2[-min_len:],
                    period=period
                )
                
                if corr is not None:
                    correlations[(symbol1, symbol2)] = corr
                    if abs(corr) > 0.7:  # High correlation threshold
                        high_correlations.append((symbol1, symbol2, corr))
        
        # Calculate diversification score
        # Lower average correlation = better diversification
        if correlations:
            avg_correlation = sum(abs(c) for c in correlations.values()) / len(correlations)
            diversification_score = max(0, 100 * (1 - avg_correlation))
        else:
            diversification_score = 50.0  # Default if no correlations
        
        return CorrelationMatrix(
            correlations=correlations,
            high_correlations=high_correlations,
            diversification_score=diversification_score
        )
    
    def suggest_stop_loss(
        self,
        symbol: str,
        current_price: float,
        entry_price: Optional[float] = None,
        prices: Optional[List[float]] = None,
        peak_price: Optional[float] = None
    ) -> StopLossSuggestion:
        """
        Suggest stop-loss levels for long-term strategy
        
        For long-term: Wide emergency stops, trailing stops for profit protection
        
        Args:
            symbol: Asset symbol
            current_price: Current price
            entry_price: Average entry price (if available)
            prices: Historical prices for ATR calculation
            peak_price: Peak price reached (for trailing stop)
            
        Returns:
            StopLossSuggestion object
        """
        from technical_indicators import TechnicalIndicators
        
        # Calculate gain if we have entry price
        gain_pct = None
        if entry_price and entry_price > 0:
            gain_pct = ((current_price - entry_price) / entry_price) * 100
        
        # Emergency stop-loss: 60% below entry (only for extreme scenarios)
        emergency_stop = None
        if entry_price and entry_price > 0:
            emergency_stop = entry_price * 0.4  # 60% below entry
        
        # Trailing stop for profit protection (only if significant gains)
        trailing_stop = None
        trailing_stop_pct = None
        recommendation = "HOLD"
        
        if gain_pct and gain_pct > 100:  # Only if >100% gain
            # Use peak price or current price
            reference_price = peak_price if peak_price and peak_price > current_price else current_price
            
            # Calculate ATR-based trailing stop
            if prices:
                atr = TechnicalIndicators.calculate_atr(prices, period=14)
                if atr:
                    # Trailing stop: 2.5x ATR below peak (wide for long-term)
                    trailing_stop = reference_price - (2.5 * atr)
                    trailing_stop_pct = ((reference_price - trailing_stop) / reference_price) * 100
                    
                    if current_price <= trailing_stop:
                        recommendation = "PROTECT_PROFITS"
                    elif gain_pct > 200:
                        recommendation = "SET_TRAILING"
            else:
                # Fallback: 30% trailing stop
                trailing_stop = reference_price * 0.7
                trailing_stop_pct = 30.0
                if gain_pct > 200:
                    recommendation = "SET_TRAILING"
        
        return StopLossSuggestion(
            symbol=symbol,
            current_price=current_price,
            entry_price=entry_price,
            gain_pct=gain_pct,
            emergency_stop=emergency_stop,
            trailing_stop=trailing_stop,
            trailing_stop_pct=trailing_stop_pct,
            recommendation=recommendation
        )
    
    def analyze_portfolio_risk(
        self,
        portfolio: Dict,  # Dict[str, Asset] - using Dict to avoid circular import
        asset_prices: Dict[str, List[float]],
        risk_metrics: Dict[str, RiskMetrics]
    ) -> PortfolioRiskAnalysis:
        """
        Analyze overall portfolio risk
        
        Args:
            portfolio: Dictionary of Asset objects
            asset_prices: Historical prices for all assets
            risk_metrics: Risk metrics for each asset
            
        Returns:
            PortfolioRiskAnalysis object
        """
        warnings = []
        
        # Calculate correlation matrix
        correlation_matrix = self.calculate_correlation_matrix(asset_prices)
        
        # Check for high correlations
        if correlation_matrix.high_correlations:
            for symbol1, symbol2, corr in correlation_matrix.high_correlations:
                warnings.append(
                    f"High correlation ({corr:.2f}) between {symbol1} and {symbol2}. "
                    f"Consider reducing one to improve diversification."
                )
        
        # Check for over-allocation relative to risk
        concentration_risk = 0.0
        risk_adjusted_allocations = {}
        
        for symbol, asset in portfolio.items():
            if symbol in risk_metrics:
                risk_metric = risk_metrics[symbol]
                current_allocation = asset.allocation_percent
                max_allocation = risk_metric.max_allocation_pct
                
                risk_adjusted_allocations[symbol] = max_allocation
                
                if current_allocation > max_allocation:
                    excess = current_allocation - max_allocation
                    concentration_risk += excess
                    warnings.append(
                        f"{symbol}: Allocation ({current_allocation:.1f}%) exceeds "
                        f"risk-adjusted limit ({max_allocation:.1f}%). "
                        f"Consider rebalancing when profitable."
                    )
        
        # Calculate total risk score (weighted average)
        total_value = sum(asset.value for asset in portfolio.values())
        total_risk_score = 0.0
        
        for symbol, asset in portfolio.items():
            if symbol in risk_metrics:
                weight = asset.value / total_value if total_value > 0 else 0
                total_risk_score += risk_metrics[symbol].risk_score * weight
        
        return PortfolioRiskAnalysis(
            total_risk_score=total_risk_score,
            concentration_risk=concentration_risk,
            correlation_risk=len(correlation_matrix.high_correlations) * 10,  # Simple scoring
            diversification_score=correlation_matrix.diversification_score,
            risk_adjusted_allocations=risk_adjusted_allocations,
            warnings=warnings
        )


