from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

from src.backtest.engine import BacktestEngine
from src.backtest.metrics import calculate_metrics
from src.common.log import setup_logger
from src.common.time import timeframe_to_hours
from src.data.candles import resample_candles
from src.data.storage import DataStorage
from src.exchange.fees import FeeCalculator
from src.execution.slippage import SlippageModel
from src.risk.limits import RiskLimits
from src.strategies.cs_reversal import CrossSectionalReversalStrategy
from src.strategies.regime import RegimeDetector
from src.optimize.grid import apply_overrides
from src.optimize.walkforward import build_walkforward_splits

logger = setup_logger(__name__)


@dataclass(frozen=True)
class OptimizationResult:
    overrides: Dict[str, Any]
    timeframe: str
    score: float
    metrics: Dict[str, Any]
    n_symbols: int


def _build_components(config: Dict[str, Any], storage: DataStorage) -> BacktestEngine:
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
        timeframe=config["data"]["timeframe"],
        regime_detector=regime_detector,
        regime_enabled=config["strategy"]["regime"]["enabled"],
    )
    return BacktestEngine(
        config=config,
        storage=storage,
        strategy=strategy,
        fee_calculator=fee_calculator,
        slippage_model=slippage_model,
        risk_limits=risk_limits,
    )


def _compute_default_windows(config: Dict[str, Any]) -> None:
    """
    Keep volatility window stable in HOURS across timeframes unless explicitly overridden.

    - If portfolio.vol_window_hours exists, use it.
    - Otherwise use 72 hours (matches original 72 x 1h bars default).
    """
    tf = config["data"]["timeframe"]
    tf_hours = timeframe_to_hours(tf)
    vol_window_hours = float(config.get("optimizer", {}).get("vol_window_hours", 72))
    bars = max(10, int(round(vol_window_hours / tf_hours)))
    config["portfolio"]["vol_window"] = int(bars)


def prepare_timeframe_data(
    base_data: Dict[str, pd.DataFrame],
    timeframe: str,
    base_timeframe: str,
) -> Dict[str, pd.DataFrame]:
    if timeframe == base_timeframe:
        return base_data

    # resample each symbol's candles
    resampled: Dict[str, pd.DataFrame] = {}
    for sym, df in base_data.items():
        try:
            r = resample_candles(df, timeframe)
            if r is not None and len(r) > 0:
                resampled[sym] = r
        except Exception:
            continue
    return resampled


def score_config(
    base_config: Dict[str, Any],
    storage: DataStorage,
    universe_data: Dict[str, pd.DataFrame],
    overrides: Dict[str, Any],
    walkforward: bool = True,
    seed: int = 1337,
    initial_equity: float = 100000.0,
) -> OptimizationResult:
    np.random.seed(seed)

    cfg = apply_overrides(base_config, overrides)
    _compute_default_windows(cfg)

    engine = _build_components(cfg, storage)

    # Use unified timestamps for splits
    any_df = next(iter(universe_data.values()))
    ts = pd.to_datetime(any_df["timestamp"]).sort_values().tolist()

    if walkforward:
        splits = build_walkforward_splits(ts, n_splits=3, train_ratio=0.6, test_ratio=0.2)
        if not splits:
            walkforward = False

    if not walkforward:
        eq = engine.run_on_data(universe_data=universe_data, initial_equity=initial_equity)
        metrics = calculate_metrics(eq)
        score = float(metrics.get("sharpe_ratio", 0.0) or 0.0)
        return OptimizationResult(
            overrides=overrides,
            timeframe=cfg["data"]["timeframe"],
            score=score,
            metrics=metrics,
            n_symbols=len(universe_data),
        )

    scores: List[float] = []
    dds: List[float] = []
    for sp in splits:
        eq = engine.run_on_data(
            universe_data=universe_data,
            start_date=sp.test_start,
            end_date=sp.test_end,
            initial_equity=initial_equity,
        )
        m = calculate_metrics(eq)
        scores.append(float(m.get("sharpe_ratio", 0.0) or 0.0))
        dds.append(float(m.get("max_drawdown", 0.0) or 0.0))

    metrics = {
        "wf_avg_sharpe": float(np.mean(scores)) if scores else 0.0,
        "wf_avg_max_drawdown": float(np.mean(dds)) if dds else 0.0,
        "wf_splits": len(splits),
    }
    score = metrics["wf_avg_sharpe"]
    return OptimizationResult(
        overrides=overrides,
        timeframe=cfg["data"]["timeframe"],
        score=float(score),
        metrics=metrics,
        n_symbols=len(universe_data),
    )


def save_results(
    base_config: Dict[str, Any],
    results: List[OptimizationResult],
    output_dir: str,
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    for r in results:
        row = {
            "score": r.score,
            "timeframe": r.timeframe,
            "n_symbols": r.n_symbols,
            **{k.replace(".", "_"): v for k, v in r.overrides.items()},
            "metrics_json": json.dumps(r.metrics, sort_keys=True),
        }
        rows.append(row)

    df = pd.DataFrame(rows).sort_values("score", ascending=False)
    df.to_csv(out / "results.csv", index=False)

    best = results[0] if results else None
    summary = {
        "n_runs": len(results),
        "best_score": best.score if best else None,
        "best_overrides": best.overrides if best else None,
        "best_timeframe": best.timeframe if best else None,
        "best_metrics": best.metrics if best else None,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))

    if best:
        best_cfg = apply_overrides(base_config, best.overrides)
        _compute_default_windows(best_cfg)
        (out / "best_config.yaml").write_text(yaml.safe_dump(best_cfg, sort_keys=False))


