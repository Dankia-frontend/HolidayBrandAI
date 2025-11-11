# Voice AI: Assistants vs Agents - Quick Comparison

## 🎯 Overview

GoHighLevel has **TWO different Voice AI systems**:

1. **Conversation AI Assistants** - Chat-based AI for text conversations
2. **Voice AI Agents** - Advanced phone call automation

This guide helps you understand the difference and choose the right one.

---

## 📊 Comparison Table

| Feature | Conversation AI Assistants | Voice AI Agents |
|---------|---------------------------|-----------------|
| **Primary Use** | Text-based conversations (SMS, chat) | Phone call automation |
| **API Endpoint** | `/conversations/assistants` | `/voice-ai/agents` |
| **Voice Support** | No | Yes (ElevenLabs, Azure, etc.) |
| **Phone Integration** | No | Yes |
| **Model Support** | GPT-4, GPT-3.5 | GPT-4, GPT-3.5, Claude, etc. |
| **Voicemail Detection** | N/A | Yes |
| **Call Recording** | N/A | Yes |
| **Custom Actions** | Limited | Advanced |
| **Real-time Interruption** | N/A | Yes |
| **Silence Detection** | N/A | Yes |

---

## 🔄 When to Use What

### Use Conversation AI Assistants When:
- ✅ Building SMS/text chat bots
- ✅ Automating text-based customer support
- ✅ Creating FAQ chatbots for websites
- ✅ Handling text-only interactions

### Use Voice AI Agents When:
- ✅ Automating phone calls
- ✅ Building IVR (Interactive Voice Response) systems
- ✅ Creating voice-based customer support
- ✅ Handling inbound/outbound voice calls
- ✅ Implementing call screening/voicemail detection

---

## 📚 Your Current Implementation

### Backend Files:

1. **`utils/voice_ai_utils.py`**
   - Handles **Conversation AI Assistants**
   - Text-based chat automation
   - Uses `/conversations/assistants` endpoint

2. **`utils/voice_ai_agents.py`** ⭐ NEW
   - Handles **Voice AI Agents**
   - Phone call automation
   - Uses `/voice-ai/agents` endpoint

---

## 🚀 Available API Endpoints

### Conversation AI Assistants (Text-based)

```
GET  /voice-ai/summary/{location_id}         - Get assistants summary
POST /voice-ai/clone                         - Clone assistants
GET  /voice-ai/assistants/{location_id}      - List all assistants
```

### Voice AI Agents (Phone calls) ⭐ NEW

```
GET    /voice-ai-agents/list/{location_id}              - List all agents
GET    /voice-ai-agents/get/{location_id}/{agent_id}    - Get agent details
POST   /voice-ai-agents/create                          - Create agent
PATCH  /voice-ai-agents/update/{location_id}/{agent_id} - Update agent
DELETE /voice-ai-agents/delete/{location_id}/{agent_id} - Delete agent
GET    /voice-ai-agents/summary/{location_id}           - Get agents summary
POST   /voice-ai-agents/clone                           - Clone agents
GET    /voice-ai-agents/compare                         - Compare agents
```

---

## 💡 Example Use Cases

### Scenario 1: Holiday Park Booking Automation

**Conversation AI Assistant (Text):**
```
Guest texts: "What's available for next weekend?"
Assistant responds with available sites and pricing
Guest books via text conversation
```

**Voice AI Agent (Phone):**
```
Guest calls: "Hi, I'd like to book a site"
Agent asks about dates, guests, preferences
Agent checks availability in real-time
Agent provides pricing and completes booking
```

### Scenario 2: Customer Support

**Conversation AI Assistant (Text):**
```
Customer: "How do I reset my password?"
Assistant: "I can help you with that! Click this link..."
```

**Voice AI Agent (Phone):**
```
Customer calls support line
Agent answers: "Hello! How can I help you today?"
Agent understands spoken question
Agent provides voice response with instructions
Agent can transfer to human if needed
```

---

## 🔧 Quick Start Examples

### Clone Conversation AI Assistants (Text-based)

```bash
POST http://localhost:8000/voice-ai/clone

{
  "source_location_id": "source_id",
  "target_location_id": "target_id",
  "clone_assistants": true,
  "clone_workflows": true,
  "clone_phone_numbers": false
}
```

### Clone Voice AI Agents (Phone-based) ⭐ NEW

```bash
POST http://localhost:8000/voice-ai-agents/clone

{
  "source_location_id": "source_id",
  "target_location_id": "target_id",
  "clone_all": true,
  "specific_agent_ids": null
}
```

---

## 📖 Full Documentation

- **Voice AI Agents (Phone):** See `VOICE_AI_AGENTS_GUIDE.md`
- **Voice AI Assistants (Text):** See `VOICE_AI_QUICK_START.md`
- **Voice AI Cloning:** See `VOICE_AI_CLONING_GUIDE.md`

---

## 🎯 Which One Should You Use?

**For your holiday park business:**

1. **Use Voice AI Agents** if you want to:
   - Automate incoming phone calls
   - Handle booking inquiries by phone
   - Provide 24/7 voice support
   - Screen calls and route to staff

2. **Use Conversation AI Assistants** if you want to:
   - Automate SMS responses
   - Handle text-based booking questions
   - Provide chat support on website
   - Send automated text reminders

3. **Use BOTH** for complete automation:
   - Voice AI Agents handle phone calls
   - Conversation AI Assistants handle texts/chats
   - Seamless omnichannel customer experience

---

## 🔐 Authentication

Both systems use the same authentication:
- Agency API Key (recommended)
- OAuth access tokens with appropriate scopes

**Required Scopes:**
- Assistants: `conversations.readonly`, `conversations.write`
- Agents: `voice-ai.read`, `voice-ai.write`

---

## ⚠️ Important Notes

1. **Different APIs:** These are completely separate systems in GHL
2. **Different Pricing:** Voice AI Agents may have different pricing than Conversation AI
3. **Configuration:** Each system has its own configuration and settings
4. **Cloning:** You can clone each system independently
5. **Testing:** Test both systems separately before deploying

---

## 📞 Integration Workflow

### Complete Voice + Text Automation Setup:

```
1. Create GHL Sub-Account
   ↓
2. Clone Conversation AI Assistants (for text/SMS)
   POST /voice-ai/clone
   ↓
3. Clone Voice AI Agents (for phone calls)
   POST /voice-ai-agents/clone
   ↓
4. Configure phone numbers
   ↓
5. Test text conversations and voice calls
   ↓
6. Deploy to production
```

---

## 🆘 Quick Troubleshooting

### "No agents found" but assistants exist
**Solution:** You're looking at the wrong system. Agents ≠ Assistants.

### Voice settings not working in assistants
**Solution:** Conversation AI Assistants don't support voice. Use Voice AI Agents.

### Can't make phone calls with assistant
**Solution:** Use Voice AI Agents, not Conversation AI Assistants.

---

**Version:** 1.0  
**Last Updated:** November 10, 2025

**Quick Links:**
- [Voice AI Agents Guide](VOICE_AI_AGENTS_GUIDE.md)
- [Voice AI Assistants Quick Start](VOICE_AI_QUICK_START.md)
- [Voice AI Cloning Guide](VOICE_AI_CLONING_GUIDE.md)

