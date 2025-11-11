# 🚀 Quick Fix: Voice AI Agents 401 Error

## The Problem
```
❌ Error: {"statusCode":401,"message":"The token is not authorized for this scope."}
```

## The Solution (2 Minutes)

### ✅ Create Private Integration with Voice AI Scopes

#### 1️⃣ Open GHL Settings
- Login to **GoHighLevel Agency Account**
- **Settings** → **Company Settings** → **Integrations**

#### 2️⃣ Create Integration
- Click **"Create Integration"**
- Name: `Voice AI Agents`

#### 3️⃣ Select These Scopes (REQUIRED)
```
✅ voiceai.agents.read
✅ voiceai.agents.write
✅ locations.readonly
```

**🚨 NOT THESE (wrong API):**
```
❌ conversations.readonly
❌ conversations.write
```

#### 4️⃣ Copy the API Key
- Click **Save**
- Copy the key (starts with `pk_...`)

#### 5️⃣ Update .env
```env
GHL_AGENCY_API_KEY=pk_your_key_here
```

#### 6️⃣ Restart Backend
```bash
cd D:\Projects\HolidayBrandAI
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🆘 Don't See voiceai.agents.read Scope?

**This means your account doesn't have Voice AI API access.**

### Contact GHL Support:

**Email:** support@gohighlevel.com

**Message:**
```
Hi, I need Voice AI Agents API access enabled for my agency.

I'm trying to access the /voice-ai/agents API endpoint but don't see 
the voiceai.agents.read and voiceai.agents.write scopes.

Can you please enable Voice AI Agents API for my account?

Agency ID: [your ID]
Email: [your email]
```

---

## ✅ Test It Works

```bash
python test_voice_ai_auth.py
```

Expected: `✅ SUCCESS! Voice AI Agents API is working!`

---

## 📖 Full Guide

See: `VOICE_AI_AGENTS_CORRECT_SCOPES.md`

---

**Last Updated:** November 11, 2025

