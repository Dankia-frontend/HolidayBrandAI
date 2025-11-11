# Voice AI Cloning - Quick Start Guide

## 🎯 Your Setup

**Source Location (Master Template):** `UTkbqQXAR7A3UsirpOje`

This location contains your Voice AI configuration that you want to clone to other sub-accounts.

---

## 🚀 Quick Start - Backend API

### 1. View Your Master Configuration

```bash
GET http://localhost:8000/voice-ai/summary/UTkbqQXAR7A3UsirpOje
```

**Response shows:**
- Number of AI assistants
- Assistant names and types
- Voice AI related workflows

---

### 2. Clone to Another Location

```bash
POST http://localhost:8000/voice-ai/clone

Body:
{
  "source_location_id": "UTkbqQXAR7A3UsirpOje",
  "target_location_id": "YOUR_TARGET_LOCATION_ID",
  "clone_assistants": true,
  "clone_workflows": true,
  "clone_phone_numbers": false
}
```

**Result:**
- ✅ AI Assistants cloned with all settings
- ✅ Workflows identified (manual export/import needed)
- ✅ Detailed report of what was cloned

---

## 🖥️ Frontend Integration (React/Next.js)

### Simple Implementation

```typescript
const cloneVoiceAI = async (targetLocationId: string) => {
  const response = await fetch('http://your-backend/voice-ai/clone', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_location_id: 'UTkbqQXAR7A3UsirpOje',
      target_location_id: targetLocationId,
      clone_assistants: true,
      clone_workflows: true,
      clone_phone_numbers: false
    })
  });
  
  const result = await response.json();
  return result;
};
```

### UI Component

Add a dropdown/selector for target locations and a "Clone Voice AI" button that calls the above function.

---

## 📋 Complete Workflow

1. **User selects target sub-account** in your frontend
2. **Click "Clone Voice AI Configuration"** button
3. **Backend API clones:**
   - ✅ All AI assistants
   - ✅ Voice settings
   - ✅ Prompts and instructions
   - ✅ Model configurations
4. **Manual steps (if needed):**
   - Export/import workflows via GHL UI
   - Configure phone numbers

---

## 🔧 API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/voice-ai/summary/{location_id}` | GET | View Voice AI config summary |
| `/voice-ai/clone` | POST | Clone Voice AI configuration |
| `/voice-ai/assistants/{location_id}` | GET | List all AI assistants |

---

## ✅ What Gets Cloned Automatically

- ✅ AI Assistant configurations
- ✅ Voice settings (provider, voice ID)
- ✅ AI prompts and instructions
- ✅ Model settings (GPT-4, temperature)
- ✅ Tools and integrations
- ✅ Knowledge base references

## ⚠️ Manual Steps Required

- ⚠️ Workflows (export/import via GHL UI)
- ⚠️ Phone number configurations (if needed)
- ⚠️ Custom fields/tags (if referenced)

---

## 💡 Pro Tips

1. **Test First:** Clone to a test location before production
2. **Naming:** Cloned assistants get "(Cloned)" suffix - rename as needed
3. **Verification:** Always test Voice AI in target location after cloning
4. **Updates:** Re-clone if you update source configuration

---

## 🆘 Quick Troubleshooting

**Problem:** Clone fails  
**Solution:** Check GHL access token and permissions

**Problem:** Assistants not showing  
**Solution:** Refresh GHL dashboard, wait a few seconds

**Problem:** Workflows missing  
**Solution:** Expected - export/import manually via GHL UI

---

## 📞 Example Frontend Flow

```
User Dashboard
    ↓
Voice AI Management Page
    ↓
Select Target Location (Dropdown)
    ↓
Click "Clone Voice AI" Button
    ↓
API Call: POST /voice-ai/clone
    ↓
Show Results:
  ✅ 3 AI Assistants Cloned
  ✅ 2 Workflows Identified
  ℹ️ Manual workflow export/import needed
```

---

**Ready to Use!** 🎉

See `VOICE_AI_CLONING_GUIDE.md` for detailed implementation examples and frontend code.

