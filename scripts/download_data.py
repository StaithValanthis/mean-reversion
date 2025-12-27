"""Download historical data for backtesting."""
import argparse
from datetime import datetime, timedelta
from pathlib import Path

from src.common.log import setup_logger
from src.common.time import utc_now
from src.data.candles import download_candles, normalize_symbol
from src.data.storage import DataStorage
from src.data.universe import select_universe
from src.exchange.bybit import BybitExchange
from src.main import load_config

logger = setup_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Download historical data")
    parser.add_argument("--config", type=str, default="config/config.yaml", help="Config file path")
    parser.add_argument(
        "--days", type=int, default=30, help="Number of days of history to download"
    )
    parser.add_argument("--symbols", type=str, nargs="+", help="Specific symbols to download")
    parser.add_argument(
        "--universe",
        action="store_true",
        help="Download for all symbols in universe",
    )
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

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

    timeframe = config["data"]["timeframe"]

    # Determine symbols
    symbols = []
    if args.symbols:
        symbols = args.symbols
    elif args.universe or not args.symbols:
        # Select universe
        symbols = select_universe(
            exchange,
            top_n=config["universe"]["top_n"],
            quote=config["universe"]["quote"],
            contract_type=config["universe"]["contract_type"],
            blacklist=config["universe"].get("blacklist", []),
            min_24h_volume_usdt=config["universe"]["min_24h_volume_usdt"],
            min_history_bars=config["universe"]["min_history_bars"],
            timeframe=timeframe,
            storage=storage,
        )
        logger.info(f"Selected {len(symbols)} symbols from universe")
    else:
        logger.error("No symbols specified")
        return

    # Calculate date range
    end_date = utc_now()
    start_date = end_date - timedelta(days=args.days)

    logger.info(f"Downloading data from {start_date} to {end_date}")

    # Download data for each symbol
    for symbol in symbols:
        try:
            normalized = normalize_symbol(symbol)
            logger.info(f"Downloading {normalized}...")

            df = download_candles(
                exchange,
                normalized,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
            )

            if df is not None and len(df) > 0:
                # Save to storage
                symbol_key = symbol.replace("/", "").replace(":USDT", "")
                storage.save_candles(symbol_key, timeframe, df)
                logger.info(f"Saved {len(df)} candles for {symbol_key}")
            else:
                logger.warning(f"No data downloaded for {symbol}")

        except Exception as e:
            logger.error(f"Error downloading {symbol}: {e}")

    logger.info("Data download completed")


if __name__ == "__main__":
    main()

