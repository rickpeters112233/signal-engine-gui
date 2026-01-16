#!/usr/bin/env python3
"""
Test script to explore TopstepX API endpoints and capabilities.
"""

import os
import requests
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TopstepXAPIExplorer:
    def __init__(self):
        self.base_url = "https://api.topstepx.com/api"
        self.username = os.getenv("TOPSTEP_USERNAME")
        self.api_key = os.getenv("TOPSTEP_APIKEY")
        self.token = None

    def authenticate(self):
        """Authenticate and get token"""
        print("\n" + "="*60)
        print("1. AUTHENTICATION TEST")
        print("="*60)

        payload = {
            "userName": self.username,
            "apiKey": self.api_key
        }

        try:
            response = requests.post(
                f"{self.base_url}/Auth/loginKey",
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'accept': 'text/plain'
                },
                timeout=10
            )

            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("token"):
                    self.token = data["token"]
                    print(f"✓ Authentication successful")
                    print(f"Token: {self.token[:30]}...")
                    return True
                else:
                    print(f"❌ Login failed: {data}")
                    return False
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    def test_endpoint(self, endpoint, method="GET", params=None, description=""):
        """Test a specific endpoint"""
        print(f"\n  Testing: {endpoint}")
        if description:
            print(f"  Description: {description}")

        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

        try:
            if method == "GET":
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    params=params,
                    headers=headers,
                    timeout=10
                )
            elif method == "POST":
                response = requests.post(
                    f"{self.base_url}{endpoint}",
                    json=params,
                    headers=headers,
                    timeout=10
                )

            print(f"  Status: {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"  ✓ Success!")
                    print(f"  Response type: {type(data)}")
                    if isinstance(data, dict):
                        print(f"  Keys: {list(data.keys())}")
                        # Show first few items
                        for key, value in list(data.items())[:3]:
                            print(f"    {key}: {str(value)[:100]}")
                    elif isinstance(data, list):
                        print(f"  List length: {len(data)}")
                        if len(data) > 0:
                            print(f"  First item: {str(data[0])[:200]}")
                    return True
                except:
                    print(f"  Response (text): {response.text[:200]}")
                    return True
            elif response.status_code == 404:
                print(f"  ❌ Not Found")
                return False
            elif response.status_code == 401:
                print(f"  ❌ Unauthorized")
                return False
            else:
                print(f"  ❌ Error: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False

    def explore_api(self):
        """Explore common API endpoints"""
        print("\n" + "="*60)
        print("2. API ENDPOINT EXPLORATION")
        print("="*60)

        # Calculate date range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=24)

        endpoints_to_try = [
            # Account/User endpoints
            ("/Account/profile", "GET", None, "User profile"),
            ("/Account/info", "GET", None, "Account info"),
            ("/User/profile", "GET", None, "User profile (alt)"),

            # Contract/Symbol endpoints
            ("/Contracts", "GET", None, "List all contracts"),
            ("/Contracts/active", "GET", None, "Active contracts"),
            ("/Symbols", "GET", None, "Available symbols"),
            ("/Instruments", "GET", None, "Available instruments"),

            # Market Data endpoints (various patterns)
            ("/MarketData/contracts", "GET", None, "Market data contracts"),
            ("/MarketData/symbols", "GET", None, "Market data symbols"),
            ("/MarketData/quote", "GET", {"symbol": "GC"}, "Get quote for GC"),
            ("/MarketData/quotes", "GET", {"symbols": "GC,SI"}, "Get multiple quotes"),

            # Historical data patterns
            ("/MarketData/history", "GET", {
                "symbol": "GC",
                "from": start_time.isoformat(),
                "to": end_time.isoformat()
            }, "Historical data (pattern 1)"),

            ("/MarketData/bars", "GET", {
                "symbol": "CON.F.US.GCE.Z25",
                "interval": "1m",
                "count": 10
            }, "Bars with contract ID"),

            ("/MarketData/ohlc", "GET", {
                "symbol": "GC",
                "timeframe": "1m",
                "count": 10
            }, "OHLC data"),

            ("/Data/historical", "GET", {
                "contract": "CON.F.US.GCE.Z25",
                "interval": "1",
                "count": 10
            }, "Historical data (pattern 2)"),

            # Chart data
            ("/Chart/data", "GET", {
                "symbol": "GC",
                "interval": "1m"
            }, "Chart data"),
        ]

        successful_endpoints = []

        for endpoint, method, params, description in endpoints_to_try:
            if self.test_endpoint(endpoint, method, params, description):
                successful_endpoints.append((endpoint, description))

        print("\n" + "="*60)
        print("3. SUMMARY")
        print("="*60)

        if successful_endpoints:
            print(f"\n✓ Found {len(successful_endpoints)} working endpoint(s):")
            for endpoint, description in successful_endpoints:
                print(f"  - {endpoint}: {description}")
        else:
            print("\n❌ No working endpoints found")
            print("This suggests TopstepX may only provide real-time data via SignalR")

        print("\n" + "="*60)


if __name__ == "__main__":
    print("\nTopstepX API Explorer")
    print("Testing API endpoints to discover available functionality\n")

    explorer = TopstepXAPIExplorer()

    if explorer.authenticate():
        explorer.explore_api()
    else:
        print("\n❌ Authentication failed. Please check credentials in .env")
