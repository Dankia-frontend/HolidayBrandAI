# Voice AI Agents - Complete Guide

## 🎯 Overview

This guide covers the **Voice AI Agents API** implementation for GoHighLevel. Voice AI Agents are different from Conversation AI Assistants and provide advanced voice call automation capabilities.

**Key Features:**
- ✅ List all Voice AI agents in a location
- ✅ Get detailed agent configurations
- ✅ Create new Voice AI agents
- ✅ Update existing agents
- ✅ Delete agents
- ✅ Clone agents between locations
- ✅ Compare agents across locations

---

## 📚 API Documentation Reference

[GoHighLevel Voice AI Agents API](https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents)

---

## 🚀 API Endpoints

### 1. List Voice AI Agents

Retrieve all Voice AI agents for a location.

```http
GET /voice-ai-agents/list/{location_id}?limit=100&offset=0
```

**Parameters:**
- `location_id` (path) - GHL location ID
- `limit` (query, optional) - Number of agents to retrieve (default: 100)
- `offset` (query, optional) - Pagination offset (default: 0)

**Response:**
```json
{
  "success": true,
  "location_id": "UTkbqQXAR7A3UsirpOje",
  "data": {
    "agents": [
      {
        "id": "agent_123",
        "name": "Customer Support Agent",
        "voiceId": "elevenlabs_voice_id",
        "provider": "elevenlabs",
        "model": "gpt-4",
        "language": "en-US",
        "enabled": true
      }
    ],
    "total": 5,
    "limit": 100,
    "offset": 0
  }
}
```

---

### 2. Get Voice AI Agent Details

Get detailed configuration for a specific agent.

```http
GET /voice-ai-agents/get/{location_id}/{agent_id}
```

**Parameters:**
- `location_id` (path) - GHL location ID
- `agent_id` (path) - Voice AI agent ID

**Response:**
```json
{
  "success": true,
  "location_id": "UTkbqQXAR7A3UsirpOje",
  "agent_id": "agent_123",
  "data": {
    "id": "agent_123",
    "name": "Customer Support Agent",
    "prompt": "You are a helpful customer support agent...",
    "systemPrompt": "Always be professional and courteous.",
    "firstMessage": "Hello! How can I help you today?",
    "voiceId": "elevenlabs_voice_id",
    "provider": "elevenlabs",
    "model": "gpt-4",
    "temperature": 0.7,
    "language": "en-US",
    "enabled": true,
    "endCallAfterSilence": true,
    "endCallAfterSilenceDuration": 30,
    "enableVoicemailDetection": true,
    "callRecording": true,
    "webhookUrl": "https://your-webhook.com/voice-ai",
    "actions": [],
    "tools": []
  }
}
```

---

### 3. Create Voice AI Agent

Create a new Voice AI agent in a location.

```http
POST /voice-ai-agents/create
```

**Request Body:**
```json
{
  "location_id": "UTkbqQXAR7A3UsirpOje",
  "name": "New Support Agent",
  "prompt": "You are a helpful customer support agent for a holiday park.",
  "systemPrompt": "Always be professional, friendly, and helpful.",
  "firstMessage": "Hello! Welcome to our holiday park. How can I assist you today?",
  "voiceId": "elevenlabs_voice_id",
  "provider": "elevenlabs",
  "language": "en-US",
  "model": "gpt-4",
  "temperature": 0.7
}
```

**Response:**
```json
{
  "success": true,
  "message": "Voice AI agent 'New Support Agent' created successfully",
  "data": {
    "id": "new_agent_456",
    "name": "New Support Agent",
    "voiceId": "elevenlabs_voice_id",
    "provider": "elevenlabs",
    "model": "gpt-4",
    "enabled": true
  }
}
```

---

### 4. Update Voice AI Agent

Update an existing Voice AI agent.

```http
PATCH /voice-ai-agents/update/{location_id}/{agent_id}
```

