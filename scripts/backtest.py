"""Run backtest."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.backtest.engine import BacktestEngine
from src.backtest.metrics import calculate_metrics, print_metrics, save_metrics
from src.common.log import setup_logger
from src.data.storage import DataStorage
from src.exchange.bybit import BybitExchange
from src.exchange.fees import FeeCalculator
from src.execution.slippage import SlippageModel
from src.risk.limits import RiskLimits
from src.strategies.cs_reversal import CrossSectionalReversalStrategy
from src.strategies.regime import RegimeDetector
from src.main import load_config

logger = setup_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run backtest")
    parser.add_argument("--config", type=str, default="config/config.yaml", help="Config file path")
    parser.add_argument("--output", type=str, help="Output directory for results")
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Setup logging
    log_level = config["runtime"]["log_level"]
    logger.setLevel(log_level)

    # Initialize components
    storage = DataStorage(
        storage_path=config["data"]["storage_path"],
        cache_db=config["data"]["cache_db"],
    )

    fee_calculator = FeeCalculator(
        maker_bps=config["fees"]["maker_bps"],
        taker_bps=config["fees"]["taker_bps"],
        funding_rate_bps=config["fees"]["funding_rate_bps"],
    )

    slippage_model = SlippageModel(slippage_bps=config["fees"]["slippage_bps"])

    risk_limits = RiskLimits(
        leverage_cap=config["risk"]["leverage_cap"],
        daily_loss_cap=config["risk"]["daily_loss_cap"],
        max_drawdown_cap=config["risk"]["max_drawdown_cap"],
    )

    regime_detector = RegimeDetector(
        adx_period=config["strategy"]["regime"]["adx_period"],
        ema_period=config["strategy"]["regime"]["ema_period"],
        adx_threshold=config["strategy"]["regime"]["adx_threshold"],
        ema_slope_threshold=config["strategy"]["regime"]["ema_slope_threshold"],
    )

    strategy = CrossSectionalReversalStrategy(
        quantile=config["strategy"]["quantile"],
        ret_lookback_hours=config["strategy"]["ret_lookback_hours"],
        regime_detector=regime_detector,
        regime_enabled=config["strategy"]["regime"]["enabled"],
    )

    # Initialize backtest engine
    engine = BacktestEngine(
        config=config,
        storage=storage,
        strategy=strategy,
        fee_calculator=fee_calculator,
        slippage_model=slippage_model,
        risk_limits=risk_limits,
    )

    # Get symbols with data
    symbols = storage.list_symbols(config["data"]["timeframe"])
    if not symbols:
        logger.error("No symbols found in storage. Run download_data.py first.")
        return

    logger.info(f"Running backtest on {len(symbols)} symbols")

    # Parse date range
    start_date = config["data"].get("start_date")
    end_date = config["data"].get("end_date")

    if start_date:
        start_date = datetime.fromisoformat(start_date)
    if end_date:
        end_date = datetime.fromisoformat(end_date)

    # Run backtest
    equity_curve = engine.run(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        initial_equity=100000.0,
    )

    if equity_curve.empty:
        logger.error("Backtest returned empty results")
        return

    # Calculate metrics
    metrics = calculate_metrics(equity_curve)
    print_metrics(metrics)

    # Save results
    output_dir = Path(args.output) if args.output else Path(config["data"]["storage_path"])
    output_dir.mkdir(parents=True, exist_ok=True)

    equity_file = output_dir / "equity_curve.csv"
    equity_curve.to_csv(equity_file, index=False)
    logger.info(f"Saved equity curve to {equity_file}")

    metrics_file = output_dir / "metrics.json"
    save_metrics(metrics, str(metrics_file))
    logger.info(f"Saved metrics to {metrics_file}")


if __name__ == "__main__":
    main()

