# Strategy Documentation

## Overview

The bot implements a **cross-sectional short-term reversal strategy** with regime-aware position sizing.

## Core Strategy Logic

### Signal Generation

1. **Return Calculation**: For each symbol, compute 24-hour return:
   ```
   ret_24h = (close_t / close_{t-24}) - 1
   ```

2. **Ranking**: Rank all symbols by `ret_24h` (ascending order)

3. **Selection**:
   - **Long**: Bottom 20% (recent losers)
   - **Short**: Top 20% (recent winners)

### Regime Detection

To avoid fading strong trends, the strategy uses regime detection:

1. **Trend Proxy**: On BTCUSDT (or specified symbol):
   - EMA(50) slope
   - ADX(14)

2. **Regime Classification**:
   - **Strong Trend**: ADX > threshold (default 25) AND |EMA slope| > threshold
   - **Range**: Otherwise

3. **Position Scaling**: In strong trends, scale down mean-reversion exposure:
   - Scale factor: 0.25 (reduce to 25% of normal size)

### Portfolio Construction

1. **Volatility Targeting**:
   - Calculate per-symbol volatility (rolling 72-hour std dev of returns)
   - Weight inversely proportional to volatility: `weight ∝ 1/vol`
   - Normalize so long book and short book each sum to target gross exposure (default 100% of equity)

2. **Dollar Neutrality**:
   - Ensure long notional ≈ short notional (within tolerance, default 2%)
   - If imbalance detected, scale both sides proportionally

3. **Position Caps**:
   - Maximum per-symbol exposure: 5% of equity (default)
   - Maximum total gross exposure: 200% of equity (100% per side)

### Rebalancing

- Rebalance every 4 hours (configurable)
- At rebalance time:
  1. Fetch latest data
  2. Generate signals
  3. Calculate target weights
  4. Compare to current positions
  5. Execute orders to reach targets

## Parameters

Key parameters (configurable in `config/config.yaml`):

- `quantile`: Top/bottom quantile for selection (default: 0.2 = 20%)
- `ret_lookback_hours`: Return lookback period (default: 24 hours)
- `rebalance_hours`: Rebalance frequency (default: 4 hours)
- `vol_window`: Volatility calculation window (default: 72 bars)
- `target_gross_exposure`: Target exposure per side (default: 1.0 = 100%)
- `per_symbol_cap`: Max per-symbol exposure (default: 0.05 = 5%)

### Regime Parameters

- `adx_period`: ADX calculation period (default: 14)
- `ema_period`: EMA period for trend detection (default: 50)
- `adx_threshold`: ADX threshold for strong trend (default: 25)
- `ema_slope_threshold`: EMA slope threshold (default: 0.0001)
- `scale_factor`: Exposure scale in strong trends (default: 0.25)

## Failure Modes

1. **Strong Trends**: Mean reversion fails in trending markets → mitigated by regime gating
2. **Low Liquidity**: Wide spreads, execution slippage → universe filters by volume
3. **Extreme Volatility**: Large moves can overwhelm mean reversion → extreme vol guard halts trading
4. **Data Quality**: Missing or stale data → checks for minimum history and data freshness

## Tuning Guidelines

### Increase Returns
- Reduce `quantile` (trade more symbols)
- Increase `target_gross_exposure` (use more capital)
- Reduce `regime.scale_factor` (trade more in trends)

### Reduce Risk
- Increase `per_symbol_cap` (diversify more)
- Reduce `target_gross_exposure` (use less capital)
- Increase `regime.adx_threshold` (be more conservative about trend detection)

### Adapt to Market Conditions
- **Range-bound markets**: Increase `quantile`, disable regime gating
- **Trending markets**: Increase `regime.scale_factor`, reduce `quantile`
- **Volatile markets**: Increase `vol_window`, reduce `target_gross_exposure`

## Performance Expectations

- **Sharpe Ratio**: Typically 0.5-1.5 (varies by market regime)
- **Win Rate**: 45-55% (due to dollar-neutral structure)
- **Max Drawdown**: Expect 5-15% in adverse conditions
- **Turnover**: High (rebalance every 4 hours) → consider fees

## Monitoring

Monitor these metrics:
- Sharpe ratio
- Profit factor
- Max drawdown
- Win rate
- Average holding period
- Dollar neutrality (long vs short exposure)
- Regime classification (trend vs range)

