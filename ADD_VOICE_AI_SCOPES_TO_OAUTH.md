# How to Add Voice AI Scopes to Your OAuth App

## 🎯 Current Situation

Your backend is now configured to use the **OAuth access token** from your database for Voice AI Agents API calls. This token is automatically generated and refreshed!

However, your current OAuth token is **missing the required scopes** for Voice AI Agents.

---

## ✅ Solution: Add Scopes to Your OAuth App

### Step 1: Access Your OAuth App

1. Go to **GHL Marketplace**: https://marketplace.gohighlevel.com/
2. Click **"My Apps"** in the top navigation
3. Find your OAuth application in the list
4. Click **"Edit"** or the settings icon

### Step 2: Add Required Scopes

1. In your OAuth app settings, find the **"Scopes"** section
2. Look for and **check these scopes**:

```
✅ voiceai.agents.read
✅ voiceai.agents.write
✅ locations.readonly (recommended)
```

3. Click **"Save"** to update your OAuth app

### Step 3: Re-Authorize Your Application

**CRITICAL:** Adding scopes doesn't automatically update existing tokens! You MUST re-authorize.

#### Option A: Quick Re-Authorization (Recommended)

```bash
# 1. Delete old tokens from database
# Connect to your MySQL database and run:
DELETE FROM tokens WHERE id = 1;

# 2. Re-run OAuth authorization
cd D:\Projects\HolidayBrandAI
python test_ghl_auth.py

# 3. Follow the authorization URL that appears
# 4. Complete the OAuth flow
# 5. New tokens with correct scopes will be saved to database
```

#### Option B: Manual Database Token Deletion

```sql
-- Connect to MySQL
mysql -u your_username -p your_database

-- Delete old tokens
DELETE FROM tokens WHERE id = 1;

-- Verify deletion
SELECT * FROM tokens;
```

Then run your authorization script.

### Step 4: Restart Backend

```bash
cd D:\Projects\HolidayBrandAI

# Stop current server (Ctrl+C)

# Restart
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Step 5: Verify It Works

```bash
# Run the test script
python test_voice_ai_agents_auth.py
```

**Expected Output:**
```
✅ Using OAuth access token from database for Voice AI Agents
✅ SUCCESS! Voice AI Agents API is working!
Found X agents
```

---

## 🔍 What If I Don't See Those Scopes?

If `voiceai.agents.read` and `voiceai.agents.write` are not available in your OAuth app's scopes dropdown, it means:

### Possible Reasons:

1. **Your GHL plan doesn't include Voice AI**
   - Solution: Upgrade your plan or contact GHL support

2. **Voice AI API is not enabled for your agency**
   - Solution: Contact GHL support to enable it

3. **Scopes require agency approval**
   - Solution: Request access from GHL support

### Contact GHL Support

**Email:** support@gohighlevel.com

**Message Template:**
```
Subject: Enable Voice AI Agents API Scopes for OAuth App

Hi GHL Support Team,

I need to enable Voice AI Agents API access for my OAuth application.

When I try to add scopes to my OAuth app, I don't see:
- voiceai.agents.read
- voiceai.agents.write

Can you please enable Voice AI Agents API access for my agency account?

My Details:
- Agency ID: [your agency ID]
- OAuth App Name: [your app name]
- Email: [your email]

I want to use the Voice AI Agents API endpoint:
GET/POST https://services.leadconnectorhq.com/voice-ai/agents

Thank you!
```

---

## 🔄 How Your Authentication Works Now

Your backend uses this priority for Voice AI Agents:

1. **OAuth Token from Database** ✅ (PREFERRED)
   - Auto-generated via OAuth flow
   - Auto-refreshes when expired
   - Stored in `tokens` table

2. **Agency API Key** (Fallback)
   - From `.env` file: `GHL_AGENCY_API_KEY`
   - Used only if OAuth token is unavailable

3. **No Auth** ❌ (Will fail with 401)

---

## 📊 Verification Checklist

After following all steps:

- [ ] Scopes added to OAuth app (voiceai.agents.read, voiceai.agents.write)
- [ ] OAuth app changes saved
- [ ] Old tokens deleted from database
- [ ] Re-authorization completed successfully
- [ ] New tokens saved to database with new scopes
- [ ] Backend server restarted
- [ ] Test script confirms tokens work
- [ ] Voice AI cloning works in frontend

---

## 🎓 Understanding OAuth Scopes

### What Are Scopes?

Scopes define what permissions your OAuth token has. Without the correct scopes, GHL's API will reject your requests with a 401 error.

### Why Re-Authorize?

When you add new scopes to your OAuth app, existing tokens don't automatically get those scopes. You must:
1. Delete old tokens
2. Get a new authorization code
3. Exchange it for new tokens
4. New tokens will include all scopes

---

## 🚨 Troubleshooting

### Still Getting 401 After Re-Authorization?

**Check 1:** Verify tokens are in database
```sql
SELECT id, access_token, created_at, expire_in FROM tokens WHERE id = 1;
```

**Check 2:** Check backend logs
```bash
tail -f logs/app_info.log
tail -f logs/app_errors.log
```

Look for: "✅ Using OAuth access token from database for Voice AI Agents"

**Check 3:** Test OAuth token directly
```bash
python test_voice_ai_agents_auth.py
```

### Token Keeps Expiring?

OAuth tokens expire (usually after 24 hours), but they should auto-refresh. Check:

```python
# In ghl_api.py, line 406-422
def get_valid_access_token(client_id, client_secret):
    # This function should auto-refresh expired tokens
```

If auto-refresh isn't working, you may need to re-authorize more frequently.

---

## 📖 Related Documentation

- `VOICE_AI_AGENTS_CORRECT_SCOPES.md` - Full guide on scopes
- `QUICK_FIX_VOICE_AI_SCOPES.md` - Quick reference
- `test_voice_ai_agents_auth.py` - Test script
- `test_ghl_auth.py` - OAuth authorization script

---

## 🎯 Quick Commands Reference

```bash
# Delete old tokens
mysql -u user -p database -e "DELETE FROM tokens WHERE id = 1;"

# Re-authorize
python test_ghl_auth.py

# Test Voice AI
python test_voice_ai_agents_auth.py

# Restart backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

**Last Updated:** November 11, 2025  
**Status:** ✅ Backend configured to use OAuth tokens

---

## ✨ Summary

Your backend is now properly configured to use OAuth tokens for Voice AI Agents! 

**All you need to do is:**
1. Add the scopes to your OAuth app in GHL Marketplace
2. Re-authorize to get new tokens with those scopes
3. Restart your backend
4. You're done! 🎉

The tokens will auto-refresh, and everything will work seamlessly!

