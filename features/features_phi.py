"""
Phi Sigma Feature Calculation
Contains compute_phi_sigma function for volatility regime scoring
"""

import pandas as pd
import numpy as np

def compute_phi_sigma(df, ticker_base="GC=F", window=14, ma_period=240):
    """
    Computes the Phi Sigma volatility regime score based on minute OHLC data.

    Returns the ATR Z-score (standard deviations from mean), NOT the CDF.
    This allows for thresholds like phi_sigma >= 4.0 (4 std devs above mean)
    which indicate extreme volatility spikes.

    Args:
        df: DataFrame with OHLC data
        ticker_base: Ticker symbol
        window: ATR calculation window
        ma_period: Moving average period for baseline

    Returns:
        pd.Series: Phi Sigma Z-scores (can be negative or positive)
            - phi_sigma >= 4.0: Extreme high volatility (BUY signal condition)
            - phi_sigma <= -4.0: Extreme low volatility (SELL signal condition)
            - phi_sigma ~= 0: Average volatility
    """
    print(f"\nComputing Phi Sigma for {ticker_base} (ATR({window}), MA({ma_period}))...")

    high_col = f'High_{ticker_base}'
    low_col = f'Low_{ticker_base}'
    close_col = f'Close_{ticker_base}'
    required_cols = [high_col, low_col, close_col]
    phi_sigma_col_name = f'phi_sigma_{ticker_base}'

    # Create a default result Series with the correct name and NaN values
    empty_result = pd.Series(np.nan, index=df.index, name=phi_sigma_col_name)

    if not all(col in df.columns for col in required_cols):
        print(f"  - Warning: Missing columns for Phi Sigma ({ticker_base}). Need {required_cols}. Returning NaNs.")
        return empty_result

    if len(df) < max(window, ma_period) + 1:
        print(f"  - Warning: Not enough data ({len(df)}) for Phi Sigma calculations. Returning NaNs.")
        return empty_result

    temp_df = pd.DataFrame(index=df.index)

    try:
        # Calculate ATR
        temp_df['tr1'] = abs(df[high_col] - df[low_col])
        temp_df['tr2'] = abs(df[high_col] - df[close_col].shift())
        temp_df['tr3'] = abs(df[low_col] - df[close_col].shift())
        temp_df['tr'] = temp_df[['tr1', 'tr2', 'tr3']].max(axis=1)
        temp_df['atr'] = temp_df['tr'].rolling(window=window).mean()

        # Calculate ATR MA and Standard Deviation
        temp_df['atr_ma'] = temp_df['atr'].rolling(window=ma_period).mean()
        temp_df['atr_std'] = temp_df['atr'].rolling(window=ma_period).std()

        # Calculate Z-score of ATR (raw Z-score, NOT CDF transformed)
        # This allows thresholds like >= 4.0 to work as designed in backtesting
        phi_sigma_series = pd.Series(
            (temp_df['atr'] - temp_df['atr_ma']) / (temp_df['atr_std'] + 1e-9),
            index=df.index,
            name=phi_sigma_col_name
        )

        print(f"  - Phi Sigma calculation successful.")
        return phi_sigma_series

    except Exception as e:
        print(f"  - ERROR during Phi Sigma calculation: {e}")
        import traceback
        traceback.print_exc()
        return empty_result
