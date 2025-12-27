"""Kill switch for emergency stops."""
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from src.common.log import setup_logger

logger = setup_logger(__name__)


class KillSwitch:
    """Circuit breaker and kill switch."""

    def __init__(
        self,
        max_consecutive_errors: int = 10,
        cooldown_seconds: int = 300,
        extreme_vol_enabled: bool = True,
        extreme_vol_threshold: float = 3.0,
        extreme_vol_halt_hours: int = 2,
    ):
        """
        Initialize kill switch.

        Args:
            max_consecutive_errors: Maximum consecutive errors before halt
            cooldown_seconds: Cooldown period after error burst
            extreme_vol_enabled: Enable extreme volatility guard
            extreme_vol_threshold: Threshold multiplier for extreme volatility
            extreme_vol_halt_hours: Hours to halt after extreme volatility
        """
        self.max_consecutive_errors = max_consecutive_errors
        self.cooldown_seconds = cooldown_seconds
        self.extreme_vol_enabled = extreme_vol_enabled
        self.extreme_vol_threshold = extreme_vol_threshold
        self.extreme_vol_halt_hours = extreme_vol_halt_hours

        self.consecutive_errors = 0
        self.last_error_time: Optional[float] = None
        self.extreme_vol_halt_until: Optional[datetime] = None
        self.is_halted = False
        self.halt_reason: Optional[str] = None

    def record_error(self):
        """Record an error."""
        self.consecutive_errors += 1
        self.last_error_time = time.time()

        if self.consecutive_errors >= self.max_consecutive_errors:
            self.halt(f"Circuit breaker: {self.consecutive_errors} consecutive errors")
            logger.error(f"Kill switch activated: {self.halt_reason}")

    def record_success(self):
        """Record a successful operation (resets error count)."""
        if self.consecutive_errors > 0:
            logger.info(f"Reset error counter (was {self.consecutive_errors})")
        self.consecutive_errors = 0

    def check_extreme_volatility(
        self,
        current_return: float,
        normal_volatility: float,
    ) -> bool:
        """
        Check for extreme volatility event.

        Args:
            current_return: Current period return
            normal_volatility: Normal volatility level

        Returns:
            True if extreme volatility detected
        """
        if not self.extreme_vol_enabled:
            return False

        if normal_volatility <= 0:
            return False

        abs_return = abs(current_return)
        threshold = self.extreme_vol_threshold * normal_volatility

        if abs_return > threshold:
            halt_until = datetime.now(timezone.utc) + timedelta(
                hours=self.extreme_vol_halt_hours
            )
            self.extreme_vol_halt_until = halt_until
            self.halt(
                f"Extreme volatility: {abs_return:.2%} > {threshold:.2%} "
                f"(normal vol: {normal_volatility:.2%})"
            )
            logger.error(f"Extreme volatility detected: {self.halt_reason}")
            return True

        return False

    def halt(self, reason: str):
        """Halt trading."""
        self.is_halted = True
        self.halt_reason = reason
        logger.critical(f"Kill switch HALTS trading: {reason}")

    def resume(self):
        """Resume trading (manual intervention)."""
        self.is_halted = False
        self.halt_reason = None
        self.consecutive_errors = 0
        self.extreme_vol_halt_until = None
        logger.info("Kill switch RESUMES trading")

    def is_trading_allowed(self) -> tuple[bool, Optional[str]]:
        """
        Check if trading is allowed.

        Returns:
            Tuple of (is_allowed, reason_if_halted)
        """
        if not self.is_halted:
            return True, None

        # Check if cooldown period has passed
        if self.last_error_time:
            elapsed = time.time() - self.last_error_time
            if elapsed > self.cooldown_seconds:
                self.resume()
                return True, None

        # Check if extreme vol halt has expired
        if self.extreme_vol_halt_until:
            if datetime.now(timezone.utc) >= self.extreme_vol_halt_until:
                self.resume()
                return True, None

        return False, self.halt_reason

