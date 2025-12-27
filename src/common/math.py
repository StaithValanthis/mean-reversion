"""Mathematical utilities."""
import numpy as np


def safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    """Divide with zero protection."""
    result = np.zeros_like(numerator, dtype=float)
    mask = denominator != 0
    result[mask] = numerator[mask] / denominator[mask]
    return result


def rolling_volatility(
    returns: np.ndarray,
    window: int,
) -> np.ndarray:
    """
    Calculate rolling volatility (annualized).

    Args:
        returns: Array of returns
        window: Rolling window size

    Returns:
        Array of volatility values (same length as returns, NaNs for initial values)
    """
    if len(returns) < window:
        return np.full(len(returns), np.nan)

    vol = np.full(len(returns), np.nan)
    for i in range(window - 1, len(returns)):
        window_returns = returns[i - window + 1 : i + 1]
        vol[i] = np.std(window_returns, ddof=1)

    # Annualize (assuming hourly returns, 365*24 hours per year)
    vol *= np.sqrt(365 * 24)
    return vol


def rank_normalize(arr: np.ndarray) -> np.ndarray:
    """
    Rank normalize array to [0, 1] range.

    Args:
        arr: Input array

    Returns:
        Rank-normalized array (0 = min, 1 = max)
    """
    if len(arr) == 0:
        return arr
    ranks = np.argsort(np.argsort(arr))
    return ranks / (len(arr) - 1) if len(arr) > 1 else np.array([0.5])


def quantile_cut(
    arr: np.ndarray,
    q: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Cut array into quantiles.

    Args:
        arr: Input array
        q: Quantile threshold (e.g., 0.2 for bottom/top 20%)

    Returns:
        Tuple of (bottom_mask, middle_mask, top_mask) boolean arrays
    """
    if len(arr) == 0:
        return (
            np.array([], dtype=bool),
            np.array([], dtype=bool),
            np.array([], dtype=bool),
        )

    bottom_threshold = np.nanquantile(arr, q)
    top_threshold = np.nanquantile(arr, 1 - q)

    bottom_mask = arr <= bottom_threshold
    top_mask = arr >= top_threshold
    middle_mask = ~(bottom_mask | top_mask)

    return bottom_mask, middle_mask, top_mask

