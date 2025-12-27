"""Slippage models for backtesting."""
import numpy as np

from src.common.log import setup_logger

logger = setup_logger(__name__)


class SlippageModel:
    """Slippage model for backtesting."""

    def __init__(self, slippage_bps: float = 2.0):
        """
        Initialize slippage model.

        Args:
            slippage_bps: Slippage in basis points (e.g., 2.0 = 0.02%)
        """
        self.slippage_bps = slippage_bps

    def apply_slippage(
        self,
        price: float,
        side: str,
        quantity: float,
    ) -> float:
        """
        Apply slippage to execution price.

        Args:
            price: Intended execution price
            side: 'buy' or 'sell'
            quantity: Order quantity (not used in simple model, but available for volume-based models)

        Returns:
            Executed price with slippage
        """
        slippage_multiplier = self.slippage_bps / 10000.0

        if side == "buy":
            # Buy orders execute at higher price (slippage cost)
            executed_price = price * (1 + slippage_multiplier)
        else:
            # Sell orders execute at lower price (slippage cost)
            executed_price = price * (1 - slippage_multiplier)

        return executed_price

