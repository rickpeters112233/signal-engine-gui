"""
CVD (Cumulative Volume Delta) Feature Calculation
Contains compute_cvd function for volume delta analysis with status and momentum tracking
"""

import pandas as pd
import numpy as np
from scipy.stats import percentileofscore


def compute_cvd(df, ticker_base="GC=F", momentum_lookback=5, pct_lookback=100):
    """
    Computes Cumulative Volume Delta (CVD) with status and momentum tracking.

    Uses CONTINUOUS ACCUMULATION (no daily reset).

    The CVD approximation calculates buy vs sell volume based on where price closed
    within the bar's range. This provides insight into buying/selling pressure.

    Args:
        df: DataFrame with OHLCV data
        ticker_base: Ticker symbol
        momentum_lookback: Number of bars to calculate momentum change (default: 5)
        pct_lookback: Lookback period for percentile rank calculation (default: 100)

    Returns:
        pd.DataFrame: DataFrame with CVD columns:
            - cvd: Cumulative volume delta value
            - cvd_pct: Percentile rank of CVD (0-1)
            - cvd_status: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
            - cvd_momentum: 'RISING' | 'FALLING' | 'FLAT'
            - delta: Per-bar volume delta
    """
    print(f"\nComputing CVD (Cumulative Volume Delta) for {ticker_base}...")

    # Config
    EPS = 1e-8

    # Column names
    high_col = f'High_{ticker_base}'
    low_col = f'Low_{ticker_base}'
    close_col = f'Close_{ticker_base}'
    open_col = f'Open_{ticker_base}'
    vol_col = f'Volume_{ticker_base}'
    required_cols = [high_col, low_col, close_col, open_col, vol_col]

    # Output column names
    output_cols = [
        f'cvd_{ticker_base}',
        f'cvd_pct_{ticker_base}',
        f'cvd_status_{ticker_base}',
        f'cvd_momentum_{ticker_base}',
        f'delta_{ticker_base}'
    ]

    empty_result = pd.DataFrame(index=df.index, columns=output_cols)
    for col in output_cols:
        if col.endswith('_status') or col.endswith('_momentum'):
            empty_result[col] = 'NEUTRAL' if 'status' in col else 'FLAT'
        else:
            empty_result[col] = np.nan

    if not all(col in df.columns for col in required_cols):
        print(f"  - Warning: Missing columns for CVD ({ticker_base}). Need {required_cols}.")
        return empty_result

    if len(df) < momentum_lookback + 1:
        print(f"  - Warning: Not enough data ({len(df)}) for CVD.")
        return empty_result

    temp_df = pd.DataFrame(index=df.index)

    try:
        # 1. Check for actual bid/ask volume data (more accurate)
        ask_vol_col = f'AskVolume_{ticker_base}'
        bid_vol_col = f'BidVolume_{ticker_base}'

        if ask_vol_col in df.columns and bid_vol_col in df.columns:
            print("  - Using actual bid/ask volume data for delta calculation")
            temp_df['delta'] = df[ask_vol_col] - df[bid_vol_col]
        else:
            # 2. Approximate delta using bar structure
            # Formula: allocates volume proportionally based on where close is in the range
            print("  - Approximating delta from bar structure")

            high = df[high_col]
            low = df[low_col]
            open_ = df[open_col]
            close = df[close_col]
            volume = df[vol_col]

            # Range of the bar
            bar_range = high - low + EPS

            # Calculate buy/sell volume based on close position
            def compute_bar_delta(row_high, row_low, row_open, row_close, row_volume):
                """
                Approximates buy vs sell volume based on where price closed.
                Bullish bar (close > open): allocate more to buy side
                Bearish bar (close < open): allocate more to sell side
                """
                range_ = row_high - row_low + EPS

                if row_close >= row_open:
                    # Bullish bar
                    buy_vol = row_volume * (row_close - row_open) / range_
                    sell_vol = row_volume - buy_vol
                else:
                    # Bearish bar
                    sell_vol = row_volume * (row_open - row_close) / range_
                    buy_vol = row_volume - sell_vol

                return buy_vol - sell_vol

            # Vectorized calculation
            bullish_mask = close >= open_
            temp_df['delta'] = np.where(
                bullish_mask,
                volume * (close - open_) / bar_range,  # Bullish: net buy
                -volume * (open_ - close) / bar_range  # Bearish: net sell
            )

            # Handle doji bars (open == close) using previous close direction
            doji_mask = close == open_
            prev_close = df[close_col].shift(1)
            temp_df.loc[doji_mask, 'delta'] = np.where(
                close[doji_mask] > prev_close[doji_mask],
                volume[doji_mask],
                np.where(
                    close[doji_mask] < prev_close[doji_mask],
                    -volume[doji_mask],
                    0
                )
            )

        # 3. Calculate CVD (continuous accumulation)
        temp_df['cvd'] = temp_df['delta'].cumsum()

        # 4. Calculate CVD percentile rank
        def rolling_percentile_rank(series, window):
            def pr(x):
                if len(x) < window:
                    return np.nan
                return percentileofscore(x[:-1], x.iloc[-1]) / 100
            return series.rolling(window).apply(pr, raw=False)

        temp_df['cvd_pct'] = rolling_percentile_rank(temp_df['cvd'], pct_lookback)

        # 5. Determine CVD Status (latest value direction)
        def get_status(cvd_val):
            if pd.isna(cvd_val):
                return 'NEUTRAL'
            elif cvd_val > 0:
                return 'BULLISH'
            elif cvd_val < 0:
                return 'BEARISH'
            else:
                return 'NEUTRAL'

        temp_df['cvd_status'] = temp_df['cvd'].apply(get_status)

        # 6. Calculate CVD Momentum (change over lookback period)
        cvd_change = temp_df['cvd'] - temp_df['cvd'].shift(momentum_lookback)

        def get_momentum(change_val):
            if pd.isna(change_val):
                return 'FLAT'
            elif change_val > 0:
                return 'RISING'
            elif change_val < 0:
                return 'FALLING'
            else:
                return 'FLAT'

        temp_df['cvd_momentum'] = cvd_change.apply(get_momentum)

        # Build output DataFrame
        result = pd.DataFrame(index=df.index)
        result[f'cvd_{ticker_base}'] = temp_df['cvd'].round(0)
        result[f'cvd_pct_{ticker_base}'] = temp_df['cvd_pct'].round(3)
        result[f'cvd_status_{ticker_base}'] = temp_df['cvd_status']
        result[f'cvd_momentum_{ticker_base}'] = temp_df['cvd_momentum']
        result[f'delta_{ticker_base}'] = temp_df['delta'].round(0)

        # Log summary
        latest_status = temp_df['cvd_status'].iloc[-1] if len(temp_df) > 0 else 'N/A'
        latest_momentum = temp_df['cvd_momentum'].iloc[-1] if len(temp_df) > 0 else 'N/A'
        print(f"  - CVD calculation complete. Status: {latest_status}, Momentum: {latest_momentum}")

        return result

    except Exception as e:
        print(f"  - ERROR computing CVD: {e}")
        import traceback
        traceback.print_exc()
        return empty_result
