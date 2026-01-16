"""
Directional Indicator Feature
Computes market direction based on momentum fade algorithm
"""

import pandas as pd
import numpy as np
from scipy.stats import percentileofscore


def compute_directional_indicator(
    df: pd.DataFrame,
    ticker_base: str = "",
    lookback: int = 20,
    percentile_window: int = 100
) -> pd.Series:
    """
    Computes Directional Indicator feature based on the momentum fade algorithm.

    The directional indicator combines:
    - Momentum magnitude (% change over lookback period)
    - Fade direction (contrarian signal)
    - Conviction score (based on percentile rank of momentum)

    Args:
        df: DataFrame with OHLCV data (requires 'Close' column)
        ticker_base: Base ticker name (for column naming)
        lookback: Lookback period for momentum calculation (default: 20)
        percentile_window: Window for percentile rank calculation (default: 100)

    Returns:
        pd.Series: Directional indicator values (-1.0 to 1.0)
    """
    EPS = 1e-8

    df_work = df.copy()

    # Handle both 'Close' and 'close' column names
    close_col = 'Close' if 'Close' in df_work.columns else 'close'

    # 1. Momentum (% change over lookback period)
    df_work['momentum'] = 100 * (
        (df_work[close_col] - df_work[close_col].shift(lookback)) /
        (df_work[close_col].shift(lookback) + EPS)
    )

    # 2. Recent direction
    df_work['recent_direction'] = np.sign(
        df_work[close_col] - df_work[close_col].shift(lookback)
    )

    # 3. Fade direction (contrarian trade signal)
    df_work['fade_direction'] = -np.sign(
        df_work[close_col] - df_work[close_col].shift(lookback)
    )

    # 4. Momentum magnitude
    df_work['momentum_magnitude'] = np.abs(df_work['momentum'])

    # 5. Vectorized percentile rank
    def vectorized_percentile_rank(series: pd.Series, window: int) -> np.ndarray:
        """Compute rolling percentile rank efficiently"""
        values = series.to_numpy()
        result = np.full_like(values, np.nan, dtype=np.float64)

        for i in range(window - 1, len(values)):
            window_values = values[max(0, i - window + 1):i + 1]
            if len(window_values) > 0 and not np.isnan(window_values[-1]):
                result[i] = percentileofscore(window_values, window_values[-1]) / 100

        return result

    df_work['percentile_rank'] = vectorized_percentile_rank(
        df_work['momentum_magnitude'],
        percentile_window
    )

    # 6. Conviction score (tiered based on percentile)
    def ftier(p: float) -> float:
        """Convert percentile to conviction score"""
        if np.isnan(p):
            return 0.0
        if p <= 0.25:
            return 0.1
        elif p <= 0.50:
            return 0.3
        elif p <= 0.75:
            return 0.6
        else:
            return 1.0

    df_work['conviction_score'] = df_work['percentile_rank'].apply(ftier)

    # 7. Final directional indicator
    directional_indicator = df_work['fade_direction'] * df_work['conviction_score']

    return directional_indicator


def compute_directional_enhanced(
    df: pd.DataFrame,
    ticker_base: str = "",
    lookback: int = 20,
    percentile_window: int = 100,
    include_components: bool = False
) -> pd.DataFrame:
    """
    Enhanced version that returns all components of directional calculation.

    Args:
        df: DataFrame with OHLCV data
        ticker_base: Base ticker name
        lookback: Lookback period for momentum
        percentile_window: Window for percentile rank
        include_components: If True, include all intermediate calculations

    Returns:
        pd.DataFrame: DataFrame with directional_indicator and optional components
    """
    result = df.copy()

    # Compute main indicator
    result['directional_indicator'] = compute_directional_indicator(
        df, ticker_base, lookback, percentile_window
    )

    if include_components:
        # Add component calculations for analysis
        EPS = 1e-8

        result['momentum'] = 100 * (
            (result['Close'] - result['Close'].shift(lookback)) /
            (result['Close'].shift(lookback) + EPS)
        )

        result['momentum_magnitude'] = np.abs(result['momentum'])
        result['fade_direction'] = -np.sign(
            result['Close'] - result['Close'].shift(lookback)
        )

        # Compute percentile rank
        def vectorized_percentile_rank(series: pd.Series, window: int) -> np.ndarray:
            values = series.to_numpy()
            result_arr = np.full_like(values, np.nan, dtype=np.float64)

            for i in range(window - 1, len(values)):
                window_values = values[max(0, i - window + 1):i + 1]
                if len(window_values) > 0 and not np.isnan(window_values[-1]):
                    result_arr[i] = percentileofscore(window_values, window_values[-1]) / 100

            return result_arr

        result['percentile_rank'] = vectorized_percentile_rank(
            result['momentum_magnitude'],
            percentile_window
        )

        def ftier(p: float) -> float:
            if np.isnan(p):
                return 0.0
            if p <= 0.25:
                return 0.1
            elif p <= 0.50:
                return 0.3
            elif p <= 0.75:
                return 0.6
            else:
                return 1.0

        result['conviction_score'] = result['percentile_rank'].apply(ftier)

    return result
