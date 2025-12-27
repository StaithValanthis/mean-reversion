"""Fee calculation utilities."""
from typing import Optional

from src.common.log import setup_logger

logger = setup_logger(__name__)


class FeeCalculator:
    """Calculate trading fees."""

    def __init__(
        self,
        maker_bps: float = 0.2,
        taker_bps: float = 0.55,
        funding_rate_bps: float = 0.01,
    ):
        """
        Initialize fee calculator.

        Args:
            maker_bps: Maker fee in basis points (0.2 = 0.02%)
            taker_bps: Taker fee in basis points (0.55 = 0.055%)
            funding_rate_bps: Funding rate per 8h in basis points
        """
        self.maker_bps = maker_bps
        self.taker_bps = taker_bps
        self.funding_rate_bps = funding_rate_bps

    def calculate_fee(
        self,
        notional: float,
        is_maker: bool = True,
    ) -> float:
        """
        Calculate trading fee.

        Args:
            notional: Notional value (price * quantity)
            is_maker: Whether order is maker

        Returns:
            Fee amount
        """
        fee_bps = self.maker_bps if is_maker else self.taker_bps
        return notional * (fee_bps / 10000.0)

    def calculate_funding(
        self,
        position_notional: float,
        hours: float = 8.0,
    ) -> float:
        """
        Calculate funding cost/income.

        Args:
            position_notional: Absolute position notional value
            hours: Hours to calculate funding for (default 8h = 1 funding period)

        Returns:
            Funding amount (positive = cost, negative = income)
        """
        periods = hours / 8.0
        return position_notional * (self.funding_rate_bps / 10000.0) * periods

