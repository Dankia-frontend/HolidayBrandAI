# Frontend Voice AI Setup - Complete Guide

## ✅ What's Been Implemented

Your frontend now has **full support** for both Voice AI systems:

1. **Voice AI Agents** (Phone Calls) - ⭐ NEW
2. **Conversation AI Assistants** (Text/Chat) - Existing

---

## 🎨 Frontend Features

### Tabbed Interface

The Voice AI Management page now has **two tabs**:

1. **Voice AI Agents (Phone Calls)** Tab
   - Displays Voice AI agents for phone automation
   - Shows agent details: provider, model, voice ID
   - Clone agents with all configurations
   - Phone icon (📞) for agents

2. **Conversation AI (Text/Chat)** Tab
   - Displays Conversation AI assistants
   - Shows assistant details: type, status
   - Clone assistants with workflows
   - Chat icon (💬) for assistants

---

## 📂 Files Modified

### Frontend Files:

```
HolidayBrandAIDashboard/
└── src/app/components/
    └── voiceaimanagement.tsx  ✅ Updated
```

**Changes Made:**
- ✅ Added tab navigation (Agents vs Assistants)
- ✅ Separate state management for agents and assistants
- ✅ Fetch Voice AI agents from new API endpoint
- ✅ Clone Voice AI agents functionality
- ✅ Display agent details (provider, model, voice)
- ✅ Context-aware UI (different content per tab)
- ✅ Enhanced results display for agents vs assistants

---

## 🔗 API Endpoints Used

### Voice AI Agents (NEW):
```typescript
// Get agents summary
GET /voice-ai-agents/summary/{location_id}

// Clone agents
POST /voice-ai-agents/clone
Body: {
  source_location_id: string,
  target_location_id: string,
  clone_all: boolean,
  specific_agent_ids: string[] | null
}
```

### Conversation AI Assistants (Existing):
```typescript
// Get assistants summary
GET /voice-ai/summary/{location_id}

// Clone assistants
POST /voice-ai/clone
Body: {
  source_location_id: string,
  target_location_id: string,
  clone_assistants: boolean,
  clone_workflows: boolean,
  clone_phone_numbers: boolean
}
```

---

## 🚀 How to Use the Frontend

### 1. Navigate to Voice AI Management

```
Dashboard → Voice AI Management
```

### 2. Choose Your Tab

**For Phone Call Automation:**
- Click "Voice AI Agents (Phone Calls)" tab
- See all agents configured for phone calls

**For Text/Chat Automation:**
- Click "Conversation AI (Text/Chat)" tab
- See all assistants for SMS/chat

### 3. Select Target Location

```
1. Select target sub-account from dropdown
2. Review what will be cloned
3. Click "Clone Voice AI Agents" or "Clone Conversation AI"
4. Wait for completion
5. Review results
```

---

## 🎯 UI Components

### Left Panel - Source Configuration

Shows your master template location and lists available:
- **Voice AI Agents** (when on Agents tab)
  - Agent name
  - Provider (ElevenLabs, Azure, etc.)
  - Model (GPT-4, etc.)
  - Voice ID preview

- **Conversation AI Assistants** (when on Assistants tab)
  - Assistant name
  - Type
  - Status

### Middle/Right Panel - Clone Configuration

**Voice AI Agents Tab:**
- Target location selector
- Information about what gets cloned:
  - Agent prompts and instructions
  - Voice settings (voice ID, provider)
  - Model configurations
  - Call behavior settings
  - Actions and tools
- Clone button
- Results display with next steps

**Conversation AI Tab:**
- Target location selector
- Checkboxes for:
  - Clone AI Assistants
  - Identify Workflows
  - Identify Phone Numbers
- Clone button
- Results display

### Bottom Panel - Quick Guide

Context-aware guide that changes based on active tab:
- Voice AI Agents guide for phone automation
- Conversation AI guide for text automation
- Tips and best practices

---

## 🎨 Visual Indicators

### Tab Badges

Each tab shows a count badge:
```tsx
Voice AI Agents (Phone Calls) [3]  ← 3 agents available
Conversation AI (Text/Chat)   [2]  ← 2 assistants available
```

### Icons

- 📞 Phone icon for Voice AI Agents
- 💬 Chat icon for Conversation AI Assistants
- ✓ Success checkmarks
- ⚠ Warning indicators

### Color Coding

- **Blue** - Voice AI Agents (primary color)
- **Green** - Conversation AI Assistants
- **Green backgrounds** - Success states
- **Yellow backgrounds** - Warning states
- **Red backgrounds** - Error states

---

## 🔄 State Management

### TypeScript Interfaces

```typescript
interface VoiceAIAgent {
  id: string;
  name: string;
  voiceId?: string;
  provider?: string;
  model?: string;
  language?: string;
  enabled?: boolean;
}

interface AgentsCloneResult {
  success: boolean;
  source_location_id: string;
  target_location_id: string;
  cloned_agents: Array<{
    original_id: string;
    original_name: string;
    new_id: string;
    new_name: string;
    voice_id?: string;
    provider?: string;
    model?: string;
  }>;
  errors: string[];
}
```

