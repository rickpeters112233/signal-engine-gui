"""
File-based data provider implementation.
Wraps the existing DataLoader to provide parquet file access.
"""

import pandas as pd
from typing import Optional, Callable
from pathlib import Path

from .base import DataProvider


class FileDataProvider(DataProvider):
    """
    File-based data provider.

    Loads historical data from parquet files using the existing DataLoader.
    Real-time streaming is not supported.
    """

    # Ticker mapping from standard format to file symbols
    TICKER_MAP = {
        'XAUUSD': 'gc',  # Gold
        'XAGUSD': 'si',  # Silver
        'XPTUSD': 'pl',  # Platinum
        'XPDUSD': 'pa',  # Palladium
    }

    def __init__(self, data_dir: str = './data'):
        """
        Initialize file provider.

        Args:
            data_dir: Directory containing parquet files
        """
        self.data_dir = Path(data_dir)
        self.data_loader = None
        self.authenticated = False

        # Try to import and initialize DataLoader
        try:
            from data.data_loader import DataLoader
            self.data_loader = DataLoader(str(self.data_dir))
            self.authenticated = True
        except ImportError:
            print("WARNING: DataLoader not available. File provider will not work.")
        except Exception as e:
            print(f"WARNING: Failed to initialize DataLoader: {e}")

    def authenticate(self) -> bool:
        """
        Validate that data directory exists and DataLoader is available.

        Returns:
            bool: True if data directory is accessible
        """
        if self.data_loader is None:
            return False

        if not self.data_dir.exists():
            print(f"ERROR: Data directory does not exist: {self.data_dir}")
            return False

        self.authenticated = True
        return True

    def normalize_ticker(self, ticker: str) -> str:
        """
        Convert standard ticker to file symbol format.

        Args:
            ticker: Standard ticker (e.g., "XAUUSD")

        Returns:
            str: File symbol (e.g., "gc")
        """
        ticker_upper = ticker.upper()
        return self.TICKER_MAP.get(ticker_upper, ticker.lower())

    def fetch_historical_data(
        self,
        ticker: str,
        hours: float
    ) -> Optional[pd.DataFrame]:
        """
        Load historical data from parquet files.

        Args:
            ticker: Ticker symbol
            hours: Number of hours of data to load

        Returns:
            DataFrame with OHLCV data
        """
        print(f"\nLoading data from files for {ticker}...")

        if not self.authenticated:
            if not self.authenticate():
                return None

        if self.data_loader is None:
            print("ERROR: DataLoader not available")
            return None

        try:
            # Map ticker to file symbol
            file_symbol = self.normalize_ticker(ticker)

            # Load data using DataLoader
            df = self.data_loader.get_recent_data(
                ticker=file_symbol,
                tier='silver',  # Default to silver tier
                hours=hours
            )

            if df is None or len(df) == 0:
                print(f"  - WARNING: No data found for {ticker} ({file_symbol})")
                return None

            # Prepare for pipeline (adds ticker suffixes)
            df = self.data_loader.prepare_for_pipeline(df, ticker=ticker)

            print(f"  - Loaded {len(df)} bars from file")
            print(f"  - Date range: {df.index[0]} to {df.index[-1]}")

            return df

        except Exception as e:
            print(f"  - ERROR loading data from files: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def stream_realtime_data(
        self,
        ticker: str,
        callback: Optional[Callable] = None
    ) -> None:
        """
        Real-time streaming is not supported for file-based provider.

        Raises:
            NotImplementedError: Always raised
        """
        raise NotImplementedError(
            "Real-time streaming is not supported for file-based data provider. "
            "Use 'massive' or 'topstepx' provider for streaming."
        )

    def normalize_dataframe(
        self,
        df: pd.DataFrame,
        ticker: str
    ) -> pd.DataFrame:
        """
        Normalize DataFrame to expected format.

        Note: The DataLoader.prepare_for_pipeline() method already
        handles normalization, so this is mostly a passthrough.

        Args:
            df: DataFrame from files
            ticker: Ticker symbol

        Returns:
            Normalized DataFrame
        """
        # DataLoader already normalizes the data
        # Just ensure we have VWAP if missing
        ticker_base = ticker.upper()
        vwap_col = f'VWAP_{ticker_base}'

        if vwap_col not in df.columns:
            # Calculate approximate VWAP
            high_col = f'High_{ticker_base}'
            low_col = f'Low_{ticker_base}'
            close_col = f'Close_{ticker_base}'

            if all(col in df.columns for col in [high_col, low_col, close_col]):
                df[vwap_col] = (
                    df[high_col] + df[low_col] + df[close_col]
                ) / 3

        return df

    def stop_streaming(self) -> None:
        """No-op for file provider (streaming not supported)."""
        pass

    def get_health_stats(self) -> dict:
        """Get provider health statistics."""
        stats = super().get_health_stats()
        stats.update({
            'data_dir': str(self.data_dir),
            'data_dir_exists': self.data_dir.exists(),
            'dataloader_available': self.data_loader is not None
        })
        return stats
