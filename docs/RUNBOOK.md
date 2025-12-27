# Runbook

## Prerequisites

1. Python 3.11+
2. Bybit API keys (for live trading) or testnet access
3. Sufficient disk space for data storage (several GB for full history)

## Initial Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys (or leave empty for testnet)
   ```

3. **Review configuration:**
   - Edit `config/config.yaml` to adjust strategy parameters
   - Default settings are conservative (paper mode, testnet)

## Running the Bot

### Data Download

Download historical data for backtesting:
```bash
# Download for universe (top 50 symbols)
python scripts/download_data.py --config config/config.yaml --days 30 --universe

# Download for specific symbols
python scripts/download_data.py --config config/config.yaml --days 30 --symbols BTCUSDT ETHUSDT
```

### Backtesting

Run backtest:
```bash
python scripts/backtest.py --config config/config.yaml
```

Results are saved to:
- `data/equity_curve.csv`: Equity curve over time
- `data/metrics.json`: Performance metrics

### Paper Trading

Run in paper mode (simulated orders):
```bash
python scripts/live.py --config config/config.yaml --paper
```

### Live Trading

**WARNING**: Live trading places real orders with real capital. Use at your own risk.

1. **Enable testnet in config:**
   ```yaml
   exchange:
     testnet: true
   ```

2. **Test with paper mode first:**
   ```bash
   python scripts/live.py --config config/config.yaml --paper
   ```

3. **Switch to testnet:**
   ```bash
   # Ensure testnet: true in config
   python scripts/live.py --config config/config.yaml --paper
   ```

4. **Live trading (REAL MONEY):**
   ```bash
   # Set testnet: false in config
   # Set runtime.mode: live in config
   python scripts/live.py --config config/config.yaml --live
   ```

## Environment Variables

Set these in `.env`:

- `BYBIT_API_KEY`: Your Bybit API key
- `BYBIT_API_SECRET`: Your Bybit API secret
- `BYBIT_TESTNET`: Set to `true` for testnet (optional, can use config)

## Stopping the Bot Safely

1. **Graceful shutdown:**
   - Press `Ctrl+C` to stop
   - Bot will flatten all positions before exiting

2. **Emergency stop:**
   - Kill the process
   - Manually close positions on exchange
   - Check logs for any pending orders

## Interpreting Logs

### Log Levels

- `INFO`: Normal operations (rebalances, orders)
- `WARNING`: Non-fatal issues (partial fills, risk warnings)
- `ERROR`: Errors that may affect trading
- `CRITICAL`: Kill switch activated, positions flattened

### Key Log Messages

- `Starting rebalance...`: Beginning rebalance process
- `Signal generation: X longs, Y shorts`: Signals generated
- `Executing N rebalance orders`: Orders being placed
- `Risk limit breached`: Risk limit triggered, positions flattened
- `Kill switch activated`: Trading halted due to errors/volatility

## Monitoring

### Daily Checks

1. Review log file: `logs/bot.log`
2. Check equity curve: `data/equity_curve.csv`
3. Verify positions on exchange match bot state

### Weekly Review

1. Analyze metrics: `data/metrics.json`
2. Review drawdown and Sharpe ratio
3. Check for any error patterns in logs
4. Verify strategy performance vs backtest

## Troubleshooting

### Bot won't start

- Check API keys in `.env`
- Verify config file is valid YAML
- Check disk space for data storage

### No symbols in universe

- Reduce `universe.min_24h_volume_usdt` threshold
- Check exchange connectivity
- Verify testnet/mainnet settings match API keys

### Frequent kill switch activations

- Check exchange API status
- Review error logs for patterns
- Increase `circuit_breaker.max_consecutive_errors` if legitimate errors

### Positions not executing

- Check exchange balance
- Verify testnet vs mainnet settings
- Review order execution logs for errors

## Maintenance

### Regular Tasks

1. **Weekly**: Download latest data for backtesting
2. **Monthly**: Review and update configuration
3. **Quarterly**: Full backtest on updated data

### Data Management

- Clean old data files if disk space is limited
- Archive equity curves and metrics for historical analysis
- Backup configuration files

## Emergency Procedures

### Kill Switch Activated

1. Bot automatically flattens positions
2. Review logs to determine cause
3. Fix underlying issue
4. Manually resume (kill switch resets after cooldown)

### Exchange API Issues

1. Bot will record errors and activate kill switch if threshold exceeded
2. Check exchange status page
3. Wait for API recovery
4. Restart bot when stable

### Extreme Market Conditions

1. Bot halts trading if extreme volatility detected
2. Review `extreme_vol_guard` settings
3. Resume after cooldown period

## Support

For issues or questions:
1. Check logs: `logs/bot.log`
2. Review configuration: `config/config.yaml`
3. Consult documentation: `docs/`

