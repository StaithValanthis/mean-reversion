"""Universe selection and filtering."""
from typing import Dict, List, Optional, TYPE_CHECKING

import pandas as pd

from src.common.log import setup_logger
from src.exchange.bybit import BybitExchange
from src.data.candles import normalize_symbol

if TYPE_CHECKING:
    from src.data.storage import DataStorage

logger = setup_logger(__name__)


def select_universe(
    exchange: BybitExchange,
    top_n: int = 50,
    quote: str = "USDT",
    contract_type: str = "swap",
    blacklist: List[str] = None,
    min_24h_volume_usdt: float = 10000000,
    min_history_bars: int = 100,
    timeframe: str = "1h",
    storage: Optional["DataStorage"] = None,
) -> List[str]:
    """
    Select trading universe.

    Args:
        exchange: Exchange client
        top_n: Top N symbols by volume
        quote: Quote currency (e.g., 'USDT')
        contract_type: Contract type ('swap' for perpetuals)
        blacklist: List of symbols to exclude
        min_24h_volume_usdt: Minimum 24h volume in USDT
        min_history_bars: Minimum historical bars required
        timeframe: Timeframe for checking history
        storage: Optional DataStorage to check history

    Returns:
        List of selected symbols (normalized)
    """
    blacklist = blacklist or []
    blacklist_set = set(blacklist)

    logger.info(f"Selecting universe: top_n={top_n}, min_volume={min_24h_volume_usdt}")

    try:
        # Get all markets
        markets = exchange.get_markets()
        tickers = exchange.get_tickers()

        candidates = []

        for symbol, market_info in markets.items():
            # Filter by contract type and quote
            if market_info.get("type") != contract_type:
                continue
            if market_info.get("quote") != quote:
                continue
            if not market_info.get("active", True):
                continue

            # Check blacklist
            if symbol in blacklist_set:
                continue

            # Get ticker data
            ticker = tickers.get(symbol)
            if not ticker:
                continue

            volume_usdt = ticker.get("quoteVolume", 0) or 0

            if volume_usdt < min_24h_volume_usdt:
                continue

            # Check history if storage provided
            if storage:
                symbol_normalized = symbol.replace("/", "").replace(":USDT", "")
                metadata = storage.get_metadata(symbol_normalized, timeframe)
                if not metadata or metadata["num_bars"] < min_history_bars:
                    continue

            candidates.append((symbol, volume_usdt))

        # Sort by volume and take top N
        candidates.sort(key=lambda x: x[1], reverse=True)
        selected = [s[0] for s in candidates[:top_n]]

        logger.info(f"Selected {len(selected)} symbols for universe")
        return selected

    except Exception as e:
        logger.error(f"Error selecting universe: {e}")
        raise

