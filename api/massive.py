"""
Massive.io data provider implementation.
Handles REST API and WebSocket streaming for Massive.io forex data.
"""

import asyncio
import json
import pandas as pd
import websockets
from datetime import datetime, timedelta, timezone
from typing import Optional, Callable, Dict
from massive import RESTClient

from .base import DataProvider, DataFetchError


class MassiveDataProvider(DataProvider):
    """
    Massive.io API data provider.

    Provides historical data via REST API and real-time streaming via WebSocket.
    """

    def __init__(self, api_key: str):
        """
        Initialize Massive.io provider.

        Args:
            api_key: Massive.io API key
        """
        self.api_key = api_key
        self.client = None
        self.rest_base_url = "https://api.massive.com/v2"
        self.ws_url = "wss://socket.massive.com/forex"
        self.authenticated = False
        self.is_streaming = False
        self.stop_event = asyncio.Event()
        self.minute_data = []
        self.max_history_length = 500

    def authenticate(self) -> bool:
        """
        Authenticate with Massive.io by initializing the REST client.

        Returns:
            bool: True if successful
        """
        try:
            self.client = RESTClient(self.api_key)
            self.authenticated = True
            return True
        except Exception as e:
            print(f"Massive.io authentication failed: {e}")
            self.authenticated = False
            return False

    def normalize_ticker(self, ticker: str) -> Dict[str, str]:
        """
        Convert standard ticker to Massive.io format.

        Supports prefixed tickers:
        - X: for crypto (e.g., "X:BTCUSD")
        - C: for forex (e.g., "C:XAUUSD" or just "XAUUSD")

        Args:
            ticker: Ticker symbol, optionally with prefix (e.g., "XAUUSD", "X:BTCUSD")

        Returns:
            dict: {"rest": "C:XAUUSD", "ws": "AM.C:XAUUSD"} or
                  {"rest": "X:BTCUSD", "ws": "AM.X:BTCUSD"}
        """
        # Check if ticker already has a valid prefix (X:, C:, etc.)
        if ':' in ticker:
            # Ticker already has prefix, use as-is
            return {
                'rest': ticker,
                'ws': f"AM.{ticker}"
            }
        else:
            # Default to C: (forex) for unprefixed tickers
            return {
                'rest': f"C:{ticker}",
                'ws': f"AM.C:{ticker}"
            }

    def fetch_historical_data(
        self,
        ticker: str,
        hours: float
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical minute data from Massive.io REST API.

        Args:
            ticker: Ticker symbol (e.g., "XAUUSD")
            hours: Number of hours of historical data

        Returns:
            DataFrame with OHLCV data and ticker suffixes
        """
        print(f"\nFetching historical data for {ticker}...")

        if not self.authenticated:
            if not self.authenticate():
                return None

        # Get ticker formats
        ticker_formats = self.normalize_ticker(ticker)
        ticker_rest = ticker_formats['rest']

        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Calculate required number of bars (minutes)
        required_bars = int(hours * 60)

        try:
            # Get aggregates using Massive SDK
            print(f"  - Requesting {required_bars} minute bars for ticker: {ticker_rest}")
            print(f"  - Time range: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}")

            resp = self.client.get_aggs(
                ticker=ticker_rest,
                multiplier=1,
                timespan="minute",
                from_=start_time,
                to=end_time,
                limit=required_bars, # MAX LIMIT IS 50,000 -- if req. bars > 50,000 it limits to 50K
                sort="asc"
            )

            print(f"  - API Response type: {type(resp)}")
            print(f"  - API Response length: {len(resp) if resp else 0}")

            if not resp or len(resp) == 0:
                print(f"  - WARNING: Retrieved 0 bars for {ticker}.")
                print(f"  - Possible reasons:")
                print(f"    1. Market is closed (forex markets close Friday 5pm EST to Sunday 5pm EST)")
                print(f"    2. API key permissions may not include forex data")
                print(f"    3. Ticker format may be incorrect (using: {ticker_rest})")
                return None

            # Convert response to DataFrame
            data = [{
                'datetime': pd.to_datetime(bar.timestamp, unit='ms'),
                'Open': bar.open,
                'High': bar.high,
                'Low': bar.low,
                'Close': bar.close,
                'Volume': bar.volume,
                'VWAP': getattr(bar, 'vwap', None),
                'timestamp': bar.timestamp
            } for bar in resp]

            df = pd.DataFrame(data)

            if len(df) == 0:
                print(f"  - WARNING: No data returned from API")
                return None

            # Set datetime as index
            df = df.set_index('datetime').sort_index()

            # Normalize DataFrame
            df = self.normalize_dataframe(df, ticker)

            print(f"  - Fetched {len(df)} minute bars")
            print(f"  - Date range: {df.index[0]} to {df.index[-1]}")

            # Store in history buffer
            self.minute_data = df.to_dict('records')

            return df

        except Exception as e:
            print(f"  - ERROR fetching historical data: {e}")
            import traceback
            traceback.print_exc()
            raise DataFetchError(f"Failed to fetch Massive.io data: {e}")

    async def stream_realtime_data(
        self,
        ticker: str,
        callback: Optional[Callable] = None
    ) -> None:
        """
        Stream real-time minute aggregates from Massive.io WebSocket.

        Args:
            ticker: Ticker symbol
            callback: Optional callback function to handle incoming bars
        """
        print(f"\nStarting real-time stream for {ticker}...")

        # Get ticker formats
        ticker_formats = self.normalize_ticker(ticker)
        ticker_ws = ticker_formats['ws']

        auth_message = json.dumps({
            "action": "auth",
            "params": self.api_key
        })

        subscribe_message = json.dumps({
            "action": "subscribe",
            "params": ticker_ws
        })

        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Authenticate
                await websocket.send(auth_message)
                auth_response = await websocket.recv()
                print(f"  - Auth response: {auth_response}")

                # Subscribe to ticker
                await websocket.send(subscribe_message)
                sub_response = await websocket.recv()
                print(f"  - Subscribe response: {sub_response}")

                self.is_streaming = True
                print(f"  - Streaming live minute aggregates for {ticker}")

                # Stream loop
                while not self.stop_event.is_set():
                    try:
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=1.0
                        )

                        # Parse message
                        data = json.loads(message)

                        # Process aggregate bars
                        for item in data:
                            if item.get("ev") == "AM":
                                # Extract bar data
                                bar = {
                                    "timestamp": item.get("s"),
                                    "Open": item.get("o"),
                                    "High": item.get("h"),
                                    "Low": item.get("l"),
                                    "Close": item.get("c"),
                                    "Volume": item.get("v"),
                                    "VWAP": item.get("vw"),
                                    "datetime": pd.to_datetime(item.get("s"), unit="ms")
                                }

                                # Add to history
                                self.minute_data.append(bar)

                                # Maintain max history length
                                if len(self.minute_data) > self.max_history_length:
                                    self.minute_data.pop(0)

                                print(f"  - New bar: {bar['datetime']} | Close: {bar['Close']}")

                                # Execute callback if provided
                                if callback:
                                    callback(bar)

                    except asyncio.TimeoutError:
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        print("  - WebSocket connection closed")
                        break

        except Exception as e:
            print(f"  - ERROR in WebSocket stream: {e}")
        finally:
            self.is_streaming = False
            print("  - Stream stopped")

    def normalize_dataframe(
        self,
        df: pd.DataFrame,
        ticker: str
    ) -> pd.DataFrame:
        """
        Normalize DataFrame to expected format with ticker suffixes.

        Args:
            df: Raw DataFrame from Massive.io
            ticker: Ticker symbol

        Returns:
            DataFrame with standardized columns
        """
        # Add ticker suffix to columns
        ticker_base = ticker.replace(":", "_")

        for col in ["Open", "High", "Low", "Close", "Volume", "VWAP"]:
            if col in df.columns:
                df[f"{col}_{ticker_base}"] = df[col]

        # Calculate VWAP if missing
        vwap_col = f"VWAP_{ticker_base}"
        if vwap_col not in df.columns or df[vwap_col].isna().all():
            df[vwap_col] = (
                df[f"High_{ticker_base}"] +
                df[f"Low_{ticker_base}"] +
                df[f"Close_{ticker_base}"]
            ) / 3

        return df

    def stop_streaming(self) -> None:
        """Stop the real-time data stream."""
        self.stop_event.set()

    def get_health_stats(self) -> Dict:
        """Get provider health statistics."""
        stats = super().get_health_stats()
        stats.update({
            'is_streaming': self.is_streaming,
            'history_length': len(self.minute_data),
            'api_url': self.rest_base_url,
            'ws_url': self.ws_url
        })
        return stats