**Request Body:**
```json
{
  "name": "Updated Agent Name",
  "prompt": "Updated prompt text...",
  "temperature": 0.8,
  "enabled": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Voice AI agent agent_123 updated successfully",
  "data": {
    "id": "agent_123",
    "name": "Updated Agent Name",
    "temperature": 0.8,
    "enabled": true
  }
}
```

---

### 5. Delete Voice AI Agent

Delete a Voice AI agent.

```http
DELETE /voice-ai-agents/delete/{location_id}/{agent_id}
```

**Parameters:**
- `location_id` (path) - GHL location ID
- `agent_id` (path) - Voice AI agent ID to delete

**Response:**
```json
{
  "success": true,
  "message": "Voice AI agent agent_123 deleted successfully"
}
```

---

### 6. Get Voice AI Agents Summary

Get a quick summary of all agents in a location.

```http
GET /voice-ai-agents/summary/{location_id}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "location_id": "UTkbqQXAR7A3UsirpOje",
    "agents_count": 3,
    "total_agents": 3,
    "agents": [
      {
        "id": "agent_123",
        "name": "Support Agent 1",
        "voiceId": "voice_123",
        "provider": "elevenlabs",
        "model": "gpt-4",
        "language": "en-US",
        "enabled": true
      }
    ]
  }
}
```

---

### 7. Clone Voice AI Agents

Clone Voice AI agents from one location to another.

```http
POST /voice-ai-agents/clone
```

**Request Body:**
```json
{
  "source_location_id": "source_location_id_here",
  "target_location_id": "target_location_id_here",
  "clone_all": true,
  "specific_agent_ids": null
}
```

**Clone Specific Agents:**
```json
{
  "source_location_id": "source_location_id_here",
  "target_location_id": "target_location_id_here",
  "clone_all": false,
  "specific_agent_ids": ["agent_123", "agent_456"]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Voice AI agents cloning completed",
  "data": {
    "success": true,
    "source_location_id": "source_location_id_here",
    "target_location_id": "target_location_id_here",
    "cloned_agents": [
      {
        "original_id": "agent_123",
        "original_name": "Support Agent",
        "new_id": "agent_789",
        "new_name": "Support Agent (Cloned)",
        "voice_id": "voice_123",
        "provider": "elevenlabs",
        "model": "gpt-4"
      }
    ],
    "errors": []
  }
}
```

---

### 8. Compare Voice AI Agents

Compare Voice AI agents between two locations.

```http
GET /voice-ai-agents/compare?location_id_1=loc1&location_id_2=loc2
```

**Response:**
```json
{
  "success": true,
  "data": {
    "location_1": {
      "id": "loc1",
      "agents_count": 5
    },
    "location_2": {
      "id": "loc2",
      "agents_count": 3
    },
    "only_in_location_1": ["Agent A", "Agent B"],
    "only_in_location_2": ["Agent C"],
    "in_both_locations": ["Agent D", "Agent E"],
    "summary": {
      "unique_to_location_1": 2,
      "unique_to_location_2": 1,
      "common_agents": 2
    }
  }
}
```

---

## 🔧 Python/JavaScript Implementation Examples

### Python Example - Clone Voice AI Agents

```python
import requests

BASE_URL = "http://localhost:8000"

def clone_voice_ai_agents(source_location_id, target_location_id):
    """Clone all Voice AI agents from source to target location"""
    
    url = f"{BASE_URL}/voice-ai-agents/clone"
    payload = {
        "source_location_id": source_location_id,
        "target_location_id": target_location_id,
        "clone_all": True,
        "specific_agent_ids": None
    }
    
    response = requests.post(url, json=payload)
    result = response.json()
    
    if result["success"]:
        cloned_count = len(result["data"]["cloned_agents"])
        print(f"✅ Successfully cloned {cloned_count} Voice AI agents")
        
        for agent in result["data"]["cloned_agents"]:
            print(f"  - {agent['original_name']} → {agent['new_name']}")
    else:
        print(f"❌ Cloning failed: {result['data']['errors']}")
    
    return result

# Usage
clone_voice_ai_agents(
    source_location_id="UTkbqQXAR7A3UsirpOje",
    target_location_id="target_location_id_here"
)
```

