"""Bybit exchange wrapper using ccxt."""
import os
import time
from typing import Any, Dict, List, Optional

import ccxt
from dotenv import load_dotenv

from src.common.log import setup_logger

load_dotenv()

logger = setup_logger(__name__)


class BybitExchange:
    """Wrapper for Bybit exchange operations."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = True,
        rate_limit: int = 10,
        timeout: int = 30,
    ):
        """
        Initialize Bybit exchange client.

        Args:
            api_key: API key (or use env var)
            api_secret: API secret (or use env var)
            testnet: Use testnet
            rate_limit: Requests per second limit
            timeout: Request timeout in seconds
        """
        self.testnet = testnet
        self.api_key = api_key or os.getenv("BYBIT_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BYBIT_API_SECRET", "")

        # Initialize ccxt exchange
        exchange_options = {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "rateLimit": int(1000 / rate_limit),
            "timeout": timeout * 1000,
            "options": {
                "defaultType": "swap",  # USDT Perpetual
            },
        }

        if testnet:
            exchange_options["options"]["testnet"] = True

        self.exchange = ccxt.bybit(exchange_options)
        logger.info(f"Initialized Bybit client (testnet={testnet})")

    def get_markets(self) -> Dict[str, Any]:
        """
        Fetch all markets.

        Returns:
            Dictionary of market information
        """
        try:
            markets = self.exchange.load_markets(reload=True)
            logger.debug(f"Loaded {len(markets)} markets")
            return markets
        except Exception as e:
            logger.error(f"Error loading markets: {e}")
            raise

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get ticker for symbol.

        Args:
            symbol: Symbol (e.g., 'BTC/USDT:USDT')

        Returns:
            Ticker data
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            raise

    def get_tickers(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all tickers.

        Returns:
            Dictionary of tickers by symbol
        """
        try:
            tickers = self.exchange.fetch_tickers()
            return tickers
        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
            raise

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[List[Any]]:
        """
        Fetch OHLCV candles.

        Args:
            symbol: Symbol (e.g., 'BTC/USDT:USDT')
            timeframe: Timeframe (e.g., '1h', '4h', '1d')
            since: Timestamp in milliseconds
            limit: Number of candles to fetch

        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        try:
            candles = self.exchange.fetch_ohlcv(
                symbol, timeframe, since=since, limit=limit
            )
            return candles
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            raise

    def get_balance(self) -> Dict[str, Any]:
        """
        Get account balance.

        Returns:
            Balance information
        """
        try:
            balance = self.exchange.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            raise

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get open positions.

        Returns:
            List of position dictionaries
        """
        try:
            positions = self.exchange.fetch_positions()
            # Filter to only open positions
            open_positions = [p for p in positions if float(p.get("contracts", 0)) != 0]
            return open_positions
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            raise

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get open orders.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of open orders
        """
        try:
            orders = self.exchange.fetch_open_orders(symbol)
            return orders
        except Exception as e:
            logger.error(f"Error fetching open orders: {e}")
            raise

    def place_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "limit",
        reduce_only: bool = False,
        post_only: bool = False,
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place an order.

        Args:
            symbol: Symbol (e.g., 'BTC/USDT:USDT')
            side: 'buy' or 'sell'
            amount: Order amount
            price: Limit price (required for limit orders)
            order_type: 'limit' or 'market'
            reduce_only: Reduce-only flag
            post_only: Post-only flag (maker order)
            client_order_id: Custom client order ID

        Returns:
            Order information
        """
        try:
            params = {}
            if reduce_only:
                params["reduceOnly"] = True
            if post_only:
                params["postOnly"] = True
            if client_order_id:
                params["clientOrderId"] = client_order_id

            if order_type == "limit":
                if price is None:
                    raise ValueError("Price required for limit orders")
                order = self.exchange.create_limit_order(
                    symbol, side, amount, price, params=params
                )
            else:
                order = self.exchange.create_market_order(
                    symbol, side, amount, params=params
                )

            logger.info(
                f"Placed {order_type} {side} order: {symbol} {amount} @ {price}"
            )
            return order
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an order.

        Args:
            order_id: Order ID
            symbol: Symbol

        Returns:
            Cancellation result
        """
        try:
            result = self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Cancelled order {order_id} for {symbol}")
            return result
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            raise

    def cancel_all_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Cancel all open orders.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of cancelled orders
        """
        try:
            result = self.exchange.cancel_all_orders(symbol)
            logger.info(f"Cancelled all orders for {symbol or 'all symbols'}")
            return result
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            raise

    def get_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Get order status.

        Args:
            order_id: Order ID
            symbol: Symbol

        Returns:
            Order information
        """
        try:
            order = self.exchange.fetch_order(order_id, symbol)
            return order
        except Exception as e:
            logger.error(f"Error fetching order {order_id}: {e}")
            raise

    def close_position(self, symbol: str) -> Dict[str, Any]:
        """
        Close a position by placing an opposite market order.

        Args:
            symbol: Symbol

        Returns:
            Order result
        """
        try:
            positions = self.get_positions()
            position = next((p for p in positions if p["symbol"] == symbol), None)
            if not position:
                logger.warning(f"No open position for {symbol}")
                return {}

            contracts = float(position.get("contracts", 0))
            side = "sell" if contracts > 0 else "buy"
            amount = abs(contracts)

            if amount == 0:
                logger.warning(f"Position size is 0 for {symbol}")
                return {}

            # Market order to close
            order = self.place_order(
                symbol, side, amount, order_type="market", reduce_only=True
            )
            logger.info(f"Closed position for {symbol}: {side} {amount}")
            return order
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")
            raise

