"""
DA-TEM-E Score Calculation
Contains compute_da_tem_e_minute function for calculating the DA-TEM-E score
"""

import pandas as pd
import numpy as np

def compute_da_tem_e_minute(minute_data, latest_oi, sentiment=0.5, sma_period=60, corr_period=240):
    """
    Computes the DA-TEM-E score using minute data.

    Args:
        minute_data: DataFrame with minute OHLC data
        latest_oi: Latest open interest value
        sentiment: Sentiment score (0-1)
        sma_period: SMA period for momentum calculation
        corr_period: Correlation calculation period

    Returns:
        dict: Dictionary containing the DA-TEM-E score and components
    """
    print("\nComputing DA-TEM-E Score (Minute Version)...")

    try:
        gold_col = 'Close_GC=F'
        silver_col = 'Close_SI=F'
        plat_col = 'Close_PL=F'
        spx_col = 'Close_^GSPC'
        copper_col = 'Close_HG=F'
        gold_vol_col = 'Volume_GC=F'

        required_cols = [gold_col, silver_col, plat_col, spx_col, copper_col, gold_vol_col, 'DFF']

        if not all(col in minute_data.columns for col in required_cols):
            missing = [col for col in required_cols if col not in minute_data.columns]
            raise ValueError(f"Minute data missing: {missing}")

        if len(minute_data) < max(sma_period, corr_period):
            raise ValueError(f"Not enough minute data ({len(minute_data)})")

        # Calculate SMAs
        gold_sma = minute_data[gold_col].rolling(window=sma_period).mean()
        silver_sma = minute_data[silver_col].rolling(window=sma_period).mean()
        platinum_sma = minute_data[plat_col].rolling(window=sma_period).mean()

        # Get latest values
        latest_minute = minute_data.iloc[-1]
        latest_prices = {
            'gold': latest_minute[gold_col],
            'silver': latest_minute[silver_col],
            'platinum': latest_minute[plat_col]
        }
        latest_sma = {
            'gold': gold_sma.iloc[-1],
            'silver': silver_sma.iloc[-1],
            'platinum': platinum_sma.iloc[-1]
        }
        latest_vol = latest_minute[gold_vol_col] if gold_vol_col in latest_minute and not pd.isna(latest_minute[gold_vol_col]) else 0.0

        if not all(isinstance(latest_prices[m], (int, float)) and latest_prices[m] > 0 for m in latest_prices):
            raise ValueError(f"Invalid minute prices: {latest_prices}")

        if not all(isinstance(latest_sma[m], (int, float)) and latest_sma[m] > 0 for m in latest_sma):
            raise ValueError(f"Invalid minute SMAs: {latest_sma}.")

        # Calculate momentum
        gold_momentum = latest_prices['gold'] / (latest_sma['gold'] + 1e-9)
        silver_momentum = latest_prices['silver'] / (latest_sma['silver'] + 1e-9)
        platinum_momentum = latest_prices['platinum'] / (latest_sma['platinum'] + 1e-9)

        lydian_momentum_index = 4 * gold_momentum + 75 * silver_momentum + 1.5 * platinum_momentum
        neutral_index_value = 80.5

        flux_lyd = abs(lydian_momentum_index - neutral_index_value) / (neutral_index_value + 1e-9)

        print(f"  - Lydian Momentum Index (Minute): {lydian_momentum_index:.4f}, Flux: {flux_lyd:.4f}")

        # Price-based index
        price_based_index = 4 * latest_prices['gold'] + 75 * latest_prices['silver'] + 1.5 * latest_prices['platinum']
        price_flux = abs(price_based_index - 20000) / 20000

        tf_crit_minute = (latest_vol / 1000) * np.exp(price_flux * 10000 / 1200) if latest_vol > 0 else 0

        print(f"  - Volume Criticality (Minute): {tf_crit_minute:.4f}")

        # Calculate correlations
        print(f"  - Calculating correlations ({corr_period} minutes)...")
        corr_data = minute_data.iloc[-corr_period:]
        avg_correlation = 0.0

        corr_gold_sma = corr_data[gold_col].rolling(window=sma_period).mean()
        corr_silver_sma = corr_data[silver_col].rolling(window=sma_period).mean()
        corr_plat_sma = corr_data[plat_col].rolling(window=sma_period).mean()

        corr_gold_mom = (corr_data[gold_col] / (corr_gold_sma + 1e-9)).replace([np.inf, -np.inf], np.nan)
        corr_silver_mom = (corr_data[silver_col] / (corr_silver_sma + 1e-9)).replace([np.inf, -np.inf], np.nan)
        corr_plat_mom = (corr_data[plat_col] / (corr_plat_sma + 1e-9)).replace([np.inf, -np.inf], np.nan)

        historical_momentum_index = (4 * corr_gold_mom + 75 * corr_silver_mom + 1.5 * corr_plat_mom).dropna()
        historical_momentum_index.name = 'MomentumIndex'

        spx_hist = corr_data[spx_col].rename('SPX')
        copper_hist = corr_data[copper_col].rename('Copper')

        merged_df = pd.concat([historical_momentum_index, spx_hist, copper_hist], axis=1, join='inner')

        if len(merged_df) >= 20:
            correlation_matrix = merged_df.corr()
            corr_spx = correlation_matrix.loc['MomentumIndex', 'SPX'] if 'SPX' in correlation_matrix.columns and 'MomentumIndex' in correlation_matrix.index else 0.0
            corr_copper = correlation_matrix.loc['MomentumIndex', 'Copper'] if 'Copper' in correlation_matrix.columns and 'MomentumIndex' in correlation_matrix.index else 0.0
            avg_correlation = (corr_spx + corr_copper) / 2
            print(f"    - Momentum Index Corr SPX: {corr_spx:.4f}, Copper: {corr_copper:.4f}, Avg: {avg_correlation:.4f}")
        else:
            print(f"    - Warning: Not enough minute data ({len(merged_df)}) for correlation.")

        # Calculate final score
        base_score = (lydian_momentum_index / (neutral_index_value + 1e-9)) * 100 * sentiment
        correlation_penalty = abs(base_score * avg_correlation)
        oi_penalty = latest_oi / 1_000_000

        final_score = base_score - correlation_penalty - tf_crit_minute - oi_penalty

        print(f"  - Base Score (Minute): {base_score:.4f}, Corr Pen: {correlation_penalty:.4f}, TF_crit (Min): {tf_crit_minute:.4f}, OI Pen: {oi_penalty:.4f}")
        print(f"  - Final DA-TEM-E Score (Minute): {final_score:.4f}")

        return {
            "DA-TEM-E Score": final_score,
            "Components": {
                "Lydian Momentum Index": lydian_momentum_index,
                "Momentum Flux": flux_lyd,
                "Volume Criticality (Minute)": tf_crit_minute,
                "Avg Correlation (Minute)": avg_correlation,
                "Sentiment (P/C Ratio Based)": sentiment,
                "Open Interest (Daily)": latest_oi
            }
        }

    except Exception as e:
        print(f"  - ERROR during DA-TEM-E MINUTE calc: {e}")
        import traceback
        traceback.print_exc()
        return None