### State Variables

```typescript
const [activeTab, setActiveTab] = useState<"assistants" | "agents">("agents");
const [sourceAgents, setSourceAgents] = useState<VoiceAIAgent[]>([]);
const [agentsCloneResult, setAgentsCloneResult] = useState<AgentsCloneResult | null>(null);
```

---

## 📱 Responsive Design

The interface is fully responsive:

### Desktop (lg and up):
```
+----------------------------------+
| Source Info | Clone Configuration|
|    (33%)    |       (67%)        |
+----------------------------------+
```

### Mobile:
```
+------------------+
| Source Info      |
+------------------+
| Clone Config     |
+------------------+
```

---

## 🧪 Testing the Frontend

### Test Voice AI Agents Cloning:

1. **Start Backend:**
   ```bash
   cd D:\Projects\HolidayBrandAI
   python -m uvicorn main:app --reload
   ```

2. **Start Frontend:**
   ```bash
   cd D:\Projects\HolidayBrandAIDashboard
   npm run dev
   ```

3. **Test Flow:**
   - Navigate to Voice AI Management
   - Click "Voice AI Agents (Phone Calls)" tab
   - Should see agents loading from `UTkbqQXAR7A3UsirpOje`
   - Select a target location
   - Click "Clone Voice AI Agents"
   - Verify results display

### Expected Behavior:

✅ **Success State:**
- Green success message
- List of cloned agents with details
- "Next Steps" guidance
- No errors

⚠️ **Warning State:**
- Yellow warning message
- Partial success (some cloned, some errors)
- Error details displayed

❌ **Error State:**
- Red error message
- Clear error description
- Troubleshooting hints

---

## 🔧 Configuration

### Environment Variables

Frontend needs:
```env
# .env.local
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

### Backend Base URL

The component automatically uses:
```typescript
const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
```

---

## 📊 Data Flow

```
1. User loads Voice AI Management page
   ↓
2. Frontend fetches locations (GET /ghl/list-locations)
   ↓
3. Frontend fetches source agents (GET /voice-ai-agents/summary/{location})
   ↓
4. Frontend fetches source assistants (GET /voice-ai/summary/{location})
   ↓
5. User selects tab (Agents or Assistants)
   ↓
6. User selects target location
   ↓
7. User clicks clone button
   ↓
8. Frontend calls appropriate API:
   - Agents: POST /voice-ai-agents/clone
   - Assistants: POST /voice-ai/clone
   ↓
9. Backend processes cloning
   ↓
10. Frontend displays results
    ↓
11. User reviews cloned items and next steps
```

---

## 🆘 Frontend Troubleshooting

### Agents not loading
**Check:**
- Backend is running
- OAuth authentication is working
- Network tab in browser dev tools
- Console for errors

### Clone button disabled
**Check:**
- Target location is selected
- Target location is different from source
- Not currently loading

### Results not showing
**Check:**
- API response in network tab
- Console errors
- State updates in React DevTools

### Styling issues
**Check:**
- Tailwind CSS is configured
- No CSS conflicts
- Browser cache cleared

---

## 🎯 Next Features to Add (Optional)

### Advanced Features:

1. **Compare Agents**
   - Button to compare agents between locations
   - Visual diff display

2. **Selective Cloning**
   - Checkboxes to select specific agents
   - Uses `specific_agent_ids` parameter

3. **Agent Preview**
   - Modal to view full agent configuration
   - Before cloning preview

4. **Clone History**
   - Track cloning operations
   - Show last cloned date

5. **Bulk Operations**
   - Clone to multiple locations at once
   - Progress indicators

---

## ✅ What's Working Now

- ✅ Tab navigation between Agents and Assistants
- ✅ Fetch and display Voice AI Agents
- ✅ Fetch and display Conversation AI Assistants
- ✅ Clone Voice AI Agents with full configuration
- ✅ Clone Conversation AI Assistants with options
- ✅ Responsive design for mobile and desktop
- ✅ Loading states and error handling
- ✅ Success/warning/error result displays
- ✅ Context-aware UI and guides
- ✅ Real-time agent/assistant counts in tabs

---

## 📞 Support

If you encounter issues:

1. Check browser console for errors
2. Check network tab for API responses
3. Verify backend is running
4. Verify OAuth authentication is working
5. Check `VOICE_AI_AGENTS_AUTH_SETUP.md` for auth issues

---

**Frontend Status:** ✅ Fully Implemented  
**Backend Status:** ✅ Fully Implemented  
**Authentication:** ⚠️ Needs OAuth setup (see VOICE_AI_AGENTS_AUTH_SETUP.md)

**Last Updated:** November 10, 2025

