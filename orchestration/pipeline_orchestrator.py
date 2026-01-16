"""
Pipeline Orchestrator with Multi-Provider Support
Coordinates real-time data streaming, feature computation, and TGC-enhanced caching
Supports Massive.io, TopstepX, and file-based data providers
"""

import asyncio
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

# Import feature calculation modules
sys.path.append('..')
from features.features_tf import compute_tf_mod, compute_tf_crit
from features.features_phi import compute_phi_sigma
from features.features_tvi import compute_tvi_enhanced
from features.features_svc import compute_svc_delta
from features.features_cvd import compute_cvd
from features.score_da_tem_e import compute_da_tem_e_minute
from features.features_directional import compute_directional_indicator

# Import Tribernachi modules
from tribernachi.tgc_encoder import TGCEncoder
from tribernachi.tvc_versioning import generate_tvc, generate_cache_key

# Import cache wrapper
from cache.feature_cache_wrapper import FeatureCacheWrapper


class PipelineOrchestrator:
    """
    Main orchestrator for the Tribernachi-Enhanced trading pipeline.

    Responsibilities:
    - Fetch historical data via pluggable data providers (Massive.io, TopstepX, or File)
    - Stream real-time data from supported providers
    - Compute features on incoming data
    - Cache results with TGC compression
    - Provide real-time feature updates
    """

    def __init__(
        self,
        provider,  # DataProvider instance
        ticker: str = "XAUUSD",
        cache_dir: str = "./cache_data",
        enable_compression: bool = True,
        history_hours: float = 48
    ):
        """
        Initialize the pipeline orchestrator.

        Args:
            provider: Data provider instance (Massive.io, TopstepX, or File)
            ticker: Ticker symbol (e.g., "XAUUSD" for gold, "XAGUSD" for silver)
            cache_dir: Directory for cache storage
            enable_compression: Enable TGC compression for caching
            history_hours: Hours of historical data to fetch (can be fractional, e.g., 0.5 = 30 minutes)
        """
        self.provider = provider
        self.ticker = ticker
        self.history_hours = history_hours

        # Initialize cache wrapper with TGC compression
        self.cache = FeatureCacheWrapper(
            cache_dir=cache_dir,
            enable_compression=enable_compression,
            enable_memory_cache=True
        )

        # TGC encoder for direct compression needs
        self.encoder = TGCEncoder()

        # Data history buffer (stores recent minute bars)
        self.minute_data = []
        self.max_history_length = 500  # Keep last 500 minutes

        # Real-time state
        self.latest_features = {}
        self.is_streaming = False

        print(f"Pipeline Orchestrator initialized:")
        print(f"  - Ticker: {ticker}")
        print(f"  - Provider: {provider.__class__.__name__}")
        print(f"  - Compression: {'Enabled' if enable_compression else 'Disabled'}")
        print(f"  - History: {history_hours} hours")

    def fetch_historical_data(self) -> Optional[pd.DataFrame]:
        """
        Fetch historical minute data using the configured provider.

        Returns:
            pd.DataFrame: Historical minute data with OHLCV columns
        """
        try:
            df = self.provider.fetch_historical_data(
                ticker=self.ticker,
                hours=self.history_hours
            )

            if df is not None and len(df) > 0:
                # Store in history buffer
                self.minute_data = df.to_dict('records')

            return df

        except Exception as e:
            print(f"  - ERROR fetching historical data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def compute_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all features on minute data.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            pd.DataFrame: DataFrame with all computed features
        """
        print(f"\nComputing features on {len(df)} minute bars...")

        ticker_base = self.ticker.replace(":", "_")

        # Check cache first
        cache_key_data = {
            'ticker': self.ticker,
            'start': str(df.index[0]),
            'end': str(df.index[-1]),
            'shape': df.shape
        }

        cached_features = self.cache.get(
            namespace='features',
            key_data=cache_key_data,
            max_age_hours=1.0  # Cache valid for 1 hour
        )

        if cached_features is not None:
            print("  - Using cached features")
            return cached_features

        # Compute features
        df_features = df.copy()

        # 1. TF features (Time-Flow compression)
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
        except Exception as e:
            print(f"  - Warning: TF feature computation failed: {e}")

        # 2. Phi Sigma (volatility regime)
        try:
            df_features['phi_sigma'] = compute_phi_sigma(
                df_features,
                ticker_base=ticker_base,
                window=14,
                ma_period=240
            )
        except Exception as e:
            print(f"  - Warning: Phi Sigma computation failed: {e}")

        # 3. TVI Enhanced (Time-Value Index with VWAP gating)
        try:
            tvi_result = compute_tvi_enhanced(
                df_features,
                ticker_base=ticker_base,
                atr_window=14,
                norm_window=60
            )
            # Merge TVI features back
            for col in tvi_result.columns:
                if col not in df_features.columns:
                    df_features[col] = tvi_result[col]
        except Exception as e:
            print(f"  - Warning: TVI Enhanced computation failed: {e}")

        # 4. SVC Delta (Signed Volume Change) - now returns DataFrame with multiple columns
        try:
            svc_result = compute_svc_delta(
                df_features,
                ticker_base=ticker_base,
                atr_window=14,
                baseline_window=120,
                quantile_lookback=240
            )
            # Merge SVC features back (includes svc_delta, svc_delta_pct, svc_extreme, etc.)
            for col in svc_result.columns:
                if col not in df_features.columns:
                    df_features[col] = svc_result[col]
        except Exception as e:
            print(f"  - Warning: SVC Delta computation failed: {e}")

        # 4.5. CVD (Cumulative Volume Delta) - status and momentum
        try:
            cvd_result = compute_cvd(
                df_features,
                ticker_base=ticker_base,
                momentum_lookback=5,
                pct_lookback=100
            )
            # Merge CVD features back (includes cvd, cvd_pct, cvd_status, cvd_momentum, delta)
            for col in cvd_result.columns:
                if col not in df_features.columns:
                    df_features[col] = cvd_result[col]
        except Exception as e:
            print(f"  - Warning: CVD computation failed: {e}")

        # 5. Directional Indicator (Momentum Fade)
        try:
            df_features['directional_indicator'] = compute_directional_indicator(
                df_features,
                ticker_base=ticker_base,
                lookback=20,
                percentile_window=100
            )
        except Exception as e:
            print(f"  - Warning: Directional Indicator computation failed: {e}")

        print(f"  - Feature computation complete")

        # Cache the results
        self.cache.set(
            namespace='features',
            key_data=cache_key_data,
            value=df_features,
            metadata={
                'ticker': self.ticker,
                'feature_count': len(df_features.columns),
                'row_count': len(df_features)
            }
        )

        return df_features

    def compute_da_tem_e_score(
        self,
        minute_data: pd.DataFrame,
        latest_oi: float = 0.0,
        sentiment: float = 0.5
    ) -> Optional[Dict]:
        """
        Compute DA-TEM-E score on minute data.

        Args:
            minute_data: DataFrame with minute OHLC data
            latest_oi: Latest open interest value
            sentiment: Sentiment score (0-1)

        Returns:
            dict: DA-TEM-E score and components
        """
        try:
            score_result = compute_da_tem_e_minute(
                minute_data,
                latest_oi=latest_oi,
                sentiment=sentiment,
                sma_period=60,
                corr_period=240
            )
            return score_result
        except Exception as e:
            print(f"  - ERROR computing DA-TEM-E score: {e}")
            return None

    async def stream_realtime_data(self, callback=None):
        """
        Stream real-time data using the configured provider.

        Args:
            callback: Optional callback function to handle incoming bars/ticks
        """
        try:
            await self.provider.stream_realtime_data(
                ticker=self.ticker,
                callback=callback
            )
        except NotImplementedError as e:
            print(f"  - {e}")
        except Exception as e:
            print(f"  - ERROR in real-time stream: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_streaming = False

    def stop_streaming(self):
        """Stop the real-time data stream."""
        self.provider.stop_streaming()

    def run_batch_pipeline(self) -> pd.DataFrame:
        """
        Run the complete batch processing pipeline.

        Returns:
            pd.DataFrame: Processed data with all features
        """
        print("\n=== Running Batch Pipeline ===")

        # 1. Fetch historical data using provider
        df = self.fetch_historical_data()

        if df is None:
            print("ERROR: Failed to load data")
            return None

        # 2. Compute all features
        df_features = self.compute_all_features(df)

        # 3. Display summary
        print(f"\n=== Pipeline Complete ===")
        print(f"Total bars processed: {len(df_features)}")
        print(f"Total features: {len(df_features.columns)}")
        print(f"\nLatest values:")
        print(df_features.tail(1).T)

        return df_features

    async def run_realtime_pipeline(self, callback=None):
        """
        Run the real-time streaming pipeline.

        Args:
            callback: Optional callback for processing incoming bars
        """
        print("\n=== Running Real-Time Pipeline ===")

        # 1. Fetch historical data to prime the buffer
        df = self.fetch_historical_data()

        # 2. Start streaming
        await self.stream_realtime_data(callback=callback)

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            dict: Cache statistics
        """
        return self.cache.get_stats()
