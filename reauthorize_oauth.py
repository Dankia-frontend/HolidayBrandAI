"""
Script to re-authorize OAuth with updated scopes (including Voice AI)

Run this script when you've added new scopes to your OAuth app
and need to get a fresh token that includes those scopes.
"""

import json


print("\n" + "="*70)
print(" OAuth Re-Authorization Script - Voice AI Scopes")
print("="*70)

try:
    from config.config import GHL_CLIENT_ID, GHL_CLIENT_SECRET, GHL_REDIRECT_URI
    import requests
    from urllib.parse import quote
    
    # Define all scopes you need (including Voice AI)
    scopes = [
        # "contacts.readonly",
        # "contacts.write",
        "locations.readonly", 
        # "locations.write",
        # "opportunities.readonly",
        # "opportunities.write",
        # "calendars.readonly",
        # "calendars.write",
        # "conversations/message.readonly",
        # "conversations/message.write",
        "voice-ai-agents.readonly",    # 🎯 Voice AI scope
        "voice-ai-agents.write",       # 🎯 Voice AI scope
    ]

    REDIRECT_URI = "https://oauth.pstmn.io/v1/callback"
    
    # Build authorization URL
    scope_string = quote(" ".join(scopes))
    
    auth_url = (
        f"https://marketplace.gohighlevel.com/oauth/chooselocation?"
        f"response_type=code"
        f"&redirect_uri={quote(REDIRECT_URI)}"
        f"&client_id={GHL_CLIENT_ID}"
        f"&scope={scope_string}"
    )
    
    print("\n📋 SCOPES INCLUDED:")
    for i, scope in enumerate(scopes, 1):
        indicator = "🎯" if "voice-ai" in scope else "  "
        print(f"   {indicator} {i}. {scope}")
    
    print("\n" + "="*70)
    print("STEP 1: Open this URL in your browser:")
    print("="*70)
    print(f"\n{auth_url}\n")
    
    print("="*70)
    print("⚠️  IMPORTANT: Choose a SPECIFIC LOCATION")
    print("="*70)
    print("When you open the URL, you'll see a location selector.")
    print("⚠️  DO NOT choose 'All Locations' or 'Company-wide access'")
    print("✅  SELECT A SPECIFIC LOCATION from the dropdown")
    print("    (e.g., 'UTkbqQXAR7A3UsirpOje' or your location name)")
    print("\nWhy? Voice AI endpoints require location-scoped tokens,")
    print("not company-scoped tokens.")
    print("="*70)
    
    print("\nSTEP 2: After authorization, you'll be redirected to your redirect_uri")
    print("        Copy the 'code' parameter from the URL")
    print("="*70)
    
    # Wait for user input
    auth_code = input("\nPaste the authorization code here: ").strip()
    
    if not auth_code:
        print("\n❌ No authorization code provided. Exiting.")
        exit(1)
    
    print("\n🔄 Exchanging authorization code for tokens...")
    
    # Exchange code for tokens
    token_url = "https://services.leadconnectorhq.com/oauth/token"
    data = {
        "client_id": GHL_CLIENT_ID,
        "client_secret": GHL_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI
    }
    
    response = requests.post(token_url, data=data)
    
    if response.status_code != 200:
        print(f"\n❌ Error: {response.status_code}")
        print(f"Response: {response.text}")
        exit(1)
    
    tokens = response.json()
    
    print("\n✅ Got new tokens!")
    print(f"   Access Token: {tokens['access_token'][:20]}...")
    print(f"   Refresh Token: {tokens['refresh_token'][:20]}...")
    print(f"   Expires In: {tokens['expires_in']} seconds")
    
    # Debug: Show what's in the token
    print("\n🔍 Debug: Decoding token to check scopes...")
    import base64
    parts = tokens['access_token'].split('.')
    if len(parts) == 3:
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        decoded = base64.urlsafe_b64decode(payload)
        token_data = json.loads(decoded)
        
        # Scopes can be at top level OR in oauthMeta
        scopes = token_data.get('scopes', [])
        if not scopes and 'oauthMeta' in token_data:
            scopes = token_data.get('oauthMeta', {}).get('scopes', [])
        
        auth_class = token_data.get('authClass', 'Unknown')
        auth_class_id = token_data.get('authClassId', 'N/A')
        location_id = token_data.get('locationId', 'N/A')
        
        print(f"   Auth Type: {auth_class}")
        print(f"   Auth ID: {auth_class_id}")
        print(f"   Location ID: {location_id}")
        print(f"   Scopes in token: {scopes}")
        
        # Show FULL token payload for debugging
        print("\n🔍 FULL TOKEN PAYLOAD (for debugging):")
        print(json.dumps(token_data, indent=2))
    else:
        print("   ⚠️  Token is not a JWT format")
    
    # Update database
    print("\n🔄 Updating tokens in database...")
    
    try:
        from utils.ghl_api import update_tokens
        update_tokens(tokens)
        print("✅ Tokens successfully updated in database!")
    except Exception as e:
        print(f"❌ Error updating database: {e}")
        print("\nPlease update manually:")
        print(f"   Access Token: {tokens['access_token']}")
        print(f"   Refresh Token: {tokens['refresh_token']}")
        print(f"   Expires In: {tokens['expires_in']}")
    
    print("\n" + "="*70)
    print("🎉 SUCCESS! Your token now includes Voice AI scopes!")
    print("="*70)
    print("\nYou can now use the Voice AI endpoints:")
    print("   - /voice-ai/list-agents")
    print("   - /voice-ai/copy-agent")
    print("   - /voice-ai/copy-all-agents")
    print("\n" + "="*70 + "\n")
    
except ImportError as e:
    print(f"\n❌ Import Error: {e}")
    print("\nMake sure you're running this from the project directory")
    print("and that config.config is properly set up.")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

