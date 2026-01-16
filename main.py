#!/usr/bin/env python3
"""
Main entry point for the Tribernachi-Enhanced TMS Pipeline
Demonstrates basic usage of the orchestration pipeline with multi-provider support
"""

import sys
import os
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Import orchestrator and data provider factory
from orchestration import PipelineOrchestrator
from api import DataProviderFactory, get_broadcaster
from api.auth_server import get_auth_server
from features.signal_generator import TradingSignalGenerator

# Load environment variables from .env file
load_dotenv()


def run_batch_mode(symbol: str, history_hours: float, provider_type: str = "massive"):
    """
    Run batch processing mode.

    Args:
        symbol: Ticker symbol (e.g., XAUUSD) or contract ID (e.g., CON.F.US.GCE.Z25)
        history_hours: Hours of historical data to fetch (can be fractional, e.g., 0.5 = 30 minutes)
        provider_type: Data provider type ("massive", "topstepx", or "file")
    """
    print(f"\n{'='*60}")
    print(f"BATCH MODE: {symbol}")
    print(f"{'='*60}")

    # Create configuration from environment variables
    config = {
        'MASSIVE_API_KEY': os.getenv('MASSIVE_API_KEY'),
        'TOPSTEP_USERNAME': os.getenv('TOPSTEP_USERNAME'),
        'TOPSTEP_PASSWORD': os.getenv('TOPSTEP_PASSWORD'),
        'TOPSTEP_APIKEY': os.getenv('TOPSTEP_APIKEY'),
        'TOPSTEP_CURRENT_TOKEN': os.getenv('TOPSTEP_CURRENT_TOKEN'),
        'DATA_DIR': os.getenv('DATA_DIR', './data')
    }

    # Create provider using factory
    try:
        provider = DataProviderFactory.create_provider(provider_type, config)
    except Exception as e:
        print(f"\nERROR: Failed to create {provider_type} provider: {e}")
        print("\nPlease check:")
        print("  1. Your .env file exists and contains valid credentials")
        print("  2. Required credentials for the selected provider are set")
        print(f"  3. For provider '{provider_type}', see .env.example for required variables")
        return None

    # Initialize orchestrator with provider
    orchestrator = PipelineOrchestrator(
        provider=provider,
        ticker=symbol,
        enable_compression=True,
        history_hours=history_hours
    )

    # Run batch pipeline
    df_result = orchestrator.run_batch_pipeline()

    if df_result is not None:
        print(f"\n{'='*60}")
        print("RESULTS SUMMARY")
        print(f"{'='*60}")
        print(f"Total bars: {len(df_result)}")
        print(f"Total features: {len(df_result.columns)}")
        print(f"\nDate range: {df_result.index[0]} to {df_result.index[-1]}")

        print(f"\n{'='*60}")
        print("LATEST VALUES")
        print(f"{'='*60}")
        print(df_result.tail(5))

        # Get cache stats
        print(f"\n{'='*60}")
        print("CACHE STATISTICS")
        print(f"{'='*60}")
        stats = orchestrator.get_cache_stats()
        for key, value in stats.items():
            print(f"{key:30s}: {value}")

        return df_result
    else:
        print("\nERROR: Batch pipeline failed")
        return None


