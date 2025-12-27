"""Run live trading engine."""
import argparse
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.common.log import setup_logger
from src.data.storage import DataStorage
from src.exchange.bybit import BybitExchange
from src.exchange.fees import FeeCalculator
from src.execution.orders import OrderExecutor
from src.execution.slippage import SlippageModel
from src.live.engine import LiveTradingEngine
from src.risk.killswitch import KillSwitch
from src.risk.limits import RiskLimits
from src.strategies.cs_reversal import CrossSectionalReversalStrategy
from src.strategies.regime import RegimeDetector
from src.main import load_config

logger = setup_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run live trading")
    parser.add_argument("--config", type=str, default="config/config.yaml", help="Config file path")
    parser.add_argument(
        "--paper",
        action="store_true",
        help="Run in paper trading mode (simulate orders)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run in live trading mode (REAL ORDERS)",
    )
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Determine mode
    if args.live:
        paper_mode = False
        logger.warning("=" * 60)
        logger.warning("LIVE TRADING MODE ENABLED - REAL ORDERS WILL BE PLACED")
        logger.warning("=" * 60)
    elif args.paper:
        paper_mode = True
        logger.info("Paper trading mode enabled")
    else:
        # Default from config
        paper_mode = config["runtime"]["mode"] != "live"
        if not paper_mode:
            logger.warning(
                "Config specifies live mode, but --live flag not provided. "
                "Defaulting to paper mode for safety."
            )
            paper_mode = True

    # Setup logging
    log_level = config["runtime"]["log_level"]
    log_file = config["runtime"].get("log_file")
    logger_obj = setup_logger(__name__, log_level=log_level, log_file=log_file)

    # Initialize exchange
    exchange = BybitExchange(
        testnet=config["exchange"]["testnet"],
        rate_limit=config["exchange"]["rate_limit_requests_per_second"],
        timeout=config["exchange"]["request_timeout"],
    )

    # Initialize storage
    storage = DataStorage(
        storage_path=config["data"]["storage_path"],
        cache_db=config["data"]["cache_db"],
    )

    # Initialize fee calculator
    fee_calculator = FeeCalculator(
        maker_bps=config["fees"]["maker_bps"],
        taker_bps=config["fees"]["taker_bps"],
        funding_rate_bps=config["fees"]["funding_rate_bps"],
    )

    # Initialize order executor
    order_executor = OrderExecutor(
        exchange=exchange,
        post_only=config["execution"]["post_only"],
        timeout_sec=config["execution"]["timeout_sec"],
        max_retries=config["execution"]["max_retries"],
    )

    # Initialize risk management
    risk_limits = RiskLimits(
        leverage_cap=config["risk"]["leverage_cap"],
        daily_loss_cap=config["risk"]["daily_loss_cap"],
        max_drawdown_cap=config["risk"]["max_drawdown_cap"],
    )

    circuit_breaker_config = config["risk"]["circuit_breaker"]
    extreme_vol_config = config["risk"]["extreme_vol_guard"]

    kill_switch = KillSwitch(
        max_consecutive_errors=circuit_breaker_config["max_consecutive_errors"],
        cooldown_seconds=circuit_breaker_config["cooldown_seconds"],
        extreme_vol_enabled=extreme_vol_config["enabled"],
        extreme_vol_threshold=extreme_vol_config["threshold_multiplier"],
        extreme_vol_halt_hours=extreme_vol_config["halt_duration_hours"],
    )

    # Initialize strategy
    regime_detector = RegimeDetector(
        adx_period=config["strategy"]["regime"]["adx_period"],
        ema_period=config["strategy"]["regime"]["ema_period"],
        adx_threshold=config["strategy"]["regime"]["adx_threshold"],
        ema_slope_threshold=config["strategy"]["regime"]["ema_slope_threshold"],
    )

    strategy = CrossSectionalReversalStrategy(
        quantile=config["strategy"]["quantile"],
        ret_lookback_hours=config["strategy"]["ret_lookback_hours"],
        timeframe=config["data"]["timeframe"],
        regime_detector=regime_detector,
        regime_enabled=config["strategy"]["regime"]["enabled"],
    )

    # Initialize live trading engine
    engine = LiveTradingEngine(
        config=config,
        exchange=exchange,
        storage=storage,
        strategy=strategy,
        order_executor=order_executor,
        fee_calculator=fee_calculator,
        risk_limits=risk_limits,
        kill_switch=kill_switch,
        paper_mode=paper_mode,
    )

    # Run engine
    try:
        engine.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()

