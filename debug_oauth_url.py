"""
Debug script to show the exact OAuth URL being generated
"""
from config.config import GHL_CLIENT_ID
from urllib.parse import quote

# The scopes you're using
scopes = [
    "locations.readonly", 
    "voice-ai-agents.readonly",
    "voice-ai-agents.write",
]

REDIRECT_URI = "https://oauth.pstmn.io/v1/callback"

print("\n" + "="*70)
print("OAuth URL Debug")
print("="*70)

# Show individual scopes
print("\n📋 Scopes to request:")
for i, scope in enumerate(scopes, 1):
    print(f"   {i}. {scope}")

# Join scopes with space
scope_string = " ".join(scopes)
print(f"\n🔗 Scope string (before encoding):")
print(f"   {scope_string}")

# URL encode
encoded_scopes = quote(scope_string)
print(f"\n🔗 Scope string (after URL encoding):")
print(f"   {encoded_scopes}")

# Build the full URL
auth_url = (
    f"https://marketplace.gohighlevel.com/oauth/chooselocation?"
    f"response_type=code"
    f"&redirect_uri={quote(REDIRECT_URI)}"
    f"&client_id={GHL_CLIENT_ID}"
    f"&scope={encoded_scopes}"
)

print(f"\n🌐 Full Authorization URL:")
print(f"\n{auth_url}\n")

print("="*70)
print("\n⚠️  IMPORTANT CHECKS:")
print("   1. Open this URL in your browser")
print("   2. You should see a page listing the permissions:")
print("      - locations.readonly")
print("      - voice-ai-agents.readonly")
print("      - voice-ai-agents.write")
print("   3. If you DON'T see these permissions listed,")
print("      the scope names are incorrect!")
print("\n" + "="*70 + "\n")

# Also try alternative scope format
print("\n🔄 ALTERNATIVE: Try with different scope names if above doesn't work:")
alternative_scopes = [
    "locations.readonly",
    "voice-ai.readonly",
    "voice-ai.write",
]

alt_scope_string = quote(" ".join(alternative_scopes))
alt_auth_url = (
    f"https://marketplace.gohighlevel.com/oauth/chooselocation?"
    f"response_type=code"
    f"&redirect_uri={quote(REDIRECT_URI)}"
    f"&client_id={GHL_CLIENT_ID}"
    f"&scope={alt_scope_string}"
)

print("\n📋 Alternative scopes:")
for scope in alternative_scopes:
    print(f"   - {scope}")

print(f"\n🌐 Alternative Authorization URL:")
print(f"\n{alt_auth_url}\n")
print("="*70 + "\n")

