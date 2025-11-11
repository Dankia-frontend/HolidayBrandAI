# Voice AI Agents - Authentication Setup Guide

## 🔴 Error: "Invalid JWT" - Authentication Issue

The error you're seeing indicates that the **Voice AI Agents API requires OAuth tokens with specific scopes**, not the Agency API Key.

---

## 🔐 Authentication Requirements

### Voice AI Agents API Requires:
✅ **OAuth Access Token** (from your GHL app)  
✅ **Specific Scopes** for Voice AI access  
❌ **NOT Agency API Key** (Agency API Key doesn't work for Voice AI Agents)

---

## 📋 Step-by-Step Fix

### Step 1: Check Your OAuth Scopes

Your GoHighLevel OAuth app must have the following scopes:

**Required Scopes for Voice AI Agents:**
```
conversations/messages.readonly
conversations/messages.write
locations.readonly
```

**How to Add Scopes:**

1. Go to [GoHighLevel Marketplace](https://marketplace.gohighlevel.com/)
2. Navigate to your app settings
3. Go to **OAuth** section
4. Add the required scopes:
   - `conversations/messages.readonly`
   - `conversations/messages.write`
   - `locations.readonly`
5. **Save changes**

---

### Step 2: Re-Authorize Your Application

After adding scopes, you **MUST re-authorize** your application:

1. **Delete existing tokens** from your database:
   ```sql
   -- Run this in your MySQL database
   DELETE FROM tokens WHERE id = 1;
   ```

2. **Re-run the OAuth authorization flow**:
   ```bash
   cd D:\Projects\HolidayBrandAI
   python test_ghl_auth.py
   ```

3. **Follow the authorization link** in the console
4. **Authorize the app** with the new scopes
5. **Verify tokens are saved** in the database

---

### Step 3: Verify OAuth Token is Working

Run this test script to verify your OAuth token:

```python
# test_voice_ai_auth.py
import requests
from utils.ghl_api import get_valid_access_token
from config.config import GHL_CLIENT_ID, GHL_CLIENT_SECRET

# Get OAuth token
access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)

if not access_token:
    print("❌ No OAuth token found. Run test_ghl_auth.py first")
    exit(1)

print(f"✅ OAuth token found: {access_token[:20]}...")

# Test Voice AI Agents API
headers = {
    "Authorization": f"Bearer {access_token}",
    "Version": "2021-07-28",
    "Content-Type": "application/json"
}

location_id = "UTkbqQXAR7A3UsirpOje"  # Your source location
url = f"https://services.leadconnectorhq.com/voice-ai/agents"
params = {"locationId": location_id, "limit": 10}

print(f"\n🔍 Testing Voice AI Agents API...")
response = requests.get(url, headers=headers, params=params)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text[:500]}")

if response.status_code == 200:
    print("\n✅ SUCCESS! Voice AI Agents API is working!")
    data = response.json()
    print(f"Found {len(data.get('agents', []))} agents")
elif response.status_code == 401:
    print("\n❌ UNAUTHORIZED: OAuth token is invalid or missing scopes")
    print("Please re-authorize your app with the correct scopes")
else:
    print(f"\n⚠️ ERROR: {response.status_code}")
```

**Run the test:**
```bash
python test_voice_ai_auth.py
```

---

## 🔧 Alternative: Use Sub-Account Access Tokens

If your OAuth app has agency-level access, you can also generate sub-account access tokens:

```python
import requests

def get_subaccount_access_token(agency_token: str, location_id: str) -> str:
    """Generate a sub-account access token from agency token"""
    url = "https://services.leadconnectorhq.com/oauth/locationToken"
    headers = {
        "Authorization": f"Bearer {agency_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json"
    }
    payload = {
        "locationId": location_id,
        "scopes": [
            "conversations/messages.readonly",
            "conversations/messages.write",
            "locations.readonly"
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()["access_token"]
    return None
```

---

## 📊 Quick Troubleshooting Checklist

- [ ] **OAuth app has correct scopes**
  - conversations/messages.readonly
  - conversations/messages.write
  - locations.readonly

- [ ] **Re-authorized app after adding scopes**
  - Deleted old tokens from database
  - Ran test_ghl_auth.py
  - Got new authorization
  - Tokens saved to database

- [ ] **Database has valid tokens**
  ```sql
  SELECT access_token, refresh_token, created_at, expire_in 
  FROM tokens 
  WHERE id = 1;
  ```

- [ ] **OAuth token not expired**
  - Tokens expire after ~24 hours
  - System should auto-refresh
  - Check `created_at` + `expire_in` in database

- [ ] **Using OAuth token, not Agency API Key**
  - Voice AI Agents API doesn't support Agency API Key
  - Must use OAuth access tokens

---

## 🔄 Current Authentication Flow

The system now uses this priority for Voice AI Agents:

1. ✅ **OAuth Access Token** (from database) - **PREFERRED**
2. ⚠️ **Agency API Key** (fallback, may not work)
3. ❌ No authentication (will fail)

---

## 🆘 Still Getting Errors?

### Error: "Invalid JWT"
**Solution:** Re-authorize your OAuth app with correct scopes

### Error: "Forbidden" or "Insufficient permissions"
**Solution:** Add required scopes to your OAuth app and re-authorize

### Error: "No token found"
**Solution:** Run `test_ghl_auth.py` to authorize and save tokens

### Tokens keep expiring
**Solution:** System should auto-refresh. Check `get_valid_access_token()` function

---

## 📝 Environment Variables Required

Make sure your `.env` file has:

```env
# OAuth Configuration (REQUIRED for Voice AI Agents)
GHL_CLIENT_ID=your_client_id_here
GHL_CLIENT_SECRET=your_client_secret_here
GHL_REDIRECT_URI=http://localhost:8000/ghl/callback

# Database (for storing tokens)
DBUSERNAME=your_db_user
DBPASSWORD=your_db_password
DBHOST=localhost
DATABASENAME=your_database_name

# Optional: Agency API Key (for other APIs)
GHL_AGENCY_API_KEY=your_agency_key_here
```

---

## 🎯 Summary

**The Issue:** Voice AI Agents API requires OAuth tokens with specific scopes, not Agency API Key.

**The Fix:**
1. Add required scopes to OAuth app
2. Re-authorize application
3. Ensure OAuth tokens are saved to database
4. System will now use OAuth tokens for Voice AI Agents

**Test Command:**
```bash
python test_voice_ai_auth.py
```

---

## 📞 Next Steps After Fixing Auth

Once authentication is working:

1. ✅ Test fetching agents: `GET /voice-ai-agents/list/{location_id}`
2. ✅ Test cloning agents: `POST /voice-ai-agents/clone`
3. ✅ Use frontend to clone Voice AI configurations

---

**Last Updated:** November 10, 2025  
**Status:** ✅ Ready to use after OAuth setup

