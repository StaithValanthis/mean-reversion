# Mean Reversion Trading Bot

A production-ready crypto mean-reversion trading bot for Bybit USDT Perpetuals.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and add your Bybit API keys (or leave empty for testnet)
   ```

3. **Download historical data:**
   ```bash
   python scripts/download_data.py --config config/config.yaml --days 30 --universe
   ```

4. **Run backtest:**
   ```bash
   python scripts/backtest.py --config config/config.yaml
   ```

5. **Run live (paper trading):**
   ```bash
   python scripts/live.py --config config/config.yaml --paper
   ```

## Features

- **Cross-sectional reversal strategy**: Ranks symbols by recent returns and longs losers, shorts winners
- **Regime gating**: Reduces exposure during strong trend regimes
- **Volatility targeting**: Equal-risk weighting with per-symbol caps
- **Dollar neutrality**: Maintains approximately equal long/short exposure
- **Risk management**: Leverage caps, daily loss limits, drawdown protection, circuit breakers
- **Backtesting**: Full backtest engine with realistic fees and slippage
- **Live trading**: Paper and live modes with position reconciliation

## Configuration

See `docs/CONFIG_REFERENCE.md` for detailed configuration options.

## Documentation

- [Strategy Documentation](STRATEGY.md) - Strategy logic and parameters
- [Runbook](RUNBOOK.md) - Operational guide for running the bot
- [Config Reference](CONFIG_REFERENCE.md) - Complete configuration documentation

## Safety

- **Default mode**: Paper trading on testnet
- **Position limits**: Per-symbol and total exposure caps
- **Risk limits**: Daily loss caps, max drawdown protection
- **Circuit breakers**: Automatic halt on error bursts or extreme volatility
- **Kill switch**: Emergency position flattening

## Testing

Run tests:
```bash
pytest tests/
```

## License

See LICENSE file for details.

