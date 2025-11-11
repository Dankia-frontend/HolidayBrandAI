# Voice AI Agents - Correct Scopes Guide

## 🎯 Important Clarification

**Voice AI Agents ≠ Conversation AI**

- **Voice AI Agents**: Phone call AI agents (what you want)
- **Conversation AI**: Chat/messaging bots (different product)

They use **DIFFERENT API scopes!**

---

## ✅ Correct Scopes for Voice AI Agents API

To access the Voice AI Agents API (`/voice-ai/agents`), you need:

```
✅ voiceai.agents.read     - Read Voice AI agents
✅ voiceai.agents.write    - Create/update Voice AI agents
✅ locations.readonly      - Access location info (optional but recommended)
```

**NOT** `conversations.readonly` or `conversations.write` (those are for chat bots)

---

## 📋 How to Create Private Integration with Correct Scopes

### Step 1: Access Private Integrations in GHL

1. Login to **GoHighLevel Agency Account**
2. Go to **Settings** → **Company Settings**
3. Click **"Integrations"** or **"Private Integrations"**
4. Click **"Create Integration"**

### Step 2: Name Your Integration

- **Name**: `Voice AI Agents Integration`
- **Description**: `API access for Voice AI Agents cloning`

### Step 3: Select the Correct Scopes

Look for these EXACT scope names:

```
✅ voiceai.agents.read
✅ voiceai.agents.write
✅ locations.readonly
```

**🚨 If you don't see these scopes:**

This means your GHL account doesn't have Voice AI Agents API access enabled.

**What to do:**
1. Contact GHL Support: support@gohighlevel.com
2. Tell them: "I need Voice AI Agents API access enabled for my agency"
3. Ask them to enable the `voiceai.agents.read` and `voiceai.agents.write` scopes
4. Provide your Agency ID

### Step 4: Generate the API Key

1. **Save** the integration
2. Copy the generated API key (starts with `pk_...`)
3. Save it securely

### Step 5: Update Your `.env` File

```env
# Replace your existing GHL_AGENCY_API_KEY
GHL_AGENCY_API_KEY=pk_your_voice_ai_integration_key_here
```

### Step 6: Restart Your Backend

```bash
cd D:\Projects\HolidayBrandAI
# Stop current server (Ctrl+C)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🧪 Test the Integration

Run this to verify it works:

```bash
python test_voice_ai_auth.py
```

**Expected Output:**
```
✅ Using GHL Agency/Private Integration API Key for Voice AI Agents
✅ SUCCESS! Voice AI Agents API is working!
Found X agents
```

---

## 🔍 If You Don't See Voice AI Scopes

### Option 1: Your Account Doesn't Have Voice AI

**Possible reasons:**
- Your GHL plan doesn't include Voice AI features
- Voice AI API access is not enabled for your agency
- You need to upgrade your plan

**Solution:** Contact GHL support to enable Voice AI API

### Option 2: Use OAuth Instead

If Private Integrations don't work, you can use OAuth:

1. Go to **GHL Marketplace** → **My Apps**
2. Find your OAuth app or create a new one
3. Edit the app and select these scopes:
   - `voiceai.agents.read`
   - `voiceai.agents.write`
   - `locations.readonly`
4. Re-authorize your app
5. The OAuth tokens will be stored in your database

---

## 📧 Template Email for GHL Support

```
Subject: Enable Voice AI Agents API Access

Hello GHL Support,

I'm trying to integrate with the Voice AI Agents API but don't see the 
required scopes in my Private Integrations.

I need these scopes enabled for my agency:
- voiceai.agents.read
- voiceai.agents.write

My account details:
- Agency ID: [your agency ID]
- Email: [your email]
- Plan: [your plan name]

API endpoint I'm trying to access: 
GET https://services.leadconnectorhq.com/voice-ai/agents

Could you please enable Voice AI Agents API access for my account?

Thank you!
```

---

## 🎯 Summary

**The Problem:** You were seeing a 401 error because your API key doesn't have Voice AI Agents scopes.

**The Solution:**
1. ✅ Create a Private Integration in GHL
2. ✅ Select `voiceai.agents.read` and `voiceai.agents.write` scopes
3. ✅ If scopes are not visible, contact GHL support
4. ✅ Update your `.env` with the new key
5. ✅ Restart backend and test

---

## 📚 Official Documentation

- [Voice AI Public APIs - GHL Help](https://help.gohighlevel.com/support/solutions/articles/155000006379-voice-ai-public-apis)
- [GHL API Documentation](https://highlevel.stoplight.io/docs/integrations)
- [Voice AI Agents API Reference](https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents)

---

**Last Updated:** November 11, 2025  
**Status:** ✅ Correct scopes identified

---

## Quick Reference Card

**Copy these scope names when creating Private Integration:**
```
voiceai.agents.read
voiceai.agents.write
locations.readonly
```

**NOT these (wrong - for Conversation AI):**
```
❌ conversations.readonly
❌ conversations.write
❌ conversations/messages.readonly
❌ conversations/messages.write
```

