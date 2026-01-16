"""
Whitelist Database Operations

CRUD operations for the whitelist table used in MetaMask authentication.
"""

import logging
from typing import Dict, Any, List, Optional

from . import get_db

logger = logging.getLogger(__name__)


def add_address(address: str, whitelisted: bool = False) -> bool:
    """
    Add a new address to the whitelist table.

    Args:
        address: Ethereum address (will be stored lowercase)
        whitelisted: Whether the address is whitelisted (default False)

    Returns:
        True if added successfully, False if address already exists
    """
    address = address.lower()
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO whitelist (address, whitelisted) VALUES (?, ?)",
                (address, 1 if whitelisted else 0)
            )
            logger.info(f"Added address {address} to whitelist (whitelisted={whitelisted})")
            return True
        except Exception as e:
            logger.warning(f"Failed to add address {address}: {e}")
            return False


def is_whitelisted(address: str) -> bool:
    """
    Check if an address is whitelisted.

    Args:
        address: Ethereum address to check

    Returns:
        True if the address exists and is whitelisted, False otherwise
    """
    address = address.lower()
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT whitelisted FROM whitelist WHERE address = ?",
            (address,)
        )
        row = cursor.fetchone()
        if row is None:
            return False
        return row['whitelisted'] == 1


def address_exists(address: str) -> bool:
    """
    Check if an address exists in the whitelist table.

    Args:
        address: Ethereum address to check

    Returns:
        True if the address exists (regardless of whitelist status)
    """
    address = address.lower()
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM whitelist WHERE address = ?",
            (address,)
        )
        return cursor.fetchone() is not None


def set_whitelisted(address: str, whitelisted: bool) -> bool:
    """
    Set the whitelist status for an address.

    Args:
        address: Ethereum address
        whitelisted: New whitelist status

    Returns:
        True if updated successfully, False if address doesn't exist
    """
    address = address.lower()
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE whitelist SET whitelisted = ? WHERE address = ?",
            (1 if whitelisted else 0, address)
        )
        if cursor.rowcount > 0:
            logger.info(f"Updated address {address} whitelist status to {whitelisted}")
            return True
        return False


def remove_address(address: str) -> bool:
    """
    Remove an address from the whitelist table.

    Args:
        address: Ethereum address to remove

    Returns:
        True if removed, False if address didn't exist
    """
    address = address.lower()
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM whitelist WHERE address = ?",
            (address,)
        )
        if cursor.rowcount > 0:
            logger.info(f"Removed address {address} from whitelist")
            return True
        return False


def get_all_addresses() -> List[Dict[str, Any]]:
    """
    Get all addresses in the whitelist table.

    Returns:
        List of dictionaries with address and whitelisted status
    """
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT address, whitelisted FROM whitelist ORDER BY address"
        )
        rows = cursor.fetchall()
        return [{'address': row['address'], 'whitelisted': row['whitelisted'] == 1} for row in rows]


def get_whitelisted_addresses() -> List[str]:
    """
    Get all whitelisted addresses.

    Returns:
        List of whitelisted addresses
    """
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT address FROM whitelist WHERE whitelisted = 1 ORDER BY address"
        )
        rows = cursor.fetchall()
        return [row['address'] for row in rows]
