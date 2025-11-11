"""
Test script to verify GHL authentication methods
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Load all possible auth methods
GHL_AGENCY_API_KEY = os.getenv("GHL_AGENCY_API_KEY")
GHL_API_KEY = os.getenv("GHL_API_KEY")

TEST_LOCATION_ID = "UTkbqQXAR7A3UsirpOje"
GHL_API_BASE = "https://services.leadconnectorhq.com"

print("=" * 80)
print("GHL Authentication Test")
print("=" * 80)

# Test 1: Agency API Key
print("\n[TEST 1] Testing Agency API Key...")
if GHL_AGENCY_API_KEY:
    print(f"✓ Agency API Key found (length: {len(GHL_AGENCY_API_KEY)})")
    print(f"  First 10 chars: {GHL_AGENCY_API_KEY[:10]}...")
    
    headers = {
        "Authorization": f"Bearer {GHL_AGENCY_API_KEY}",
        "Version": "2021-07-28",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"{GHL_API_BASE}/conversations/assistants",
            headers=headers,
            params={"locationId": TEST_LOCATION_ID},
            timeout=10
        )
        
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.text[:200]}...")
        
        if response.status_code == 200:
            print("  ✅ SUCCESS - Agency API Key is valid!")
            data = response.json()
            assistants = data.get("assistants", [])
            print(f"  Found {len(assistants)} AI assistants")
        elif response.status_code == 401:
            print("  ❌ FAILED - Agency API Key is invalid or expired")
            print("  Possible issues:")
            print("    - Key has been revoked")
            print("    - Key is expired")
            print("    - Wrong key format")
        else:
            print(f"  ⚠️ UNEXPECTED - Got {response.status_code}")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
else:
    print("  ⚠️ No Agency API Key found in environment")

# Test 2: Alternative - Location API Key  
print("\n[TEST 2] Testing Alternative API Key (GHL_API_KEY)...")
if GHL_API_KEY:
    print(f"✓ Alternative API Key found (length: {len(GHL_API_KEY)})")
    print(f"  First 10 chars: {GHL_API_KEY[:10]}...")
    
    headers = {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Version": "2021-07-28",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"{GHL_API_BASE}/conversations/assistants",
            headers=headers,
            params={"locationId": TEST_LOCATION_ID},
            timeout=10
        )
        
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.text[:200]}...")
        
        if response.status_code == 200:
            print("  ✅ SUCCESS - This API Key works!")
            data = response.json()
            assistants = data.get("assistants", [])
            print(f"  Found {len(assistants)} AI assistants")
            print("\n  💡 RECOMMENDATION: Use this key instead!")
        elif response.status_code == 401:
            print("  ❌ FAILED - This API Key is also invalid")
        else:
            print(f"  ⚠️ UNEXPECTED - Got {response.status_code}")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
else:
    print("  ⚠️ No alternative API Key found")

# Test 3: List locations (simpler test)
print("\n[TEST 3] Testing GHL Access with Locations API...")
print("Trying Agency API Key on locations endpoint...")

if GHL_AGENCY_API_KEY:
    headers = {
        "Authorization": f"Bearer {GHL_AGENCY_API_KEY}",
        "Version": "2021-07-28"
    }
    
    try:
        response = requests.get(
            f"{GHL_API_BASE}/locations/search",
            headers=headers,
            params={"companyId": "all"},
            timeout=10
        )
        
        print(f"  Status Code: {response.status_code}")
        if response.status_code == 200:
            print("  ✅ Agency Key works for locations API")
            print("  Issue might be specific to Conversations API")
        else:
            print(f"  ❌ Failed: {response.text[:200]}")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")

print("\n" + "=" * 80)
print("Test Complete")
print("=" * 80)

print("\n📋 RECOMMENDATIONS:")
print("1. If Test 1 failed: Your Agency API Key is invalid")
print("   → Get a new Agency API Key from GHL Settings")
print("2. If Test 2 succeeded: Use GHL_API_KEY instead of GHL_AGENCY_API_KEY")
print("3. If both failed: Generate a new API key from GHL dashboard")
print("\n🔗 Get API Key: https://app.gohighlevel.com/settings/api-keys")

