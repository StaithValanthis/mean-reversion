"""Backtest performance metrics."""
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from src.common.log import setup_logger

logger = setup_logger(__name__)


def calculate_metrics(equity_curve: pd.DataFrame) -> Dict:
    """
    Calculate performance metrics from equity curve.

    Args:
        equity_curve: DataFrame with columns ['timestamp', 'equity', 'pnl', ...]

    Returns:
        Dictionary of metrics
    """
    if len(equity_curve) < 2:
        return {}

    equity = equity_curve["equity"].values
    pnl = equity_curve["pnl"].values if "pnl" in equity_curve.columns else np.diff(equity)

    # Returns
    returns = np.diff(equity) / equity[:-1]

    # Total return
    total_return = (equity[-1] / equity[0]) - 1

    # CAGR (if we have timestamps)
    if "timestamp" in equity_curve.columns:
        start_date = pd.to_datetime(equity_curve["timestamp"].iloc[0])
        end_date = pd.to_datetime(equity_curve["timestamp"].iloc[-1])
        years = (end_date - start_date).days / 365.25
        if years > 0:
            cagr = ((equity[-1] / equity[0]) ** (1 / years)) - 1
        else:
            cagr = np.nan
    else:
        cagr = np.nan
        years = np.nan

    # Sharpe ratio (annualized)
    if len(returns) > 0 and np.std(returns) > 0:
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24)  # Assuming hourly returns
    else:
        sharpe = 0.0

    # Sortino ratio (annualized, downside deviation)
    downside_returns = returns[returns < 0]
    if len(downside_returns) > 0:
        downside_std = np.std(downside_returns)
        if downside_std > 0:
            sortino = np.mean(returns) / downside_std * np.sqrt(252 * 24)
        else:
            sortino = sharpe
    else:
        sortino = np.inf if sharpe > 0 else 0.0

    # Maximum drawdown
    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / running_max
    max_drawdown = np.min(drawdown)

    # Profit factor
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    total_wins = np.sum(wins) if len(wins) > 0 else 0
    total_losses = abs(np.sum(losses)) if len(losses) > 0 else 1
    profit_factor = total_wins / total_losses if total_losses > 0 else np.inf

    # Win rate
    num_wins = len(wins)
    num_trades = len(pnl[pnl != 0])
    win_rate = num_wins / num_trades if num_trades > 0 else 0.0

    # Average win/loss
    avg_win = np.mean(wins) if len(wins) > 0 else 0.0
    avg_loss = np.mean(losses) if len(losses) > 0 else 0.0

    # Turnover (if available)
    turnover = equity_curve["turnover"].mean() if "turnover" in equity_curve.columns else np.nan

    # Exposure (if available)
    avg_long_exposure = (
        equity_curve["long_exposure"].mean() if "long_exposure" in equity_curve.columns else np.nan
    )
    avg_short_exposure = (
        equity_curve["short_exposure"].mean() if "short_exposure" in equity_curve.columns else np.nan
    )

    metrics = {
        "total_return": float(total_return),
        "cagr": float(cagr) if not np.isnan(cagr) else None,
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino) if not np.isinf(sortino) else None,
        "max_drawdown": float(max_drawdown),
        "profit_factor": float(profit_factor) if not np.isinf(profit_factor) else None,
        "win_rate": float(win_rate),
        "num_trades": int(num_trades),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "turnover": float(turnover) if not np.isnan(turnover) else None,
        "avg_long_exposure": float(avg_long_exposure) if not np.isnan(avg_long_exposure) else None,
        "avg_short_exposure": float(avg_short_exposure) if not np.isnan(avg_short_exposure) else None,
        "start_equity": float(equity[0]),
        "end_equity": float(equity[-1]),
    }

    return metrics


def save_metrics(metrics: Dict, file_path: str):
    """Save metrics to JSON file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"Saved metrics to {file_path}")


def print_metrics(metrics: Dict):
    """Print metrics in readable format."""
    print("\n" + "=" * 60)
    print("BACKTEST METRICS")
    print("=" * 60)
    print(f"Total Return:        {metrics['total_return']:.2%}")
    if metrics.get("cagr") is not None:
        print(f"CAGR:                {metrics['cagr']:.2%}")
    print(f"Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}")
    if metrics.get("sortino_ratio") is not None:
        print(f"Sortino Ratio:       {metrics['sortino_ratio']:.2f}")
    print(f"Max Drawdown:        {metrics['max_drawdown']:.2%}")
    if metrics.get("profit_factor") is not None:
        print(f"Profit Factor:       {metrics['profit_factor']:.2f}")
    print(f"Win Rate:            {metrics['win_rate']:.2%}")
    print(f"Number of Trades:    {metrics['num_trades']}")
    print(f"Avg Win:             ${metrics['avg_win']:.2f}")
    print(f"Avg Loss:            ${metrics['avg_loss']:.2f}")
    if metrics.get("turnover") is not None:
        print(f"Avg Turnover:        {metrics['turnover']:.2%}")
    if metrics.get("avg_long_exposure") is not None:
        print(f"Avg Long Exposure:   {metrics['avg_long_exposure']:.2%}")
    if metrics.get("avg_short_exposure") is not None:
        print(f"Avg Short Exposure:  {metrics['avg_short_exposure']:.2%}")
    print(f"Start Equity:        ${metrics['start_equity']:.2f}")
    print(f"End Equity:          ${metrics['end_equity']:.2f}")
    print("=" * 60 + "\n")