def run_realtime_mode(symbol: str, provider_type: str = "massive", enable_websocket: bool = True):
    """
    Run real-time streaming mode with WebSocket broadcasting.

    Args:
        symbol: Ticker symbol (e.g., XAUUSD) or contract ID (e.g., CON.F.US.GCE.Z25)
        provider_type: Data provider type ("massive" or "topstepx")
        enable_websocket: Enable WebSocket server for broadcasting (default: True)
    """
    # Extract display name from symbol
    if provider_type == "topstepx" and symbol.startswith("CON.F.US."):
        # Parse contract: CON.F.US.GCE.Z25 -> Gold Futures (GCE) Dec 2025
        parts = symbol.split('.')
        if len(parts) >= 5:
            base_symbol = parts[3]  # GCE
            expiry = parts[4]  # Z25

            # Map symbols to full names
            symbol_names = {
                'GCE': 'Gold Futures',
                'SIE': 'Silver Futures',
                'PLE': 'Platinum Futures',
                'PAE': 'Palladium Futures',
                'CLE': 'Crude Oil Futures',
                'RTYE': 'Russell 2000 Futures',
                'ESE': 'E-mini S&P 500 Futures',
                'NQE': 'E-mini Nasdaq Futures',
            }

            # Map month codes to names
            month_codes = {
                'F': 'Jan', 'G': 'Feb', 'H': 'Mar', 'J': 'Apr',
                'K': 'May', 'M': 'Jun', 'N': 'Jul', 'Q': 'Aug',
                'U': 'Sep', 'V': 'Oct', 'X': 'Nov', 'Z': 'Dec'
            }

            full_name = symbol_names.get(base_symbol, base_symbol)
            month_code = expiry[0] if expiry else '?'
            year = f"20{expiry[1:]}" if len(expiry) > 1 else '??'
            month_name = month_codes.get(month_code, month_code)

            display_name = f"{full_name} ({base_symbol}) {month_name} {year}"
        else:
            display_name = symbol
    else:
        display_name = symbol

    print(f"\n{'='*60}")
    print(f"REAL-TIME MODE: {display_name}")
    print(f"{'='*60}")
    if enable_websocket:
        print("WebSocket Server: ENABLED on ws://localhost:8765")
        print("Auth Server: ENABLED on http://localhost:8766")
    print("Press Ctrl+C to stop streaming\n")

    # Create configuration from environment variables
    config = {
        'MASSIVE_API_KEY': os.getenv('MASSIVE_API_KEY'),
        'TOPSTEP_USERNAME': os.getenv('TOPSTEP_USERNAME'),
        'TOPSTEP_PASSWORD': os.getenv('TOPSTEP_PASSWORD'),
        'TOPSTEP_APIKEY': os.getenv('TOPSTEP_APIKEY'),
        'TOPSTEP_CURRENT_TOKEN': os.getenv('TOPSTEP_CURRENT_TOKEN'),
        'DATA_DIR': os.getenv('DATA_DIR', './data')
    }

    # Create provider using factory
    try:
        provider = DataProviderFactory.create_provider(provider_type, config)
    except Exception as e:
        print(f"\nERROR: Failed to create {provider_type} provider: {e}")
        print("\nPlease check your .env file and credentials")
        return

    # Initialize orchestrator with provider
    orchestrator = PipelineOrchestrator(
        provider=provider,
        ticker=symbol,
        enable_compression=True,
        history_hours=24
    )

    # Initialize WebSocket broadcaster and auth server if enabled
    broadcaster = None
    auth_server = None
    if enable_websocket:
        broadcaster = get_broadcaster(host="localhost", port=8765)
        auth_server = get_auth_server(host="localhost", port=8766)

    # Initialize trading signal generator
    signal_generator = TradingSignalGenerator()

    # Historical data buffer for incremental feature computation
    historical_buffer = None

    # Define callback for incoming bars
    async def handle_bar(bar):
        nonlocal historical_buffer
        import pandas as pd

        # Print raw bar data
        print(f"\n[{bar['datetime']}]")
        print(f"  OHLC: O={bar['Open']:.2f} H={bar['High']:.2f} "
              f"L={bar['Low']:.2f} C={bar['Close']:.2f}")
        print(f"  Volume: {bar['Volume']:.0f}")
        print(f"  VWAP: {bar['VWAP']:.2f}")

        # Convert bar to DataFrame row with proper column names to match historical buffer
        # The historical buffer uses columns like:
        #   - Prefixed: Open_{ticker}, High_{ticker}, Close_{ticker}, etc.
        #   - Lowercase: open, high, low, close, volume (original from API)
        # NOTE: Do NOT add title-case columns (Open, Close, etc.) as they cause
        # compute_directional_indicator to pick the wrong column with NaN values
        ticker_base = symbol.upper()
        bar_normalized = {
            'datetime': bar['datetime'],
            # Prefixed columns (for phi_sigma, tvi, svc_delta features)
            f'Open_{ticker_base}': bar['Open'],
            f'High_{ticker_base}': bar['High'],
            f'Low_{ticker_base}': bar['Low'],
            f'Close_{ticker_base}': bar['Close'],
            f'Volume_{ticker_base}': bar['Volume'],
            f'VWAP_{ticker_base}': bar['VWAP'],
            # Lowercase columns (for directional_indicator, matches TopstepX normalize_dataframe)
            'open': bar['Open'],
            'high': bar['High'],
            'low': bar['Low'],
            'close': bar['Close'],
            'volume': bar['Volume'],
        }
        bar_df = pd.DataFrame([bar_normalized])
        bar_df.set_index('datetime', inplace=True)

        # Initialize buffer from orchestrator's historical data if needed
        if historical_buffer is None:
            historical_buffer = orchestrator.fetch_historical_data()
            if historical_buffer is None:
                return

        # Append new bar to buffer (avoid duplicates)
        if bar_df.index[0] not in historical_buffer.index:
            print(f"  [NEW BAR - Adding to buffer]")
            historical_buffer = pd.concat([historical_buffer, bar_df])
            # Keep only last 24 hours
            historical_buffer = historical_buffer.tail(1440)  # 24h * 60min
        else:
            # Skip processing for duplicate bars - don't recompute or broadcast
            return

        # Compute and display features for the new bar
        df_features = orchestrator.compute_all_features(historical_buffer)

        # Display latest feature values
        if df_features is not None and len(df_features) > 0:
            print(f"\n{'='*60}")
            print("LATEST FEATURE VALUES")
            print(f"{'='*60}")
            latest = df_features.iloc[-1]

            # Prepare data for WebSocket broadcast
            broadcast_data = {}

            # Map feature columns to client-expected names
            feature_mapping = {
                'phi_sigma': 'phi_sigma',
                'tf_mod': 'tf_mod',
                'tf_crit': 'tf_crit',
                'directional_indicator': 'directional_indicator',
                'atr_14': 'atr_14',
            }

            # Additional mapping for new SVC and CVD columns (with ticker suffix)
            ticker_base = symbol.upper()
            svc_cvd_mapping = {
                f'svc_delta_{ticker_base}': 'svc_delta',
                f'svc_delta_pct_{ticker_base}': 'svc_delta_pct',
                f'svc_extreme_{ticker_base}': 'svc_extreme',
                f'svc_overbought_{ticker_base}': 'svc_overbought',
                f'svc_oversold_{ticker_base}': 'svc_oversold',
                f'svc_extreme_sell_{ticker_base}': 'svc_extreme_sell',
                f'cvd_{ticker_base}': 'cvd',
                f'cvd_pct_{ticker_base}': 'cvd_pct',
                f'cvd_status_{ticker_base}': 'cvd_status',
                f'cvd_momentum_{ticker_base}': 'cvd_momentum',
                f'tvi_gated_reversal_flag_{ticker_base}': 'tvi_reversal_flag',
            }

            # Find columns with ticker suffixes and map them
            for col in df_features.columns:
                # Skip base OHLCV columns
                if col in {'Open', 'High', 'Low', 'Close', 'Volume', 'VWAP', 'datetime', 'timestamp'}:
                    continue

                try:
                    value = latest[col]

                    # Map ticker-specific columns to clean names
                    if col.startswith('tvi_norm_'):
                        broadcast_data['tvi'] = value
                        print(f"  tvi: {value:.6f}")
                    elif col.startswith('vwap_') and not col.startswith('vwap_dev_'):
                        # Skip VWAP itself (not needed by client)
                        pass
                    elif col.startswith('vwap_dev_'):
                        # Skip VWAP deviation (not needed by client)
                        pass
                    elif col in feature_mapping:
                        # Map known features to client names
                        client_key = feature_mapping[col]
                        broadcast_data[client_key] = value
                        if isinstance(value, (int, float)):
                            print(f"  {client_key}: {value:.6f}")
                        else:
                            print(f"  {client_key}: {value}")
                    elif col in svc_cvd_mapping:
                        # Map new SVC and CVD columns
                        client_key = svc_cvd_mapping[col]
                        broadcast_data[client_key] = value
                        if isinstance(value, (int, float)):
                            print(f"  {client_key}: {value:.6f}")
                        else:
                            print(f"  {client_key}: {value}")
                except:
                    pass

            # Add major event warning logic (99th percentile SVC = precursor to tf_crit)
            svc_extreme = broadcast_data.get('svc_extreme', 0)
            svc_extreme_sell = broadcast_data.get('svc_extreme_sell', 0)
            major_event_warning = (svc_extreme == 1) or (svc_extreme_sell == 1)
            broadcast_data['major_event_warning'] = major_event_warning
            broadcast_data['warning_countdown'] = 10 if major_event_warning else 0

            if major_event_warning:
                event_type = "BUY PRESSURE" if svc_extreme == 1 else "SELL PRESSURE"
                print(f"\n  ⚠️ MAJOR EVENT WARNING: {event_type} DETECTED (10 MIN)")

            # Add OHLCV data to broadcast
            broadcast_data['timestamp'] = str(bar['datetime'])
            broadcast_data['symbol'] = symbol  # Include trading symbol/contract
            broadcast_data['close'] = float(bar['Close'])
            broadcast_data['volume'] = int(bar['Volume'])

            # Generate trading signal
            phi_sigma = broadcast_data.get('phi_sigma', 0.0)
            directional = broadcast_data.get('directional_indicator', 0.0)
            current_price = float(bar['Close'])

            signal, signal_metadata = signal_generator.generate_signal(
                phi_sigma_value=phi_sigma if isinstance(phi_sigma, (int, float)) else 0.0,
                directional_indicator_value=directional if isinstance(directional, (int, float)) else 0.0,
                current_price=current_price
            )

            # Add signal data to broadcast
            broadcast_data['trading_signal'] = signal
            broadcast_data['entry_price'] = signal_metadata['entry_price']
            broadcast_data['position_open'] = signal_metadata['position_open']
            broadcast_data['pnl_pct'] = signal_metadata['pnl_pct']
            broadcast_data['stop_loss_price'] = signal_metadata['stop_loss_price']
            broadcast_data['take_profit_price'] = signal_metadata['take_profit_price']

            # Print signal info
            print(f"\n  SIGNAL: {signal}")
            if signal_metadata['position_open']:
                print(f"  Entry: {signal_metadata['entry_price']:.2f} | P&L: {signal_metadata['pnl_pct']:.4f}%")

            # Broadcast data via WebSocket
            if broadcaster and broadcaster.is_running:
                await broadcaster.broadcast(broadcast_data)
                print(f"\n  [WebSocket] Broadcasted to {len(broadcaster.clients)} clients")

    # Run real-time pipeline with WebSocket server
    import asyncio

    # Pipeline task reference
    pipeline_task_ref = {'task': None}

    async def start_pipeline():
        """Start the data pipeline when first client connects."""
        if pipeline_task_ref['task'] is None:
            print("\n[Pipeline] Starting data pipeline...")
            pipeline_task_ref['task'] = asyncio.create_task(
                orchestrator.run_realtime_pipeline(callback=handle_bar)
            )

    async def stop_pipeline():
        """Stop the data pipeline when last client disconnects."""
        if pipeline_task_ref['task'] is not None:
            print("\n[Pipeline] Stopping data pipeline...")
            orchestrator.stop_streaming()
            if not pipeline_task_ref['task'].done():
                pipeline_task_ref['task'].cancel()
                try:
                    await pipeline_task_ref['task']
                except asyncio.CancelledError:
                    pass
            pipeline_task_ref['task'] = None
            print("[Pipeline] Data pipeline stopped")

    async def broadcast_initial_data():
        """Broadcast initial historical data so clients have something to display."""
        nonlocal historical_buffer
        import pandas as pd

        print("\n[Pipeline] Fetching initial historical data...")
        historical_buffer = orchestrator.fetch_historical_data()

        if historical_buffer is None or len(historical_buffer) == 0:
            print("[Pipeline] No historical data available")
            return

        print(f"[Pipeline] Computing features on {len(historical_buffer)} historical bars...")
        df_features = orchestrator.compute_all_features(historical_buffer)

        if df_features is None or len(df_features) == 0:
            print("[Pipeline] Feature computation failed")
            return

        # Get the latest bar and features
        latest = df_features.iloc[-1]
        latest_bar = historical_buffer.iloc[-1]

        # Build broadcast data from latest features
        broadcast_data = {
            'timestamp': str(historical_buffer.index[-1]),
            'symbol': symbol,
            'close': float(latest_bar.get('Close', latest_bar.get(f'Close_{symbol}', 0))),
            'volume': int(latest_bar.get('Volume', latest_bar.get(f'Volume_{symbol}', 0))),
            'cvd_pct': 0.5,  # Default
        }

        # Map features to client-expected names
        feature_mapping = {
            'phi_sigma': 'phi_sigma',
            'tf_mod': 'tf_mod',
            'tf_crit': 'tf_crit',
            'directional_indicator': 'directional_indicator',
            'atr_14': 'atr_14',
        }

        # Additional mapping for new SVC and CVD columns (with ticker suffix)
        ticker_base = symbol.upper()
        svc_cvd_mapping = {
            f'svc_delta_{ticker_base}': 'svc_delta',
            f'svc_delta_pct_{ticker_base}': 'svc_delta_pct',
            f'svc_extreme_{ticker_base}': 'svc_extreme',
            f'svc_overbought_{ticker_base}': 'svc_overbought',
            f'svc_oversold_{ticker_base}': 'svc_oversold',
            f'svc_extreme_sell_{ticker_base}': 'svc_extreme_sell',
            f'cvd_{ticker_base}': 'cvd',
            f'cvd_pct_{ticker_base}': 'cvd_pct',
            f'cvd_status_{ticker_base}': 'cvd_status',
            f'cvd_momentum_{ticker_base}': 'cvd_momentum',
            f'tvi_gated_reversal_flag_{ticker_base}': 'tvi_reversal_flag',
        }

        for col in df_features.columns:
            try:
                value = latest[col]
                if col.startswith('tvi_norm_'):
                    broadcast_data['tvi'] = value
                elif col in feature_mapping:
                    broadcast_data[feature_mapping[col]] = value
                elif col in svc_cvd_mapping:
                    broadcast_data[svc_cvd_mapping[col]] = value
            except:
                pass

        # Add major event warning logic
        svc_extreme = broadcast_data.get('svc_extreme', 0)
        svc_extreme_sell = broadcast_data.get('svc_extreme_sell', 0)
        major_event_warning = (svc_extreme == 1) or (svc_extreme_sell == 1)
        broadcast_data['major_event_warning'] = major_event_warning
        broadcast_data['warning_countdown'] = 10 if major_event_warning else 0

        # Generate initial trading signal (will be HOLD since no position)
        phi_sigma = broadcast_data.get('phi_sigma', 0.0)
        directional = broadcast_data.get('directional_indicator', 0.0)
        current_price = broadcast_data.get('close', 0.0)

        signal, signal_metadata = signal_generator.generate_signal(
            phi_sigma_value=phi_sigma if isinstance(phi_sigma, (int, float)) else 0.0,
            directional_indicator_value=directional if isinstance(directional, (int, float)) else 0.0,
            current_price=current_price
        )

        # Add signal data to broadcast
        broadcast_data['trading_signal'] = signal
        broadcast_data['entry_price'] = signal_metadata['entry_price']
        broadcast_data['position_open'] = signal_metadata['position_open']
        broadcast_data['pnl_pct'] = signal_metadata['pnl_pct']
        broadcast_data['stop_loss_price'] = signal_metadata['stop_loss_price']
        broadcast_data['take_profit_price'] = signal_metadata['take_profit_price']

        # Broadcast initial data
        if broadcaster and broadcaster.is_running:
            await broadcaster.broadcast(broadcast_data)
            print(f"[Pipeline] Broadcasted initial data to clients")
            print(f"[Pipeline] Features: phi_sigma={broadcast_data.get('phi_sigma', 'N/A'):.4f}, "
                  f"directional={broadcast_data.get('directional_indicator', 'N/A'):.4f}")
            print(f"[Pipeline] Signal: {signal}")

    async def run_with_websocket():
        """Run WebSocket server, Auth server, and data pipeline continuously."""
        # Start Auth server
        if auth_server:
            await auth_server.start()
            print(f"\nAuth server started on http://localhost:8766")

        # Start WebSocket server
        if broadcaster:
            await broadcaster.start()
            print(f"WebSocket server started on ws://localhost:8765")

            # Broadcast initial historical data so clients have something to display
            await broadcast_initial_data()

            # Start the data pipeline immediately (don't wait for clients)
            print("\n[Pipeline] Starting data pipeline...")
            pipeline_task_ref['task'] = asyncio.create_task(
                orchestrator.run_realtime_pipeline(callback=handle_bar)
            )
            print("[Pipeline] Data pipeline running continuously")
            print("Waiting for client connections...\n")

            # Keep the server running
            try:
                await asyncio.Future()  # Run forever
            except asyncio.CancelledError:
                pass

    try:
        asyncio.run(run_with_websocket())
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        # Stop the pipeline
        orchestrator.stop_streaming()
        if pipeline_task_ref['task'] and not pipeline_task_ref['task'].done():
            pipeline_task_ref['task'].cancel()
        # Stop the servers
        async def cleanup():
            if broadcaster:
                await broadcaster.stop()
            if auth_server:
                await auth_server.stop()
        asyncio.run(cleanup())
        print("Servers stopped.")


