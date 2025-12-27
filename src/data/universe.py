"""Universe selection and filtering."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

import pandas as pd

from src.common.log import setup_logger
from src.exchange.bybit import BybitExchange
from src.data.candles import normalize_symbol

if TYPE_CHECKING:
    from src.data.storage import DataStorage

logger = setup_logger(__name__)


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _extract_volume_usdt(ticker: Dict[str, Any]) -> float:
    """
    Best-effort 24h USDT turnover from a ccxt ticker.

    For Bybit USDT perps, `quoteVolume` is often missing; `info.turnover24h` is usually present.
    """
    if not ticker:
        return 0.0

    qv = _safe_float(ticker.get("quoteVolume"), 0.0)
    if qv > 0:
        return qv

    base_v = _safe_float(ticker.get("baseVolume"), 0.0)
    last = _safe_float(ticker.get("last") or ticker.get("close"), 0.0)
    if base_v > 0 and last > 0:
        return base_v * last

    info = ticker.get("info") or {}
    for k in ("turnover24h", "turnover_24h", "quoteVolume", "quote_volume"):
        v = _safe_float(info.get(k), 0.0)
        if v > 0:
            return v

    vol24 = _safe_float(info.get("volume24h") or info.get("volume_24h"), 0.0)
    if vol24 > 0 and last > 0:
        return vol24 * last

    return 0.0


def _is_linear_usdt_swap(market_info: Dict[str, Any], quote: str, contract_type: str) -> bool:
    if not market_info:
        return False
    if not market_info.get("active", True):
        return False

    if contract_type == "swap":
        if market_info.get("swap") is False and market_info.get("type") not in ("swap", "perpetual"):
            return False
    else:
        if market_info.get("type") != contract_type:
            return False

    if market_info.get("linear") is False:
        return False

    q = quote.upper()
    settle = (market_info.get("settle") or market_info.get("settlement") or "").upper()
    quote_ccxt = (market_info.get("quote") or "").upper()
    if settle and settle != q:
        return False
    if quote_ccxt and quote_ccxt != q:
        return False

    if market_info.get("contract") is False:
        return False

    return True


def _symbol_in_blacklist(symbol: str, blacklist_set: set[str]) -> bool:
    if symbol in blacklist_set:
        return True
    compact = symbol.replace("/", "").replace(":", "").replace("-", "").upper()
    return compact in blacklist_set


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
    blacklist_set = {b.replace("/", "").replace(":", "").replace("-", "").upper() for b in blacklist}

    logger.info(f"Selecting universe: top_n={top_n}, min_volume={min_24h_volume_usdt}")

    try:
        # Get all markets
        markets = exchange.get_markets()
        tickers = exchange.get_tickers()

        candidates = []

        for symbol, market_info in markets.items():
            if not _is_linear_usdt_swap(market_info, quote=quote, contract_type=contract_type):
                continue

            if _symbol_in_blacklist(symbol, blacklist_set):
                continue

            # Get ticker data
            ticker = tickers.get(symbol) if tickers else None
            if not ticker:
                # Fallback: per-symbol ticker (slower, but robust)
                try:
                    ticker = exchange.get_ticker(symbol)
                except Exception:
                    ticker = None
            if not ticker:
                continue

            volume_usdt = _extract_volume_usdt(ticker)

            if volume_usdt < min_24h_volume_usdt:
                continue

            # Optional history check if cache already exists.
            # IMPORTANT: On a fresh VM, metadata may be missing; do not exclude in that case.
            if storage:
                symbol_normalized = symbol.replace("/", "").replace(":USDT", "")
                metadata = storage.get_metadata(symbol_normalized, timeframe)
                if metadata and metadata.get("num_bars", 0) < min_history_bars:
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

