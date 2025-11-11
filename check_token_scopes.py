"""
Check what scopes are included in your current access token
"""
import base64
import json
from utils.ghl_api import get_valid_access_token, get_token_row
from config.config import GHL_CLIENT_ID, GHL_CLIENT_SECRET

print("\n" + "="*60)
print("Current Token Scope Checker")
print("="*60)

# Get current token from database
token_data = get_token_row()

if not token_data:
    print("\n❌ No token found in database!")
    exit(1)

print(f"\n✅ Token found in database")
print(f"Created at: {token_data['created_at']}")
print(f"Expires in: {token_data['expire_in']} seconds")

# Get valid access token (will refresh if needed)
access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)

if not access_token:
    print("\n❌ Failed to get valid access token")
    exit(1)

# JWT tokens have 3 parts separated by dots: header.payload.signature
# We can decode the payload (middle part) to see the scopes
parts = access_token.split('.')

if len(parts) == 3:
    # Decode the payload (add padding if needed)
    payload = parts[1]
    # Add padding
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += '=' * padding
    
    try:
        decoded_bytes = base64.urlsafe_b64decode(payload)
        decoded_str = decoded_bytes.decode('utf-8')
        token_data_json = json.loads(decoded_str)
        
        auth_class = token_data_json.get('authClass', 'Unknown')
        
        print("\n📋 Token Information:")
        print(f"Auth Type: {auth_class}")
        print(f"Location ID: {token_data_json.get('locationId', 'N/A')}")
        print(f"Company ID: {token_data_json.get('companyId', 'N/A')}")
        print(f"Auth Class ID: {token_data_json.get('authClassId', 'N/A')}")
        print(f"User ID: {token_data_json.get('sub', 'N/A')}")
        
        # Check for scopes - can be at top level OR in oauthMeta
        scopes = token_data_json.get('scopes', [])
        if not scopes and 'oauthMeta' in token_data_json:
            scopes = token_data_json.get('oauthMeta', {}).get('scopes', [])
        
        if isinstance(scopes, list):
            print(f"\n✅ Current Scopes ({len(scopes)}):")
            for scope in sorted(scopes):
                print(f"   - {scope}")
            
            # Check for Voice AI scopes (both naming conventions)
            print("\n🔍 Voice AI Scope Check:")
            has_voice_ai_read = 'voice-ai.readonly' in scopes or 'voice-ai-agents.readonly' in scopes
            has_voice_ai_write = 'voice-ai.write' in scopes or 'voice-ai-agents.write' in scopes
            
            if has_voice_ai_read:
                print("   ✅ Voice AI Read - PRESENT")
            else:
                print("   ❌ Voice AI Read - MISSING")
            
            if has_voice_ai_write:
                print("   ✅ Voice AI Write - PRESENT")
            else:
                print("   ❌ Voice AI Write - MISSING")
            
            # Check auth class
            print("\n🔍 Auth Type Check:")
            if auth_class == "Location":
                print(f"   ✅ Token is Location-scoped - GOOD!")
            elif auth_class == "Company":
                print(f"   ⚠️  Token is Company-scoped - PROBLEM!")
                print(f"   Voice AI endpoints require Location-scoped tokens")
            else:
                print(f"   ⚠️  Token auth type: {auth_class}")
            
            if not (has_voice_ai_read and has_voice_ai_write):
                print("\n⚠️  PROBLEM FOUND!")
                print("Your token is missing Voice AI scopes.")
                print("You need to re-authorize to get a new token with these scopes.")
            elif auth_class == "Company":
                print("\n⚠️  PROBLEM FOUND!")
                print("Your token has Voice AI scopes BUT is Company-scoped.")
                print("You need to re-authorize and SELECT A SPECIFIC LOCATION.")
                print("Do NOT choose 'All Locations' or company-wide access.")
            else:
                print("\n✅ Token looks good!")
                print("All Voice AI scopes present and token is location-scoped.")
        else:
            print(f"\n⚠️  Scopes format unexpected: {scopes}")
            
    except Exception as e:
        print(f"\n❌ Error decoding token: {e}")
        print("This might be an Agency API Key token (not OAuth)")
else:
    print("\n⚠️  Token format unexpected (not a JWT)")
    print("This might be an Agency API Key, not an OAuth token")

print("\n" + "="*60)

