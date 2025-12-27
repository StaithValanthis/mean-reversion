"""Backtest engine."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.common.log import setup_logger
from src.common.time import align_to_timeframe, next_rebalance_time, utc_now
from src.data.candles import normalize_symbol
from src.data.storage import DataStorage
from src.exchange.fees import FeeCalculator
from src.execution.slippage import SlippageModel
from src.portfolio.weights import calculate_volatility_target_weights
from src.portfolio.rebalance import calculate_rebalance_orders
from src.risk.limits import RiskLimits
from src.strategies.cs_reversal import CrossSectionalReversalStrategy
from src.strategies.regime import RegimeDetector

logger = setup_logger(__name__)


class BacktestEngine:
    """Event-driven backtest engine."""

    def __init__(
        self,
        config: Dict,
        storage: DataStorage,
        strategy: CrossSectionalReversalStrategy,
        fee_calculator: FeeCalculator,
        slippage_model: SlippageModel,
        risk_limits: RiskLimits,
    ):
        """
        Initialize backtest engine.

        Args:
            config: Configuration dictionary
            storage: Data storage instance
            strategy: Strategy instance
            fee_calculator: Fee calculator
            slippage_model: Slippage model
            risk_limits: Risk limits checker
        """
        self.config = config
        self.storage = storage
        self.strategy = strategy
        self.fee_calculator = fee_calculator
        self.slippage_model = slippage_model
        self.risk_limits = risk_limits

        self.timeframe = config["data"]["timeframe"]
        self.rebalance_hours = config["strategy"]["rebalance_hours"]
        self.initial_equity = 100000.0  # Default $100k

        # State
        self.positions: Dict[str, float] = {}  # symbol -> quantity (positive=long, negative=short)
        self.position_entries: Dict[str, float] = {}  # symbol -> entry_price (average)
        self.equity_curve: List[Dict] = []
        self.trades: List[Dict] = []
        self.total_fees: float = 0.0  # Total fees paid

    def run(
        self,
        symbols: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        initial_equity: float = 100000.0,
    ) -> pd.DataFrame:
        """
        Run backtest.

        Args:
            symbols: List of symbols to trade
            start_date: Start date
            end_date: End date
            initial_equity: Initial equity

        Returns:
            Equity curve DataFrame
        """
        self.initial_equity = initial_equity
        equity = initial_equity
        self.positions = {}
        self.position_entries = {}
        self.total_fees = 0.0

        # Load data for all symbols
        logger.info(f"Loading data for {len(symbols)} symbols")
        universe_data = {}
        for symbol in symbols:
            df = self.storage.load_candles(
                symbol, self.timeframe, start_date=start_date, end_date=end_date
            )
            if df is not None and len(df) > 0:
                universe_data[symbol] = df

        if not universe_data:
            logger.error("No data loaded for backtest")
            return pd.DataFrame()

        # Get date range
        all_timestamps = set()
        for df in universe_data.values():
            all_timestamps.update(df["timestamp"].tolist())

        timestamps = sorted(all_timestamps)
        if not timestamps:
            logger.error("No timestamps found")
            return pd.DataFrame()

        start_ts = start_date if start_date else timestamps[0]
        end_ts = end_date if end_date else timestamps[-1]

        # Filter timestamps to range
        timestamps = [ts for ts in timestamps if start_ts <= ts <= end_ts]

        logger.info(f"Running backtest from {start_ts} to {end_ts} ({len(timestamps)} bars)")

        # Get regime data (BTC)
        regime_symbol = self.config["strategy"]["regime"]["lookback_symbol"]
        regime_df = None
        if regime_symbol in universe_data:
            regime_df = universe_data[regime_symbol]
        elif f"{regime_symbol.replace('USDT', '')}/USDT:USDT" in universe_data:
            regime_df = universe_data[f"{regime_symbol.replace('USDT', '')}/USDT:USDT"]

        regime_detector = RegimeDetector(
            adx_period=self.config["strategy"]["regime"]["adx_period"],
            ema_period=self.config["strategy"]["regime"]["ema_period"],
            adx_threshold=self.config["strategy"]["regime"]["adx_threshold"],
            ema_slope_threshold=self.config["strategy"]["regime"]["ema_slope_threshold"],
        )

        # Run bar-by-bar
        current_time = timestamps[0]
        last_rebalance_time = None

        for i, timestamp in enumerate(timestamps):
            current_time = timestamp

            # Check if rebalance time
            should_rebalance = False
            if last_rebalance_time is None:
                should_rebalance = True
            else:
                hours_since_rebalance = (current_time - last_rebalance_time).total_seconds() / 3600
                if hours_since_rebalance >= self.rebalance_hours:
                    should_rebalance = True

            if should_rebalance:
                # Get current data up to this point
                current_universe_data = {}
                for symbol, df in universe_data.items():
                    df_current = df[df["timestamp"] <= current_time]
                    if len(df_current) > 0:
                        current_universe_data[symbol] = df_current

                # Get regime data
                regime_data_dict = None
                if regime_df is not None:
                    regime_current = regime_df[regime_df["timestamp"] <= current_time]
                    if len(regime_current) > 0:
                        regime_data_dict = {regime_symbol: regime_current}

                # Generate signals
                signals = self.strategy.generate_signals(
                    current_universe_data, regime_data=regime_data_dict
                )

                if signals:
                    # Calculate weights
                    target_weights = calculate_volatility_target_weights(
                        signals,
                        current_universe_data,
                        vol_window=self.config["portfolio"]["vol_window"],
                        target_gross_exposure=self.config["portfolio"]["target_gross_exposure"],
                        per_symbol_cap=self.config["portfolio"]["per_symbol_cap"],
                        dollar_neutrality_tolerance=self.config["portfolio"][
                            "dollar_neutrality_tolerance"
                        ],
                    )

                    # Get current prices
                    prices = {}
                    for symbol in target_weights.keys():
                        if symbol in current_universe_data:
                            prices[symbol] = current_universe_data[symbol]["close"].iloc[-1]

                    # Calculate rebalance orders
                    orders = calculate_rebalance_orders(
                        target_weights, self.positions, equity, prices
                    )

                    # Execute orders (simulate)
                    for symbol, side, quantity, price in orders:
                        # Apply slippage
                        executed_price = self.slippage_model.apply_slippage(price, side, quantity)
                        notional = executed_price * quantity

                        # Calculate fees (assume maker for limit orders)
                        fee = self.fee_calculator.calculate_fee(notional, is_maker=True)
                        self.total_fees += fee

                        # Update position (track quantity and weighted average entry price)
                        current_quantity = self.positions.get(symbol, 0.0)
                        current_entry = self.position_entries.get(symbol, executed_price)

                        if side == "buy":
                            # Increase long position (or decrease short)
                            new_quantity = current_quantity + quantity
                            if abs(new_quantity) > 1e-8:  # Avoid division by zero
                                # Weighted average entry price
                                if current_quantity * new_quantity >= 0:  # Same sign
                                    # Adding to existing position
                                    total_cost = (current_quantity * current_entry) + (quantity * executed_price)
                                    new_entry = total_cost / new_quantity
                                else:
                                    # Flipping from short to long
                                    new_entry = executed_price
                            else:
                                new_entry = executed_price
                            self.positions[symbol] = new_quantity
                            self.position_entries[symbol] = new_entry
                        else:
                            # Increase short position (or decrease long)
                            new_quantity = current_quantity - quantity
                            if abs(new_quantity) > 1e-8:
                                if current_quantity * new_quantity >= 0:  # Same sign
                                    # Adding to existing position
                                    total_cost = (current_quantity * current_entry) - (quantity * executed_price)
                                    new_entry = total_cost / new_quantity
                                else:
                                    # Flipping from long to short
                                    new_entry = executed_price
                            else:
                                new_entry = executed_price
                            self.positions[symbol] = new_quantity
                            self.position_entries[symbol] = new_entry

                    last_rebalance_time = current_time

            # Calculate current equity (mark to market)
            # For futures/perpetuals: equity = initial_equity + sum(PnL) - fees
            total_long_exposure = 0.0
            total_short_exposure = 0.0
            total_pnl = 0.0

            for symbol, quantity in self.positions.items():
                if abs(quantity) < 1e-8:  # Skip zero positions
                    continue
                    
                if symbol in universe_data:
                    df_current = universe_data[symbol][universe_data[symbol]["timestamp"] <= current_time]
                    if len(df_current) > 0:
                        current_price = df_current["close"].iloc[-1]
                        entry_price = self.position_entries.get(symbol, current_price)
                        
                        # Calculate PnL
                        if quantity > 0:
                            # Long position: PnL = (current_price - entry_price) * quantity
                            pnl = (current_price - entry_price) * quantity
                            total_pnl += pnl
                            total_long_exposure += abs(quantity * current_price)
                        else:
                            # Short position: PnL = (entry_price - current_price) * |quantity|
                            pnl = (entry_price - current_price) * abs(quantity)
                            total_pnl += pnl
                            total_short_exposure += abs(quantity * current_price)

            # Total equity = initial equity + PnL - fees
            current_equity = initial_equity + total_pnl - self.total_fees

            # Record equity curve point
            pnl = current_equity - initial_equity
            self.equity_curve.append(
                {
                    "timestamp": current_time,
                    "equity": current_equity,
                    "pnl": pnl,
                    "long_exposure": total_long / current_equity if current_equity > 0 else 0.0,
                    "short_exposure": total_short / current_equity if current_equity > 0 else 0.0,
                }
            )

            equity = current_equity

            # Check risk limits
            gross_exposure = total_long + total_short
            valid, msg = self.risk_limits.check_all(equity, gross_exposure)
            if not valid:
                logger.warning(f"Risk limit breached: {msg}")
                # Flatten positions (reset to zero, PnL already included in equity)
                self.positions = {}
                self.position_entries = {}

        # Convert to DataFrame
        equity_df = pd.DataFrame(self.equity_curve)
        return equity_df

