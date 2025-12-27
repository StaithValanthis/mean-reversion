"""Time utilities for trading."""
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytz


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def parse_iso8601(ts: str) -> datetime:
    """Parse ISO8601 timestamp string to UTC datetime."""
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def to_iso8601(dt: datetime) -> str:
    """Convert datetime to ISO8601 string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def align_to_timeframe(
    dt: datetime,
    timeframe: str,
    align_to_end: bool = True,
) -> datetime:
    """
    Align datetime to timeframe boundary.

    Args:
        dt: Datetime to align
        timeframe: Timeframe string (e.g., '1h', '4h', '1d')
        align_to_end: If True, align to end of period; else to start

    Returns:
        Aligned datetime
    """
    dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    # Parse timeframe
    if timeframe.endswith("h"):
        hours = int(timeframe[:-1])
        td = timedelta(hours=hours)
    elif timeframe.endswith("d"):
        days = int(timeframe[:-1])
        td = timedelta(days=days)
    elif timeframe.endswith("m"):
        minutes = int(timeframe[:-1])
        td = timedelta(minutes=minutes)
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    # Align
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    seconds_since_epoch = (dt - epoch).total_seconds()
    periods = int(seconds_since_epoch / td.total_seconds())
    aligned_seconds = periods * td.total_seconds()

    if align_to_end:
        aligned_seconds += td.total_seconds()

    aligned = epoch + timedelta(seconds=aligned_seconds)
    return aligned


def next_rebalance_time(
    current_time: datetime,
    rebalance_hours: int,
) -> datetime:
    """Get next rebalance time aligned to rebalance_hours intervals."""
    # Align to hour boundaries
    hour = (current_time.hour // rebalance_hours) * rebalance_hours
    next_hour = hour + rebalance_hours
    if next_hour >= 24:
        # Next day
        next_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        next_time += timedelta(days=1)
        next_time += timedelta(hours=(next_hour % 24))
    else:
        next_time = current_time.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    return next_time.replace(tzinfo=timezone.utc)

