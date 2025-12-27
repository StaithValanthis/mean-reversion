"""Grid-search optimizer for strategy parameters and timeframes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.common.log import setup_logger
from src.data.storage import DataStorage
from src.main import load_config
from src.optimize.grid import expand_grid
from src.optimize.runner import (
    OptimizationResult,
    prepare_timeframe_data,
    save_results,
    score_config,
)

logger = setup_logger(__name__)


def _default_grid() -> Dict[str, List[Any]]:
    """
    Safe default grid (kept intentionally small).
    - ret_lookback_hours stays in HOURS (strategy converts to bars by timeframe)
    """
    return {
        "strategy.quantile": [0.15, 0.20, 0.25],
        "strategy.rebalance_hours": [4, 6],
        "strategy.ret_lookback_hours": [24],
        "strategy.regime.adx_threshold": [20, 25, 30],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize parameters/timeframes (grid + walk-forward)")
    parser.add_argument("--config", type=str, default="config/config.yaml")
    parser.add_argument("--output", type=str, default="opt_results/")
    parser.add_argument(
        "--timeframes",
        type=str,
        default="1h,4h",
        help="Comma-separated timeframes to test (e.g. '1h,2h,4h')",
    )
    parser.add_argument("--no-walkforward", action="store_true", help="Disable walk-forward scoring")
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--max-runs", type=int, default=200)
    args = parser.parse_args()

    base_config = load_config(args.config)

    storage = DataStorage(
        storage_path=base_config["data"]["storage_path"],
        cache_db=base_config["data"]["cache_db"],
    )

    base_tf = base_config["data"]["timeframe"]
    symbols = storage.list_symbols(base_tf)
    if not symbols:
        raise SystemExit(
            f"No candles found for timeframe={base_tf}. Run download first:\n"
            f"  python scripts/download_data.py --config {args.config} --days 60 --universe"
        )

    logger.info(f"Loading base data for {len(symbols)} symbols (timeframe={base_tf})")
    base_data: Dict[str, pd.DataFrame] = {}
    for s in symbols:
        df = storage.load_candles(s, base_tf)
        if df is not None and len(df) > 0:
            base_data[s] = df

    if not base_data:
        raise SystemExit("Loaded 0 symbols from storage; cannot optimize.")

    timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]
    grid = _default_grid()
    combos = expand_grid(grid)
    combos = combos[: args.max_runs]

    logger.info(f"Optimization: timeframes={timeframes}, grid_runs={len(combos)}, walkforward={not args.no_walkforward}")

    results: List[OptimizationResult] = []

    # Cache per-timeframe resampled data
    tf_cache: Dict[str, Dict[str, pd.DataFrame]] = {}

    for tf in timeframes:
        tf_data = prepare_timeframe_data(base_data, timeframe=tf, base_timeframe=base_tf)
        tf_cache[tf] = tf_data

    run_idx = 0
    for tf in timeframes:
        tf_data = tf_cache[tf]
        if len(tf_data) < 5:
            logger.warning(f"Skipping timeframe={tf} (too few symbols after resample: {len(tf_data)})")
            continue

        for combo in combos:
            run_idx += 1
            overrides = dict(combo)
            overrides["data.timeframe"] = tf

            r = score_config(
                base_config=base_config,
                storage=storage,
                universe_data=tf_data,
                overrides=overrides,
                walkforward=not args.no_walkforward,
                seed=args.seed,
            )
            results.append(r)

            if run_idx % 10 == 0:
                logger.info(f"Completed {run_idx} runs; latest score={r.score:.3f} (tf={tf})")

    results.sort(key=lambda x: x.score, reverse=True)
    save_results(base_config, results, args.output)

    if results:
        best = results[0]
        logger.info(f"BEST score={best.score:.3f} tf={best.timeframe} overrides={best.overrides}")
        logger.info(f"Saved: {args.output}/results.csv, summary.json, best_config.yaml")
    else:
        logger.warning("No results produced (check your data/timeframes).")


if __name__ == "__main__":
    main()


