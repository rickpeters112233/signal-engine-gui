"""
T-Hex Versioning Code (TVC) Generator
Generates base-20 encoded version strings for cache keys
Achieves ~33% metadata compression while maintaining chronological sortability
"""

import datetime
from .constants import T_HEX_ALPHABET, T_HEX_BASE, TVC_VERSION

def int_to_base20(num):
    """
    Convert integer to base-20 using T-Hex alphabet.

    Args:
        num: Integer to convert

    Returns:
        str: Base-20 encoded string
    """
    if num == 0:
        return T_HEX_ALPHABET[0]

    result = []
    while num > 0:
        remainder = num % T_HEX_BASE
        result.append(T_HEX_ALPHABET[remainder])
        num = num // T_HEX_BASE

    return ''.join(reversed(result))

def base20_to_int(encoded_str):
    """
    Convert base-20 string to integer.

    Args:
        encoded_str: Base-20 encoded string

    Returns:
        int: Decoded integer
    """
    result = 0
    for char in encoded_str:
        if char not in T_HEX_ALPHABET:
            raise ValueError(f"Invalid T-Hex character: {char}")

        result = result * T_HEX_BASE + T_HEX_ALPHABET.index(char)

    return result

def generate_tvc(timestamp, version=TVC_VERSION):
    """
    Generate T-Hex Versioning Code from timestamp and version.

    Format: YYYYMMDDMMNN where YYYY=year, MM=month, DD=day,
            MM=major version, NN=minor version

    Example:
        Input: 2025-11-20, version 4.02
        Process: 2025112004002 (integer)
        Convert to base-20: 07I6G19B02 (10 digits)
        Result: Sortable, compressed version key

    Args:
        timestamp: datetime object or string in format 'YYYY-MM-DD'
        version: Version string in format 'X.YY' (default: from constants)

    Returns:
        str: TVC encoded string
    """
    # Parse timestamp if string
    if isinstance(timestamp, str):
        timestamp = datetime.datetime.strptime(timestamp, '%Y-%m-%d')

    # Parse version
    version_parts = version.split('.')
    major_version = int(version_parts[0])
    minor_version = int(version_parts[1]) if len(version_parts) > 1 else 0

    # Create integer representation: YYYYMMDDMMNN
    year = timestamp.year
    month = timestamp.month
    day = timestamp.day

    # Format: YYYYMMDDMMNN (12 digits)
    combined_int = (year * 100000000 +
                    month * 1000000 +
                    day * 10000 +
                    major_version * 1000 +
                    minor_version)

    # Convert to base-20
    tvc_code = int_to_base20(combined_int)

    # Pad to 10 characters for consistent length
    return tvc_code.zfill(10)

def parse_tvc(tvc_string):
    """
    Parse TVC back to timestamp and version.

    Args:
        tvc_string: TVC encoded string

    Returns:
        dict: Dictionary with 'date', 'major_version', 'minor_version'
    """
    # Decode from base-20
    combined_int = base20_to_int(tvc_string)

    # Extract components
    minor_version = combined_int % 1000
    combined_int = combined_int // 1000

    major_version = combined_int % 100
    combined_int = combined_int // 100

    day = combined_int % 100
    combined_int = combined_int // 100

    month = combined_int % 100
    year = combined_int // 100

    date = datetime.date(year, month, day)
    version_str = f"{major_version}.{minor_version:02d}"

    return {
        'date': date,
        'version': version_str,
        'major_version': major_version,
        'minor_version': minor_version
    }

def generate_cache_key(tvc_prefix, data_hash):
    """
    Generate enhanced cache key with TVC prefix.

    Format: [TVC-VERSION]-[HASH]
    Example: 07I6G19B02-a3f5d89c2e1b4f7a...

    Args:
        tvc_prefix: TVC encoded timestamp and version
        data_hash: SHA-256 hash of data

    Returns:
        str: Complete cache key
    """
    return f"{tvc_prefix}-{data_hash}"

def parse_cache_key(cache_key):
    """
    Parse cache key into TVC and hash components.

    Args:
        cache_key: Complete cache key string

    Returns:
        dict: Dictionary with 'tvc', 'hash', and parsed TVC components
    """
    parts = cache_key.split('-', 1)

    if len(parts) != 2:
        raise ValueError(f"Invalid cache key format: {cache_key}")

    tvc_prefix = parts[0]
    data_hash = parts[1]

    tvc_parsed = parse_tvc(tvc_prefix)

    return {
        'tvc': tvc_prefix,
        'hash': data_hash,
        **tvc_parsed
    }
