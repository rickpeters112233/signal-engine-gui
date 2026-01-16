"""
TVI (Time-Value Index) Enhanced Feature Calculation - Updated Version
Contains compute_tvi_enhanced function with VWAP gating, Donchian Channel, and CVD flow modulation
"""

import pandas as pd
import numpy as np
from scipy.stats import percentileofscore


def compute_tvi_enhanced(df, ticker_base="GC=F", atr_window=14, median_vol_period=20,
                          dc_period=20, vwap_period=240, norm_period=30, cvd_lookback=100,
                          tvi_gated_target=0.118, tvi_gated_threshold=0.01):
    """
    Computes enhanced TVI with structure gating and CVD flow modulation.

    This version implements:
    - ATR-based raw TVI with volume ratio
    - Donchian Channel price position
    - Rolling VWAP deviation
    - Structure gate combining VWAP deviation and price position
    - TVI gated reversal flag
    - CVD flow modulation for final TVI
    - Normalization with quantile-based min/max

    Args:
        df: DataFrame with OHLCV data
        ticker_base: Ticker symbol
        atr_window: ATR calculation window (default: 14)
        median_vol_period: Period for median volume (default: 20)
        dc_period: Donchian Channel period (default: 20)
        vwap_period: Rolling VWAP period (default: 240 = 4 hours)
        norm_period: Normalization window (default: 30)
        cvd_lookback: CVD percentile lookback (default: 100)
        tvi_gated_target: Target TVI value for reversal (default: 0.118)
        tvi_gated_threshold: Threshold around target (default: 0.01)

    Returns:
        pd.DataFrame: DataFrame with TVI features and flags
    """
    print(f"\nComputing Enhanced TVI w/ Structure Gating for {ticker_base}...")

    # Config
    EPS = 1e-8
    W1 = 0.3  # VWAP weight
    W2 = 0.2  # DC weight
    LAMBDA = 0.3  # Flow modulation

    # Column names
    high_col = f'High_{ticker_base}'
    low_col = f'Low_{ticker_base}'
    close_col = f'Close_{ticker_base}'
    open_col = f'Open_{ticker_base}'
    vol_col = f'Volume_{ticker_base}'
    required_cols = [high_col, low_col, close_col, open_col, vol_col]

    # Output column names
    output_cols = [
        f'tvi_norm_{ticker_base}',
        f'vwap_{ticker_base}',
        f'vwap_dev_{ticker_base}',
        f'tvi_gated_reversal_flag_{ticker_base}',
        f'cvd_{ticker_base}',
        f'cvd_pct_{ticker_base}'
    ]

    empty_result = pd.DataFrame(np.nan, index=df.index, columns=output_cols)

    if not all(col in df.columns for col in required_cols):
        print(f"  - Warning: Missing columns for Enhanced TVI ({ticker_base}). Need {required_cols}.")
        return empty_result

    min_required = max(atr_window, median_vol_period, dc_period, vwap_period, norm_period, cvd_lookback) + 1
    if len(df) < min_required:
        print(f"  - Warning: Not enough data ({len(df)}) for Enhanced TVI. Need at least {min_required}.")
        return empty_result

    temp_df = pd.DataFrame(index=df.index)

    try:
        # 1. Calculate ATR(14) using EMA
        temp_df['tr1'] = abs(df[high_col] - df[low_col])
        temp_df['tr2'] = abs(df[high_col] - df[close_col].shift())
        temp_df['tr3'] = abs(df[low_col] - df[close_col].shift())
        temp_df['tr'] = temp_df[['tr1', 'tr2', 'tr3']].max(axis=1)
        temp_df['atr'] = temp_df['tr'].ewm(span=atr_window, adjust=False).mean()

        # 2. Calculate volume ratio (current volume / median volume)
        temp_df['v_typical'] = df[vol_col].rolling(median_vol_period).median()
        temp_df['v_t'] = np.where(temp_df['v_typical'] == 0, 0, df[vol_col] / temp_df['v_typical'])

        # 3. Calculate raw TVI
        delta_t = 1
        temp_df['tvi_raw'] = (temp_df['atr'] * temp_df['v_t'] * delta_t) / 6.0

        # 4. Donchian Channel price position
        temp_df['dc_high'] = df[high_col].rolling(dc_period).max()
        temp_df['dc_low'] = df[low_col].rolling(dc_period).min()
        temp_df['price_position'] = (df[close_col] - temp_df['dc_low']) / (
            temp_df['dc_high'] - temp_df['dc_low'] + EPS
        )

        # 5. Rolling VWAP (4-hour)
        temp_df['pv'] = df[close_col] * df[vol_col]
        temp_df['cum_pv'] = temp_df['pv'].rolling(vwap_period).sum()
        temp_df['cum_vol'] = df[vol_col].rolling(vwap_period).sum()
        temp_df['vwap'] = temp_df['cum_pv'] / (temp_df['cum_vol'] + EPS)

        # 6. VWAP deviation (normalized by ATR)
        temp_df['vwap_dev'] = abs(df[close_col] - temp_df['vwap']) / (temp_df['atr'] + EPS)

        # 7. Structure gate
        temp_df['structure_gate'] = 1 + W1 * temp_df['vwap_dev'] + W2 * (1 - temp_df['price_position'])

        # 8. Gated TVI
        temp_df['tvi_gated'] = temp_df['tvi_raw'] * temp_df['structure_gate']

        # 9. TVI Gated Reversal Flag
        temp_df['tvi_gated_reversal_flag'] = (
            abs(temp_df['tvi_gated'] - tvi_gated_target) < tvi_gated_threshold
        ).astype(int)

        # 10. Normalization using rolling quantiles
        temp_df['min_n'] = temp_df['tvi_gated'].rolling(norm_period).quantile(0.05)
        temp_df['max_n'] = temp_df['tvi_gated'].rolling(norm_period).quantile(0.95)
        temp_df['tvi_n'] = (temp_df['tvi_gated'] - temp_df['min_n']) / (
            temp_df['max_n'] - temp_df['min_n'] + EPS
        )
        temp_df['tvi_n'] = temp_df['tvi_n'].clip(0, 1)

        # 11. CVD calculation (for flow modulation)
        # Check for AskVolume/BidVolume columns (tick data)
        ask_vol_col = f'AskVolume_{ticker_base}'
        bid_vol_col = f'BidVolume_{ticker_base}'

        if ask_vol_col in df.columns and bid_vol_col in df.columns:
            temp_df['delta'] = df[ask_vol_col] - df[bid_vol_col]
        else:
            # Approximate using bar direction
            temp_df['delta'] = np.sign(df[close_col] - df[open_col]) * df[vol_col]

        temp_df['cvd'] = temp_df['delta'].cumsum()

        # 12. CVD percentile rank
        def rolling_percentile_rank(series, window):
            def pr(x):
                if len(x) < window:
                    return np.nan
                return percentileofscore(x[:-1], x.iloc[-1]) / 100
            return series.rolling(window).apply(pr, raw=False)

        temp_df['cvd_pct'] = rolling_percentile_rank(temp_df['cvd'], cvd_lookback)

        # 13. Z-score of CVD percentile
        temp_df['z_cvd'] = (temp_df['cvd_pct'] - 0.5) / 0.15
        temp_df['sigma'] = np.tanh(temp_df['z_cvd'])

        # 14. Final TVI with CVD flow modulation
        temp_df['tvi'] = temp_df['tvi_n'] * (1 + LAMBDA * temp_df['sigma'])
        temp_df['tvi'] = temp_df['tvi'].clip(0, 1).round(3)

        # Build output DataFrame
        result = pd.DataFrame(index=df.index)
        result[f'tvi_norm_{ticker_base}'] = temp_df['tvi']
        result[f'vwap_{ticker_base}'] = temp_df['vwap'].round(2)
        result[f'vwap_dev_{ticker_base}'] = temp_df['vwap_dev'].round(3)
        result[f'tvi_gated_reversal_flag_{ticker_base}'] = temp_df['tvi_gated_reversal_flag']
        result[f'cvd_{ticker_base}'] = temp_df['cvd'].round(0)
        result[f'cvd_pct_{ticker_base}'] = temp_df['cvd_pct'].round(3)

        print(f"  - Enhanced TVI calculation complete with {len(output_cols)} output columns.")
        return result

    except Exception as e:
        print(f"  - ERROR computing Enhanced TVI: {e}")
        import traceback
        traceback.print_exc()
        return empty_result
