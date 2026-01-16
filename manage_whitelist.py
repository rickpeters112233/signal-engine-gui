#!/usr/bin/env python3
"""
Whitelist Management CLI

Utility script to manage whitelisted addresses for dashboard authentication.

Usage:
    python manage_whitelist.py add <address>       Add and whitelist an address
    python manage_whitelist.py remove <address>   Remove an address
    python manage_whitelist.py enable <address>   Enable (whitelist) an address
    python manage_whitelist.py disable <address>  Disable an address
    python manage_whitelist.py list               List all addresses
    python manage_whitelist.py check <address>    Check if an address is whitelisted
"""

import sys
import argparse
from api.db import whitelist


def add_address(address: str):
    """Add and whitelist an address."""
    address = address.lower()
    if not address.startswith('0x') or len(address) != 42:
        print(f"Error: Invalid Ethereum address format: {address}")
        return False

    if whitelist.address_exists(address):
        print(f"Address {address} already exists")
        # Enable it if it exists
        whitelist.set_whitelisted(address, True)
        print(f"Enabled address {address}")
    else:
        whitelist.add_address(address, whitelisted=True)
        print(f"Added and whitelisted: {address}")
    return True


def remove_address(address: str):
    """Remove an address from the whitelist."""
    address = address.lower()
    if whitelist.remove_address(address):
        print(f"Removed: {address}")
        return True
    else:
        print(f"Address not found: {address}")
        return False


def enable_address(address: str):
    """Enable (whitelist) an address."""
    address = address.lower()
    if not whitelist.address_exists(address):
        print(f"Address not found: {address}")
        print("Use 'add' command to add a new address")
        return False

    whitelist.set_whitelisted(address, True)
    print(f"Enabled: {address}")
    return True


def disable_address(address: str):
    """Disable an address."""
    address = address.lower()
    if not whitelist.address_exists(address):
        print(f"Address not found: {address}")
        return False

    whitelist.set_whitelisted(address, False)
    print(f"Disabled: {address}")
    return True


def list_addresses():
    """List all addresses."""
    addresses = whitelist.get_all_addresses()
    if not addresses:
        print("No addresses in whitelist")
        return

    print(f"\n{'Address':<44} {'Status':<10}")
    print("-" * 54)
    for entry in addresses:
        status = "ENABLED" if entry['whitelisted'] else "DISABLED"
        status_color = "\033[92m" if entry['whitelisted'] else "\033[91m"
        reset = "\033[0m"
        print(f"{entry['address']:<44} {status_color}{status:<10}{reset}")
    print(f"\nTotal: {len(addresses)} address(es)")


def check_address(address: str):
    """Check if an address is whitelisted."""
    address = address.lower()
    if not whitelist.address_exists(address):
        print(f"Address not found: {address}")
        return False

    if whitelist.is_whitelisted(address):
        print(f"\033[92m{address} is WHITELISTED\033[0m")
        return True
    else:
        print(f"\033[91m{address} exists but is NOT whitelisted\033[0m")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Manage whitelisted addresses for dashboard authentication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python manage_whitelist.py add 0x742d35Cc6634C0532925a3b844Bc9e7595f5fB12
    python manage_whitelist.py list
    python manage_whitelist.py check 0x742d35Cc6634C0532925a3b844Bc9e7595f5fB12
    python manage_whitelist.py disable 0x742d35Cc6634C0532925a3b844Bc9e7595f5fB12
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Add command
    add_parser = subparsers.add_parser('add', help='Add and whitelist an address')
    add_parser.add_argument('address', help='Ethereum address (0x...)')

    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove an address')
    remove_parser.add_argument('address', help='Ethereum address (0x...)')

    # Enable command
    enable_parser = subparsers.add_parser('enable', help='Enable (whitelist) an address')
    enable_parser.add_argument('address', help='Ethereum address (0x...)')

    # Disable command
    disable_parser = subparsers.add_parser('disable', help='Disable an address')
    disable_parser.add_argument('address', help='Ethereum address (0x...)')

    # List command
    subparsers.add_parser('list', help='List all addresses')

    # Check command
    check_parser = subparsers.add_parser('check', help='Check if an address is whitelisted')
    check_parser.add_argument('address', help='Ethereum address (0x...)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == 'add':
        add_address(args.address)
    elif args.command == 'remove':
        remove_address(args.address)
    elif args.command == 'enable':
        enable_address(args.address)
    elif args.command == 'disable':
        disable_address(args.address)
    elif args.command == 'list':
        list_addresses()
    elif args.command == 'check':
        check_address(args.address)


if __name__ == "__main__":
    main()
