#!/usr/bin/env python3
"""
Fetch Historical Data Script
Fetches 7 days of minute bar data from Topstep API and saves to JSON.
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()


def authenticate() -> str:
    """Authenticate with TopstepX API and return token."""
    # Try existing token first
    current_token = os.getenv('TOPSTEP_CURRENT_TOKEN')
    if current_token:
        response = requests.post(
            "https://api.topstepx.com/api/Auth/validate",
            headers={"Authorization": f"Bearer {current_token}"},
            timeout=10
        )
        if response.status_code == 200:
            print("Using existing token (validated)")
            return current_token

    # Login with credentials
    username = os.getenv('TOPSTEP_USERNAME')
    api_key = os.getenv('TOPSTEP_APIKEY')

    if not username or not api_key:
        raise ValueError("TOPSTEP_USERNAME and TOPSTEP_APIKEY required in .env")

    response = requests.post(
        "https://api.topstepx.com/api/Auth/loginKey",
        json={"userName": username, "apiKey": api_key},
        headers={"Content-Type": "application/json"},
        timeout=10
    )

    if response.status_code == 200:
        data = response.json()
        if data.get("success") and data.get("token"):
            print("Authentication successful")
            return data["token"]

    raise ValueError(f"Authentication failed: {response.text}")


def fetch_bars(token: str, contract_id: str, start_time: datetime, end_time: datetime, limit: int = 500) -> list:
    """Fetch bars for a specific time range."""
    payload = {
        "contractId": contract_id,
        "live": False,
        "startTime": start_time.isoformat(),
        "endTime": end_time.isoformat(),
        "unit": 2,  # Minute
        "unitNumber": 1,  # 1-minute bars
        "limit": limit,
        "includePartialBar": False,
    }

    response = requests.post(
        "https://api.topstepx.com/api/History/retrieveBars",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30
    )

    if response.status_code != 200:
        print(f"HTTP Error: {response.status_code}")
        return []

    data = response.json()
    if not data.get("success"):
        print(f"API Error: {data.get('errorMessage', 'Unknown')}")
        return []

    return data.get("bars", [])


def fetch_7_days(contract_id: str, output_file: str):
    """
    Fetch 7 days of minute bar data.

    7 days = 7 * 24 * 60 = 10,080 minute bars
    API limit is ~500-1000 bars per request, so we fetch in chunks.
    """
    print(f"\n{'='*60}")
    print("FETCHING 7 DAYS OF HISTORICAL DATA")
    print(f"{'='*60}")
    print(f"Contract: {contract_id}")

    # Authenticate
    token = authenticate()

    # Calculate time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=7)

    print(f"Time range: {start_time.isoformat()} to {end_time.isoformat()}")

    # Fetch in chunks (12 hours each = 720 bars, well under limit)
    all_bars = []
    chunk_hours = 12
    current_start = start_time
    chunk_num = 0

    while current_start < end_time:
        chunk_num += 1
        current_end = min(current_start + timedelta(hours=chunk_hours), end_time)

        print(f"\nChunk {chunk_num}: {current_start.strftime('%Y-%m-%d %H:%M')} to {current_end.strftime('%Y-%m-%d %H:%M')}")

        bars = fetch_bars(token, contract_id, current_start, current_end, limit=1000)

        if bars:
            print(f"  Retrieved {len(bars)} bars")
            all_bars.extend(bars)
        else:
            print(f"  No bars returned (market may have been closed)")

        current_start = current_end

    # Remove duplicates (by timestamp)
    seen = set()
    unique_bars = []
    for bar in all_bars:
        ts = bar.get('t')
        if ts not in seen:
            seen.add(ts)
            unique_bars.append(bar)

    # Sort by timestamp
    unique_bars.sort(key=lambda x: x.get('t', ''))

    print(f"\n{'='*60}")
    print(f"Total unique bars: {len(unique_bars)}")

    if unique_bars:
        print(f"Date range: {unique_bars[0]['t']} to {unique_bars[-1]['t']}")

    # Save to JSON
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump({
            'contract_id': contract_id,
            'fetch_time': datetime.now(timezone.utc).isoformat(),
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'bar_count': len(unique_bars),
            'bars': unique_bars
        }, f, indent=2)

    print(f"\nSaved to: {output_path}")
    print(f"{'='*60}\n")

    return unique_bars


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch 7 days of historical minute bar data")
    parser.add_argument(
        '--contract_id',
        type=str,
        default='CON.F.US.GCE.G26',
        help='Contract ID (default: CON.F.US.GCE.G26 - Gold Feb 2026)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='./data/historical_bars.json',
        help='Output JSON file path'
    )

    args = parser.parse_args()

    fetch_7_days(args.contract_id, args.output)
