# Optimization (Parameter + Timeframe)

This repo includes a simple, deterministic optimizer that can:
- Grid-search strategy parameters
- Test multiple candle timeframes (via resampling)
- Optionally score configurations using walk-forward (out-of-sample) Sharpe

## Prereqs

You must have downloaded candle data first (default base timeframe is `1h`):

```bash
python scripts/download_data.py --config config/config.yaml --days 60 --universe
```

## Run optimizer

```bash
python scripts/optimize.py --config config/config.yaml --output opt_results/
```

Defaults:
- **Timeframes**: `1h,4h`
- **Walk-forward**: enabled (can be disabled)
- **Grid**: a small built-in grid over quantile, rebalance_hours, adx_threshold

### Change timeframes

```bash
python scripts/optimize.py --config config/config.yaml --timeframes 1h,2h,4h --output opt_results/
```

### Disable walk-forward

```bash
python scripts/optimize.py --config config/config.yaml --no-walkforward --output opt_results/
```

## Outputs

The optimizer writes to `--output`:
- `results.csv`: ranked runs
- `summary.json`: best run summary
- `best_config.yaml`: config with best overrides applied (use this for backtest/live)

## Notes / Caveats

- This is a **grid-search** (not Bayesian). It’s meant to be transparent and safe-by-default.
- Walk-forward splits are **expanding window** splits; if data is too short, it falls back to a single full-period run.
- Timeframe testing is done via resampling the base stored timeframe candles (usually `1h`).


