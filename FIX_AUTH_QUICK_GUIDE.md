# 🔴 FIX: "Invalid JWT" Error - Quick Guide

## The Problem

You're getting this error:
```
"Invalid JWT" - Status 401
```

This means the Voice AI Agents API needs **OAuth tokens with specific scopes**, not the Agency API Key.

---

## ⚡ Quick Fix (5 Steps)

### Step 1: Add OAuth Scopes

1. Go to [GoHighLevel Marketplace](https://marketplace.gohighlevel.com/)
2. Open your app
3. Go to **OAuth** section
4. Add these scopes:
   ```
   conversations/messages.readonly
   conversations/messages.write
   locations.readonly
   ```
5. **Save**

### Step 2: Delete Old Tokens

Run this SQL in your database:
```sql
DELETE FROM tokens WHERE id = 1;
```

### Step 3: Re-Authorize Your App

```bash
cd D:\Projects\HolidayBrandAI
python test_ghl_auth.py
```

Follow the link and authorize your app.

### Step 4: Test Authentication

```bash
python test_voice_ai_auth.py
```

**Expected Output:**
```
✅ SUCCESS! Voice AI Agents API is working!
📊 Found X agents
```

### Step 5: Try Cloning Again

If the test passes, go to your frontend and try cloning Voice AI Agents again. It should work now!

---

## 🎯 That's It!

After these steps, your Voice AI Agents cloning should work perfectly.

---

## 📚 Detailed Guides

For more details, see:
- **`VOICE_AI_AGENTS_AUTH_SETUP.md`** - Detailed authentication guide
- **`VOICE_AI_IMPLEMENTATION_SUMMARY.md`** - Complete implementation overview

---

**Quick Test:**
```bash
# After fixing auth, run this to verify:
python test_voice_ai_auth.py
```

**If you see ✅ SUCCESS, you're good to go!**

