"""
SQLite Database Module for Gestalt Signal Engine

Provides persistent storage for trading signals.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Database file location - in the project root for easy transport to prod
DB_PATH = Path(__file__).parent.parent.parent / "signals.sqlite"


def get_connection() -> sqlite3.Connection:
    """
    Get a new database connection.

    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row
    """
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    """
    Context manager for database connections.

    Usage:
        with get_db() as conn:
            cursor = conn.execute("SELECT * FROM signals")
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_db():
    """
    Initialize the database schema.
    Creates the signals and whitelist tables if they don't exist.
    """
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                signal TEXT NOT NULL,
                timestamp TEXT,
                symbol TEXT,
                price REAL,
                directional_indicator REAL,
                phi_sigma REAL,
                svc_delta_pct REAL,
                tf_crit REAL
            )
        """)

        # Create index on recorded_at for faster ordering/filtering
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_recorded_at
            ON signals(recorded_at DESC)
        """)

        # Whitelist table for MetaMask authentication
        conn.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                address TEXT PRIMARY KEY,
                whitelisted INTEGER NOT NULL DEFAULT 0
            )
        """)

        logger.info(f"Database initialized at {DB_PATH}")


# Initialize database on module import
init_db()
