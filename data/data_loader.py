"""
Data Loader Module
Loads historical OHLCV data from parquet files for testing and development
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Literal
from datetime import datetime, timedelta


class DataLoader:
    """
    Loads tiered data from parquet files.

    Data Tiers:
    - Bronze: Raw OHLC data
    - Silver: Cleaned OHLC data
    - Gold: OHLC data with computed features
    """

    def __init__(self, data_dir: str = "./data"):
        """
        Initialize data loader.

        Args:
            data_dir: Path to data directory containing bronze/silver/gold subdirectories
        """
        self.data_dir = Path(data_dir)

        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

        print(f"DataLoader initialized: {self.data_dir}")

    def load_bronze(
        self,
        ticker: str = "gc",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Load bronze tier data (raw OHLC).

        Args:
            ticker: Ticker symbol (gc=gold, si=silver, pl=platinum, etc.)
            start_date: Start date (YYYY-MM-DD) or None for all data
            end_date: End date (YYYY-MM-DD) or None for all data
            limit: Maximum number of rows to return

        Returns:
            pd.DataFrame: Bronze data with columns: Open, High, Low, Close, Volume, datetime
        """
        ticker = ticker.lower()
        bronze_file = self.data_dir / "bronze" / f"bronze.{ticker}.parquet"

        if not bronze_file.exists():
            raise FileNotFoundError(f"Bronze file not found: {bronze_file}")

        print(f"\nLoading bronze data: {bronze_file.name}")
        df = pd.read_parquet(bronze_file)

        # Rename 'Last' to 'Close' if present
        if 'Last' in df.columns and 'Close' not in df.columns:
            df = df.rename(columns={'Last': 'Close'})

        # Convert datetime to datetime index
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime').sort_index()

        # Filter by date range
        if start_date:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df.index <= pd.to_datetime(end_date)]

        # Apply limit
        if limit:
            df = df.tail(limit)

        print(f"  - Loaded {len(df)} rows")
        print(f"  - Date range: {df.index[0]} to {df.index[-1]}")
        print(f"  - Columns: {df.columns.tolist()}")

        return df

    def load_silver(
        self,
        ticker: str = "gc",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Load silver tier data (cleaned OHLC).

        Args:
            ticker: Ticker symbol
            start_date: Start date (YYYY-MM-DD) or None
            end_date: End date (YYYY-MM-DD) or None
            limit: Maximum number of rows

        Returns:
            pd.DataFrame: Silver data
        """
        ticker = ticker.lower()
        silver_file = self.data_dir / "silver" / f"silver.{ticker}.parquet"

        if not silver_file.exists():
            raise FileNotFoundError(f"Silver file not found: {silver_file}")

        print(f"\nLoading silver data: {silver_file.name}")
        df = pd.read_parquet(silver_file)

        # Convert datetime to index
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime').sort_index()

        # Filter by date range
        if start_date:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df.index <= pd.to_datetime(end_date)]

        # Apply limit
        if limit:
            df = df.tail(limit)

        print(f"  - Loaded {len(df)} rows")
        print(f"  - Date range: {df.index[0]} to {df.index[-1]}")

        return df

    def load_gold(
        self,
        ticker: str = "gc",
        version: Optional[str] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Load gold tier data (OHLC + computed features).

        Args:
            ticker: Ticker symbol
            version: Specific version (e.g., "20251017.01") or None for latest
            limit: Maximum number of rows

        Returns:
            pd.DataFrame: Gold data with features
        """
        ticker = ticker.lower()
        gold_dir = self.data_dir / "gold"

        if version:
            gold_file = gold_dir / f"gold.{ticker}_{version}.parquet"
        else:
            # Find latest version
            gold_files = list(gold_dir.glob(f"gold.{ticker}_*.parquet"))
            if not gold_files:
                raise FileNotFoundError(f"No gold files found for ticker: {ticker}")
            gold_file = sorted(gold_files)[-1]  # Latest version

        if not gold_file.exists():
            raise FileNotFoundError(f"Gold file not found: {gold_file}")

        print(f"\nLoading gold data: {gold_file.name}")
        df = pd.read_parquet(gold_file)

        # Convert datetime to index
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime').sort_index()

        # Apply limit
        if limit:
            df = df.tail(limit)

        print(f"  - Loaded {len(df)} rows")
        print(f"  - Date range: {df.index[0]} to {df.index[-1]}")
        print(f"  - Features: {[c for c in df.columns if c not in ['Open', 'High', 'Low', 'Close', 'Volume']]}")

        return df

    def prepare_for_pipeline(
        self,
        df: pd.DataFrame,
        ticker: str = "GC=F"
    ) -> pd.DataFrame:
        """
        Prepare loaded data for pipeline processing.
        Adds ticker suffix to column names to match pipeline expectations.

        Args:
            df: DataFrame with OHLC data
            ticker: Ticker symbol for column naming

        Returns:
            pd.DataFrame: Prepared data with ticker-suffixed columns
        """
        # Reset index to have datetime as column
        if df.index.name == 'datetime' or isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            if 'index' in df.columns:
                df = df.rename(columns={'index': 'datetime'})

        # Ensure datetime column exists
        if 'datetime' not in df.columns:
            raise ValueError("DataFrame must have a 'datetime' column")

        # Set datetime as index
        df = df.set_index('datetime').sort_index()

        # Add ticker suffix to OHLCV columns
        ticker_base = ticker.replace(":", "_").replace("=", "")

        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df.columns:
                df[f"{col}_{ticker_base}"] = df[col]

        # Add VWAP if not present (approximate as (H+L+C)/3)
        vwap_col = f"VWAP_{ticker_base}"
        if vwap_col not in df.columns and all(c in df.columns for c in ['High', 'Low', 'Close']):
            df[vwap_col] = (df['High'] + df['Low'] + df['Close']) / 3

        print(f"\nPrepared data for pipeline:")
        print(f"  - Ticker: {ticker} -> {ticker_base}")
        print(f"  - Columns: {[c for c in df.columns if ticker_base in c]}")

        return df

    def get_recent_data(
        self,
        ticker: str = "gc",
        tier: Literal["bronze", "silver", "gold"] = "silver",
        hours: float = 24
    ) -> pd.DataFrame:
        """
        Get most recent N hours of data.

        Args:
            ticker: Ticker symbol
            tier: Data tier to load from
            hours: Number of hours of recent data (can be fractional, e.g., 0.5 = 30 minutes)

        Returns:
            pd.DataFrame: Recent data
        """
        # Calculate limit (approximate minutes) - convert to int for indexing
        limit = int(hours * 60)

        if tier == "bronze":
            df = self.load_bronze(ticker, limit=limit)
        elif tier == "silver":
            df = self.load_silver(ticker, limit=limit)
        elif tier == "gold":
            df = self.load_gold(ticker, limit=limit)
        else:
            raise ValueError(f"Invalid tier: {tier}")

        return df


# Example usage
if __name__ == "__main__":
    loader = DataLoader()

    # Load recent 24 hours of gold data
    df = loader.get_recent_data(ticker="gc", tier="silver", hours=24)

    # Prepare for pipeline
    df_prepared = loader.prepare_for_pipeline(df, ticker="GC=F")

    print(f"\nSample data:")
    print(df_prepared.tail())
