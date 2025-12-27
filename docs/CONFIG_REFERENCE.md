# Configuration Reference

Complete reference for all configuration options in `config/config.yaml`.

## Exchange Settings

```yaml
exchange:
  name: bybit                    # Exchange name (currently only 'bybit' supported)
  testnet: true                  # Use testnet (safe default)
  api_key_env: BYBIT_API_KEY     # Environment variable name for API key
  api_secret_env: BYBIT_API_SECRET  # Environment variable name for API secret
  testnet_env: BYBIT_TESTNET     # Optional env var override for testnet
  rate_limit_requests_per_second: 10  # API rate limit
  rate_limit_retries: 3          # Retry attempts for rate-limited requests
  request_timeout: 30            # Request timeout in seconds
```

## Universe Selection

```yaml
universe:
  top_n: 50                      # Top N symbols by 24h volume
  quote: USDT                    # Quote currency (USDT for perpetuals)
  contract_type: swap            # Contract type ('swap' for perpetuals)
  blacklist: []                  # Symbols to exclude (e.g., ["1000PEPEUSDT"])
  min_24h_volume_usdt: 10000000  # Minimum 24h volume in USDT (10M default)
  min_history_bars: 100          # Minimum historical bars required
  min_spread_bps: 5              # Minimum spread in basis points
```

## Data Settings

```yaml
data:
  timeframe: 1h                  # Candle timeframe ('1h', '4h', '1d', etc.)
  storage_path: data/            # Path for storing Parquet files
  cache_db: data/cache.sqlite    # SQLite database for metadata
  start_date: null               # Start date for backtest (null = use available)
  end_date: null                 # End date for backtest (null = use latest)
```

## Strategy Parameters

```yaml
strategy:
  quantile: 0.2                  # Top/bottom quantile for selection (0.2 = 20%)
  rebalance_hours: 4             # Rebalance frequency in hours
  ret_lookback_hours: 24         # Return lookback period in hours
  regime:
    enabled: true                # Enable regime detection
    lookback_symbol: BTCUSDT     # Symbol for regime detection
    adx_period: 14               # ADX calculation period
    ema_period: 50               # EMA period for trend detection
    adx_threshold: 25            # ADX threshold for strong trend
    ema_slope_threshold: 0.0001  # EMA slope threshold
    scale_factor: 0.25           # Exposure scale in strong trends (0.25 = 25%)
```

### Strategy Parameters Explained

- **quantile**: Fraction of symbols to long (bottom) and short (top). 0.2 means top/bottom 20%.
- **rebalance_hours**: How often to rebalance positions. 4 hours = rebalance 6 times per day.
- **ret_lookback_hours**: Period for calculating returns. 24 hours = daily returns.
- **regime.enabled**: If false, regime gating is disabled (always trade at full size).
- **regime.lookback_symbol**: Symbol to use for regime detection (usually BTCUSDT).
- **regime.adx_threshold**: ADX value above which market is considered "strong trend".
- **regime.scale_factor**: Multiply position sizes by this factor in strong trends.

## Portfolio Construction

```yaml
portfolio:
  vol_window: 72                 # Volatility calculation window (bars)
  target_gross_exposure: 1.0     # Target gross exposure per side (1.0 = 100% of equity)
  per_symbol_cap: 0.05           # Maximum per-symbol exposure (0.05 = 5% of equity)
  dollar_neutrality_tolerance: 0.02  # Tolerance for dollar neutrality (0.02 = 2%)
```

### Portfolio Parameters Explained

- **vol_window**: Number of bars to use for volatility calculation. 72 = 3 days for 1h candles.
- **target_gross_exposure**: Target exposure per side (long book and short book). 1.0 means 100% of equity on each side, 200% gross.
- **per_symbol_cap**: Maximum exposure to any single symbol as fraction of equity.
- **dollar_neutrality_tolerance**: Maximum allowed imbalance between long and short notional.

## Execution Settings

