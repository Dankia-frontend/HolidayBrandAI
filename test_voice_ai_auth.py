"""
Test script to verify Voice AI Agents API authentication
"""
import requests
from utils.ghl_api import get_valid_access_token
from config.config import GHL_CLIENT_ID, GHL_CLIENT_SECRET

def test_voice_ai_auth():
    """Test Voice AI Agents API authentication"""
    
    print("="*60)
    print("Voice AI Agents - Authentication Test")
    print("="*60)
    
    # Step 1: Get OAuth token
    print("\n[Step 1] Getting OAuth access token from database...")
    access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
    
    if not access_token:
        print("❌ ERROR: No OAuth token found!")
        print("\nPlease run the OAuth authorization first:")
        print("   python test_ghl_auth.py")
        print("\nThen try this test again.")
        return False
    
    print(f"✅ OAuth token found: {access_token[:30]}...")
    
    # Step 2: Test Voice AI Agents API
    print("\n[Step 2] Testing Voice AI Agents API...")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Use your master template location
    location_id = "UTkbqQXAR7A3UsirpOje"
    url = "https://services.leadconnectorhq.com/voice-ai/agents"
    params = {
        "locationId": location_id,
        "limit": 10,
        "offset": 0
    }
    
    print(f"   URL: {url}")
    print(f"   Location ID: {location_id}")
    print(f"   Making request...")
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        print(f"\n[Step 3] Response:")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("\n" + "="*60)
            print("✅ SUCCESS! Voice AI Agents API is working!")
            print("="*60)
            
            data = response.json()
            agents = data.get("agents", [])
            total = data.get("total", len(agents))
            
            print(f"\n📊 Found {len(agents)} agents (Total: {total})")
            
            if agents:
                print("\nAgent Details:")
                for i, agent in enumerate(agents[:5], 1):  # Show first 5
                    print(f"\n{i}. {agent.get('name', 'Unnamed')}")
                    print(f"   ID: {agent.get('id')}")
                    print(f"   Provider: {agent.get('provider', 'N/A')}")
                    print(f"   Model: {agent.get('model', 'N/A')}")
                    print(f"   Voice ID: {agent.get('voiceId', 'N/A')}")
                
                if len(agents) > 5:
                    print(f"\n   ... and {len(agents) - 5} more agents")
            else:
                print("\nℹ️ No agents found in this location.")
                print("   This is normal if you haven't created any Voice AI agents yet.")
            
            print("\n" + "="*60)
            print("✅ Authentication is working correctly!")
            print("="*60)
            print("\nYou can now use the Voice AI Agents cloning feature.")
            return True
            
        elif response.status_code == 401:
            print("\n" + "="*60)
            print("❌ ERROR: UNAUTHORIZED (401)")
            print("="*60)
            print(f"\nResponse: {response.text}")
            print("\n🔧 SOLUTION:")
            print("1. Your OAuth token is invalid or missing required scopes")
            print("2. Required scopes:")
            print("   - conversations/messages.readonly")
            print("   - conversations/messages.write")
            print("   - locations.readonly")
            print("\n3. Steps to fix:")
            print("   a. Go to GoHighLevel Marketplace")
            print("   b. Add the required scopes to your OAuth app")
            print("   c. Delete old tokens from database:")
            print("      DELETE FROM tokens WHERE id = 1;")
            print("   d. Re-authorize your app:")
            print("      python test_ghl_auth.py")
            print("\n4. Then run this test again:")
            print("   python test_voice_ai_auth.py")
            return False
            
        elif response.status_code == 404:
            print("\n" + "="*60)
            print("⚠️ WARNING: Not Found (404)")
            print("="*60)
            print(f"\nResponse: {response.text}")
            print("\nPossible reasons:")
            print("1. Voice AI Agents feature is not enabled for this location")
            print("2. Location ID is incorrect")
            print("3. API endpoint has changed")
            print("\nTry checking the location ID and GHL documentation.")
            return False
            
        else:
            print("\n" + "="*60)
            print(f"⚠️ ERROR: HTTP {response.status_code}")
            print("="*60)
            print(f"\nResponse: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print("\n❌ ERROR: Request timed out")
        print("Check your internet connection or try again.")
        return False
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_voice_ai_auth()
    
    if success:
        print("\n✅ All tests passed! You're ready to use Voice AI Agents cloning.")
        exit(0)
    else:
        print("\n❌ Tests failed. Please follow the instructions above to fix the issue.")
        exit(1)