---

### JavaScript Example - Fetch and Clone Agents

```javascript
const BASE_URL = 'http://localhost:8000';

async function listVoiceAIAgents(locationId) {
  const response = await fetch(
    `${BASE_URL}/voice-ai-agents/list/${locationId}`
  );
  const data = await response.json();
  
  if (data.success) {
    console.log(`Found ${data.data.agents.length} Voice AI agents`);
    return data.data.agents;
  }
  
  throw new Error('Failed to fetch agents');
}

async function cloneVoiceAIAgents(sourceLocationId, targetLocationId) {
  const response = await fetch(`${BASE_URL}/voice-ai-agents/clone`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      source_location_id: sourceLocationId,
      target_location_id: targetLocationId,
      clone_all: true,
      specific_agent_ids: null
    })
  });
  
  const result = await response.json();
  
  if (result.success) {
    console.log(`✅ Cloned ${result.data.cloned_agents.length} agents`);
    result.data.cloned_agents.forEach(agent => {
      console.log(`  - ${agent.original_name} → ${agent.new_name}`);
    });
  } else {
    console.error('❌ Cloning failed:', result.data.errors);
  }
  
  return result;
}

// Usage
cloneVoiceAIAgents('source_loc_id', 'target_loc_id');
```

---

## 🖥️ Frontend Integration (React/Next.js)

### Complete Voice AI Management Component

