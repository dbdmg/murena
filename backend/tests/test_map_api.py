"""
Test script for Map API endpoints.
"""

import sys
import os
import asyncio
from fastapi.testclient import TestClient

# Imports are configured via tests/conftest.py

from app.main import app

client = TestClient(app)


def test_map_config():
    """Test map config endpoint."""
    print("Testing /map/config...")
    response = client.get("/api/v1/map/config")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Config: Center={data['center']}, Zoom={data['zoom']}")
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")


def test_map_overlays():
    """Test map overlays endpoint."""
    print("\nTesting /map/overlays/municipi...")
    response = client.get("/api/v1/map/overlays/municipi")
    if response.status_code == 200:
        data = response.json()
        # Check if valid GeoJSON
        if "type" in data and "features" in data:
            print(f"✅ Municip overlay loaded: {len(data['features'])} features")
        else:
            print("❌ Invalid GeoJSON format")
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")


def test_map_markers():
    """Test map markers endpoint."""
    print("\nTesting /map/markers...")
    # NOTE: This relies on RealEstateService loading data.
    # In test environment, data loading might need time or mock.
    # But since it loads from parquet on startup/first call, it should work if parquet exists.

    response = client.get("/api/v1/map/markers?limit=10")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Markers retrieved: {len(data)} markers")
        if len(data) > 0:
            print(f"   Sample: {data[0]}")
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")


if __name__ == "__main__":
    try:
        test_map_config()
        test_map_overlays()
        test_map_markers()
        print("\n🎉 Map API tests completed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
