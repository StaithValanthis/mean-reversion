"""Candle data fetching and processing."""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import numpy as np
import pandas as pd

from src.common.log import setup_logger
from src.common.time import to_iso8601, utc_now
from src.exchange.bybit import BybitExchange
from src.data.storage import DataStorage

logger = setup_logger(__name__)


def normalize_symbol(symbol: str) -> str:
    """
    Normalize symbol to ccxt format.

    Args:
        symbol: Symbol (e.g., 'BTCUSDT' or 'BTC/USDT:USDT')

    Returns:
        Normalized symbol (e.g., 'BTC/USDT:USDT')
    """
    if "/" in symbol:
        return symbol
    # Assume USDT perpetual
    if len(symbol) > 4 and symbol.endswith("USDT"):
        base = symbol[:-4]
        return f"{base}/USDT:USDT"
    return symbol


def download_candles(
    exchange: BybitExchange,
    symbol: str,
    timeframe: str = "1h",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 1000,
) -> pd.DataFrame:
    """
    Download candles from exchange.

    Args:
        exchange: Exchange client
        symbol: Symbol
        timeframe: Timeframe (e.g., '1h')
        start_date: Optional start date
        end_date: Optional end date (default: now)
        limit: Maximum candles per request

    Returns:
        DataFrame with columns [timestamp, open, high, low, close, volume]
    """
    symbol_normalized = normalize_symbol(symbol)
    end_date = end_date or utc_now()

    all_candles = []
    since = None

    if start_date:
        since = int(start_date.timestamp() * 1000)

    logger.info(f"Downloading candles for {symbol} {timeframe} from {start_date} to {end_date}")

    try:
        while True:
            candles = exchange.fetch_ohlcv(
                symbol_normalized, timeframe, since=since, limit=limit
            )

            if not candles:
                break

            all_candles.extend(candles)
            last_ts = candles[-1][0]

            # Check if we've reached end_date
            if end_date and last_ts >= int(end_date.timestamp() * 1000):
                # Trim to end_date
                all_candles = [
                    c for c in all_candles
                    if c[0] <= int(end_date.timestamp() * 1000)
                ]
                break

            # Update since for next batch
            since = last_ts + 1

            # Prevent infinite loop
            if len(candles) < limit:
                break

        if not all_candles:
            logger.warning(f"No candles downloaded for {symbol}")
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(
            all_candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")

        logger.info(f"Downloaded {len(df)} candles for {symbol}")
        return df

    except Exception as e:
        logger.error(f"Error downloading candles for {symbol}: {e}")
        raise


def resample_candles(
    df: pd.DataFrame,
    target_timeframe: str,
) -> pd.DataFrame:
    """
    Resample candles to target timeframe.

    Args:
        df: Input DataFrame with candles
        target_timeframe: Target timeframe (e.g., '4h', '1d')

    Returns:
        Resampled DataFrame
    """
    if df.empty:
        return df

    df = df.set_index("timestamp")

    # Parse timeframe
    if target_timeframe.endswith("h"):
        freq = f"{target_timeframe[:-1]}H"
    elif target_timeframe.endswith("d"):
        freq = f"{target_timeframe[:-1]}D"
    elif target_timeframe.endswith("m"):
        freq = f"{target_timeframe[:-1]}min"
    else:
        raise ValueError(f"Unsupported timeframe: {target_timeframe}")

    resampled = df.resample(freq).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    ).dropna()

    resampled = resampled.reset_index()
    return resampled