def main():
    """Main entry point with CLI argument parsing"""
    parser = argparse.ArgumentParser(
        description="Tribernachi-Enhanced TMS Pipeline with Multi-Provider Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run batch mode for gold using Massive.io (24 hours - default)
  python3 main.py --ticker XAUUSD --mode batch

  # Run batch mode for silver (48 hours) using Massive.io
  python3 main.py --ticker XAGUSD --mode batch --hours 48

  # Run batch mode for gold (30 minutes) using Massive.io
  python3 main.py --ticker XAUUSD --mode batch --minutes 30

  # Run batch mode for gold (2 hours and 30 minutes)
  python3 main.py --ticker XAUUSD --mode batch --hours 2 --minutes 30

  # Run with TopstepX provider
  python3 main.py --ticker XAUUSD --mode batch --hours 24 --provider topstepx

  # Run with file provider (parquet data)
  python3 main.py --ticker XAUUSD --mode batch --hours 24 --provider file

  # Run real-time streaming for gold using Massive.io
  python3 main.py --ticker XAUUSD --mode realtime

  # Run real-time streaming using TopstepX
  python3 main.py --ticker XAUUSD --mode realtime --provider topstepx
        """
    )

    parser.add_argument(
        '--ticker',
        type=str,
        default=None,
        help='Ticker symbol (e.g., XAUUSD for Massive.io)'
    )

    parser.add_argument(
        '--contract_id',
        type=str,
        default=None,
        help='Contract ID for TopstepX (e.g., CON.F.US.GCE.Z25)'
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['batch', 'realtime'],
        default='batch',
        help='Processing mode: batch or realtime (default: batch)'
    )

    parser.add_argument(
        '--hours',
        type=int,
        default=None,
        help='Hours of historical data for batch mode (default: 24 if neither hours nor minutes specified)'
    )

    parser.add_argument(
        '--minutes',
        type=int,
        default=None,
        help='Minutes of historical data for batch mode (can be combined with --hours)'
    )

    parser.add_argument(
        '--provider',
        type=str,
        choices=['massive', 'topstepx', 'file'],
        default='massive',
        help='Data provider: massive (Massive.io), topstepx (TopstepX), or file (parquet files) (default: massive)'
    )

    args = parser.parse_args()

    # Validate ticker/contract_id based on provider
    if args.ticker is None and args.contract_id is None:
        # Default to XAUUSD ticker
        args.ticker = 'XAUUSD'

    if args.ticker and args.contract_id:
        print("ERROR: Cannot specify both --ticker and --contract_id")
        print("Use --ticker for Massive.io or --contract_id for TopstepX")
        sys.exit(1)

    # Determine the symbol to use
    if args.contract_id:
        symbol = args.contract_id
        if args.provider != 'topstepx':
            print(f"WARNING: --contract_id is typically used with --provider topstepx")
    else:
        symbol = args.ticker

    # Calculate total hours from hours and/or minutes
    if args.hours is None and args.minutes is None:
        # Default: 24 hours
        total_hours = 24
    else:
        # Combine hours and minutes
        hours_value = args.hours if args.hours is not None else 0
        minutes_value = args.minutes if args.minutes is not None else 0
        total_hours = hours_value + (minutes_value / 60.0)

    # Format time display
    if args.hours is not None or args.minutes is not None:
        time_parts = []
        if args.hours:
            time_parts.append(f"{args.hours}h")
        if args.minutes:
            time_parts.append(f"{args.minutes}m")
        time_display = " ".join(time_parts)
    else:
        time_display = "24h (default)"

    # Print header
    print("\n" + "="*60)
    print("TRIBERNACHI-ENHANCED TMS PIPELINE")
    print("="*60)
    print(f"Timestamp: {datetime.now()}")
    print(f"Symbol: {symbol}")
    print(f"Mode: {args.mode.upper()}")
    print(f"Provider: {args.provider.upper()}")
    if args.mode == 'batch':
        print(f"History: {time_display} ({total_hours:.2f} hours)")
    print("="*60)

    # Run selected mode
    try:
        if args.mode == 'batch':
            run_batch_mode(symbol, total_hours, args.provider)
        elif args.mode == 'realtime':
            run_realtime_mode(symbol, args.provider)

        print("\n" + "="*60)
        print("EXECUTION COMPLETE")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
