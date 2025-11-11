# Voice AI Agent Export & Edit Feature Guide

## 🎯 Overview

The **Export & Edit** feature allows you to export a Voice AI agent configuration from your master template, make custom modifications, and deploy it to any target location. This is more flexible than bulk cloning because you can customize each agent before deployment.

---

## ✨ Key Features

- ✅ **Export agent configuration** from master template
- ✅ **Edit all fields** directly in the frontend UI
- ✅ **No JSON editing required** - everything in a user-friendly form
- ✅ **Deploy to any location** with custom changes
- ✅ **Perfect for park-specific customizations**

---

## 📋 How to Use

### Step 1: Access the Export & Edit Tab

1. Go to **Voice AI Management** in your dashboard
2. Click on the **"✏️ Export & Edit Agent"** tab
3. You'll see a 3-step workflow

### Step 2: Select and Load an Agent

1. **Select an agent** from the dropdown (shows all agents from your master template)
2. Click **"Load Configuration"**
3. Wait for the configuration to load

### Step 3: Edit the Configuration

Once loaded, you'll see an editable form with sections:

#### Basic Settings
- **Agent Name** - Give it a unique name for the target location
- **Provider** - Voice provider (e.g., elevenlabs, azure)
- **Voice ID** - The specific voice to use
- **Model** - AI model (e.g., gpt-4, gpt-3.5-turbo)
- **Language** - Language code (e.g., en, es)
- **Temperature** - Creativity level (0-1)

#### Prompts and Messages
- **First Message** - What the agent says when call starts
- **System Prompt** - System-level instructions
- **Main Prompt** - Core instructions and context

#### Advanced Settings (Collapsible)
- **Max Tokens** - Response length limit
- **Interruption Threshold** - How quickly agent responds when interrupted
- **Silence Timeout** - How long to wait before ending call
- **Response Delay** - Delay before agent responds
- **Webhook URL** - Endpoint for call events

### Step 4: Select Target Location

Choose where you want to deploy the modified agent from the dropdown.

### Step 5: Deploy

Click **"Deploy to Target Location"** button to create the agent with your modifications.

---

## 💡 Use Cases

### Park-Specific Customization
```
Master Agent: "Holiday RV Park Booking Agent"
↓ Export & Edit
Park A Agent: "Sunshine RV Park - Las Vegas"
- Modified first message: "Thanks for calling Sunshine RV Park in Las Vegas!"
- Updated prompt with park-specific amenities
- Custom pricing information

Park B Agent: "Mountain View RV Resort - Colorado"
- Modified first message: "Thanks for calling Mountain View in Colorado!"
- Updated prompt with mountain resort features
- Different pricing structure
```

### Testing Different Prompts
Export the same agent multiple times with different prompt variations to test which performs better.

### Regional Variations
Create region-specific agents with different:
- Languages
- Voices
- Cultural context
- Time zones

---

## 🔄 Workflow Example

```
1. Select Agent: "Holiday Park Booking Agent"
   ↓
2. Load Configuration
   ↓
3. Edit fields:
   - Name: "Lake Paradise RV Resort - Minnesota"
   - First Message: "Hi! Welcome to Lake Paradise RV Resort in Minnesota!"
   - Update prompt with lake-specific activities
   - Add local attractions and pricing
   ↓
4. Select Target: "Lake Paradise Location ID"
   ↓
5. Deploy → Agent created in target location!
```

---

## ⚡ Quick Tips

1. **Always change the name** to avoid confusion with the source agent
2. **Review the prompt** - make sure it references the correct park/location
3. **Test after deployment** - make a test call to verify the agent works
4. **Save changes externally** - if you want to reuse a configuration, copy it before deploying
5. **Use Advanced Settings** for fine-tuning behavior

---

## 🆚 Export & Edit vs. Bulk Clone

| Feature | Export & Edit | Bulk Clone |
|---------|---------------|------------|
| **Customization** | ✅ Edit before deploy | ❌ No editing |
| **Speed** | Slower (one at a time) | ✅ Fast (all at once) |
| **Use Case** | Custom variations | Exact copies |
| **Flexibility** | ✅ High | ❌ Low |
| **Best For** | Different parks/regions | Testing/initial setup |

---

## 🔧 Technical Details

### Backend Endpoints Used
- `GET /voice-ai-agents/get/{location_id}/{agent_id}` - Fetch agent config
- `POST /voice-ai-agents/create` - Create agent with custom config

### Fields Automatically Removed
These fields are removed before deployment (auto-generated):
- `id`
- `locationId`
- `createdAt`
- `updatedAt`
- `createdBy`
- `updatedBy`
- `_id`

---

## 🎯 Best Practices

### Before Exporting
1. ✅ Ensure source agent is working correctly
2. ✅ Have target location ready
3. ✅ Know what changes you want to make

### While Editing
1. ✅ Use descriptive names
2. ✅ Update all location-specific references
3. ✅ Test prompts for clarity
4. ✅ Verify voice IDs are valid

### After Deploying
1. ✅ Test with a phone call
2. ✅ Assign a phone number in GHL
3. ✅ Monitor first few calls
4. ✅ Adjust as needed using the patch endpoint

---

## 🚨 Troubleshooting

### Agent Won't Load
- **Check:** Is the master template location correct?
- **Solution:** Verify `sourceLocationId` in the component

### Deploy Fails
- **Check:** Do you have correct API authentication?
- **Solution:** Ensure GHL_AGENCY_API_KEY has `voiceai.agents.write` scope

### Changes Not Showing
- **Check:** Did you click "Deploy"?
- **Solution:** Configuration must be deployed to take effect

### Voice ID Invalid
- **Check:** Is the voice ID available in target location?
- **Solution:** Use voices that exist in the target account

---

## 📚 Related Features

- **Bulk Clone** - Clone all agents at once without modifications
- **Voice AI Management** - Manage all Voice AI features
- **Park Configuration** - Set up park-specific settings

---

## 🎓 Video Tutorial (Coming Soon)

Watch a step-by-step video demonstration of the Export & Edit feature.

---

**Last Updated:** November 11, 2025  
**Feature Status:** ✅ Production Ready

---

## Quick Start Checklist

- [ ] Navigate to Voice AI Management → Export & Edit tab
- [ ] Select an agent from master template
- [ ] Click "Load Configuration"
- [ ] Edit the fields you want to customize
- [ ] Select target location
- [ ] Click "Deploy to Target Location"
- [ ] Test the newly created agent

**That's it! Your customized agent is now ready to use! 🎉**

