"""
SVC (Signed Volume Change) Delta Feature Calculation - Enhanced Version
Contains compute_svc_delta function with directional component and quantile-based flags
"""

import pandas as pd
import numpy as np
from scipy.stats import percentileofscore


def compute_svc_delta(df, ticker_base="GC=F", atr_window=14, baseline_window=120, quantile_lookback=240):
    """
    Computes DIRECTIONAL Signed Volume Change Delta (SVC_Delta) with dynamic quantile-based flags.

    This enhanced version incorporates:
    - Bar direction (up/down) for directional energy
    - Dynamic quantile thresholds for adaptive flagging
    - Rolling percentile rank for relative positioning

    Args:
        df: DataFrame with OHLCV data
        ticker_base: Ticker symbol
        atr_window: ATR calculation window (default: 14)
        baseline_window: EMA period for baseline energy (default: 120 = 2 hours)
        quantile_lookback: Rolling window for dynamic thresholds (default: 240 = 4 hours)

    Returns:
        pd.DataFrame: DataFrame with svc_delta and flag columns
    """
    print(f"\nComputing Directional SVC_Delta for {ticker_base} (ATR({atr_window}), Baseline({baseline_window}))...")

    # Config
    EPS = 1e-8
    CLIP_MIN = -5.0
    CLIP_MAX = 5.0
    Q_EXTREME_HIGH = 0.99  # Top 1% (extreme buying)
    Q_OVERBOUGHT = 0.95    # Top 5% (overbought)
    Q_OVERSOLD = 0.05      # Bottom 5% (oversold, climactic selling)
    Q_EXTREME_LOW = 0.01   # Bottom 1% (extreme selling)

    # Column names
    high_col = f'High_{ticker_base}'
    low_col = f'Low_{ticker_base}'
    close_col = f'Close_{ticker_base}'
    open_col = f'Open_{ticker_base}'
    vol_col = f'Volume_{ticker_base}'
    required_cols = [high_col, low_col, close_col, open_col, vol_col]

    # Output column names
    output_cols = [
        f'svc_delta_{ticker_base}',
        f'svc_delta_pct_{ticker_base}',
        f'svc_extreme_{ticker_base}',
        f'svc_overbought_{ticker_base}',
        f'svc_oversold_{ticker_base}',
        f'svc_extreme_sell_{ticker_base}'
    ]

    # Create empty result with NaN
    empty_result = pd.DataFrame(np.nan, index=df.index, columns=output_cols)

    # Check for required columns
    if not all(col in df.columns for col in required_cols):
        print(f"  - Warning: Missing columns for SVC_Delta ({ticker_base}). Need {required_cols}.")
        return empty_result

    if len(df) < max(atr_window, baseline_window, quantile_lookback) + 1:
        print(f"  - Warning: Not enough data ({len(df)}) for SVC_Delta.")
        return empty_result

    temp_df = pd.DataFrame(index=df.index)

    try:
        # 1. Calculate ATR(14) using EMA
        temp_df['tr1'] = abs(df[high_col] - df[low_col])
        temp_df['tr2'] = abs(df[high_col] - df[close_col].shift())
        temp_df['tr3'] = abs(df[low_col] - df[close_col].shift())
        temp_df['tr'] = temp_df[['tr1', 'tr2', 'tr3']].max(axis=1)
        temp_df['atr'] = temp_df['tr'].ewm(span=atr_window, adjust=False).mean()

        # 2. Calculate bar direction: +1 for up (green), -1 for down (red), 0 for doji
        temp_df['bar_direction'] = np.sign(df[close_col] - df[open_col])

        # 3. Calculate directional SVC_raw
        delta_t = 1
        temp_df['svc_raw'] = temp_df['bar_direction'] * temp_df['atr'] * df[vol_col] * delta_t

        # 4. Calculate baseline (EMA of directional raw - will be near zero)
        temp_df['svc_bar'] = temp_df['svc_raw'].ewm(span=baseline_window, adjust=False).mean()
        temp_df['volume_baseline'] = df[vol_col].ewm(span=baseline_window, adjust=False).mean()

        # 5. Calculate SVC_Delta: standardized deviation
        temp_df['svc_delta'] = (temp_df['svc_raw'] - temp_df['svc_bar']) / (
            temp_df['atr'] * temp_df['volume_baseline'] + EPS
        )
        temp_df['svc_delta'] = temp_df['svc_delta'].clip(CLIP_MIN, CLIP_MAX).round(3)

        # 6. Calculate rolling percentile rank
        def rolling_percentile_rank(series, window):
            def pr(x):
                if len(x) < window:
                    return np.nan
                return percentileofscore(x[:-1], x.iloc[-1]) / 100
            return series.rolling(window).apply(pr, raw=False)

        temp_df['svc_delta_pct'] = rolling_percentile_rank(temp_df['svc_delta'], quantile_lookback).round(3)

        # 7. Calculate dynamic quantile thresholds
        print("  - Setting SVC dynamic binary flags...")
        temp_df['q_extreme_high'] = temp_df['svc_delta'].rolling(quantile_lookback).quantile(Q_EXTREME_HIGH)
        temp_df['q_overbought'] = temp_df['svc_delta'].rolling(quantile_lookback).quantile(Q_OVERBOUGHT)
        temp_df['q_oversold'] = temp_df['svc_delta'].rolling(quantile_lookback).quantile(Q_OVERSOLD)
        temp_df['q_extreme_low'] = temp_df['svc_delta'].rolling(quantile_lookback).quantile(Q_EXTREME_LOW)

        # 8. Set mutually exclusive flags
        # Extreme Buy: above 99th percentile
        temp_df['svc_extreme'] = (temp_df['svc_delta'] > temp_df['q_extreme_high']).astype(int)

        # Overbought: 95th-99th percentile
        temp_df['svc_overbought'] = (
            (temp_df['svc_delta'] > temp_df['q_overbought']) &
            (temp_df['svc_delta'] <= temp_df['q_extreme_high'])
        ).astype(int)

        # Oversold: 1st-5th percentile (climactic selling)
        temp_df['svc_oversold'] = (
            (temp_df['svc_delta'] < temp_df['q_oversold']) &
            (temp_df['svc_delta'] >= temp_df['q_extreme_low'])
        ).astype(int)

        # Extreme Sell: below 1st percentile
        temp_df['svc_extreme_sell'] = (temp_df['svc_delta'] < temp_df['q_extreme_low']).astype(int)

        # 9. Build output DataFrame with proper column names
        result = pd.DataFrame(index=df.index)
        result[f'svc_delta_{ticker_base}'] = temp_df['svc_delta']
        result[f'svc_delta_pct_{ticker_base}'] = temp_df['svc_delta_pct']
        result[f'svc_extreme_{ticker_base}'] = temp_df['svc_extreme']
        result[f'svc_overbought_{ticker_base}'] = temp_df['svc_overbought']
        result[f'svc_oversold_{ticker_base}'] = temp_df['svc_oversold']
        result[f'svc_extreme_sell_{ticker_base}'] = temp_df['svc_extreme_sell']

        print(f"  - Directional SVC_Delta calculation complete with {len(output_cols)} output columns.")
        return result

    except Exception as e:
        print(f"  - ERROR computing SVC_Delta: {e}")
        import traceback
        traceback.print_exc()
        return empty_result
