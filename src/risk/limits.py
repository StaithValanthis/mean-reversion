"""Risk limits and monitoring."""
from datetime import datetime, timezone
from typing import Dict, Optional

from src.common.log import setup_logger

logger = setup_logger(__name__)


class RiskLimits:
    """Monitor and enforce risk limits."""

    def __init__(
        self,
        leverage_cap: float = 2.0,
        daily_loss_cap: float = -0.02,
        max_drawdown_cap: float = -0.10,
    ):
        """
        Initialize risk limits.

        Args:
            leverage_cap: Maximum leverage (e.g., 2.0 = 2x)
            daily_loss_cap: Maximum daily loss as fraction (e.g., -0.02 = -2%)
            max_drawdown_cap: Maximum drawdown from high watermark (e.g., -0.10 = -10%)
        """
        self.leverage_cap = leverage_cap
        self.daily_loss_cap = daily_loss_cap
        self.max_drawdown_cap = max_drawdown_cap

        self.equity_high_watermark: Optional[float] = None
        self.daily_start_equity: Optional[float] = None
        self.daily_start_date: Optional[datetime] = None

    def update_equity(self, equity: float):
        """Update equity and high watermark."""
        if self.equity_high_watermark is None or equity > self.equity_high_watermark:
            self.equity_high_watermark = equity

        # Reset daily tracking at start of new UTC day
        now = datetime.now(timezone.utc)
        if (
            self.daily_start_date is None
            or now.date() != self.daily_start_date.date()
        ):
            self.daily_start_equity = equity
            self.daily_start_date = now
            logger.info(f"New trading day started: equity={equity:.2f}")

    def check_leverage(
        self,
        gross_exposure: float,
        equity: float,
    ) -> tuple[bool, Optional[str]]:
        """
        Check leverage limit.

        Args:
            gross_exposure: Gross exposure (sum of absolute position values)
            equity: Current equity

        Returns:
            Tuple of (is_valid, error_message)
        """
        if equity <= 0:
            return False, "Equity must be positive"

        leverage = gross_exposure / equity if equity > 0 else 0
        if leverage > self.leverage_cap:
            return False, f"Leverage {leverage:.2f}x exceeds cap {self.leverage_cap}x"
        return True, None

    def check_daily_loss(self, equity: float) -> tuple[bool, Optional[str]]:
        """
        Check daily loss limit.

        Args:
            equity: Current equity

        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.daily_start_equity is None:
            self.daily_start_equity = equity
            return True, None

        daily_return = (equity - self.daily_start_equity) / self.daily_start_equity
        if daily_return < self.daily_loss_cap:
            return (
                False,
                f"Daily loss {daily_return:.2%} exceeds cap {self.daily_loss_cap:.2%}",
            )
        return True, None

    def check_drawdown(self, equity: float) -> tuple[bool, Optional[str]]:
        """
        Check maximum drawdown limit.

        Args:
            equity: Current equity

        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.equity_high_watermark is None:
            self.equity_high_watermark = equity
            return True, None

        drawdown = (equity - self.equity_high_watermark) / self.equity_high_watermark
        if drawdown < self.max_drawdown_cap:
            return (
                False,
                f"Drawdown {drawdown:.2%} exceeds cap {self.max_drawdown_cap:.2%}",
            )
        return True, None

    def check_all(
        self,
        equity: float,
        gross_exposure: float = 0.0,
    ) -> tuple[bool, Optional[str]]:
        """
        Check all risk limits.

        Args:
            equity: Current equity
            gross_exposure: Gross exposure

        Returns:
            Tuple of (is_valid, error_message)
        """
        self.update_equity(equity)

        # Check leverage
        valid, msg = self.check_leverage(gross_exposure, equity)
        if not valid:
            return False, msg

        # Check daily loss
        valid, msg = self.check_daily_loss(equity)
        if not valid:
            return False, msg

        # Check drawdown
        valid, msg = self.check_drawdown(equity)
        if not valid:
            return False, msg

        return True, None

