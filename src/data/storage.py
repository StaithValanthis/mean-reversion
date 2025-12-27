"""Data storage using Parquet and SQLite."""
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import pyarrow.parquet as pq

from src.common.log import setup_logger

logger = setup_logger(__name__)


class DataStorage:
    """Handle data storage and retrieval."""

    def __init__(self, storage_path: str = "data/", cache_db: str = "data/cache.sqlite"):
        """
        Initialize storage.

        Args:
            storage_path: Path to store Parquet files
            cache_db: Path to SQLite cache database
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.cache_db = Path(cache_db)
        self.cache_db.parent.mkdir(parents=True, exist_ok=True)

        # Initialize cache database
        self._init_cache()

    def _init_cache(self):
        """Initialize cache database tables."""
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS candle_metadata (
                symbol TEXT,
                timeframe TEXT,
                first_timestamp INTEGER,
                last_timestamp INTEGER,
                num_bars INTEGER,
                PRIMARY KEY (symbol, timeframe)
            )
        """
        )
        conn.commit()
        conn.close()

    def save_candles(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
    ):
        """
        Save candles to Parquet file.

        Args:
            symbol: Symbol name
            timeframe: Timeframe (e.g., '1h')
            df: DataFrame with columns [timestamp, open, high, low, close, volume]
        """
        file_path = self.storage_path / f"{symbol}_{timeframe}.parquet"

        # Ensure proper column names
        df = df.copy()
        if "timestamp" not in df.columns:
            raise ValueError("DataFrame must have 'timestamp' column")

        # Convert timestamp to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

        # Save to Parquet
        df.to_parquet(file_path, index=False, compression="snappy")
        logger.debug(f"Saved {len(df)} candles for {symbol} {timeframe} to {file_path}")

        # Update metadata
        self._update_metadata(symbol, timeframe, df)

    def load_candles(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[pd.Timestamp] = None,
        end_date: Optional[pd.Timestamp] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Load candles from Parquet file.

        Args:
            symbol: Symbol name
            timeframe: Timeframe
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            DataFrame with candles, or None if file doesn't exist
        """
        file_path = self.storage_path / f"{symbol}_{timeframe}.parquet"

        if not file_path.exists():
            logger.debug(f"No data file found for {symbol} {timeframe}")
            return None

        try:
            df = pd.read_parquet(file_path)
            df["timestamp"] = pd.to_datetime(df["timestamp"])

            # Filter by date if specified
            if start_date is not None:
                df = df[df["timestamp"] >= start_date]
            if end_date is not None:
                df = df[df["timestamp"] <= end_date]

            df = df.sort_values("timestamp")
            logger.debug(f"Loaded {len(df)} candles for {symbol} {timeframe}")
            return df
        except Exception as e:
            logger.error(f"Error loading candles for {symbol} {timeframe}: {e}")
            return None

    def _update_metadata(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
    ):
        """Update cache metadata."""
        if len(df) == 0:
            return

        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()

        first_ts = int(df["timestamp"].min().timestamp() * 1000)
        last_ts = int(df["timestamp"].max().timestamp() * 1000)
        num_bars = len(df)

        cursor.execute(
            """
            INSERT OR REPLACE INTO candle_metadata
            (symbol, timeframe, first_timestamp, last_timestamp, num_bars)
            VALUES (?, ?, ?, ?, ?)
        """,
            (symbol, timeframe, first_ts, last_ts, num_bars),
        )

        conn.commit()
        conn.close()

    def get_metadata(
        self,
        symbol: str,
        timeframe: str,
    ) -> Optional[Dict]:
        """Get metadata for symbol/timeframe."""
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT first_timestamp, last_timestamp, num_bars
            FROM candle_metadata
            WHERE symbol = ? AND timeframe = ?
        """,
            (symbol, timeframe),
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return {
            "first_timestamp": row[0],
            "last_timestamp": row[1],
            "num_bars": row[2],
        }

    def list_symbols(self, timeframe: str) -> List[str]:
        """List all symbols with data for timeframe."""
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT DISTINCT symbol
            FROM candle_metadata
            WHERE timeframe = ?
        """,
            (timeframe,),
        )

        symbols = [row[0] for row in cursor.fetchall()]
        conn.close()
        return symbols

