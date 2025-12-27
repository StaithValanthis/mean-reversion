"""Tests for slippage model."""
import pytest

from src.execution.slippage import SlippageModel


def test_slippage_model():
    """Test slippage application."""
    slippage = SlippageModel(slippage_bps=10.0)  # 10 bps = 0.1%

    price = 100.0
    quantity = 1.0

    # Buy order: should execute at higher price
    buy_price = slippage.apply_slippage(price, "buy", quantity)
    assert buy_price > price
    assert abs(buy_price - price) / price < 0.001  # Approximately 0.1%

    # Sell order: should execute at lower price
    sell_price = slippage.apply_slippage(price, "sell", quantity)
    assert sell_price < price
    assert abs(price - sell_price) / price < 0.001  # Approximately 0.1%

