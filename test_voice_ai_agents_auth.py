"""
Test script to verify Voice AI Agents API authentication
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Load authentication keys
GHL_AGENCY_API_KEY = os.getenv("GHL_AGENCY_API_KEY")
GHL_API_KEY = os.getenv("GHL_API_KEY")

TEST_LOCATION_ID = "UTkbqQXAR7A3UsirpOje"
GHL_API_BASE = "https://services.leadconnectorhq.com"

print("=" * 80)
print("🎤 Voice AI Agents API Authentication Test")
print("=" * 80)

# Test 1: Agency/Private Integration API Key
print("\n[TEST 1] Testing Agency/Private Integration API Key for Voice AI Agents...")
if GHL_AGENCY_API_KEY:
    print(f"✓ Agency API Key found (length: {len(GHL_AGENCY_API_KEY)})")
    print(f"  First 10 chars: {GHL_AGENCY_API_KEY[:10]}...")
    
    headers = {
        "Authorization": f"Bearer {GHL_AGENCY_API_KEY}",
        "Version": "2021-07-28",
        "Content-Type": "application/json"
    }
    
    try:
        # Test Voice AI Agents API endpoint
        response = requests.get(
            f"{GHL_API_BASE}/voice-ai/agents",
            headers=headers,
            params={"locationId": TEST_LOCATION_ID, "limit": 10},
            timeout=10
        )
        
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.text[:300]}...")
        
        if response.status_code == 200:
            print("\n  ✅ SUCCESS - Agency API Key works for Voice AI Agents!")
            data = response.json()
            agents = data.get("agents", [])
            print(f"  Found {len(agents)} Voice AI agents")
        elif response.status_code == 401:
            print("\n  ❌ FAILED - API Key is missing required scopes")
            print("\n  📋 REQUIRED SCOPES for Voice AI Agents:")
            print("     ✅ voiceai.agents.read")
            print("     ✅ voiceai.agents.write")
            print("     ✅ locations.readonly")
            print("\n  🔧 HOW TO FIX:")
            print("     1. Go to GHL Settings → Company Settings → Integrations")
            print("     2. Create a new Private Integration")
            print("     3. Select the scopes listed above")
            print("     4. Copy the generated key and update your .env file")
            print("\n  📖 See: VOICE_AI_AGENTS_CORRECT_SCOPES.md")
        else:
            print(f"\n  ⚠️ UNEXPECTED - Got {response.status_code}")
    except Exception as e:
        print(f"\n  ❌ ERROR: {e}")
else:
    print("  ⚠️ No Agency API Key found in environment")
    print("\n  📋 TO SET UP:")
    print("     1. Create a Private Integration in GHL")
    print("     2. Select scopes: voiceai.agents.read, voiceai.agents.write")
    print("     3. Add to .env: GHL_AGENCY_API_KEY=your_key_here")

# Test 2: Alternative API Key
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
            f"{GHL_API_BASE}/voice-ai/agents",
            headers=headers,
            params={"locationId": TEST_LOCATION_ID, "limit": 10},
            timeout=10
        )
        
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.text[:300]}...")
        
        if response.status_code == 200:
            print("\n  ✅ SUCCESS - This API Key works for Voice AI Agents!")
            data = response.json()
            agents = data.get("agents", [])
            print(f"  Found {len(agents)} Voice AI agents")
            print("\n  💡 RECOMMENDATION: Use this key as GHL_AGENCY_API_KEY!")
        elif response.status_code == 401:
            print("\n  ❌ FAILED - This API Key also lacks Voice AI scopes")
        else:
            print(f"\n  ⚠️ UNEXPECTED - Got {response.status_code}")
    except Exception as e:
        print(f"\n  ❌ ERROR: {e}")
else:
    print("  ⚠️ No alternative API Key found")

print("\n" + "=" * 80)
print("Test Complete")
print("=" * 80)

print("\n📋 NEXT STEPS:")
print("")
print("✅ If any test succeeded:")
print("   → You're all set! Voice AI cloning should work.")
print("")
print("❌ If both tests failed with 401:")
print("   → Your API keys are missing Voice AI Agents scopes")
print("")
print("🔧 TO FIX:")
print("   1. Create a Private Integration in GHL with these scopes:")
print("      • voiceai.agents.read")
print("      • voiceai.agents.write")
print("      • locations.readonly")
print("")
print("   2. If you don't see those scopes:")
print("      → Contact GHL Support: support@gohighlevel.com")
print("      → Ask them to enable 'Voice AI Agents API access'")
print("")
print("📖 Full guide: VOICE_AI_AGENTS_CORRECT_SCOPES.md")
print("📖 Quick fix: QUICK_FIX_VOICE_AI_SCOPES.md")
print("")