```yaml
execution:
  post_only: true                # Use post-only orders (maker orders)
  timeout_sec: 60                # Order timeout in seconds
  max_retries: 3                 # Maximum retry attempts
  partial_fill_timeout: 300      # Timeout for partial fills (5 minutes)
```

## Fee and Slippage Assumptions

```yaml
fees:
  maker_bps: 0.2                 # Maker fee in basis points (0.2 = 0.02%)
  taker_bps: 0.55                # Taker fee in basis points (0.55 = 0.055%)
  funding_rate_bps: 0.01         # Funding rate per 8h in basis points
  slippage_bps: 2                # Slippage assumption in basis points (backtest only)
```

### Fee Parameters Explained

- **maker_bps**: Fee for maker (post-only) orders. Typical Bybit rate: 0.02% = 0.2 bps.
- **taker_bps**: Fee for taker orders. Typical Bybit rate: 0.055% = 0.55 bps.
- **funding_rate_bps**: Average funding rate per 8-hour period (approximate).
- **slippage_bps**: Slippage assumption for backtesting (not used in live trading).

## Risk Management

```yaml
risk:
  leverage_cap: 2.0              # Maximum leverage (2.0 = 2x)
  daily_loss_cap: -0.02          # Maximum daily loss (-0.02 = -2%)
  max_drawdown_cap: -0.10        # Maximum drawdown from high watermark (-0.10 = -10%)
  circuit_breaker:
    enabled: true                # Enable circuit breaker
    max_consecutive_errors: 10   # Maximum consecutive errors before halt
    cooldown_seconds: 300        # Cooldown period after halt (5 minutes)
  extreme_vol_guard:
    enabled: true                # Enable extreme volatility guard
    symbol: BTCUSDT              # Symbol to monitor
    threshold_multiplier: 3.0    # Threshold multiplier (3.0 = 3x normal volatility)
    halt_duration_hours: 2       # Hours to halt after extreme volatility
```

### Risk Parameters Explained

- **leverage_cap**: Maximum allowed leverage (gross exposure / equity).
- **daily_loss_cap**: If daily loss exceeds this, bot flattens positions and stops trading until next UTC day.
- **max_drawdown_cap**: If drawdown from high watermark exceeds this, bot flattens positions.
- **circuit_breaker.max_consecutive_errors**: Number of consecutive API errors before halt.
- **extreme_vol_guard.threshold_multiplier**: If current return > threshold_multiplier * normal_vol, halt trading.

## Runtime Settings

```yaml
runtime:
  mode: paper                    # Trading mode: 'paper' or 'live'
  log_level: INFO                # Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  log_file: logs/bot.log         # Log file path
  equity_curve_file: data/equity_curve.csv  # Equity curve output file
```

### Runtime Parameters Explained

- **mode**: 'paper' = simulate orders, 'live' = place real orders.
- **log_level**: Minimum logging level. DEBUG includes all messages.
- **log_file**: Path to log file (directory will be created if needed).
- **equity_curve_file**: Path to save equity curve (for backtesting).

## Example Configurations

### Conservative (Low Risk)

```yaml
strategy:
  quantile: 0.15                 # Trade fewer symbols
  target_gross_exposure: 0.5     # Lower exposure
risk:
  leverage_cap: 1.5              # Lower leverage
  daily_loss_cap: -0.01          # Stricter daily limit
  max_drawdown_cap: -0.05        # Stricter drawdown limit
```

### Aggressive (Higher Risk/Return)

```yaml
strategy:
  quantile: 0.3                  # Trade more symbols
  target_gross_exposure: 1.5     # Higher exposure
risk:
  leverage_cap: 3.0              # Higher leverage
  daily_loss_cap: -0.03          # More lenient daily limit
  max_drawdown_cap: -0.15        # More lenient drawdown limit
```

### Range-Bound Markets

```yaml
strategy:
  quantile: 0.25                 # Trade more symbols
  regime:
    enabled: false               # Disable regime gating
```

### Trending Markets

```yaml
strategy:
  quantile: 0.15                 # Trade fewer symbols
  regime:
    scale_factor: 0.1            # Very low exposure in trends
```

