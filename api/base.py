"""
Abstract base class for data providers.
All data providers must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable, Any, Dict
import pandas as pd


class AuthenticationError(Exception):
    """Base authentication error"""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Invalid username/password/API key"""
    pass


class TokenExpiredError(AuthenticationError):
    """JWT token has expired"""
    pass


class RateLimitError(Exception):
    """API rate limit exceeded"""
    pass


class DataFetchError(Exception):
    """Error fetching data from API"""
    pass


class DataProvider(ABC):
    """
    Abstract base class for data providers.

    All providers (Massive.io, TopstepX, File) must implement these methods
    to ensure consistent interface for the orchestrator.
    """

    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the data provider.

        Returns:
            bool: True if authentication successful, False otherwise
        """
        pass

    @abstractmethod
    def fetch_historical_data(
        self,
        ticker: str,
        hours: float
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical OHLCV data.

        Args:
            ticker: Ticker symbol (e.g., "XAUUSD" for gold)
            hours: Number of hours of historical data to fetch

        Returns:
            DataFrame with columns: Open_{ticker}, High_{ticker}, Low_{ticker},
            Close_{ticker}, Volume_{ticker}, VWAP_{ticker}
            Index: DatetimeIndex (UTC)

            Returns None if fetch fails.
        """
        pass

    @abstractmethod
    async def stream_realtime_data(
        self,
        ticker: str,
        callback: Optional[Callable] = None
    ) -> None:
        """
        Stream real-time data.

        Args:
            ticker: Ticker symbol
            callback: Function to call with each new bar/tick

        Note:
            This is an async method. Must be called with await.
        """
        pass

    @abstractmethod
    def normalize_ticker(self, ticker: str) -> Any:
        """
        Convert standard ticker format to provider-specific format.

        Args:
            ticker: Standard ticker (e.g., "XAUUSD")

        Returns:
            Provider-specific ticker format (str, dict, etc.)
        """
        pass

    @abstractmethod
    def normalize_dataframe(
        self,
        df: pd.DataFrame,
        ticker: str
    ) -> pd.DataFrame:
        """
        Normalize DataFrame to expected format with ticker suffixes.

        Args:
            df: Raw DataFrame from provider
            ticker: Ticker symbol

        Returns:
            DataFrame with standardized columns:
            - Open_{ticker}, High_{ticker}, Low_{ticker}, Close_{ticker}
            - Volume_{ticker}, VWAP_{ticker}
            - DatetimeIndex (UTC)
        """
        pass

    @abstractmethod
    def stop_streaming(self) -> None:
        """
        Stop real-time streaming.
        """
        pass

    def get_health_stats(self) -> Dict[str, Any]:
        """
        Get connection health statistics.

        Returns:
            dict: Health statistics (request count, error count, etc.)
        """
        return {
            'provider': self.__class__.__name__,
            'authenticated': hasattr(self, 'authenticated') and self.authenticated,
        }


def validate_dataframe(df: pd.DataFrame, ticker: str, min_bars: int = 61) -> bool:
    """
    Validate DataFrame meets feature computation requirements.

    Args:
        df: DataFrame to validate
        ticker: Ticker symbol
        min_bars: Minimum number of bars required

    Returns:
        bool: True if valid, False otherwise
    """
    # Check index
    if not isinstance(df.index, pd.DatetimeIndex):
        print(f"ERROR: Index is not DatetimeIndex")
        return False

    # Check minimum bars
    if len(df) < min_bars:
        print(f"WARNING: Insufficient bars ({len(df)} < {min_bars})")
        return False

    # Check required columns
    required_cols = [
        f'Open_{ticker}',
        f'High_{ticker}',
        f'Low_{ticker}',
        f'Close_{ticker}',
        f'Volume_{ticker}'
    ]

    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        print(f"ERROR: Missing columns: {missing}")
        return False

    return True
