"""
API abstraction layer for data providers.
Supports multiple data sources: Massive.io, TopstepX, and file-based.
Includes WebSocket server for real-time data broadcasting.
"""

from .base import DataProvider
from .factory import DataProviderFactory
from .websocket_server import DataBroadcaster, get_broadcaster, broadcast_market_data

__all__ = [
    'DataProvider',
    'DataProviderFactory',
    'DataBroadcaster',
    'get_broadcaster',
    'broadcast_market_data'
]
