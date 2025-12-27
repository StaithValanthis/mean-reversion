"""Tests for strategy modules."""
import numpy as np
import pandas as pd
import pytest

from src.strategies.cs_reversal import CrossSectionalReversalStrategy
from src.common.math import quantile_cut


def test_quantile_cut():
    """Test quantile cut function."""
    arr = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    bottom, middle, top = quantile_cut(arr, 0.2)

    assert np.sum(bottom) == 2  # Bottom 20% = 2 elements
    assert np.sum(middle) == 6  # Middle 60% = 6 elements
    assert np.sum(top) == 2  # Top 20% = 2 elements

    # Check that bottom has smallest values
    assert np.max(arr[bottom]) <= np.min(arr[middle])
    assert np.max(arr[middle]) <= np.min(arr[top])


def test_cs_reversal_strategy():
    """Test cross-sectional reversal strategy."""
    strategy = CrossSectionalReversalStrategy(
        quantile=0.2,
        ret_lookback_hours=24,
        regime_enabled=False,
    )

    # Create mock universe data
    n_symbols = 10
    n_bars = 100
    universe_data = {}

    for i in range(n_symbols):
        # Create price series with different returns
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

        universe_data[f"SYMBOL{i}"] = df

    # Generate signals
    signals = strategy.generate_signals(universe_data)

    # Check that we have signals
    assert len(signals) > 0

    # Check that signals are in expected range
    for symbol, signal in signals.items():
        assert -1.0 <= signal <= 1.0

