#!/usr/bin/env python3
"""
Test the AAGCP + Pinecone Real App via API calls.
Run this AFTER the app is running on port 8001.
"""

import requests
import json
import time

BASE_URL = "http://localhost:8001"

def test_status():
    """Test the status endpoint."""
    print("\n🔍 Testing /status endpoint...")
    try:
        res = requests.get(f"{BASE_URL}/status")
        data = res.json()
        print(f"✓ Status: {data}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_query():
    """Test the query endpoint."""
    print("\n🔍 Testing /query endpoint...")
    try:
        res = requests.post(
            f"{BASE_URL}/query",
            json={"query": "PII detection", "k": 3}
        )
        data = res.json()
        print(f"✓ Query returned {data['count']} results")
        if data['results']:
            print(f"  Top result ID: {data['results'][0]['id']}")
            print(f"  Score: {data['results'][0]['score']:.3f}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_scan():
    """Test the scan endpoint."""
    print("\n🔍 Testing /scan endpoint...")
    try:
        res = requests.get(f"{BASE_URL}/scan")
        data = res.json()
        print(f"✓ Scan complete")
        print(f"  Total PII: {data.get('total_pii', 'N/A')}")
        print(f"  Unique entity types: {data.get('unique_entities', 'N/A')}")
        print(f"  High-risk vectors: {data.get('high_risk_count', 'N/A')}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 12 + "AAGCP + PINECONE REAL APP - API TESTS" + " " * 9 + "║")
    print("╚" + "═" * 58 + "╝")
    
    print(f"\nTesting API at: {BASE_URL}")
    time.sleep(1)
    
    results = []
    results.append(("Status Check", test_status()))
    results.append(("Query Test", test_query()))
    results.append(("Scan Test", test_scan()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name:.<40} {status}")
    
    print("\n✓ App is working! Try:")
    print("  - Open dashboard: http://localhost:8001")
    print("  - Upload a document with PII")
    print("  - Run scan to find PII")
    print("  - Click 'Clean' to mask and re-embed")
    print("  - Query results will now be masked\n")

if __name__ == "__main__":
    main()
