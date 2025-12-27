"""Regime detection for trend/range classification."""
from typing import Dict

import numpy as np
import pandas as pd

from src.common.log import setup_logger

logger = setup_logger(__name__)


def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
    """
    Calculate Exponential Moving Average.

    Args:
        prices: Price array
        period: EMA period

    Returns:
        EMA array
    """
    ema = np.full(len(prices), np.nan)
    if len(prices) < period:
        return ema

    multiplier = 2.0 / (period + 1)
    ema[period - 1] = np.mean(prices[:period])

    for i in range(period, len(prices)):
        ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1]

    return ema


def calculate_adx(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    Calculate Average Directional Index (ADX).

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ADX period

    Returns:
        ADX array
    """
    n = len(high)
    adx = np.full(n, np.nan)

    if n < period * 2:
        return adx

    # Calculate True Range (TR)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    # Calculate Directional Movement
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]

        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Smooth TR and DM using Wilder's smoothing
    atr = np.zeros(n)
    atr[period] = np.sum(tr[1 : period + 1])

    plus_di_smooth = np.zeros(n)
    minus_di_smooth = np.zeros(n)
    plus_di_smooth[period] = np.sum(plus_dm[1 : period + 1])
    minus_di_smooth[period] = np.sum(minus_dm[1 : period + 1])

    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
        plus_di_smooth[i] = (plus_di_smooth[i - 1] * (period - 1) + plus_dm[i]) / period
        minus_di_smooth[i] = (
            minus_di_smooth[i - 1] * (period - 1) + minus_dm[i]
        ) / period

    # Calculate DI+ and DI-
    plus_di = np.zeros(n)
    minus_di = np.zeros(n)

    for i in range(period, n):
        if atr[i] > 0:
            plus_di[i] = 100 * (plus_di_smooth[i] / atr[i])
            minus_di[i] = 100 * (minus_di_smooth[i] / atr[i])

    # Calculate DX
    dx = np.zeros(n)
    for i in range(period, n):
        di_sum = plus_di[i] + minus_di[i]
        if di_sum > 0:
            dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / di_sum

    # Calculate ADX (EMA of DX)
    adx_smooth = np.zeros(n)
    adx_smooth[period * 2 - 1] = np.mean(dx[period : period * 2])

    for i in range(period * 2, n):
        adx_smooth[i] = (adx_smooth[i - 1] * (period - 1) + dx[i]) / period

    adx[period * 2 - 1 :] = adx_smooth[period * 2 - 1 :]
    return adx


class RegimeDetector:
    """Detect market regime (trend vs range)."""

    def __init__(
        self,
        adx_period: int = 14,
        ema_period: int = 50,
        adx_threshold: float = 25.0,
        ema_slope_threshold: float = 0.0001,
    ):
        """
        Initialize regime detector.

        Args:
            adx_period: ADX calculation period
            ema_period: EMA period for trend detection
            adx_threshold: ADX threshold for strong trend
            ema_slope_threshold: EMA slope threshold
        """
        self.adx_period = adx_period
        self.ema_period = ema_period
        self.adx_threshold = adx_threshold
        self.ema_slope_threshold = ema_slope_threshold

    def detect_regime(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, float]:
        """
        Detect current regime.

        Args:
            df: DataFrame with columns [open, high, low, close, volume]

        Returns:
            Dictionary with regime metrics:
                - regime: 'trend' or 'range'
                - adx: Current ADX value
                - ema_slope: EMA slope (normalized)
                - scale_factor: Suggested scale factor (1.0 for range, <1.0 for trend)
        """
        if len(df) < max(self.adx_period * 2, self.ema_period):
            return {
                "regime": "unknown",
                "adx": 0.0,
                "ema_slope": 0.0,
                "scale_factor": 1.0,
            }

        close = df["close"].values
        high = df["high"].values
        low = df["low"].values

        # Calculate ADX
        adx = calculate_adx(high, low, close, self.adx_period)
        current_adx = adx[-1] if not np.isnan(adx[-1]) else 0.0

        # Calculate EMA and slope
        ema = calculate_ema(close, self.ema_period)
        if len(ema) >= 2 and not np.isnan(ema[-1]) and not np.isnan(ema[-2]):
            # Normalized slope (change / price)
            ema_slope = (ema[-1] - ema[-2]) / ema[-2]
        else:
            ema_slope = 0.0

        # Determine regime
        is_strong_trend = (
            current_adx > self.adx_threshold
            and abs(ema_slope) > self.ema_slope_threshold
        )

        regime = "trend" if is_strong_trend else "range"

        # Scale factor: reduce exposure in strong trends
        scale_factor = 0.25 if is_strong_trend else 1.0

        return {
            "regime": regime,
            "adx": current_adx,
            "ema_slope": ema_slope,
            "scale_factor": scale_factor,
        }

