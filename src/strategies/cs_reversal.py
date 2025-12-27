"""Cross-sectional reversal strategy."""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from src.common.log import setup_logger
from src.common.math import quantile_cut
from src.data.candles import normalize_symbol
from src.common.time import timeframe_to_hours
from src.strategies.regime import RegimeDetector

logger = setup_logger(__name__)


class CrossSectionalReversalStrategy:
    """Cross-sectional short-term reversal strategy."""

    def __init__(
        self,
        quantile: float = 0.2,
        ret_lookback_hours: int = 24,
        timeframe: str = "1h",
        regime_detector: Optional[RegimeDetector] = None,
        regime_enabled: bool = True,
    ):
        """
        Initialize strategy.

        Args:
            quantile: Quantile for top/bottom selection (e.g., 0.2 = top/bottom 20%)
            ret_lookback_hours: Lookback in HOURS for return calculation (e.g., 24 = 24h return)
            timeframe: Candle timeframe used for the input data (e.g., '1h', '4h')
            regime_detector: Optional regime detector
            regime_enabled: Whether to apply regime gating
        """
        self.quantile = quantile
        self.ret_lookback_hours = ret_lookback_hours
        self.timeframe = timeframe
        self.regime_detector = regime_detector or RegimeDetector()
        self.regime_enabled = regime_enabled

    def calculate_returns(
        self,
        df: pd.DataFrame,
        lookback_hours: int,
    ) -> pd.Series:
        """
        Calculate returns over lookback period.

        Args:
            df: DataFrame with timestamp index and 'close' column
            lookback_hours: Number of hours to look back

        Returns:
            Series of returns
        """
        tf_hours = timeframe_to_hours(self.timeframe)
        lookback_bars = max(1, int(round(lookback_hours / tf_hours)))

        if len(df) < lookback_bars + 1:
            return pd.Series(dtype=float)

        # ret_24h style: close / close.shift(N bars) - 1
        returns = df["close"] / df["close"].shift(lookback_bars) - 1
        return returns

    def generate_signals(
        self,
        universe_data: Dict[str, pd.DataFrame],
        regime_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> Dict[str, float]:
        """
        Generate trading signals for universe.

        Args:
            universe_data: Dictionary of {symbol: DataFrame} with OHLCV data
            regime_data: Optional regime data (e.g., BTC data for regime detection)

        Returns:
            Dictionary of {symbol: target_weight} where weight is in [-1, 1]
                (negative = short, positive = long)
        """
        signals = {}

        # Calculate returns for each symbol
        symbol_returns = {}
        valid_symbols = []

        for symbol, df in universe_data.items():
            df_sorted = df.sort_values("timestamp")
            returns = self.calculate_returns(df_sorted, self.ret_lookback_hours)

            if len(returns) > 0 and not pd.isna(returns.iloc[-1]):
                symbol_returns[symbol] = returns.iloc[-1]
                valid_symbols.append(symbol)

        if len(valid_symbols) < 2:
            logger.warning("Not enough symbols with valid returns")
            return signals

        # Convert to arrays for ranking
        symbols_array = np.array(valid_symbols)
        returns_array = np.array([symbol_returns[s] for s in valid_symbols])

        # Rank and select top/bottom quantiles
        bottom_mask, middle_mask, top_mask = quantile_cut(returns_array, self.quantile)

        # Assign signals: long losers (bottom), short winners (top)
        long_symbols = symbols_array[bottom_mask]
        short_symbols = symbols_array[top_mask]

        logger.info(
            f"Signal generation: {len(long_symbols)} longs, {len(short_symbols)} shorts"
        )

        # Calculate regime scale factor if enabled
        regime_scale = 1.0
        if self.regime_enabled and regime_data:
            # Use first available symbol for regime detection (usually BTC)
            for regime_symbol, regime_df in regime_data.items():
                if len(regime_df) > 0:
                    regime_info = self.regime_detector.detect_regime(regime_df)
                    regime_scale = regime_info.get("scale_factor", 1.0)
                    logger.info(
                        f"Regime detected: {regime_info['regime']}, scale_factor={regime_scale}"
                    )
                    break

        # Assign weights (will be normalized later)
        for symbol in long_symbols:
            signals[symbol] = 1.0 * regime_scale

        for symbol in short_symbols:
            signals[symbol] = -1.0 * regime_scale

        return signals

