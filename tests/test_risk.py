"""Tests for risk management."""
import pytest

from src.risk.limits import RiskLimits
from src.risk.killswitch import KillSwitch


def test_risk_limits_leverage():
    """Test leverage cap."""
    limits = RiskLimits(leverage_cap=2.0)

    equity = 100000.0
    gross_exposure = 150000.0  # 1.5x leverage

    valid, msg = limits.check_leverage(gross_exposure, equity)
    assert valid is True

    gross_exposure = 250000.0  # 2.5x leverage
    valid, msg = limits.check_leverage(gross_exposure, equity)
    assert valid is False
    assert "exceeds cap" in msg.lower()


def test_risk_limits_daily_loss():
    """Test daily loss cap."""
    limits = RiskLimits(daily_loss_cap=-0.02)

    # Start with 100k
    limits.update_equity(100000.0)

    # Lose 1%
    valid, msg = limits.check_daily_loss(99000.0)
    assert valid is True

    # Lose 3%
    valid, msg = limits.check_daily_loss(97000.0)
    assert valid is False
    assert "exceeds cap" in msg.lower()


def test_risk_limits_drawdown():
    """Test drawdown cap."""
    limits = RiskLimits(max_drawdown_cap=-0.10)

    # Start with 100k
    limits.update_equity(100000.0)

    # Drop 5%
    limits.update_equity(95000.0)
    valid, msg = limits.check_drawdown(95000.0)
    assert valid is True

    # Drop 15%
    limits.update_equity(85000.0)
    valid, msg = limits.check_drawdown(85000.0)
    assert valid is False
    assert "exceeds cap" in msg.lower()


def test_kill_switch():
    """Test kill switch."""
    kill_switch = KillSwitch(max_consecutive_errors=5)

    # Record some errors
    for _ in range(4):
        kill_switch.record_error()

    allowed, reason = kill_switch.is_trading_allowed()
    assert allowed is True

    # Record one more to trigger
    kill_switch.record_error()
    allowed, reason = kill_switch.is_trading_allowed()
    assert allowed is False
    assert "circuit breaker" in reason.lower()

    # Reset
    kill_switch.resume()
    allowed, reason = kill_switch.is_trading_allowed()
    assert allowed is True

