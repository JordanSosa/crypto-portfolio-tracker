"""
Technical Indicators Calculator
Calculates RSI, MACD, Moving Averages, and other technical indicators
"""

from typing import List, Optional, Dict, Tuple
import math


class TechnicalIndicators:
    """Calculate various technical indicators from price history"""
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """
        Calculate Relative Strength Index (RSI)
        
        Args:
            prices: List of prices (most recent last)
            period: RSI period (default 14)
            
        Returns:
            RSI value (0-100) or None if insufficient data
        """
        if len(prices) < period + 1:
            return None
        
        # Calculate price changes
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        # Separate gains and losses
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        
        # Calculate average gain and loss
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100.0
        
        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> Optional[float]:
        """
        Calculate Simple Moving Average
        
        Args:
            prices: List of prices (most recent last)
            period: SMA period
            
        Returns:
            SMA value or None if insufficient data
        """
        if len(prices) < period:
            return None
        
        return sum(prices[-period:]) / period
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> Optional[float]:
        """
        Calculate Exponential Moving Average
        
        Args:
            prices: List of prices (most recent last)
            period: EMA period
            
        Returns:
            EMA value or None if insufficient data
        """
        if len(prices) < period:
            return None
        
        multiplier = 2 / (period + 1)
        
        # Start with SMA
        ema = sum(prices[:period]) / period
        
        # Calculate EMA for remaining prices
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    @staticmethod
    def calculate_macd(
        prices: List[float], 
        fast_period: int = 12, 
        slow_period: int = 26, 
        signal_period: int = 9
    ) -> Optional[Dict[str, float]]:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        
        This is a simplified version that calculates current MACD value.
        For proper signal line calculation, use calculate_macd_with_history().
        
        Args:
            prices: List of prices (most recent last)
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line EMA period (default 9)
            
        Returns:
            Dictionary with 'macd', 'signal', 'histogram' or None if insufficient data
        """
        if len(prices) < slow_period:
            return None
        
        # Calculate fast and slow EMAs
        fast_ema = TechnicalIndicators.calculate_ema(prices, fast_period)
        slow_ema = TechnicalIndicators.calculate_ema(prices, slow_period)
        
        if fast_ema is None or slow_ema is None:
            return None
        
        macd_line = fast_ema - slow_ema
        
        # For signal line, we need MACD values over time
        # Simplified: use recent price changes as proxy for MACD values
        # In production, you'd maintain a history of MACD values
        macd_values = [fast_ema - slow_ema]  # Simplified single value
        
        # Calculate signal line (EMA of MACD)
        # This is simplified - in practice you'd need MACD history
        signal_line = macd_line * 0.9  # Approximation
        
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    @staticmethod
    def calculate_macd_with_history(
        prices: List[float], 
        fast_period: int = 12, 
        slow_period: int = 26, 
        signal_period: int = 9
    ) -> Optional[Dict[str, float]]:
        """
        Calculate MACD with proper signal line using historical MACD values
        
        This method calculates MACD values over time and then calculates
        the signal line as an EMA of those MACD values.
        
        Args:
            prices: List of prices (most recent last)
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line EMA period (default 9)
            
        Returns:
            Dictionary with 'macd', 'signal', 'histogram' or None if insufficient data
        """
        if len(prices) < slow_period + signal_period:
            return None
        
        # Calculate EMAs for all periods to get MACD history
        # We need to calculate EMAs progressively to build MACD history
        macd_values = []
        
        # Start from the point where we have enough data for slow EMA
        start_idx = slow_period - 1
        
        for i in range(start_idx, len(prices)):
            # Get prices up to current point
            prices_up_to_i = prices[:i+1]
            
            # Calculate EMAs
            fast_ema = TechnicalIndicators.calculate_ema(prices_up_to_i, fast_period)
            slow_ema = TechnicalIndicators.calculate_ema(prices_up_to_i, slow_period)
            
            if fast_ema is not None and slow_ema is not None:
                macd_value = fast_ema - slow_ema
                macd_values.append(macd_value)
        
        if len(macd_values) < signal_period:
            return None
        
        # Current MACD value is the last one
        current_macd = macd_values[-1]
        
        # Calculate signal line as EMA of MACD values
        signal_line = TechnicalIndicators.calculate_ema(macd_values, signal_period)
        
        if signal_line is None:
            return None
        
        histogram = current_macd - signal_line
        
        return {
            'macd': current_macd,
            'signal': signal_line,
            'histogram': histogram
        }
    
    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float], 
        period: int = 20, 
        num_std: float = 2.0
    ) -> Optional[Dict[str, float]]:
        """
        Calculate Bollinger Bands
        
        Args:
            prices: List of prices (most recent last)
            period: Period for SMA and standard deviation
            num_std: Number of standard deviations for bands
            
        Returns:
            Dictionary with 'upper', 'middle', 'lower' bands or None
        """
        if len(prices) < period:
            return None
        
        sma = TechnicalIndicators.calculate_sma(prices, period)
        if sma is None:
            return None
        
        # Calculate standard deviation
        recent_prices = prices[-period:]
        variance = sum((p - sma) ** 2 for p in recent_prices) / period
        std_dev = math.sqrt(variance)
        
        upper_band = sma + (num_std * std_dev)
        lower_band = sma - (num_std * std_dev)
        
        return {
            'upper': upper_band,
            'middle': sma,
            'lower': lower_band
        }
    
    @staticmethod
    def get_price_position_in_bands(
        current_price: float, 
        bollinger_bands: Optional[Dict[str, float]]
    ) -> Optional[str]:
        """
        Determine where current price is relative to Bollinger Bands
        
        Returns:
            'above_upper', 'upper_half', 'lower_half', 'below_lower', or None
        """
        if bollinger_bands is None:
            return None
        
        upper = bollinger_bands['upper']
        middle = bollinger_bands['middle']
        lower = bollinger_bands['lower']
        
        if current_price > upper:
            return 'above_upper'
        elif current_price > middle:
            return 'upper_half'
        elif current_price > lower:
            return 'lower_half'
        else:
            return 'below_lower'
    
    @staticmethod
    def calculate_atr(
        prices: List[float], 
        period: int = 14,
        high_prices: Optional[List[float]] = None,
        low_prices: Optional[List[float]] = None
    ) -> Optional[float]:
        """
        Calculate Average True Range (ATR) for volatility measurement
        
        For long-term strategy: ATR helps determine position sizing and stop-loss levels
        
        Args:
            prices: List of closing prices (most recent last)
            period: ATR period (default 14)
            high_prices: Optional list of high prices (if available)
            low_prices: Optional list of low prices (if available)
            
        Returns:
            ATR value or None if insufficient data
        """
        if len(prices) < period + 1:
            return None
        
        # If we only have closing prices, use price changes as proxy
        # True ATR uses high-low ranges, but this approximation works for daily data
        true_ranges = []
        
        if high_prices and low_prices and len(high_prices) == len(prices) and len(low_prices) == len(prices):
            # Calculate true range with high/low data
            for i in range(1, len(prices)):
                tr1 = high_prices[i] - low_prices[i]  # Current high - low
                tr2 = abs(high_prices[i] - prices[i-1])  # Current high - previous close
                tr3 = abs(low_prices[i] - prices[i-1])   # Current low - previous close
                true_ranges.append(max(tr1, tr2, tr3))
        else:
            # Approximation using closing prices only
            for i in range(1, len(prices)):
                true_range = abs(prices[i] - prices[i-1])
                true_ranges.append(true_range)
        
        if len(true_ranges) < period:
            return None
        
        # Calculate ATR as SMA of true ranges
        recent_ranges = true_ranges[-period:]
        atr = sum(recent_ranges) / period
        
        return atr
    
    @staticmethod
    def calculate_correlation(
        prices1: List[float],
        prices2: List[float],
        period: Optional[int] = None
    ) -> Optional[float]:
        """
        Calculate correlation coefficient between two price series
        
        For long-term strategy: Identifies assets that move together (diversification risk)
        
        Args:
            prices1: First price series (most recent last)
            prices2: Second price series (most recent last, same length as prices1)
            period: Optional period for rolling correlation (None = use all data)
            
        Returns:
            Correlation coefficient (-1 to 1) or None if insufficient data
        """
        if len(prices1) != len(prices2):
            return None
        
        # Use specified period or all available data
        if period:
            if len(prices1) < period:
                return None
            prices1 = prices1[-period:]
            prices2 = prices2[-period:]
        
        if len(prices1) < 2:
            return None
        
        # Calculate returns (percentage changes)
        returns1 = [(prices1[i] - prices1[i-1]) / prices1[i-1] 
                    for i in range(1, len(prices1))]
        returns2 = [(prices2[i] - prices2[i-1]) / prices2[i-1] 
                    for i in range(1, len(prices2))]
        
        # Calculate means
        mean1 = sum(returns1) / len(returns1)
        mean2 = sum(returns2) / len(returns2)
        
        # Calculate covariance and standard deviations
        covariance = sum((returns1[i] - mean1) * (returns2[i] - mean2) 
                         for i in range(len(returns1))) / len(returns1)
        
        variance1 = sum((r - mean1) ** 2 for r in returns1) / len(returns1)
        variance2 = sum((r - mean2) ** 2 for r in returns2) / len(returns2)
        
        std1 = variance1 ** 0.5
        std2 = variance2 ** 0.5
        
        if std1 == 0 or std2 == 0:
            return None
        
        correlation = covariance / (std1 * std2)
        return correlation
    
    @staticmethod
    def calculate_volatility_annualized(
        prices: List[float],
        period: int = 30
    ) -> Optional[float]:
        """
        Calculate annualized volatility from price series
        
        For long-term strategy: Used for risk-adjusted position sizing
        
        Args:
            prices: List of prices (most recent last)
            period: Number of days to use for calculation
            
        Returns:
            Annualized volatility as percentage (e.g., 30.0 for 30%)
        """
        if len(prices) < period + 1:
            return None
        
        recent_prices = prices[-period-1:]
        
        # Calculate daily returns
        returns = []
        for i in range(1, len(recent_prices)):
            if recent_prices[i-1] > 0:
                daily_return = (recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]
                returns.append(daily_return)
        
        if len(returns) < 2:
            return None
        
        # Calculate standard deviation of daily returns
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5
        
        # Annualize (assuming 365 trading days)
        annualized_volatility = std_dev * (365 ** 0.5) * 100
        
        return annualized_volatility
    
    @staticmethod
    def fetch_historical_prices_from_coingecko(
        symbol: str, 
        days: int = 30
    ) -> Optional[List[float]]:
        """
        Fetch historical prices from CoinGecko for indicator calculations
        
        Note: This is a placeholder - you'll need to implement actual API call
        CoinGecko's /coins/{id}/market_chart endpoint can provide this data
        
        Args:
            symbol: Asset symbol
            days: Number of days of history needed
            
        Returns:
            List of prices (oldest first) or None
        """
        # TODO: Implement actual CoinGecko API call
        # Example endpoint: /coins/{id}/market_chart?vs_currency=aud&days=30
        return None

