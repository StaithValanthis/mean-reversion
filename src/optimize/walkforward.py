from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class WalkForwardSplit:
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime


def build_walkforward_splits(
    timestamps: Sequence[datetime],
    n_splits: int = 3,
    train_ratio: float = 0.6,
    test_ratio: float = 0.2,
) -> List[WalkForwardSplit]:
    """
    Build simple expanding-window walk-forward splits based on timestamp index.

    If there isn't enough data for the requested splits, falls back to a single split.
    """
    ts = list(timestamps)
    if len(ts) < 10:
        return []

    n = len(ts)
    train_n = max(5, int(n * train_ratio))
    test_n = max(2, int(n * test_ratio))

    # If we can't fit n_splits, reduce.
    max_splits = max(1, (n - train_n) // max(1, test_n))
    n_splits = min(n_splits, max_splits)

    splits: List[WalkForwardSplit] = []
    train_end_idx = train_n - 1
    for i in range(n_splits):
        test_start_idx = train_end_idx + 1
        test_end_idx = min(n - 1, test_start_idx + test_n - 1)
        if test_start_idx >= n:
            break

        splits.append(
            WalkForwardSplit(
                train_start=ts[0],
                train_end=ts[train_end_idx],
                test_start=ts[test_start_idx],
                test_end=ts[test_end_idx],
            )
        )

        # expanding window: extend train to include this test
        train_end_idx = test_end_idx
        if train_end_idx >= n - 2:
            break

    return splits


