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

