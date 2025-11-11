# GHL OAuth Scopes Setup Guide

## 🚨 Issue: Missing OAuth Scopes

If you're seeing this error:
```
"The token is not authorized for this scope."
```

Your GHL OAuth token doesn't have permission to access Voice AI features.

---

## ✅ Solution: Add Required Scopes

### Required Scopes for Voice AI Cloning:

| Scope | Purpose | Required? |
|-------|---------|-----------|
| `conversations.readonly` | Read AI assistants | ✅ Yes |
| `conversations.write` | Create/update AI assistants | ✅ Yes |
| `workflows.readonly` | Read workflows | ⚠️ Recommended |
| `locations.readonly` | Read location details | ⚠️ Recommended |

---

## 📋 Step-by-Step Instructions

### Step 1: Access Your GHL OAuth App

1. Login to your **GoHighLevel Agency Account**
2. Go to **Settings** → **Company**
3. Navigate to **"Integrations"** in the left sidebar
4. Click on **"OAuth Applications"**

### Step 2: Edit Your OAuth App

1. Find your OAuth application in the list
2. Click **"Edit"** button
3. Scroll down to the **"Scopes"** section

### Step 3: Add Required Scopes

Check the following boxes:

✅ **Conversations**
- ✅ `conversations.readonly` - View conversation data
- ✅ `conversations.write` - Create and update conversations

✅ **Workflows** (Recommended)
- ✅ `workflows.readonly` - View workflow data

✅ **Locations** (Recommended)
- ✅ `locations.readonly` - View location data

### Step 4: Save Changes

1. Click **"Save"** at the bottom
2. Your OAuth app is now updated with new scopes

### Step 5: Re-Authorize Your App

**⚠️ IMPORTANT:** You MUST re-authorize to get a new token with these scopes.

1. Go through the OAuth flow again to get a new token
2. The new token will include the additional scopes
3. Update your database with the new token

---

## 🔄 How to Re-Authorize

### Option A: Manual OAuth Flow

Run this in your browser (replace placeholders):
```
https://marketplace.gohighlevel.com/oauth/chooselocation?response_type=code
&redirect_uri=YOUR_REDIRECT_URI
&client_id=YOUR_CLIENT_ID
&scope=conversations.readonly conversations.write workflows.readonly locations.readonly
```

After authorization, exchange the code for tokens and update your database.

### Option B: Use Your Existing Authorization Script

If you have an authorization script, update it to request the new scopes:

```python
scopes = [
    "conversations.readonly",
    "conversations.write", 
    "workflows.readonly",
    "locations.readonly",
    # ... any other scopes you need
]

scope_string = " ".join(scopes)

auth_url = f"https://marketplace.gohighlevel.com/oauth/chooselocation"
params = {
    "response_type": "code",
    "redirect_uri": GHL_REDIRECT_URI,
    "client_id": GHL_CLIENT_ID,
    "scope": scope_string
}
```

---

## 🧪 Verify Token Scopes

After re-authorizing, verify your token has the correct scopes:

### Check Database Token:

```sql
SELECT * FROM tokens WHERE id = 1;
```

### Test API Access:

```bash
# Test conversations endpoint
curl -X GET "https://services.leadconnectorhq.com/conversations/assistants?locationId=YOUR_LOCATION_ID" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Version: 2021-07-28"
```

Expected response:
- ✅ **200 OK** - Token has correct scopes
- ❌ **401 Unauthorized** - Token still missing scopes

---

## 🎯 Alternative: Use Agency API Key

If you have access to the **Agency API Key** (not OAuth), you can use it instead:

### In your `.env` file:

```bash
# Option 1: OAuth (Recommended for production)
GHL_CLIENT_ID=your_client_id
GHL_CLIENT_SECRET=your_client_secret

# Option 2: Agency API Key (If OAuth scopes are unavailable)
GHL_AGENCY_API_KEY=your_agency_api_key
```

⚠️ **Note:** Agency API keys have broader permissions but are less secure. Only use for development/testing.

---

## 📞 Common Issues

### Issue 1: Still getting 401 after re-authorization
**Solution:** 
- Make sure you saved the OAuth app changes
- Clear browser cookies and try authorization again
- Verify the new token was saved to the database

### Issue 2: Can't find OAuth Applications section
**Solution:**
- Ensure you're logged into the **Agency/Company account** (not a sub-account)
- You need Admin/Owner permissions to manage OAuth apps

### Issue 3: Scope not available in dropdown
**Solution:**
- Contact GHL support to enable the scope for your agency
- Some scopes require agency approval or specific subscription tiers

---

## ✅ Testing Voice AI Cloning

After updating scopes and re-authorizing:

1. Restart your backend server
2. Go to Voice AI Management page in your dashboard
3. Try cloning again
4. You should see AI assistants listed and cloning should work

---

## 🔍 Debugging

### Check Backend Logs:

```bash
# Look for these log messages:
✅ "Found X AI assistants for location..."  # Success
❌ "Authorization error - OAuth token missing required scopes"  # Still missing scopes
```

### Verify in Frontend:

The Voice AI Management page will now show clearer error messages if scopes are missing.

---

## 📚 Additional Resources

- [GHL OAuth Documentation](https://highlevel.stoplight.io/docs/integrations/ZG9jOjQ2MDE4)
- [GHL API Scopes Reference](https://highlevel.stoplight.io/docs/integrations/9d6a65c4838f4-authorization)

---

**Need Help?** 
- Check your GHL agency settings
- Verify OAuth app configuration
- Ensure token is fresh after adding scopes
- Test with a simple API call first

---

**Last Updated:** November 10, 2025  
**Status:** Configuration Required

