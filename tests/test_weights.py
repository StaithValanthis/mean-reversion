"""Tests for portfolio weight calculation."""
import numpy as np
import pandas as pd
import pytest

from src.portfolio.weights import calculate_volatility_target_weights


def test_volatility_target_weights():
    """Test volatility targeting and dollar neutrality."""
    # Create mock signals
    signals = {
        "SYMBOL1": 1.0,  # Long
        "SYMBOL2": 1.0,  # Long
        "SYMBOL3": -1.0,  # Short
        "SYMBOL4": -1.0,  # Short
    }

    # Create mock universe data with different volatilities
    n_bars = 100
    universe_data = {}

    for symbol in signals.keys():
        # Create price series with different volatilities
        base_price = 100.0
        vol = 0.02 if "1" in symbol or "3" in symbol else 0.01
        returns = np.random.randn(n_bars) * vol
        prices = base_price * np.cumprod(1 + returns)

        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n_bars, freq="1h"),
            "open": prices,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.rand(n_bars) * 1000,
        })

        universe_data[symbol] = df

    # Calculate weights
    weights = calculate_volatility_target_weights(
        signals,
        universe_data,
        vol_window=72,
        target_gross_exposure=1.0,
        per_symbol_cap=0.1,
        dollar_neutrality_tolerance=0.05,
    )

    # Check that we have weights
    assert len(weights) > 0

    # Check dollar neutrality (approximate)
    long_notional = sum(w for w in weights.values() if w > 0)
    short_notional = abs(sum(w for w in weights.values() if w < 0))

    if long_notional > 0 and short_notional > 0:
        imbalance = abs(long_notional - short_notional) / max(long_notional, short_notional)
        assert imbalance < 0.10  # Should be within 10% (tolerance + some margin)


def test_per_symbol_cap():
    """Test per-symbol cap enforcement."""
    signals = {"SYMBOL1": 1.0}

    universe_data = {}
    n_bars = 100
    base_price = 100.0
    returns = np.random.randn(n_bars) * 0.01
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n_bars, freq="1h"),
        "open": prices,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": np.random.rand(n_bars) * 1000,
    })
    universe_data["SYMBOL1"] = df

    weights = calculate_volatility_target_weights(
        signals,
        universe_data,
        vol_window=72,
        target_gross_exposure=1.0,
        per_symbol_cap=0.05,  # 5% cap
        dollar_neutrality_tolerance=0.02,
    )

    if "SYMBOL1" in weights:
        assert abs(weights["SYMBOL1"]) <= 0.05

