"""
TF Feature Calculations
Contains compute_tf_mod and compute_tf_crit functions
"""

import pandas as pd
import numpy as np
from scipy.stats import entropy

def compute_tf_mod(df, ticker_base="GC=F", bb_window=20, atr_window=14, entropy_window=14, vol_vol_window=14):
    """
    Computes the TF_mod compression score based on minute-level data.

    Args:
        df: DataFrame with OHLC data
        ticker_base: Ticker symbol
        bb_window: Bollinger Band window
        atr_window: ATR window
        entropy_window: Entropy calculation window
        vol_vol_window: Volatility of Volatility window

    Returns:
        pd.Series: TF_mod scores
    """
    print(f"\nComputing TF_mod score for {ticker_base}...")
    high_col = f'High_{ticker_base}'
    low_col = f'Low_{ticker_base}'
    close_col = f'Close_{ticker_base}'
    required_cols = [high_col, low_col, close_col]
    tf_mod_col_name = f'tf_mod_{ticker_base}'
    empty_result = pd.Series(np.nan, index=df.index, name=tf_mod_col_name)

    # Handle alternate column names
    if not all(col in df.columns for col in required_cols):
        high_col_alt = 'high' if ticker_base == 'GC=F' and 'high' in df.columns else high_col
        low_col_alt = 'low' if ticker_base == 'GC=F' and 'low' in df.columns else low_col
        close_col_alt = 'close' if ticker_base == 'GC=F' and 'close' in df.columns else close_col
        required_cols = [high_col_alt, low_col_alt, close_col_alt]

        if not all(col in df.columns for col in required_cols):
            print(f"  - Warning: Missing columns for TF_mod ({ticker_base}).")
            return empty_result
        else:
            high_col, low_col, close_col = high_col_alt, low_col_alt, close_col_alt

    if len(df) < max(bb_window, atr_window, entropy_window, vol_vol_window) + 1:
        print(f"  - Warning: Not enough data ({len(df)}) for TF_mod.")
        return empty_result

    temp_df = df.copy()

    try:
        # Bollinger Band Width
        temp_df['bb_mid'] = temp_df[close_col].rolling(window=bb_window).mean()
        temp_df['bb_std'] = temp_df[close_col].rolling(window=bb_window).std()
        temp_df['bbw'] = (4 * temp_df['bb_std'] / (temp_df['bb_mid'] + 1e-9)) * 100

        # ATR
        temp_df['tr1'] = abs(temp_df[high_col] - temp_df[low_col])
        temp_df['tr2'] = abs(temp_df[high_col] - temp_df[close_col].shift())
        temp_df['tr3'] = abs(temp_df[low_col] - temp_df[close_col].shift())
        temp_df['tr'] = temp_df[['tr1', 'tr2', 'tr3']].max(axis=1)
        temp_df['atr'] = temp_df['tr'].rolling(window=atr_window).mean()

        # Entropy Proxy
        temp_df['range'] = temp_df[high_col] - temp_df[low_col]
        temp_df['norm_range'] = (temp_df['range'] / (temp_df['atr'] + 1e-9)).fillna(0)
        temp_df['entropy_proxy'] = temp_df['norm_range'].rolling(window=entropy_window).std()

        # Volatility of Volatility
        temp_df['atr_sma'] = temp_df['atr'].rolling(window=vol_vol_window).mean()
        temp_df['atr_std'] = temp_df['atr'].rolling(window=vol_vol_window).std()
        temp_df['vol_of_vol'] = (temp_df['atr_std'] / (temp_df['atr_sma'] + 1e-9)).fillna(0)

        # Rank and scale
        bbw_rank = temp_df['bbw'].rank(pct=True).fillna(0.5)
        entropy_rank = temp_df['entropy_proxy'].rank(pct=True).fillna(0.5)
        volvol_rank = temp_df['vol_of_vol'].rank(pct=True).fillna(0.5)

        bbw_scaled = 1 / (bbw_rank + 1e-9)
        entropy_scaled = 1 / (entropy_rank + 1e-9)
        volvol_scaled = 1 / (volvol_rank + 1e-9)

        tf_mod_series = (bbw_scaled + entropy_scaled + volvol_scaled) / 3

        print(f"  - TF_mod calculation complete.")
        return tf_mod_series.rename(tf_mod_col_name).dropna()

    except Exception as e:
        print(f"  - ERROR computing TF_mod: {e}")
        import traceback
        traceback.print_exc()
        return empty_result


def compute_tf_crit(df, tf_mod_col='tf_mod', threshold=0.30, persistence=3):
    """
    Calculates the TF_crit signal based on TF_mod persistence below a threshold.

    Args:
        df: DataFrame containing TF_mod values
        tf_mod_col: Column name for TF_mod
        threshold: Threshold value
        persistence: Number of consecutive bars

    Returns:
        pd.Series: TF_crit binary signal
    """
    print(f"\nComputing TF_crit (TF_mod < {threshold} for {persistence} bars)...")

    if tf_mod_col not in df.columns:
        print(f"  - Warning: '{tf_mod_col}' not found. Cannot compute TF_crit. Returning zeros.")
        return pd.Series(0, index=df.index, name='tf_crit')

    try:
        is_compressed = df[tf_mod_col] < threshold
        tf_crit_signal = is_compressed.rolling(window=persistence).sum() >= persistence
        print("  - TF_crit calculation complete.")
        return tf_crit_signal.astype(int).fillna(0)

    except Exception as e:
        print(f"  - ERROR computing TF_crit: {e}")
        import traceback
        traceback.print_exc()
        return pd.Series(0, index=df.index, name='tf_crit')
