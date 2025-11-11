"""
Authorize OAuth for a Specific Location

This script helps you authorize individual locations and store their tokens
for use with Voice AI agent copying across multiple sub-accounts.
"""

import json
import base64
from urllib.parse import quote
from config.config import GHL_CLIENT_ID, GHL_CLIENT_SECRET
import requests
from utils.multi_location_tokens import store_location_token, create_multi_token_table

REDIRECT_URI = "https://oauth.pstmn.io/v1/callback"

print("\n" + "="*70)
print(" Authorize Location for Voice AI")
print("="*70)

# Make sure table exists
try:
    create_multi_token_table()
except:
    pass  # Table might already exist

# Scopes needed for Voice AI
scopes = [
    "locations.readonly",
    "voice-ai-agents.readonly",
    "voice-ai-agents.write",
]

scope_string = quote(" ".join(scopes))

# Build authorization URL
auth_url = (
    f"https://marketplace.gohighlevel.com/oauth/chooselocation?"
    f"response_type=code"
    f"&redirect_uri={quote(REDIRECT_URI)}"
    f"&client_id={GHL_CLIENT_ID}"
    f"&scope={scope_string}"
)

print("\n📋 This will authorize Voice AI access for a specific location")
print("\n" + "="*70)
print("STEP 1: Open this URL in your browser:")
print("="*70)
print(f"\n{auth_url}\n")

print("="*70)
print("⚠️  IMPORTANT: Select the SPECIFIC LOCATION you want to authorize")
print("="*70)
print("\nSTEP 2: After clicking 'Authorize', you'll be redirected")
print("        Copy the 'code' parameter from the URL")
print("="*70)

# Get authorization code
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

print("\n✅ Got tokens!")

# Decode token to get location ID
access_token = tokens.get("access_token")
parts = access_token.split('.')

if len(parts) == 3:
    payload = parts[1]
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += '=' * padding
    
    decoded = base64.urlsafe_b64decode(payload)
    token_data = json.loads(decoded)
    
    auth_class = token_data.get('authClass')
    location_id = token_data.get('authClassId') if auth_class == 'Location' else None
    
    if not location_id:
        print("\n⚠️  Warning: Could not extract location ID from token")
        location_id = input("Please enter the location ID manually: ").strip()
    
    if not location_id:
        print("\n❌ No location ID found. Cannot store token.")
        exit(1)
    
    print(f"\n📍 Location ID: {location_id}")
    print(f"📍 Auth Type: {auth_class}")
    
    # Ask for friendly name
    location_name = input("\nEnter a friendly name for this location (optional): ").strip()
    
    # Store the token
    store_location_token(location_id, tokens, location_name or None)
    
    print("\n" + "="*70)
    print("🎉 SUCCESS!")
    print("="*70)
    print(f"\n✅ Token stored for location: {location_id}")
    if location_name:
        print(f"   Name: {location_name}")
    
    print("\nYou can now use this location for Voice AI operations:")
    print(f"   - Copy FROM this location")
    print(f"   - Copy TO this location")
    
    print("\n💡 To authorize more locations, run this script again:")
    print("   python authorize_location.py")
    
    print("\n" + "="*70)
else:
    print("\n❌ Token format unexpected. Cannot extract location ID.")
    exit(1)

