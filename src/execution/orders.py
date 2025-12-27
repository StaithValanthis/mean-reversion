"""Order execution logic."""
import time
from typing import Dict, List, Optional

from src.common.log import setup_logger
from src.exchange.bybit import BybitExchange

logger = setup_logger(__name__)


class OrderExecutor:
    """Handle order execution with retries and timeouts."""

    def __init__(
        self,
        exchange: BybitExchange,
        post_only: bool = True,
        timeout_sec: int = 60,
        max_retries: int = 3,
    ):
        """
        Initialize order executor.

        Args:
            exchange: Exchange client
            post_only: Use post-only orders (maker)
            timeout_sec: Order timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.exchange = exchange
        self.post_only = post_only
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries

    def execute_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        client_order_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Execute a limit order with timeout and retry logic.

        Args:
            symbol: Symbol (ccxt format)
            side: 'buy' or 'sell'
            quantity: Order quantity
            price: Limit price
            client_order_id: Optional client order ID

        Returns:
            Order result dictionary, or None if failed
        """
        for attempt in range(self.max_retries):
            try:
                # Place order
                order = self.exchange.place_order(
                    symbol=symbol,
                    side=side,
                    amount=quantity,
                    price=price,
                    order_type="limit",
                    post_only=self.post_only,
                    client_order_id=client_order_id,
                )

                order_id = order.get("id")
                if not order_id:
                    logger.error(f"Order placed but no ID returned: {order}")
                    continue

                # Wait and check if filled
                start_time = time.time()
                while time.time() - start_time < self.timeout_sec:
                    order_status = self.exchange.get_order(order_id, symbol)

                    status = order_status.get("status")
                    if status == "closed" or status == "filled":
                        logger.info(f"Order {order_id} filled")
                        return order_status

                    if status == "canceled":
                        logger.warning(f"Order {order_id} was canceled")
                        break

                    time.sleep(2)  # Check every 2 seconds

                # Timeout: cancel order
                logger.warning(f"Order {order_id} timeout, cancelling")
                try:
                    self.exchange.cancel_order(order_id, symbol)
                except Exception as e:
                    logger.error(f"Error cancelling order {order_id}: {e}")

                # Retry with slightly adjusted price
                if attempt < self.max_retries - 1:
                    adjustment = 0.0001 if side == "buy" else -0.0001  # 1 bps
                    price = price * (1 + adjustment)
                    logger.info(f"Retrying order with adjusted price: {price}")

            except Exception as e:
                logger.error(f"Error executing order (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    return None

        return None

