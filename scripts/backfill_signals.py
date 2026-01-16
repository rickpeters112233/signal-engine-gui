#!/usr/bin/env python3
"""
Backfill Signals Script
Processes historical bar data, computes features, generates trading signals,
and stores them in the SQLite database.

Strategy: BUY (Phi_sigma >= 4 & DIR >= 0.5) | TAKE PROFIT +0.05% | STOP LOSS -0.10%
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from features.features_tf import compute_tf_mod, compute_tf_crit
from features.features_phi import compute_phi_sigma
from features.features_tvi import compute_tvi_enhanced
from features.features_svc import compute_svc_delta
from features.features_directional import compute_directional_indicator
from features.signal_generator import TradingSignalGenerator
from api.db import signals as signals_db


def load_historical_data(input_file: str) -> pd.DataFrame:
    """Load historical bar data from JSON file."""
    print(f"Loading data from {input_file}...")

    with open(input_file, 'r') as f:
        data = json.load(f)

    bars = data.get('bars', [])
    contract_id = data.get('contract_id', 'UNKNOWN')

    print(f"  Contract: {contract_id}")
    print(f"  Bars: {len(bars)}")

    if not bars:
        raise ValueError("No bars in data file")

    # Convert to DataFrame
    df_data = []
    for bar in bars:
        df_data.append({
            'datetime': pd.to_datetime(bar['t']),
            'open': float(bar['o']),
            'high': float(bar['h']),
            'low': float(bar['l']),
            'close': float(bar['c']),
            'volume': int(bar['v']),
        })

    df = pd.DataFrame(df_data)
    df = df.set_index('datetime').sort_index()

    # Add ticker-prefixed columns (required by feature functions)
    ticker_base = contract_id.upper()
    df[f'Open_{ticker_base}'] = df['open']
    df[f'High_{ticker_base}'] = df['high']
    df[f'Low_{ticker_base}'] = df['low']
    df[f'Close_{ticker_base}'] = df['close']
    df[f'Volume_{ticker_base}'] = df['volume']
    df[f'VWAP_{ticker_base}'] = (df['high'] + df['low'] + df['close']) / 3

    print(f"  Date range: {df.index[0]} to {df.index[-1]}")

    return df, contract_id


def compute_features(df: pd.DataFrame, ticker_base: str) -> pd.DataFrame:
    """Compute all required features for signal generation."""
    print(f"\nComputing features on {len(df)} bars...")

    df_features = df.copy()

    # 1. TF features
    try:
        df_features['tf_mod'] = compute_tf_mod(
            df_features,
            ticker_base=ticker_base,
            bb_window=20,
            atr_window=14
        )
        df_features['tf_crit'] = compute_tf_crit(
            df_features,
            tf_mod_col='tf_mod',
            threshold=0.30,
            persistence=3
        )
        print("  [OK] TF features")
    except Exception as e:
        print(f"  [WARN] TF features failed: {e}")
        df_features['tf_mod'] = 0.0
        df_features['tf_crit'] = 0.0

    # 2. Phi Sigma
    try:
        df_features['phi_sigma'] = compute_phi_sigma(
            df_features,
            ticker_base=ticker_base,
            window=14,
            ma_period=240
        )
        print("  [OK] Phi Sigma")
    except Exception as e:
        print(f"  [WARN] Phi Sigma failed: {e}")
        df_features['phi_sigma'] = 0.0

    # 3. TVI Enhanced
    try:
        tvi_result = compute_tvi_enhanced(
            df_features,
            ticker_base=ticker_base,
            atr_window=14,
            norm_window=60
        )
        for col in tvi_result.columns:
            if col not in df_features.columns:
                df_features[col] = tvi_result[col]
        print("  [OK] TVI Enhanced")
    except Exception as e:
        print(f"  [WARN] TVI Enhanced failed: {e}")

    # 4. SVC Delta
    try:
        df_features['svc_delta'] = compute_svc_delta(
            df_features,
            ticker_base=ticker_base,
            atr_window=14,
            baseline_window=60
        )
        print("  [OK] SVC Delta")
    except Exception as e:
        print(f"  [WARN] SVC Delta failed: {e}")
        df_features['svc_delta'] = 0.0

    # 5. Directional Indicator
    try:
        df_features['directional_indicator'] = compute_directional_indicator(
            df_features,
            ticker_base=ticker_base,
            lookback=20,
            percentile_window=100
        )
        print("  [OK] Directional Indicator")
    except Exception as e:
        print(f"  [WARN] Directional Indicator failed: {e}")
        df_features['directional_indicator'] = 0.0

    # Fill NaN values with 0
    df_features = df_features.fillna(0.0)

    print(f"  Features computed: {len(df_features.columns)} columns")

    return df_features


def generate_signals(df_features: pd.DataFrame, symbol: str) -> list:
    """
    Generate trading signals using the TradingSignalGenerator.

    Returns list of signal entries (only BUY/SELL signals, not HOLD).
    """
    print(f"\nGenerating signals...")

    signal_generator = TradingSignalGenerator()
    signals = []
    total_bars = len(df_features)

    for i, (timestamp, row) in enumerate(df_features.iterrows()):
        # Get feature values
        phi_sigma = float(row.get('phi_sigma', 0.0))
        directional = float(row.get('directional_indicator', 0.0))
        current_price = float(row.get('close', 0.0))

        # Generate signal
        signal, metadata = signal_generator.generate_signal(
            phi_sigma_value=phi_sigma,
            directional_indicator_value=directional,
            current_price=current_price
        )

        # Only store BUY/SELL signals (not HOLD)
        if signal in ('BUY', 'SELL_PROFIT', 'SELL_STOP'):
            signal_entry = {
                'recorded_at': str(timestamp),
                'signal': signal,
                'timestamp': str(timestamp),
                'symbol': symbol,
                'price': current_price,
                'directional_indicator': directional,
                'phi_sigma': phi_sigma,
                'svc_delta_pct': float(row.get('svc_delta', 0.0)),
                'tf_crit': float(row.get('tf_crit', 0.0)),
            }
            signals.append(signal_entry)

        # Progress indicator
        if (i + 1) % 1000 == 0:
            print(f"  Processed {i + 1}/{total_bars} bars ({len(signals)} signals so far)")

    print(f"\nTotal signals generated: {len(signals)}")

    # Count by type
    buy_count = sum(1 for s in signals if s['signal'] == 'BUY')
    sell_profit_count = sum(1 for s in signals if s['signal'] == 'SELL_PROFIT')
    sell_stop_count = sum(1 for s in signals if s['signal'] == 'SELL_STOP')

    print(f"  BUY: {buy_count}")
    print(f"  SELL_PROFIT: {sell_profit_count}")
    print(f"  SELL_STOP: {sell_stop_count}")

    return signals


def store_signals_in_db(signals: list):
    """Store signals in SQLite database."""
    print(f"\nStoring {len(signals)} signals in database...")

    # Clear existing signals first (optional - comment out to append)
    existing_count = signals_db.get_signal_count()
    if existing_count > 0:
        print(f"  Clearing {existing_count} existing signals...")
        signals_db.clear_all_signals()

    # Add new signals
    for i, signal in enumerate(signals):
        signals_db.add_signal(signal)

        if (i + 1) % 100 == 0:
            print(f"  Stored {i + 1}/{len(signals)} signals")

    final_count = signals_db.get_signal_count()
    print(f"\nDatabase now contains {final_count} signals")


def main(input_file: str):
    """Main backfill process."""
    print(f"\n{'='*60}")
    print("BACKFILL SIGNALS FROM HISTORICAL DATA")
    print(f"{'='*60}")

    # 1. Load historical data
    df, contract_id = load_historical_data(input_file)

    # 2. Compute features
    df_features = compute_features(df, contract_id)

    # 3. Generate signals
    signals = generate_signals(df_features, contract_id)

    # 4. Store in database
    if signals:
        store_signals_in_db(signals)
    else:
        print("\nNo signals to store")

    print(f"\n{'='*60}")
    print("BACKFILL COMPLETE")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill signals from historical bar data")
    parser.add_argument(
        '--input',
        type=str,
        default='./data/historical_bars.json',
        help='Input JSON file with historical bars'
    )

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"ERROR: Input file not found: {args.input}")
        print("Run fetch_historical_data.py first to download the data")
        sys.exit(1)

    main(args.input)