```typescript
import { useState } from 'react';

interface VoiceAIAgent {
  id: string;
  name: string;
  voiceId: string;
  provider: string;
  model: string;
  language: string;
  enabled: boolean;
}

export function VoiceAIManager() {
  const [sourceLocation, setSourceLocation] = useState('');
  const [targetLocation, setTargetLocation] = useState('');
  const [agents, setAgents] = useState<VoiceAIAgent[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const fetchAgents = async (locationId: string) => {
    setLoading(true);
    try {
      const response = await fetch(
        `http://localhost:8000/voice-ai-agents/list/${locationId}`
      );
      const data = await response.json();
      
      if (data.success) {
        setAgents(data.data.agents);
      }
    } catch (error) {
      console.error('Error fetching agents:', error);
    } finally {
      setLoading(false);
    }
  };

  const cloneAgents = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        'http://localhost:8000/voice-ai-agents/clone',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_location_id: sourceLocation,
            target_location_id: targetLocation,
            clone_all: true,
            specific_agent_ids: null
          })
        }
      );
      
      const data = await response.json();
      setResult(data);
      
      if (data.success) {
        alert(`✅ Successfully cloned ${data.data.cloned_agents.length} agents!`);
      } else {
        alert(`❌ Cloning failed: ${data.data.errors.join(', ')}`);
      }
    } catch (error) {
      console.error('Error cloning agents:', error);
      alert('❌ Error occurred during cloning');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Voice AI Agents Manager</h1>
      
      <div className="mb-6 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">
            Source Location ID
          </label>
          <input
            type="text"
            value={sourceLocation}
            onChange={(e) => setSourceLocation(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg"
            placeholder="Enter source location ID"
          />
          <button
            onClick={() => fetchAgents(sourceLocation)}
            className="mt-2 px-4 py-2 bg-blue-500 text-white rounded-lg"
            disabled={loading || !sourceLocation}
          >
            Fetch Agents
          </button>
        </div>
        
        <div>
          <label className="block text-sm font-medium mb-2">
            Target Location ID
          </label>
          <input
            type="text"
            value={targetLocation}
            onChange={(e) => setTargetLocation(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg"
            placeholder="Enter target location ID"
          />
        </div>
      </div>

      {agents.length > 0 && (
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-3">
            Found {agents.length} Voice AI Agents
          </h2>
          <div className="space-y-2">
            {agents.map((agent) => (
              <div
                key={agent.id}
                className="p-3 border rounded-lg bg-gray-50"
              >
                <div className="font-medium">{agent.name}</div>
                <div className="text-sm text-gray-600">
                  Provider: {agent.provider} | Model: {agent.model} | 
                  Voice: {agent.voiceId}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={cloneAgents}
        disabled={loading || !sourceLocation || !targetLocation}
        className="px-6 py-3 bg-green-500 text-white rounded-lg font-medium
                   disabled:bg-gray-300 disabled:cursor-not-allowed"
      >
        {loading ? 'Cloning...' : 'Clone Voice AI Agents'}
      </button>

      {result && result.success && (
        <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <h3 className="font-semibold text-green-800 mb-2">
            ✅ Cloning Successful!
          </h3>
          <p className="text-green-700">
            Cloned {result.data.cloned_agents.length} agents successfully
          </p>
          <ul className="mt-2 space-y-1">
            {result.data.cloned_agents.map((agent: any) => (
              <li key={agent.new_id} className="text-sm text-green-600">
                ✓ {agent.original_name} → {agent.new_name}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

---

## 🔐 Authentication

The API uses either:
1. **Agency API Key** (Recommended) - Set `GHL_AGENCY_API_KEY` in your config
2. **OAuth Access Token** - Automatically managed via token refresh

Make sure your GHL app has the following scopes:
- `voice-ai.read`
- `voice-ai.write`
- `locations.readonly`

---

## 📝 What Gets Cloned

When cloning Voice AI agents, the following configurations are copied:

✅ **Agent Settings:**
- Name (with "(Cloned)" suffix)
- Prompts and instructions
- System prompts
- First message

✅ **Voice Configuration:**
- Voice ID
- Voice provider (ElevenLabs, Azure, etc.)
- Language settings

✅ **AI Model Settings:**
- Model (GPT-4, GPT-3.5, etc.)
- Temperature
- Max tokens

✅ **Call Behavior:**
- End call after silence settings
- Voicemail detection
- Call recording preferences
- End call phrases
- Interruption threshold

✅ **Advanced Features:**
- Actions
- Tools
- Keywords
- Webhook URLs
- Transcription settings
- Boosted keywords

---

## ⚠️ Important Notes

1. **Agent Names:** Cloned agents automatically get "(Cloned)" appended to prevent naming conflicts
2. **Phone Numbers:** Phone number assignments are NOT cloned (must be configured manually)
3. **Location-Specific IDs:** Some IDs may need to be updated after cloning (e.g., custom field IDs)
4. **Testing:** Always test cloned agents in the target location before using in production
5. **Rate Limits:** Be mindful of GHL API rate limits when cloning multiple agents

---

## 🔄 Typical Workflow

1. **List Source Agents** → View all agents in your master location
2. **Review Configuration** → Check agent details and settings
3. **Clone to Target** → Copy agents to new sub-account
4. **Verify Cloning** → Use compare endpoint to verify
5. **Test Agents** → Make test calls to ensure proper functionality
6. **Assign Phone Numbers** → Link cloned agents to phone numbers

---

## 🆘 Troubleshooting

### Error: "Failed to fetch Voice AI agents"
**Solution:** Verify your GHL API credentials and ensure the location ID is correct.

### Error: "Authorization error"
**Solution:** Check that your Agency API Key has the required permissions or that OAuth scopes include `voice-ai.read` and `voice-ai.write`.

### Cloned agents not appearing
**Solution:** Wait a few seconds and refresh. GHL may have a slight delay in propagating changes.

### Voice settings not working
**Solution:** Verify that the voice ID and provider are available in the target location.

---

## 📞 Support

For issues or questions:
1. Check the [GHL API Documentation](https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents)
2. Review the logs in `logs/app_info.log` and `logs/app_errors.log`
3. Test endpoints using Postman or similar tools

---

**Version:** 1.0  
**Last Updated:** November 10, 2025

