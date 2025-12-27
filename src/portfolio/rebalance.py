"""Rebalancing logic."""
from typing import Dict, List, Tuple

import numpy as np

from src.common.log import setup_logger

logger = setup_logger(__name__)


def calculate_rebalance_orders(
    target_weights: Dict[str, float],
    current_positions: Dict[str, float],
    equity: float,
    prices: Dict[str, float],
) -> List[Tuple[str, str, float, float]]:
    """
    Calculate rebalance orders needed.

    Args:
        target_weights: Dictionary of {symbol: target_weight} (as fraction of equity)
        current_positions: Dictionary of {symbol: current_notional_position}
        equity: Current equity value
        prices: Dictionary of {symbol: current_price}

    Returns:
        List of (symbol, side, quantity, price) tuples
    """
    orders = []

    all_symbols = set(target_weights.keys()) | set(current_positions.keys())

    for symbol in all_symbols:
        target_weight = target_weights.get(symbol, 0.0)
        target_notional = target_weight * equity
        current_notional = current_positions.get(symbol, 0.0)

        if symbol not in prices:
            logger.warning(f"No price available for {symbol}, skipping")
            continue

        price = prices[symbol]
        if price <= 0:
            logger.warning(f"Invalid price for {symbol}: {price}")
            continue

        # Calculate target quantity
        target_quantity = target_notional / price
        current_quantity = current_notional / price if current_notional != 0 else 0.0

        # Calculate change needed
        quantity_change = target_quantity - current_quantity

        # Ignore small changes (less than 0.1% of equity)
        min_order_size = 0.001 * equity / price
        if abs(quantity_change) < min_order_size:
            continue

        side = "buy" if quantity_change > 0 else "sell"
        orders.append((symbol, side, abs(quantity_change), price))

    logger.info(f"Calculated {len(orders)} rebalance orders")
    return orders

