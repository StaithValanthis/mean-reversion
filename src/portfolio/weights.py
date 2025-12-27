"""Portfolio weight calculation with vol targeting and dollar neutrality."""
from typing import Dict

import numpy as np
import pandas as pd

from src.common.log import setup_logger
from src.common.math import rolling_volatility

logger = setup_logger(__name__)


def calculate_volatility_target_weights(
    signals: Dict[str, float],
    universe_data: Dict[str, pd.DataFrame],
    vol_window: int = 72,
    target_gross_exposure: float = 1.0,
    per_symbol_cap: float = 0.05,
    dollar_neutrality_tolerance: float = 0.02,
) -> Dict[str, float]:
    """
    Calculate portfolio weights with volatility targeting and dollar neutrality.

    Args:
        signals: Dictionary of {symbol: raw_signal} (-1 to 1)
        universe_data: Dictionary of {symbol: DataFrame} with OHLCV data
        vol_window: Window for volatility calculation
        target_gross_exposure: Target gross exposure per side (e.g., 1.0 = 100% of equity)
        per_symbol_cap: Maximum weight per symbol (e.g., 0.05 = 5% of equity)
        dollar_neutrality_tolerance: Tolerance for dollar neutrality

    Returns:
        Dictionary of {symbol: target_weight} (normalized to notional)
    """
    if not signals:
        return {}

    # Calculate returns and volatility for each symbol
    symbol_vols = {}
    symbol_prices = {}

    for symbol, signal in signals.items():
        if symbol not in universe_data:
            continue

        df = universe_data[symbol].sort_values("timestamp")
        if len(df) < vol_window + 1:
            continue

        # Calculate returns
        returns = df["close"].pct_change().dropna()
        if len(returns) < vol_window:
            continue

        # Calculate volatility
        vol = rolling_volatility(returns.values, vol_window)
        if len(vol) > 0 and not np.isnan(vol[-1]):
            symbol_vols[symbol] = vol[-1]
            symbol_prices[symbol] = df["close"].iloc[-1]

    if not symbol_vols:
        logger.warning("No symbols with valid volatility data")
        return {}

    # Separate long and short signals
    long_signals = {s: v for s, v in signals.items() if v > 0 and s in symbol_vols}
    short_signals = {s: -v for s, v in signals.items() if v < 0 and s in symbol_vols}

    # Calculate inverse volatility weights
    def calculate_side_weights(side_signals: Dict[str, float]) -> Dict[str, float]:
        if not side_signals:
            return {}

        symbols = list(side_signals.keys())
        vols = np.array([symbol_vols[s] for s in symbols])
        # Inverse volatility (avoid division by zero)
        inv_vols = np.divide(1.0, vols, out=np.zeros_like(vols), where=vols!=0)
        inv_vols = np.nan_to_num(inv_vols, nan=0.0, posinf=0.0, neginf=0.0)

        # Normalize to sum to target_gross_exposure
        total_inv_vol = np.sum(inv_vols)
        if total_inv_vol == 0:
            return {}

        weights = {}
        for i, symbol in enumerate(symbols):
            weight = (inv_vols[i] / total_inv_vol) * target_gross_exposure

            # Apply per-symbol cap
            weight = min(weight, per_symbol_cap)

            weights[symbol] = weight

        return weights

    long_weights = calculate_side_weights(long_signals)
    short_weights = calculate_side_weights(short_signals)

    # Apply per-symbol cap to ensure not exceeded
    all_symbols = set(long_weights.keys()) | set(short_weights.keys())
    for symbol in all_symbols:
        total_weight = abs(long_weights.get(symbol, 0)) + abs(short_weights.get(symbol, 0))
        if total_weight > per_symbol_cap:
            # Scale down proportionally
            scale = per_symbol_cap / total_weight
            if symbol in long_weights:
                long_weights[symbol] *= scale
            if symbol in short_weights:
                short_weights[symbol] *= scale

    # Combine weights (long positive, short negative)
    final_weights = {}
    for symbol, weight in long_weights.items():
        final_weights[symbol] = weight
    for symbol, weight in short_weights.items():
        final_weights[symbol] = -weight

    # Check dollar neutrality
    long_notional = sum(w for w in final_weights.values() if w > 0)
    short_notional = abs(sum(w for w in final_weights.values() if w < 0))

    if long_notional > 0 and short_notional > 0:
        imbalance = abs(long_notional - short_notional) / max(long_notional, short_notional)
        if imbalance > dollar_neutrality_tolerance:
            logger.warning(
                f"Dollar neutrality imbalance: {imbalance:.2%} "
                f"(long={long_notional:.2%}, short={short_notional:.2%})"
            )
            # Normalize to achieve dollar neutrality
            avg_notional = (long_notional + short_notional) / 2
            scale_long = avg_notional / long_notional if long_notional > 0 else 1.0
            scale_short = avg_notional / short_notional if short_notional > 0 else 1.0

            for symbol in final_weights:
                if final_weights[symbol] > 0:
                    final_weights[symbol] *= scale_long
                else:
                    final_weights[symbol] *= scale_short

    logger.info(
        f"Weight calculation: {len(final_weights)} symbols, "
        f"long={sum(w for w in final_weights.values() if w > 0):.2%}, "
        f"short={abs(sum(w for w in final_weights.values() if w < 0)):.2%}"
    )

    return final_weights

