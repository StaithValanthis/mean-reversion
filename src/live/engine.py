"""Live trading engine."""
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import pandas as pd

from src.common.log import setup_logger
from src.common.time import next_rebalance_time, utc_now
from src.data.candles import download_candles, normalize_symbol
from src.data.storage import DataStorage
from src.data.universe import select_universe
from src.exchange.bybit import BybitExchange
from src.exchange.fees import FeeCalculator
from src.execution.orders import OrderExecutor
from src.execution.slippage import SlippageModel
from src.portfolio.weights import calculate_volatility_target_weights
from src.portfolio.rebalance import calculate_rebalance_orders
from src.risk.killswitch import KillSwitch
from src.risk.limits import RiskLimits
from src.strategies.cs_reversal import CrossSectionalReversalStrategy
from src.strategies.regime import RegimeDetector

logger = setup_logger(__name__)


class LiveTradingEngine:
    """Live trading engine."""

    def __init__(
        self,
        config: Dict,
        exchange: BybitExchange,
        storage: DataStorage,
        strategy: CrossSectionalReversalStrategy,
        order_executor: OrderExecutor,
        fee_calculator: FeeCalculator,
        risk_limits: RiskLimits,
        kill_switch: KillSwitch,
        paper_mode: bool = True,
    ):
        """
        Initialize live trading engine.

        Args:
            config: Configuration dictionary
            exchange: Exchange client
            storage: Data storage
            strategy: Strategy instance
            order_executor: Order executor
            fee_calculator: Fee calculator
            risk_limits: Risk limits checker
            kill_switch: Kill switch
            paper_mode: If True, simulate orders (paper trading)
        """
        self.config = config
        self.exchange = exchange
        self.storage = storage
        self.strategy = strategy
        self.order_executor = order_executor
        self.fee_calculator = fee_calculator
        self.risk_limits = risk_limits
        self.kill_switch = kill_switch
        self.paper_mode = paper_mode

        self.timeframe = config["data"]["timeframe"]
        self.rebalance_hours = config["strategy"]["rebalance_hours"]
        self.universe: List[str] = []

        logger.info(f"Initialized live trading engine (paper_mode={paper_mode})")

    def initialize(self) -> bool:
        """
        Initialize engine: select universe, load data.

        Returns:
            True if successful
        """
        try:
            logger.info("Initializing live trading engine...")

            # Select universe
            self.universe = select_universe(
                self.exchange,
                top_n=self.config["universe"]["top_n"],
                quote=self.config["universe"]["quote"],
                contract_type=self.config["universe"]["contract_type"],
                blacklist=self.config["universe"].get("blacklist", []),
                min_24h_volume_usdt=self.config["universe"]["min_24h_volume_usdt"],
                min_history_bars=self.config["universe"]["min_history_bars"],
                timeframe=self.timeframe,
                storage=self.storage,
            )

            if not self.universe:
                logger.error("No symbols selected for universe")
                return False

            logger.info(f"Selected universe: {len(self.universe)} symbols")

            # Reconcile positions on startup
            self.reconcile_positions()

            self.kill_switch.record_success()
            return True

        except Exception as e:
            logger.error(f"Error initializing engine: {e}")
            self.kill_switch.record_error()
            return False

    def reconcile_positions(self):
        """Reconcile current positions with exchange."""
        try:
            positions = self.exchange.get_positions()
            logger.info(f"Current positions: {len(positions)}")

            for pos in positions:
                symbol = pos["symbol"]
                contracts = float(pos.get("contracts", 0))
                logger.info(f"Position: {symbol} {contracts} contracts")

        except Exception as e:
            logger.error(f"Error reconciling positions: {e}")
            self.kill_switch.record_error()

    def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for symbols."""
        prices = {}
        try:
            tickers = self.exchange.get_tickers()
            for symbol in symbols:
                normalized = normalize_symbol(symbol)
                ticker = tickers.get(normalized)
                if ticker:
                    prices[symbol] = float(ticker.get("last", 0) or ticker.get("close", 0))
        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            self.kill_switch.record_error()
        return prices

    def fetch_latest_data(self, symbols: List[str], bars_needed: int = 100) -> Dict[str, pd.DataFrame]:
        """Fetch latest candle data for symbols."""
        universe_data = {}
        end_date = utc_now()
        start_date = end_date - timedelta(hours=bars_needed)

        for symbol in symbols:
            try:
                normalized = normalize_symbol(symbol)
                df = download_candles(
                    self.exchange,
                    normalized,
                    timeframe=self.timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    limit=bars_needed,
                )
                if df is not None and len(df) > 0:
                    universe_data[symbol] = df
                    # Save to storage
                    self.storage.save_candles(symbol.replace("/", "").replace(":USDT", ""), self.timeframe, df)
            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")
                self.kill_switch.record_error()

        return universe_data

    def get_current_positions(self) -> Dict[str, float]:
        """Get current positions as notional values."""
        positions = {}
        try:
            exchange_positions = self.exchange.get_positions()
            prices = self.get_current_prices(self.universe)

            for pos in exchange_positions:
                symbol = pos["symbol"]
                contracts = float(pos.get("contracts", 0))
                if contracts != 0 and symbol in prices:
                    # Convert to notional (simplified: assumes contract size = price)
                    notional = contracts * prices[symbol]
                    positions[symbol] = notional

        except Exception as e:
            logger.error(f"Error getting current positions: {e}")
            self.kill_switch.record_error()

        return positions

    def get_equity(self) -> float:
        """Get current equity."""
        try:
            balance = self.exchange.get_balance()
            # Get USDT balance
            usdt_balance = balance.get("USDT", {}).get("free", 0.0) or 0.0

            # Add position values
            positions = self.get_current_positions()
            position_values = sum(positions.values())

            equity = float(usdt_balance) + position_values
            return equity

        except Exception as e:
            logger.error(f"Error getting equity: {e}")
            self.kill_switch.record_error()
            return 0.0

    def execute_rebalance(self):
        """Execute a rebalance."""
        try:
            # Check kill switch
            allowed, reason = self.kill_switch.is_trading_allowed()
            if not allowed:
                logger.warning(f"Trading halted: {reason}")
                return

            logger.info("Starting rebalance...")

            # Get current equity
            equity = self.get_equity()
            if equity <= 0:
                logger.error("Equity is zero or negative, cannot rebalance")
                return

            logger.info(f"Current equity: ${equity:.2f}")

            # Fetch latest data
            universe_data = self.fetch_latest_data(self.universe, bars_needed=100)
            if not universe_data:
                logger.error("No universe data available")
                return

            # Get regime data (BTC)
            regime_symbol = self.config["strategy"]["regime"]["lookback_symbol"]
            regime_data = None
            if regime_symbol in universe_data:
                regime_data = {regime_symbol: universe_data[regime_symbol]}

            # Generate signals
            signals = self.strategy.generate_signals(universe_data, regime_data=regime_data)
            if not signals:
                logger.warning("No signals generated")
                return

            # Calculate weights
            target_weights = calculate_volatility_target_weights(
                signals,
                universe_data,
                vol_window=self.config["portfolio"]["vol_window"],
                target_gross_exposure=self.config["portfolio"]["target_gross_exposure"],
                per_symbol_cap=self.config["portfolio"]["per_symbol_cap"],
                dollar_neutrality_tolerance=self.config["portfolio"]["dollar_neutrality_tolerance"],
            )

            if not target_weights:
                logger.warning("No target weights calculated")
                return

            # Get current positions
            current_positions = self.get_current_positions()

            # Get current prices
            prices = self.get_current_prices(list(target_weights.keys()))

            # Calculate rebalance orders
            orders = calculate_rebalance_orders(target_weights, current_positions, equity, prices)

            if not orders:
                logger.info("No rebalance orders needed")
                return

            logger.info(f"Executing {len(orders)} rebalance orders")

            # Execute orders
            for symbol, side, quantity, price in orders:
                normalized_symbol = normalize_symbol(symbol)

                if self.paper_mode:
                    # Simulate order
                    logger.info(
                        f"[PAPER] {side.upper()} {quantity:.6f} {normalized_symbol} @ ${price:.2f}"
                    )
                    time.sleep(0.1)  # Simulate execution delay
                else:
                    # Real order
                    try:
                        client_order_id = f"rebalance_{uuid.uuid4().hex[:8]}"
                        result = self.order_executor.execute_order(
                            normalized_symbol, side, quantity, price, client_order_id
                        )
                        if result:
                            logger.info(f"Order executed: {symbol} {side} {quantity}")
                        else:
                            logger.warning(f"Order failed: {symbol} {side} {quantity}")
                    except Exception as e:
                        logger.error(f"Error executing order for {symbol}: {e}")
                        self.kill_switch.record_error()

            # Check risk limits after rebalance
            new_equity = self.get_equity()
            positions = self.get_current_positions()
            gross_exposure = sum(abs(v) for v in positions.values())

            valid, msg = self.risk_limits.check_all(new_equity, gross_exposure)
            if not valid:
                logger.error(f"Risk limit breached after rebalance: {msg}")
                # Flatten positions
                self.flatten_all_positions()

            self.kill_switch.record_success()
            logger.info("Rebalance completed")

        except Exception as e:
            logger.error(f"Error during rebalance: {e}")
            self.kill_switch.record_error()

    def flatten_all_positions(self):
        """Flatten all positions (emergency exit)."""
        logger.warning("Flattening all positions")
        try:
            positions = self.exchange.get_positions()
            for pos in positions:
                symbol = pos["symbol"]
                contracts = float(pos.get("contracts", 0))
                if contracts != 0:
                    if self.paper_mode:
                        logger.info(f"[PAPER] Flattening position: {symbol} {contracts}")
                    else:
                        try:
                            self.exchange.close_position(symbol)
                            logger.info(f"Flattened position: {symbol}")
                        except Exception as e:
                            logger.error(f"Error flattening {symbol}: {e}")
        except Exception as e:
            logger.error(f"Error flattening positions: {e}")

    def run(self):
        """Run live trading loop."""
        logger.info("Starting live trading engine...")

        if not self.initialize():
            logger.error("Failed to initialize engine")
            return

        # Calculate next rebalance time
        next_rebalance = next_rebalance_time(utc_now(), self.rebalance_hours)
        logger.info(f"Next rebalance scheduled for: {next_rebalance}")

        # Main loop
        try:
            while True:
                now = utc_now()

                # Check if it's time to rebalance
                if now >= next_rebalance:
                    self.execute_rebalance()
                    next_rebalance = next_rebalance_time(now, self.rebalance_hours)
                    logger.info(f"Next rebalance scheduled for: {next_rebalance}")

                # Sleep for 1 minute
                time.sleep(60)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            self.flatten_all_positions()
        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}")
            self.kill_switch.record_error()
            self.flatten_all_positions()
            raise

