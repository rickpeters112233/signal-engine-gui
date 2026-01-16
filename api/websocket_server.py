"""
WebSocket Server for Real-Time Data Broadcasting
Broadcasts computed Tribernachi features to connected dashboard clients

Handles:
- Multiple concurrent client connections
- Graceful client disconnection (browser close, network issues, etc.)
- Automatic reconnection support for clients
- Keep-alive ping/pong mechanism
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Set, Optional, Dict, Any, List
import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

from .db import signals as signals_db


logger = logging.getLogger(__name__)


class DataBroadcaster:
    """
    WebSocket server that broadcasts real-time market data to connected clients.

    Architecture:
    - Maintains a set of connected WebSocket clients
    - Provides methods to broadcast data to all connected clients
    - Handles client connection/disconnection gracefully
    - Serializes pandas/numpy data types to JSON-compatible formats
    - Supports client reconnection without data loss
    """

    def __init__(self, host: str = "localhost", port: int = 8765):
        """
        Initialize the WebSocket broadcaster.

        Args:
            host: Host address to bind to (default: localhost)
            port: Port to listen on (default: 8765)
        """
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self.server = None
        self.is_running = False
        self.on_first_client_callback = None
        self.on_last_client_disconnect_callback = None
        self.pipeline_task = None
        self._latest_data: Optional[Dict[str, Any]] = None  # Cache latest data for new clients

        logger.info(f"DataBroadcaster initialized on {host}:{port}")

    async def register(self, websocket: WebSocketServerProtocol):
        """Register a new client connection."""
        was_empty = len(self.clients) == 0
        self.clients.add(websocket)
        client_info = f"{websocket.remote_address}" if websocket.remote_address else "unknown"
        logger.info(f"Client connected from {client_info}. Total clients: {len(self.clients)}")

        try:
            # Send welcome message
            welcome_msg = {
                "type": "connection",
                "status": "connected",
                "timestamp": datetime.now().isoformat(),
                "message": "Connected to Gestalt Signal Engine"
            }
            await websocket.send(json.dumps(welcome_msg))

            # Send the latest cached data immediately so client has data right away
            if self._latest_data is not None:
                logger.debug(f"Sending cached data to new client")
                cached_message = {
                    "type": "market_data",
                    "timestamp": datetime.now().isoformat(),
                    "data": self._latest_data
                }
                await websocket.send(json.dumps(cached_message))

            # Send signal history to new client from database
            signal_history = self.get_signal_history()
            if signal_history:
                logger.debug(f"Sending signal history to new client ({len(signal_history)} signals)")
                history_message = {
                    "type": "signal_history",
                    "timestamp": datetime.now().isoformat(),
                    "data": signal_history
                }
                await websocket.send(json.dumps(history_message))

        except Exception as e:
            logger.warning(f"Failed to send welcome/cached data to client: {e}")
            # Don't remove the client yet - they might still receive broadcasts

        # If this is the first client, start the pipeline
        if was_empty and self.on_first_client_callback:
            logger.info("First client connected - starting data pipeline")
            await self.on_first_client_callback()

    async def unregister(self, websocket: WebSocketServerProtocol):
        """Unregister a client connection."""
        self.clients.discard(websocket)
        client_info = f"{websocket.remote_address}" if websocket.remote_address else "unknown"
        logger.info(f"Client {client_info} disconnected. Total clients: {len(self.clients)}")

        # If this was the last client, stop the pipeline
        if len(self.clients) == 0 and self.on_last_client_disconnect_callback:
            logger.info("Last client disconnected - stopping data pipeline")
            await self.on_last_client_disconnect_callback()

    async def handle_client(self, websocket: WebSocketServerProtocol):
        """
        Handle incoming client connections and messages.

        Handles various disconnection scenarios:
        - Normal browser close
        - Tab close
        - Network disconnect
        - Browser crash (no close frame)

        Args:
            websocket: WebSocket connection
        """
        await self.register(websocket)
        try:
            async for message in websocket:
                # Handle incoming messages from client (if needed)
                try:
                    data = json.loads(message)
                    logger.debug(f"Received message from client: {data}")

                    # Handle ping/pong for keepalive
                    if data.get("type") == "ping":
                        await websocket.send(json.dumps({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        }))

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {message}")
                except Exception as e:
                    logger.warning(f"Error processing client message: {e}")

        except ConnectionClosedOK:
            # Client closed connection normally (code 1000 or 1001)
            logger.info("Client connection closed normally")
        except ConnectionClosedError as e:
            # Connection closed with an error (network issue, browser crash, etc.)
            # This is expected behavior - client might reconnect
            logger.info(f"Client connection closed unexpectedly: code={e.code}, reason={e.reason or 'none'}")
        except ConnectionClosed as e:
            # Generic connection closed
            logger.info(f"Client connection closed: code={e.code}")
        except asyncio.CancelledError:
            # Server is shutting down
            logger.info("Client handler cancelled during shutdown")
        except Exception as e:
            logger.error(f"Unexpected error handling client: {type(e).__name__}: {e}")
        finally:
            await self.unregister(websocket)

    def serialize_value(self, value: Any) -> Any:
        """
        Convert pandas/numpy types to JSON-serializable Python types.

        Args:
            value: Value to serialize

        Returns:
            JSON-serializable value
        """
        import math

        # Handle None
        if value is None:
            return None

        # Handle pandas/numpy numeric types - convert to Python native first
        if hasattr(value, 'item'):
            value = value.item()

        # Handle pandas Timestamp
        if hasattr(value, 'isoformat'):
            return value.isoformat()

        # Handle NaN/Inf for any numeric type (including numpy scalars)
        if isinstance(value, (int, float)):
            try:
                if math.isnan(value):
                    return None
                if math.isinf(value):
                    return None
            except (TypeError, ValueError):
                pass

        return value

    def _add_to_signal_history(self, data: Dict[str, Any]) -> bool:
        """
        Add a BUY or SELL signal to the database if applicable.

        Stores: signal, timestamp, symbol, price, directional_indicator,
                phi_sigma, svc_delta_pct, tf_crit

        Returns:
            True if a signal was added, False otherwise
        """
        trading_signal = data.get('trading_signal')

        # Only store BUY and SELL signals (not HOLD)
        if trading_signal not in ('BUY', 'SELL_PROFIT', 'SELL_STOP'):
            return False

        # Create signal entry
        signal_entry = {
            'recorded_at': datetime.now().isoformat(),
            'signal': trading_signal,
            'timestamp': data.get('timestamp'),
            'symbol': data.get('symbol'),
            'price': data.get('close'),
            'directional_indicator': data.get('directional_indicator'),
            'phi_sigma': data.get('phi_sigma'),
            'svc_delta_pct': data.get('svc_delta_pct'),
            'tf_crit': data.get('tf_crit'),
        }

        # Add to database
        signal_id = signals_db.add_signal(signal_entry)
        total = signals_db.get_signal_count()
        logger.debug(f"Added {trading_signal} signal to database (ID: {signal_id}). Total: {total}")
        return True

    def get_signal_history(self, limit: int = 500) -> List[Dict[str, Any]]:
        """
        Get signal history from the database.

        Args:
            limit: Maximum number of signals to return (default 500 for initial load)

        Returns:
            List of signal dictionaries, most recent first
        """
        signals = signals_db.get_signals(limit=limit)
        # Remove the 'id' field from each signal for client compatibility
        return [{k: v for k, v in s.items() if k != 'id'} for s in signals]

    async def broadcast(self, data: Dict[str, Any]):
        """
        Broadcast data to all connected clients.

        Args:
            data: Dictionary containing data to broadcast
        """
        # Serialize data to ensure JSON compatibility
        serialized_data = {}
        for key, value in data.items():
            serialized_data[key] = self.serialize_value(value)

        # Cache the latest data for new clients
        self._latest_data = serialized_data

        # Add to signal history if it's a BUY or SELL signal
        new_signal_added = self._add_to_signal_history(serialized_data)

        if not self.clients:
            logger.debug("No clients connected, data cached for future clients")
            return

        # Add timestamp and type
        message = {
            "type": "market_data",
            "timestamp": datetime.now().isoformat(),
            "data": serialized_data
        }

        # If a new signal was added, include the updated history
        if new_signal_added:
            message["signal_history"] = self.get_signal_history()

        # Broadcast to all clients concurrently
        json_message = json.dumps(message)
        disconnected_clients = set()

        # Create tasks for concurrent broadcast
        async def send_to_client(client):
            try:
                await client.send(json_message)
                return None
            except ConnectionClosed:
                return client
            except Exception as e:
                logger.warning(f"Error broadcasting to client: {type(e).__name__}: {e}")
                return client

        # Send to all clients concurrently
        if self.clients:
            results = await asyncio.gather(
                *[send_to_client(client) for client in self.clients],
                return_exceptions=True
            )

            # Collect disconnected clients
            for result in results:
                if result is not None and not isinstance(result, Exception):
                    disconnected_clients.add(result)

        # Clean up disconnected clients
        for client in disconnected_clients:
            await self.unregister(client)

        active_count = len(self.clients)
        if active_count > 0:
            logger.debug(f"Broadcasted data to {active_count} client(s)")

    async def start(self):
        """Start the WebSocket server."""
        logger.info(f"Starting WebSocket server on ws://{self.host}:{self.port}")

        self.server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            # Ping/pong to detect dead connections
            ping_interval=30,  # Send ping every 30 seconds
            ping_timeout=30,   # Wait 30 seconds for pong before closing
            # Close timeout for graceful shutdown
            close_timeout=5,
            # Allow large messages for market data
            max_size=10 * 1024 * 1024,  # 10MB max message size
            # Compression for bandwidth efficiency
            compression=None,  # Disable compression for lower latency
        )

        self.is_running = True
        logger.info("WebSocket server started successfully")

    async def stop(self):
        """Stop the WebSocket server gracefully."""
        logger.info("Stopping WebSocket server...")

        # Close all client connections first
        if self.clients:
            logger.info(f"Closing {len(self.clients)} client connection(s)...")
            close_tasks = []
            for client in list(self.clients):
                try:
                    close_tasks.append(client.close(1001, "Server shutting down"))
                except Exception:
                    pass

            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)

            self.clients.clear()

        # Stop the server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

        self.is_running = False
        self._latest_data = None
        logger.info("WebSocket server stopped")

    async def run_forever(self):
        """Run the server indefinitely."""
        await self.start()
        try:
            await asyncio.Future()  # Run forever
        except asyncio.CancelledError:
            await self.stop()

    def get_status(self) -> Dict[str, Any]:
        """Get server status information."""
        return {
            "is_running": self.is_running,
            "client_count": len(self.clients),
            "has_cached_data": self._latest_data is not None,
            "host": self.host,
            "port": self.port
        }


# Singleton instance for easy access
_broadcaster_instance: Optional[DataBroadcaster] = None


def get_broadcaster(host: str = "localhost", port: int = 8765) -> DataBroadcaster:
    """
    Get or create the singleton DataBroadcaster instance.

    Args:
        host: Host address (default: localhost)
        port: Port number (default: 8765)

    Returns:
        DataBroadcaster instance
    """
    global _broadcaster_instance

    if _broadcaster_instance is None:
        _broadcaster_instance = DataBroadcaster(host=host, port=port)

    return _broadcaster_instance


async def broadcast_market_data(data: Dict[str, Any]):
    """
    Convenience function to broadcast market data using the singleton broadcaster.

    Args:
        data: Market data dictionary to broadcast
    """
    broadcaster = get_broadcaster()

    if not broadcaster.is_running:
        logger.warning("Broadcaster not started, cannot send data")
        return

    await broadcaster.broadcast(data)
