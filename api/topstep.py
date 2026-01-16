"""
TopstepX data provider implementation.
Handles REST API and polling for TopstepX market data.

Features:
- Automatic retry with exponential backoff for transient errors
- SSL error handling and recovery
- Token refresh on authentication failures
- Connection pooling for efficiency
"""

import asyncio
import os
import logging
import requests
import pandas as pd
import ssl
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Callable, Dict
from pathlib import Path
from dotenv import set_key
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import (
    DataProvider,
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
    DataFetchError,
)


def create_resilient_session(
    retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple = (500, 502, 503, 504),
) -> requests.Session:
    """
    Create a requests Session with automatic retry logic.

    Args:
        retries: Number of retries for failed requests
        backoff_factor: Backoff multiplier between retries
        status_forcelist: HTTP status codes to retry

    Returns:
        Configured requests.Session
    """
    session = requests.Session()

    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10,
    )

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


class TopstepXDataProvider(DataProvider):
    """
    TopstepX API data provider.

    Provides historical data via REST API and real-time tick data via SignalR.
    """

    # Ticker mapping from standard format to TopstepX contract symbols
    TICKER_MAP = {
        "XAUUSD": "GC",  # Gold
        "XAGUSD": "SI",  # Silver
        "XPTUSD": "PL",  # Platinum
        "XPDUSD": "PA",  # Palladium
        "CL": "CL",  # Crude Oil (passthrough)
        "GC": "GC",  # Gold (passthrough)
        "SI": "SI",  # Silver (passthrough)
    }

    # Contract ID template for TopstepX
    # Format: CON.F.US.{symbol}E.{expiry}
    # Example: CON.F.US.GCE.Z25 (Gold December 2025)
    # Futures month codes: F=Jan, G=Feb, H=Mar, J=Apr, K=May, M=Jun, N=Jul, Q=Aug, U=Sep, V=Oct, X=Nov, Z=Dec
    CONTRACT_TEMPLATE = "CON.F.US.{}E.Z25"  # Using Z25 (Dec 2025)

    # Retry configuration
    MAX_RETRIES = 5
    BASE_RETRY_DELAY = 2.0  # seconds
    MAX_RETRY_DELAY = 60.0  # seconds

    # Transient errors that should trigger retry
    TRANSIENT_ERRORS = (
        requests.exceptions.SSLError,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ChunkedEncodingError,
        ConnectionResetError,
        ssl.SSLError,
    )

    def __init__(
        self,
        username: str,
        password: str,
        api_key: str,
        current_token: Optional[str] = None,
    ):
        """
        Initialize TopstepX provider.

        Args:
            username: TopstepX username
            password: TopstepX password (not used - kept for compatibility)
            api_key: TopstepX API key
            current_token: Optional current JWT token (skips login if provided)
        """
        self.username = username
        self.password = password  # Not used in loginKey endpoint
        self.api_key = api_key
        self.current_token = current_token
        self.auth_token = None
        self.base_url = "https://api.topstepx.com/api"
        self.authenticated = False
        self.stop_event = asyncio.Event()
        self.contract_cache = {}  # Cache contract IDs
        self.dotenv_path = None  # Will be set if we need to update token

        # Create resilient HTTP session
        self._session = create_resilient_session(retries=3, backoff_factor=0.5)

        # Track consecutive errors for adaptive backoff
        self._consecutive_errors = 0
        self._last_successful_request = None

    def authenticate(self) -> bool:
        """
        Authenticate with TopstepX API using loginKey endpoint.

        Returns:
            bool: True if authentication successful
        """
        # Try using current token first
        if self.current_token and self.current_token.strip():
            self.auth_token = self.current_token
            if self._validate_token():
                self.authenticated = True
                print("TopstepX: Using provided token (validated)")
                return True
            else:
                print("TopstepX: Provided token invalid, attempting login")

        # Login with username and API key
        try:
            payload = {"userName": self.username, "apiKey": self.api_key}

            response = requests.post(
                f"{self.base_url}/Auth/loginKey",
                json=payload,
                headers={"Content-Type": "application/json", "accept": "text/plain"},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("success") and data.get("token"):
                    self.auth_token = data["token"]
                    self.authenticated = True
                    print(f"TopstepX: Authentication successful")
                    self._update_env_token(self.auth_token)
                    return True
                else:
                    error_msg = data.get("message", "No error message")
                    print(f"TopstepX: Login failed: {error_msg}")
                    print(f"TopstepX: Full response: {data}")
                    raise InvalidCredentialsError(f"Login failed: {error_msg}")
            else:
                print(
                    f"TopstepX: Login failed: {response.status_code} - {response.text}"
                )
                raise InvalidCredentialsError(f"Login failed: {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"TopstepX: Authentication error: {e}")
            import traceback

            traceback.print_exc()
            raise AuthenticationError(f"Failed to authenticate: {e}")

    def _validate_token(self) -> bool:
        """
        Validate current auth token using TopstepX validate endpoint.

        Returns:
            bool: True if token is valid
        """
        try:
            response = requests.post(
                f"{self.base_url}/Auth/validate",
                headers={
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"TopstepX: Token validation failed: {e}")
            return False

    def _update_env_token(self, token: str) -> None:
        """
        Update TOPSTEP_CURRENT_TOKEN in .env file.

        Args:
            token: JWT token to save
        """
        try:
            # Find .env file (go up from api/ to project root)
            if self.dotenv_path is None:
                current_dir = Path(__file__).resolve().parent
                self.dotenv_path = current_dir.parent / ".env"

            if self.dotenv_path.exists():
                set_key(self.dotenv_path, "TOPSTEP_CURRENT_TOKEN", token)
                print(f"TopstepX: Updated TOPSTEP_CURRENT_TOKEN in .env")
            else:
                print(f"TopstepX: Warning - .env file not found at {self.dotenv_path}")
        except Exception as e:
            print(f"TopstepX: Failed to update .env token: {e}")

    def _reset_session(self) -> None:
        """Reset the HTTP session to recover from connection issues."""
        try:
            self._session.close()
        except Exception:
            pass
        self._session = create_resilient_session(retries=3, backoff_factor=0.5)
        print("TopstepX: HTTP session reset")

    def _make_request_with_retry(
        self, method: str, url: str, max_retries: Optional[int] = None, **kwargs
    ) -> Optional[requests.Response]:
        """
        Make an HTTP request with comprehensive retry logic.

        Handles:
        - SSL errors (connection reset, unexpected EOF)
        - Connection errors (network issues)
        - Timeout errors
        - Token expiration (re-authenticates)

        Args:
            method: HTTP method ('GET' or 'POST')
            url: Request URL
            max_retries: Override default max retries
            **kwargs: Additional arguments for requests

        Returns:
            Response object or None if all retries failed
        """
        retries = max_retries or self.MAX_RETRIES
        last_error = None

        # Set default timeout if not provided
        if "timeout" not in kwargs:
            kwargs["timeout"] = 30

        for attempt in range(retries):
            try:
                if method.upper() == "POST":
                    response = self._session.post(url, **kwargs)
                else:
                    response = self._session.get(url, **kwargs)

                # Check for auth errors (401/403) - might need to re-authenticate
                if response.status_code in (401, 403):
                    print(
                        f"TopstepX: Auth error ({response.status_code}), re-authenticating..."
                    )
                    self.authenticated = False
                    if self.authenticate():
                        # Update auth header and retry
                        if "headers" in kwargs:
                            kwargs["headers"]["Authorization"] = (
                                f"Bearer {self.auth_token}"
                            )
                        continue
                    else:
                        print("TopstepX: Re-authentication failed")
                        return None

                # Success - reset error counter and return
                self._consecutive_errors = 0
                self._last_successful_request = time.time()
                return response

            except self.TRANSIENT_ERRORS as e:
                last_error = e
                self._consecutive_errors += 1

                # Calculate backoff with exponential increase and jitter
                base_delay = self.BASE_RETRY_DELAY * (2**attempt)
                jitter = base_delay * 0.2 * (0.5 - time.time() % 1)  # ±10% jitter
                delay = min(base_delay + jitter, self.MAX_RETRY_DELAY)

                error_type = type(e).__name__
                print(
                    f"⚠ {error_type} on attempt {attempt + 1}/{retries}: {str(e)[:100]}"
                )

                if attempt < retries - 1:
                    print(f"  Retrying in {delay:.1f}s...")

                    # Reset session on SSL/connection errors to get fresh connection
                    if isinstance(
                        e,
                        (
                            requests.exceptions.SSLError,
                            ssl.SSLError,
                            ConnectionResetError,
                        ),
                    ):
                        self._reset_session()
                        # Re-add auth header after session reset
                        if "headers" not in kwargs:
                            kwargs["headers"] = {}
                        if self.auth_token:
                            kwargs["headers"]["Authorization"] = (
                                f"Bearer {self.auth_token}"
                            )

                    time.sleep(delay)
                else:
                    print(f"✗ All {retries} attempts failed")

            except Exception as e:
                # Unexpected error - log and don't retry
                print(f"✗ Unexpected error: {type(e).__name__}: {e}")
                last_error = e
                break

        return None

    async def _make_request_with_retry_async(
        self, method: str, url: str, max_retries: Optional[int] = None, **kwargs
    ) -> Optional[requests.Response]:
        """
        Async wrapper for _make_request_with_retry that uses asyncio.sleep.

        Args:
            method: HTTP method ('GET' or 'POST')
            url: Request URL
            max_retries: Override default max retries
            **kwargs: Additional arguments for requests

        Returns:
            Response object or None if all retries failed
        """
        retries = max_retries or self.MAX_RETRIES
        last_error = None

        # Set default timeout if not provided
        if "timeout" not in kwargs:
            kwargs["timeout"] = 30

        for attempt in range(retries):
            try:
                # Run the blocking request in a thread pool
                loop = asyncio.get_event_loop()
                if method.upper() == "POST":
                    response = await loop.run_in_executor(
                        None, lambda: self._session.post(url, **kwargs)
                    )
                else:
                    response = await loop.run_in_executor(
                        None, lambda: self._session.get(url, **kwargs)
                    )

                # Check for auth errors (401/403)
                if response.status_code in (401, 403):
                    print(
                        f"TopstepX: Auth error ({response.status_code}), re-authenticating..."
                    )
                    self.authenticated = False
                    if self.authenticate():
                        if "headers" in kwargs:
                            kwargs["headers"]["Authorization"] = (
                                f"Bearer {self.auth_token}"
                            )
                        continue
                    else:
                        print("TopstepX: Re-authentication failed")
                        return None

                # Success
                self._consecutive_errors = 0
                self._last_successful_request = time.time()
                return response

            except self.TRANSIENT_ERRORS as e:
                last_error = e
                self._consecutive_errors += 1

                # Exponential backoff with jitter
                base_delay = self.BASE_RETRY_DELAY * (2**attempt)
                jitter = base_delay * 0.2 * (0.5 - time.time() % 1)
                delay = min(base_delay + jitter, self.MAX_RETRY_DELAY)

                error_type = type(e).__name__
                print(
                    f"⚠ {error_type} on attempt {attempt + 1}/{retries}: {str(e)[:100]}"
                )

                if attempt < retries - 1:
                    print(f"  Retrying in {delay:.1f}s...")

                    # Reset session on connection errors
                    if isinstance(
                        e,
                        (
                            requests.exceptions.SSLError,
                            ssl.SSLError,
                            ConnectionResetError,
                        ),
                    ):
                        self._reset_session()
                        if "headers" not in kwargs:
                            kwargs["headers"] = {}
                        if self.auth_token:
                            kwargs["headers"]["Authorization"] = (
                                f"Bearer {self.auth_token}"
                            )

                    await asyncio.sleep(delay)
                else:
                    print(f"✗ All {retries} attempts failed")

            except Exception as e:
                print(f"✗ Unexpected error: {type(e).__name__}: {e}")
                last_error = e
                break

        return None

    def normalize_ticker(self, ticker: str) -> str:
        """
        Convert standard ticker to TopstepX contract ID format.

        Args:
            ticker: Standard ticker (e.g., "XAUUSD") or contract ID (e.g., "CON.F.US.GCE.Z25")

        Returns:
            str: TopstepX contract ID (e.g., "CON.F.US.GCE.Z25")
        """
        # If already a contract ID, return as-is
        if ticker.startswith("CON.F.US."):
            return ticker

        # Convert ticker to contract ID
        ticker_upper = ticker.upper()
        symbol = self.TICKER_MAP.get(ticker_upper, ticker_upper)
        contract_id = self.CONTRACT_TEMPLATE.format(symbol)
        return contract_id

    def _parse_contract_display(self, contract_id: str) -> str:
        """
        Parse contract ID into human-readable format.

        Args:
            contract_id: TopstepX contract ID (e.g., "CON.F.US.GCE.Z25")

        Returns:
            str: Display name (e.g., "Gold Futures (GCE) Dec 2025")
        """
        try:
            # Parse contract: CON.F.US.GCE.Z25
            parts = contract_id.split(".")
            if len(parts) >= 5:
                base_symbol = parts[3]  # GCE
                expiry = parts[4]  # Z25

                # Map symbols to full names
                symbol_names = {
                    "GCE": "Gold Futures",
                    "SIE": "Silver Futures",
                    "PLE": "Platinum Futures",
                    "PAE": "Palladium Futures",
                    "CLE": "Crude Oil Futures",
                    "RTYE": "Russell 2000 Futures",
                    "ESE": "E-mini S&P 500 Futures",
                    "NQE": "E-mini Nasdaq Futures",
                }

                # Map month codes to names
                month_codes = {
                    "F": "Jan",
                    "G": "Feb",
                    "H": "Mar",
                    "J": "Apr",
                    "K": "May",
                    "M": "Jun",
                    "N": "Jul",
                    "Q": "Aug",
                    "U": "Sep",
                    "V": "Oct",
                    "X": "Nov",
                    "Z": "Dec",
                }

                full_name = symbol_names.get(base_symbol, base_symbol)
                month_code = expiry[0] if expiry else "?"
                year = f"20{expiry[1:]}" if len(expiry) > 1 else "??"
                month_name = month_codes.get(month_code, month_code)

                return f"{full_name} ({base_symbol}) {month_name} {year}"
        except:
            pass

        return contract_id

    def _get_contract_id(self, ticker: str) -> Optional[str]:
        """
        Get TopstepX contract ID for a ticker symbol.

        Args:
            ticker: Ticker symbol

        Returns:
            str: Contract ID or None if not found
        """
        # Check cache first
        if ticker in self.contract_cache:
            return self.contract_cache[ticker]

        normalized_ticker = self.normalize_ticker(ticker)

        try:
            response = requests.get(
                f"{self.base_url}/contracts",
                params={"symbol": normalized_ticker},
                headers={"Authorization": f"Bearer {self.auth_token}"},
                timeout=10,
            )

            if response.status_code == 200:
                contracts = response.json()
                if contracts and len(contracts) > 0:
                    contract_id = contracts[0].get("id") or contracts[0].get(
                        "contractId"
                    )
                    # Cache it
                    if contract_id:
                        self.contract_cache[ticker] = contract_id
                    return contract_id

            print(f"TopstepX: No contracts found for {normalized_ticker}")
            return None

        except Exception as e:
            print(f"TopstepX: Error getting contract ID: {e}")
            return None

    def fetch_historical_data(
        self, ticker: str, hours: float
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical minute data from TopstepX using /api/History/retrieveBars endpoint.

        Args:
            ticker: Ticker symbol
            hours: Number of hours of historical data

        Returns:
            DataFrame with OHLCV data
        """
        if not self.authenticated:
            if not self.authenticate():
                return None

        # Get contract ID using template (e.g., "CON.F.US.GCE.Z25")
        contract_id = self.normalize_ticker(ticker)
        display_info = self._parse_contract_display(contract_id)

        print(f"\nFetching historical data from TopstepX...")
        print(f"  Contract: {display_info}")

        # Calculate time range
        limit = 500
        end_time = datetime.now(timezone.utc)
        start_time = datetime.now(timezone.utc) - timedelta(days=365)

        # Build request payload according to Swagger spec
        request_payload = {
            "contractId": contract_id,
            "live": False,  # Use simulation account data
            "startTime": start_time.isoformat(),
            "endTime": end_time.isoformat(),
            "unit": 2,  # 2 = Minute (from AggregateBarUnit enum)
            "unitNumber": 1,  # 1-minute bars
            "limit": limit,  # Set limit to MAX amount of bars
            "includePartialBar": False,  # Exclude incomplete bars
        }

        print(
            f"  Timeframe: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}"
        )

        try:
            response = requests.post(
                f"{self.base_url}/History/retrieveBars",
                json=request_payload,
                headers={
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()

                if not data.get("success"):
                    error_code = data.get("errorCode")
                    error_msg = data.get("errorMessage", "Unknown error")
                    print(f"  ✗ API Error (code {error_code}): {error_msg}")
                    return None

                bars = data.get("bars", [])

                if len(bars) == 0:
                    print(f"  ⚠ No bars returned (markets may be closed)")
                    return None

                df = self._parse_historical_response(bars, ticker)

                if df is not None and len(df) > 0:
                    print(f"  ✓ Received {len(df)} bars")
                    print(f"  Range: {df.index[0]} to {df.index[-1]}\n")
                    return df
                else:
                    print(f"  ✗ Failed to parse response")
                    return None

            else:
                print(f"  ✗ HTTP Error: {response.status_code}")
                return None

        except Exception as e:
            print(f"  ✗ Error: {e}")
            return None

    def _parse_historical_response(
        self, bars: list, ticker: str
    ) -> Optional[pd.DataFrame]:
        """
        Parse TopstepX historical API response into DataFrame.

        Args:
            bars: List of bar objects from API (AggregateBarModel[])
            ticker: Ticker symbol

        Returns:
            Normalized DataFrame
        """
        # Response format from Swagger (AggregateBarModel):
        # {"t": "2024-12-03T10:30:00Z", "o": 2600.5, "h": 2601.0, "l": 2600.0, "c": 2600.8, "v": 150}

        if not bars:
            return None

        df_data = []
        for bar in bars:
            # Parse AggregateBarModel with shorthand properties
            df_data.append(
                {
                    "datetime": pd.to_datetime(bar["t"]),  # ISO 8601 datetime string
                    "open": float(bar["o"]),
                    "high": float(bar["h"]),
                    "low": float(bar["l"]),
                    "close": float(bar["c"]),
                    "volume": int(bar["v"]),
                }
            )

        df = pd.DataFrame(df_data)
        df = df.set_index("datetime").sort_index()

        # Normalize to expected format (adds ticker suffix to columns)
        df = self.normalize_dataframe(df, ticker)

        return df

    async def stream_realtime_data(
        self, ticker: str, callback: Optional[Callable] = None
    ) -> None:
        """
        Poll for real-time bar data using the retrieveBars endpoint.

        Features:
        - Automatic retry with exponential backoff for transient errors
        - SSL error recovery with session reset
        - Re-authentication on token expiration
        - Adaptive polling interval based on error rate

        Args:
            ticker: Ticker symbol (e.g., "XAUUSD | CON.F.US.GCE.Z25")
            callback: Optional callback for new bars
        """
        print(f"\nStarting TopstepX polling for {ticker}...")

        if not self.authenticated:
            if not self.authenticate():
                print("TopstepX: Cannot poll - authentication failed")
                return

        contract_id = self.normalize_ticker(ticker)
        print(f"TopstepX: Using contract ID: {contract_id}")

        # Parse contract for display
        display_info = self._parse_contract_display(contract_id)
        print(f"\n{'=' * 60}")
        print(f"Polling real-time data...")
        print(f"{'=' * 60}")
        print(f"  Contract: {display_info}")
        print(f"  Poll interval: 3 seconds (adaptive)")
        print(f"  Max retries per request: {self.MAX_RETRIES}")
        print(f"  Press Ctrl+C to stop\n")

        # Configuration
        limit = 500
        base_poll_interval = 3  # Base poll interval in seconds
        max_poll_interval = 30  # Max poll interval when errors occur
        start_time = datetime.now(timezone.utc) - timedelta(minutes=limit)

        # Track last processed bar timestamp to avoid duplicates
        processed_bars = set()

        # Track polling stats
        successful_polls = 0
        failed_polls = 0

        try:
            while not self.stop_event.is_set():
                poll_start = time.time()

                try:
                    # End time is always current time
                    end_time = datetime.now(timezone.utc)

                    # API request payload
                    payload = {
                        "contractId": contract_id,
                        "live": False,
                        "startTime": start_time.isoformat(),
                        "endTime": end_time.isoformat(),
                        "unit": 2,  # Minute
                        "unitNumber": 1,
                        "limit": limit,
                        "includePartialBar": False,
                    }

                    # Make API request with retry logic
                    response = await self._make_request_with_retry_async(
                        method="POST",
                        url=f"{self.base_url}/History/retrieveBars",
                        headers={
                            "Authorization": f"Bearer {self.auth_token}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=30,
                    )

                    # Check if request completely failed (all retries exhausted)
                    if response is None:
                        failed_polls += 1
                        print(
                            f"✗ Request failed after all retries (total failures: {failed_polls})"
                        )

                        # Adaptive backoff - wait longer when experiencing repeated failures
                        backoff = min(
                            base_poll_interval
                            * (2 ** min(self._consecutive_errors, 4)),
                            max_poll_interval,
                        )
                        print(f"  Waiting {backoff:.1f}s before next attempt...")
                        await asyncio.sleep(backoff)
                        continue

                    if response.status_code != 200:
                        failed_polls += 1
                        print(f"✗ API error: HTTP {response.status_code}")
                        await asyncio.sleep(base_poll_interval)
                        continue

                    result = response.json()

                    if not result.get("success"):
                        failed_polls += 1
                        error_code = result.get("errorCode", "N/A")
                        error_msg = result.get("errorMessage", "Unknown error")
                        print(f"✗ API returned error (code {error_code}): {error_msg}")

                        # Check for token-related errors
                        if error_code in (401, 403, "UNAUTHORIZED", "TOKEN_EXPIRED"):
                            print("  Re-authenticating...")
                            self.authenticated = False
                            if not self.authenticate():
                                print("  Re-authentication failed, will retry...")

                        await asyncio.sleep(base_poll_interval)
                        continue

                    # Success!
                    successful_polls += 1
                    bars = result.get("bars", [])

                    if not bars:
                        # No data but request succeeded - this is normal during market close
                        if successful_polls % 20 == 0:  # Log every 20 polls (~1 minute)
                            print(f"⏳ Polling... no new bars (market may be closed)")
                        await asyncio.sleep(base_poll_interval)
                        continue

                    # Process new bars only
                    new_bars = []
                    for bar in bars:
                        bar_timestamp = bar.get("t")
                        if bar_timestamp and bar_timestamp not in processed_bars:
                            new_bars.append(bar)
                            processed_bars.add(bar_timestamp)

                    # Memory management - keep enough timestamps to match limit
                    # Must keep at least as many as the limit to avoid re-processing old bars
                    max_tracked = limit + 100  # Buffer for safety
                    if len(processed_bars) > max_tracked:
                        sorted_timestamps = sorted(processed_bars)
                        processed_bars = set(sorted_timestamps[-limit:])

                    # Log when we're polling but not finding new bars
                    if not new_bars and bars:
                        if successful_polls % 20 == 0:  # Log every ~1 minute
                            last_bar_time = (
                                bars[-1].get("t", "unknown") if bars else "none"
                            )
                            print(
                                f"⏳ Polling... waiting for new bar (last: {last_bar_time})"
                            )

                    # Call callback for each new bar
                    if new_bars and callback:
                        for bar in new_bars:
                            try:
                                o, h, l, c = (
                                    float(bar["o"]),
                                    float(bar["h"]),
                                    float(bar["l"]),
                                    float(bar["c"]),
                                )
                                bar_data = {
                                    "datetime": pd.to_datetime(bar["t"]),
                                    "timestamp": pd.to_datetime(bar["t"]),
                                    "Open": o,
                                    "High": h,
                                    "Low": l,
                                    "Close": c,
                                    "Volume": int(bar["v"]),
                                    "VWAP": (h + l + c) / 3,
                                }
                                await callback(bar_data)
                            except Exception as e:
                                print(f"⚠ Error processing bar: {e}")

                    # Reset consecutive errors on success
                    self._consecutive_errors = 0

                except asyncio.CancelledError:
                    print("\nPolling cancelled")
                    break
                except Exception as e:
                    failed_polls += 1
                    self._consecutive_errors += 1
                    error_type = type(e).__name__
                    print(f"✗ Unexpected polling error ({error_type}): {e}")

                    # Don't print full traceback for known transient errors
                    if not isinstance(e, self.TRANSIENT_ERRORS):
                        import traceback

                        traceback.print_exc()

                # Calculate adaptive poll interval
                # Increase interval if experiencing errors, decrease if stable
                if self._consecutive_errors > 0:
                    poll_interval = min(
                        base_poll_interval * (1.5 ** min(self._consecutive_errors, 4)),
                        max_poll_interval,
                    )
                else:
                    poll_interval = base_poll_interval

                # Account for time spent processing
                elapsed = time.time() - poll_start
                sleep_time = max(0.1, poll_interval - elapsed)

                await asyncio.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n\nStopping polling...")
        except Exception as e:
            print(f"\n✗ Fatal error: {e}")
            import traceback

            traceback.print_exc()
        finally:
            # Print stats
            total_polls = successful_polls + failed_polls
            if total_polls > 0:
                success_rate = (successful_polls / total_polls) * 100
                print(
                    f"\nPolling stats: {successful_polls}/{total_polls} successful ({success_rate:.1f}%)"
                )

    def _aggregate_tick(
        self, price: float, volume: float, timestamp: str
    ) -> Optional[dict]:
        """
        Aggregate ticks into 1-minute bars.

        Args:
            price: Trade price
            volume: Trade volume
            timestamp: Trade timestamp (ISO format)

        Returns:
            Completed bar dict if minute changed, None otherwise
        """
        try:
            # Parse timestamp and get minute start
            if timestamp.endswith("+00:00"):
                timestamp = timestamp.replace("+00:00", "Z")
            trade_time = pd.to_datetime(timestamp)

            # Round down to minute start
            minute_start = trade_time.floor("T")

            # price = round(price, 1)
            self.last_price = price

            # First tick - initialize bar
            if self.current_bar is None:
                self.current_minute = minute_start
                self.current_bar = {
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": volume,
                    "timestamp": None,
                }
                return None

            # Same minute - update current bar
            if minute_start == self.current_minute:
                self.current_bar["high"] = max(self.current_bar["high"], price)
                self.current_bar["low"] = min(self.current_bar["low"], price)
                self.current_bar["close"] = price
                self.current_bar["volume"] += volume
                return None

            # New minute - finalize previous bar and start new one
            if minute_start > self.current_minute:
                # Finalize the completed bar
                completed_bar = self.current_bar.copy()
                completed_bar["timestamp"] = self.current_minute.isoformat()
                completed_bar["datetime"] = self.current_minute

                # Fill any skipped minutes with zero-volume bars
                current_time = self.current_minute
                while current_time + pd.Timedelta(minutes=1) < minute_start:
                    current_time = current_time + pd.Timedelta(minutes=1)
                    zero_bar = {
                        "open": self.last_price,
                        "high": self.last_price,
                        "low": self.last_price,
                        "close": self.last_price,
                        "volume": 0,
                        "timestamp": current_time.isoformat(),
                        "datetime": current_time,
                    }
                    self.aggregated_bars.append(zero_bar)

                # Store completed bar
                self.aggregated_bars.append(completed_bar)

                # Keep only last 600 bars
                if len(self.aggregated_bars) > 600:
                    self.aggregated_bars.pop(0)

                # Start new bar
                self.current_minute = minute_start
                self.current_bar = {
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": volume,
                    "timestamp": None,
                }

                return completed_bar

        except Exception as e:
            print(f"TopstepX: Error aggregating tick: {e}")
            import traceback

            traceback.print_exc()
            return None

    def _parse_trade_to_tick(self, trade_data: dict, ticker: str) -> Optional[dict]:
        """
        Convert SignalR trade event to tick format.

        Args:
            trade_data: Trade data from SignalR
            ticker: Ticker symbol

        Returns:
            dict: Tick data
        """
        try:
            timestamp = (
                trade_data.get("timestamp")
                or trade_data.get("time")
                or trade_data.get("t")
            )
            price = trade_data.get("price") or trade_data.get("p")
            size = (
                trade_data.get("size")
                or trade_data.get("quantity")
                or trade_data.get("s", 0)
            )

            if not timestamp or not price:
                return None

            return {
                "timestamp": timestamp,
                "datetime": pd.to_datetime(timestamp, unit="ms"),
                "price": price,
                "size": size,
                "ticker": ticker,
            }
        except Exception as e:
            print(f"TopstepX: Error parsing trade: {e}")
            return None

    def normalize_dataframe(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """
        Normalize DataFrame to expected format.

        For tick data, we use price for all OHLC values.

        Args:
            df: Raw DataFrame
            ticker: Ticker symbol

        Returns:
            Normalized DataFrame
        """
        ticker_base = ticker.upper()

        # If we have OHLC columns, use them
        if "open" in df.columns:
            df[f"Open_{ticker_base}"] = df["open"]
            df[f"High_{ticker_base}"] = df["high"]
            df[f"Low_{ticker_base}"] = df["low"]
            df[f"Close_{ticker_base}"] = df["close"]
            df[f"Volume_{ticker_base}"] = df["volume"]

        # If we have price column (tick data), use it for OHLC
        elif "price" in df.columns:
            df[f"Open_{ticker_base}"] = df["price"]
            df[f"High_{ticker_base}"] = df["price"]
            df[f"Low_{ticker_base}"] = df["price"]
            df[f"Close_{ticker_base}"] = df["price"]
            df[f"Volume_{ticker_base}"] = df.get("size", 0)

        # Calculate VWAP (use price for tick data)
        vwap_col = f"VWAP_{ticker_base}"
        if vwap_col not in df.columns:
            if f"High_{ticker_base}" in df.columns:
                df[vwap_col] = (
                    df[f"High_{ticker_base}"]
                    + df[f"Low_{ticker_base}"]
                    + df[f"Close_{ticker_base}"]
                ) / 3
            elif "price" in df.columns:
                df[vwap_col] = df["price"]

        return df

    def stop_streaming(self) -> None:
        """Stop SignalR streaming."""
        self.stop_event.set()
        if hasattr(self, "connection") and self.connection:
            try:
                self.connection.stop()
            except:
                pass

    def get_health_stats(self) -> Dict:
        """Get provider health statistics."""
        stats = super().get_health_stats()
        stats.update(
            {
                "tick_data_count": len(self.tick_data),
                "contract_cache_size": len(self.contract_cache),
                "api_url": self.base_url,
                "signalr_url": self.signalr_url,
            }
        )
        return stats
