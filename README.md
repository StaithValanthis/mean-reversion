# Mean Reversion Trading Bot

A production-ready crypto mean-reversion trading bot for **Bybit USDT Perpetuals** with backtesting and live trading capabilities.

## Features

- **Cross-sectional reversal strategy**: Ranks symbols by recent returns; longs losers, shorts winners
- **Regime-aware**: Reduces exposure during strong trend regimes to avoid fading trends
- **Volatility targeting**: Equal-risk weighting with per-symbol position caps
- **Dollar neutral**: Maintains approximately equal long/short exposure
- **Robust risk management**: Leverage caps, daily loss limits, drawdown protection, circuit breakers
- **Full backtesting**: Event-driven backtest engine with realistic fees and slippage
- **Live trading**: Paper and live modes with position reconciliation and error handling

## Quick Start

### Option 1: Automated Installation (Recommended for Ubuntu/Debian)

Run the interactive installer:

```bash
chmod +x install.sh
./install.sh
```

The installer will:
- Check system requirements (Python 3.11+, Ubuntu/Debian)
- Install prerequisites if needed
- Create virtual environment and install dependencies
- Prompt for API keys and configuration
- Set up `.env` file and update `config/config.yaml`
- Optionally install systemd service for auto-start

### Option 2: Manual Installation

#### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 2. Configure

Copy `.env.example` to `.env` and optionally add your Bybit API keys:

```bash
cp .env.example .env
# Edit .env if you want to use real API keys (default uses testnet)
```

### 3. Download Data

Download historical data for backtesting:

```bash
python scripts/download_data.py --config config/config.yaml --days 30 --universe
```

## Parameter/Timeframe Optimization

Run a small grid-search (with optional walk-forward scoring):

```bash
python scripts/optimize.py --config config/config.yaml --output opt_results/
```

See `docs/OPTIMIZATION.md` for details.

### 4. Run Backtest (Manual Install)

```bash
# If using virtual environment, activate it first:
# source .venv/bin/activate

python scripts/backtest.py --config config/config.yaml
```

Results are saved to `data/equity_curve.csv` and `data/metrics.json`.

### 5. Run Paper Trading (Manual Install)

```bash
# If using virtual environment, activate it first:
# source .venv/bin/activate

python scripts/live.py --config config/config.yaml --paper
```

## Project Structure

```
.
├── config/
│   └── config.yaml          # Main configuration file
├── src/
│   ├── common/              # Common utilities (logging, time, math)
│   ├── exchange/            # Exchange wrapper (Bybit)
│   ├── data/                # Data download, storage, universe selection
│   ├── strategies/          # Strategy implementations
│   ├── portfolio/           # Portfolio construction and rebalancing
│   ├── execution/           # Order execution and slippage models
│   ├── risk/                # Risk management and kill switches
│   ├── backtest/            # Backtest engine and metrics
│   └── live/                # Live trading engine
├── scripts/
│   ├── download_data.py     # Download historical data
│   ├── backtest.py          # Run backtest
│   └── live.py              # Run live trading
├── tests/                   # Unit tests
└── docs/                    # Documentation
```

## Configuration

All configuration is in `config/config.yaml`. See [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md) for complete documentation.

Key configuration sections:
- `exchange`: API settings, testnet/mainnet
- `universe`: Symbol selection criteria
- `strategy`: Strategy parameters (quantile, rebalance frequency, regime settings)
- `portfolio`: Volatility targeting, position caps
- `risk`: Leverage caps, loss limits, circuit breakers
- `runtime`: Logging, mode (paper/live)

## Documentation

- **[Strategy Documentation](docs/STRATEGY.md)**: Detailed explanation of the strategy logic
- **[Runbook](docs/RUNBOOK.md)**: Operational guide for running the bot
- **[Config Reference](docs/CONFIG_REFERENCE.md)**: Complete configuration documentation

## Strategy Overview

The bot implements a **cross-sectional short-term reversal** strategy:

1. **Signal Generation**: Calculates 24-hour returns for all symbols, ranks them, and selects:
   - **Long**: Bottom 20% (recent losers)
   - **Short**: Top 20% (recent winners)

2. **Regime Gating**: Uses ADX and EMA slope on BTC to detect strong trends. In strong trends, reduces mean-reversion exposure to 25% of normal size.

3. **Portfolio Construction**:
   - Volatility targeting: weights inversely proportional to volatility
   - Dollar neutral: long notional ≈ short notional
   - Position caps: max 5% per symbol, 200% gross exposure

4. **Rebalancing**: Rebalances every 4 hours (configurable)

## Risk Management

- **Leverage cap**: Maximum 2x leverage (configurable)
- **Daily loss limit**: -2% daily loss triggers position flattening
- **Max drawdown**: -10% from high watermark triggers halt
- **Circuit breaker**: 10 consecutive API errors halt trading
- **Extreme volatility guard**: 3x normal volatility halts trading for 2 hours

## Safety Features

- **Default mode**: Paper trading on testnet
- **Position limits**: Per-symbol and total exposure caps
- **Kill switch**: Automatic halt and position flattening on errors
- **Logging**: Comprehensive structured logging

## Testing

Run tests:

```bash
pytest tests/
```

## Requirements

- Python 3.11+
- Bybit API keys (for live trading) or testnet access
- Sufficient disk space for data storage

## License

See LICENSE file for details.

## Disclaimer

This software is for educational and research purposes only. Trading cryptocurrencies carries significant risk. Use at your own risk. The authors are not responsible for any financial losses.

