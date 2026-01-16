"""
Signal Database Operations

CRUD operations for the signals table.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from . import get_db

logger = logging.getLogger(__name__)


def add_signal(signal_data: Dict[str, Any]) -> int:
    """
    Add a new signal to the database.

    Args:
        signal_data: Dictionary containing signal fields:
            - recorded_at: ISO timestamp when signal was recorded
            - signal: Signal type (BUY, SELL_PROFIT, SELL_STOP)
            - timestamp: Market data timestamp
            - symbol: Trading symbol
            - price: Price at signal
            - directional_indicator: Directional indicator value
            - phi_sigma: Phi sigma value
            - svc_delta_pct: SVC delta percentage
            - tf_crit: TF critical value

    Returns:
        The ID of the inserted row
    """
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO signals (
                recorded_at, signal, timestamp, symbol, price,
                directional_indicator, phi_sigma, svc_delta_pct, tf_crit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_data.get('recorded_at'),
                signal_data.get('signal'),
                signal_data.get('timestamp'),
                signal_data.get('symbol'),
                signal_data.get('price'),
                signal_data.get('directional_indicator'),
                signal_data.get('phi_sigma'),
                signal_data.get('svc_delta_pct'),
                signal_data.get('tf_crit'),
            )
        )
        signal_id = cursor.lastrowid
        logger.debug(f"Added signal {signal_data.get('signal')} with ID {signal_id}")
        return signal_id


def get_signals(limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Get signals from the database, ordered by most recent first.

    Args:
        limit: Maximum number of signals to return (None for all)
        offset: Number of signals to skip

    Returns:
        List of signal dictionaries
    """
    with get_db() as conn:
        if limit is not None:
            cursor = conn.execute(
                """
                SELECT * FROM signals
                ORDER BY recorded_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM signals
                ORDER BY recorded_at DESC
                """
            )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_signal_count() -> int:
    """
    Get the total number of signals in the database.

    Returns:
        Total signal count
    """
    with get_db() as conn:
        cursor = conn.execute("SELECT COUNT(*) as count FROM signals")
        row = cursor.fetchone()
        return row['count'] if row else 0


def get_signals_since(since_timestamp: str) -> List[Dict[str, Any]]:
    """
    Get all signals since a given timestamp.

    Args:
        since_timestamp: ISO timestamp to filter from

    Returns:
        List of signal dictionaries
    """
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM signals
            WHERE recorded_at > ?
            ORDER BY recorded_at DESC
            """,
            (since_timestamp,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def delete_old_signals(before_timestamp: str) -> int:
    """
    Delete signals older than a given timestamp.

    Args:
        before_timestamp: ISO timestamp - signals before this will be deleted

    Returns:
        Number of deleted rows
    """
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM signals WHERE recorded_at < ?",
            (before_timestamp,)
        )
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"Deleted {deleted} old signals")
        return deleted


def clear_all_signals() -> int:
    """
    Delete all signals from the database.

    Returns:
        Number of deleted rows
    """
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM signals")
        deleted = cursor.rowcount
        logger.info(f"Cleared all {deleted} signals from database")
        return deleted
