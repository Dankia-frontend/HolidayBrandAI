# Voice AI Configuration Cloning - Complete Guide

## 📋 Overview

This system allows you to clone Voice AI configurations (AI assistants, workflows, and settings) from one GHL sub-account to another through a simple API and frontend interface.

**Use Case:** You have configured Voice AI in location `UTkbqQXAR7A3UsirpOje` and want to replicate that setup to other sub-accounts.

---

## 🚀 Backend API Endpoints

### 1. Get Voice AI Summary

**Endpoint:** `GET /voice-ai/summary/{location_id}`

**Description:** Get an overview of Voice AI configuration for a specific location.

**Example Request:**
```bash
GET /voice-ai/summary/UTkbqQXAR7A3UsirpOje
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "location_id": "UTkbqQXAR7A3UsirpOje",
    "assistants_count": 3,
    "assistants": [
      {
        "id": "assistant_123",
        "name": "Booking Assistant",
        "type": "voice",
        "status": "active"
      },
      {
        "id": "assistant_456",
        "name": "Customer Support Bot",
        "type": "voice",
        "status": "active"
      }
    ],
    "voice_workflows_count": 2,
    "voice_workflows": [
      {
        "id": "workflow_789",
        "name": "Voice AI Call Handler",
        "status": "active"
      }
    ]
  }
}
```

---

### 2. Clone Voice AI Configuration

**Endpoint:** `POST /voice-ai/clone`

**Description:** Clone Voice AI configuration from source to target location.

**Request Body:**
```json
{
  "source_location_id": "UTkbqQXAR7A3UsirpOje",
  "target_location_id": "target_location_id_here",
  "clone_assistants": true,
  "clone_workflows": true,
  "clone_phone_numbers": false
}
```

**Parameters:**
- `source_location_id` (string, required): Source GHL location ID to copy from
- `target_location_id` (string, required): Target GHL location ID to copy to
- `clone_assistants` (boolean, optional): Clone AI assistants (default: true)
- `clone_workflows` (boolean, optional): Clone workflows (default: true)
- `clone_phone_numbers` (boolean, optional): Clone phone configs (default: false)

**Example Response:**
```json
{
  "success": true,
  "message": "Voice AI configuration cloning completed",
  "data": {
    "success": true,
    "source_location_id": "UTkbqQXAR7A3UsirpOje",
    "target_location_id": "new_location_123",
    "cloned_assistants": [
      {
        "original_id": "assistant_123",
        "original_name": "Booking Assistant",
        "new_id": "assistant_999",
        "new_name": "Booking Assistant (Cloned)"
      }
    ],
    "cloned_workflows": [
      {
        "note": "Workflow cloning requires manual export/import through GHL UI",
        "count": 2,
        "workflows": [
          {
            "id": "workflow_789",
            "name": "Voice AI Call Handler"
          }
        ]
      }
    ],
    "errors": []
  }
}
```

---

### 3. List AI Assistants

**Endpoint:** `GET /voice-ai/assistants/{location_id}`

**Description:** Get a detailed list of all AI assistants in a location.

**Example Request:**
```bash
GET /voice-ai/assistants/UTkbqQXAR7A3UsirpOje
```

**Example Response:**
```json
{
  "success": true,
  "location_id": "UTkbqQXAR7A3UsirpOje",
  "count": 2,
  "assistants": [
    {
      "id": "assistant_123",
      "name": "Booking Assistant",
      "type": "voice",
      "prompt": "You are a helpful booking assistant...",
      "model": "gpt-4",
      "temperature": 0.7,
      "voice": {
        "provider": "elevenlabs",
        "voiceId": "voice_abc123"
      }
    }
  ]
}
```

---

## 💻 Frontend Implementation Guide

### Step 1: Create a Voice AI Cloning Component

Here's a React/Next.js example for your frontend:

```typescript
// components/VoiceAICloner.tsx
import { useState } from 'react';

interface CloneRequest {
  source_location_id: string;
  target_location_id: string;
  clone_assistants: boolean;
  clone_workflows: boolean;
  clone_phone_numbers: boolean;
}

export default function VoiceAICloner() {
  const [sourceLocationId, setSourceLocationId] = useState('UTkbqQXAR7A3UsirpOje');
  const [targetLocationId, setTargetLocationId] = useState('');
  const [cloneAssistants, setCloneAssistants] = useState(true);
  const [cloneWorkflows, setCloneWorkflows] = useState(true);
  const [clonePhoneNumbers, setClonePhoneNumbers] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleClone = async () => {
    if (!targetLocationId) {
      alert('Please select a target location');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const response = await fetch('http://your-backend-url/voice-ai/clone', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // Add authentication headers if needed
          // 'Authorization': `Bearer ${yourToken}`
        },
        body: JSON.stringify({
          source_location_id: sourceLocationId,
          target_location_id: targetLocationId,
          clone_assistants: cloneAssistants,
          clone_workflows: cloneWorkflows,
          clone_phone_numbers: clonePhoneNumbers,
        }),
      });

      const data = await response.json();
      setResult(data);

      if (data.success) {
        alert('Voice AI configuration cloned successfully!');
      } else {
        alert('Cloning completed with some errors. Check the results.');
      }
    } catch (error) {
      console.error('Error cloning Voice AI:', error);
      alert('Failed to clone Voice AI configuration');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="voice-ai-cloner p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-4">Voice AI Configuration Cloner</h2>

      <div className="space-y-4">
        {/* Source Location (Read-only) */}
        <div>
          <label className="block text-sm font-medium mb-1">
            Source Location ID (Template)
          </label>
          <input
            type="text"
            value={sourceLocationId}
            disabled
            className="w-full p-2 border rounded bg-gray-100"
          />
          <p className="text-xs text-gray-500 mt-1">
            This is your master Voice AI configuration
          </p>
        </div>

        {/* Target Location Selector */}
        <div>
          <label className="block text-sm font-medium mb-1">
            Target Location ID *
          </label>
          <input
            type="text"
            value={targetLocationId}
            onChange={(e) => setTargetLocationId(e.target.value)}
            placeholder="Enter target location ID"
            className="w-full p-2 border rounded"
          />
          <p className="text-xs text-gray-500 mt-1">
            Select the sub-account to copy Voice AI configuration to
          </p>
        </div>

        {/* Clone Options */}
        <div className="border-t pt-4">
          <h3 className="font-medium mb-2">Clone Options</h3>
          
          <div className="space-y-2">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={cloneAssistants}
                onChange={(e) => setCloneAssistants(e.target.checked)}
                className="mr-2"
              />
              <span className="text-sm">Clone AI Assistants</span>
            </label>

            <label className="flex items-center">
              <input
                type="checkbox"
                checked={cloneWorkflows}
                onChange={(e) => setCloneWorkflows(e.target.checked)}
                className="mr-2"
              />
              <span className="text-sm">Clone Workflows (Identification)</span>
            </label>

            <label className="flex items-center">
              <input
                type="checkbox"
                checked={clonePhoneNumbers}
                onChange={(e) => setClonePhoneNumbers(e.target.checked)}
                className="mr-2"
              />
              <span className="text-sm">Clone Phone Number Configurations</span>
            </label>
          </div>
        </div>

        {/* Clone Button */}
        <button
          onClick={handleClone}
          disabled={loading || !targetLocationId}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {loading ? 'Cloning...' : 'Clone Voice AI Configuration'}
        </button>

        {/* Results Display */}
        {result && (
          <div className={`mt-4 p-4 rounded ${result.success ? 'bg-green-50 border border-green-200' : 'bg-yellow-50 border border-yellow-200'}`}>
            <h3 className="font-medium mb-2">
              {result.success ? '✅ Cloning Completed' : '⚠️ Cloning Completed with Warnings'}
            </h3>
            
            {result.data?.cloned_assistants && (
              <div className="mb-2">
                <p className="text-sm font-medium">Cloned Assistants: {result.data.cloned_assistants.length}</p>
                <ul className="text-xs ml-4 mt-1">
                  {result.data.cloned_assistants.map((assistant: any) => (
                    <li key={assistant.new_id}>
                      ✓ {assistant.new_name}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.data?.errors && result.data.errors.length > 0 && (
              <div className="mt-2">
                <p className="text-sm font-medium text-red-600">Errors:</p>
                <ul className="text-xs ml-4 mt-1 text-red-600">
                  {result.data.errors.map((error: string, idx: number) => (
                    <li key={idx}>• {error}</li>
                  ))}
                </ul>
              </div>
            )}

            {result.data?.cloned_workflows && result.data.cloned_workflows.length > 0 && (
              <div className="mt-2 bg-blue-50 p-2 rounded">
                <p className="text-xs">
                  <strong>Note:</strong> {result.data.cloned_workflows[0].note}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
```

---

### Step 2: Add Location Selector (Optional Enhancement)

You can enhance the UI by adding a dropdown to select from available locations:

```typescript
// components/LocationSelector.tsx
import { useState, useEffect } from 'react';

export default function LocationSelector({ onChange }: { onChange: (id: string) => void }) {
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch all GHL locations
    fetch('http://your-backend-url/ghl/list-locations')
      .then(res => res.json())
      .then(data => {
        setLocations(data.locations || []);
        setLoading(false);
      })
      .catch(err => {
        console.error('Error fetching locations:', err);
        setLoading(false);
      });
  }, []);

  return (
    <select
      onChange={(e) => onChange(e.target.value)}
      className="w-full p-2 border rounded"
      disabled={loading}
    >
      <option value="">Select a location...</option>
      {locations.map((location: any) => (
        <option key={location.id} value={location.id}>
          {location.name} ({location.id})
        </option>
      ))}
    </select>
  );
}
```

---

### Step 3: Add to Your Dashboard

```typescript
// pages/voiceAIManagement.tsx
import VoiceAICloner from '@/components/VoiceAICloner';

export default function VoiceAIManagementPage() {
  return (
    <div className="container mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">Voice AI Management</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Voice AI Cloner */}
        <div>
          <VoiceAICloner />
        </div>

        {/* Additional tools or info panels can go here */}
        <div className="bg-gray-50 p-6 rounded-lg">
          <h3 className="font-medium mb-4">Quick Guide</h3>
          <ul className="text-sm space-y-2 text-gray-700">
            <li>• Select a target location to clone Voice AI configuration to</li>
            <li>• AI Assistants will be cloned with "(Cloned)" suffix</li>
            <li>• Workflows need to be manually exported/imported in GHL</li>
            <li>• Phone number configurations are optional</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
```

---

## 🔐 Authentication

The endpoints are currently commented out for authentication during development. To enable authentication:

1. Uncomment the `_: str = Depends(authenticate_request)` lines in the endpoints
2. Ensure your frontend sends the authentication token:

```typescript
headers: {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${yourAuthToken}`,
  // or use your custom auth header
  'X-API-Key': yourApiKey
}
```

---

## 📊 What Gets Cloned

### ✅ Automatically Cloned

1. **AI Assistants (Conversation Bots)**
   - Assistant name (with "(Cloned)" suffix)
   - AI prompt/instructions
   - Voice settings (provider, voice ID)
   - Model configuration (GPT-4, temperature, etc.)
   - Tools and integrations
   - Knowledge base references

### ⚠️ Manual Steps Required

1. **Workflows**
   - The API identifies Voice AI related workflows
   - Must be manually exported from source location
   - Import into target location through GHL UI

2. **Phone Numbers**
   - Currently requires manual configuration in GHL
   - Set `clone_phone_numbers: true` to identify configurations

3. **Custom Fields & Tags**
   - May need to be recreated in target location if referenced by assistants

---

## 🎯 Complete Workflow

### For Your Specific Use Case

**Source Location:** `UTkbqQXAR7A3UsirpOje` (Master template)

**Steps:**

1. **View Source Configuration:**
   ```bash
   GET /voice-ai/summary/UTkbqQXAR7A3UsirpOje
   ```

2. **Clone to New Location:**
   ```bash
   POST /voice-ai/clone
   {
     "source_location_id": "UTkbqQXAR7A3UsirpOje",
     "target_location_id": "new_park_location_123",
     "clone_assistants": true,
     "clone_workflows": true,
     "clone_phone_numbers": false
   }
   ```

3. **Verify in Target Location:**
   ```bash
   GET /voice-ai/summary/new_park_location_123
   ```

4. **Manual Tasks (if needed):**
   - Export workflows from source in GHL UI
   - Import workflows to target in GHL UI
   - Configure phone numbers in target location
   - Test Voice AI assistants

---

## 🧪 Testing

### Test the API with cURL

```bash
# 1. Get summary of source location
curl -X GET "http://localhost:8000/voice-ai/summary/UTkbqQXAR7A3UsirpOje"

# 2. Clone to target location
curl -X POST "http://localhost:8000/voice-ai/clone" \
  -H "Content-Type: application/json" \
  -d '{
    "source_location_id": "UTkbqQXAR7A3UsirpOje",
    "target_location_id": "target_location_id",
    "clone_assistants": true,
    "clone_workflows": true,
    "clone_phone_numbers": false
  }'

# 3. List assistants in target
curl -X GET "http://localhost:8000/voice-ai/assistants/target_location_id"
```

---

## 📝 Important Notes

1. **Rate Limiting:** GHL API has rate limits. The system handles this gracefully but large clones may take time.

2. **Assistant Names:** Cloned assistants get "(Cloned)" suffix to avoid naming conflicts. You can rename them in GHL UI.

3. **Testing:** Always test Voice AI assistants in the target location after cloning.

4. **Rollback:** If something goes wrong, you can delete the cloned assistants and re-run the clone operation.

5. **Updates:** If you update the source configuration, you'll need to re-clone to propagate changes (not automatic).

---

## 🆘 Troubleshooting

### Issue: "No valid access token"
**Solution:** Ensure GHL OAuth tokens are configured correctly in your database and `.env` file.

### Issue: "Failed to clone assistant"
**Solution:** Check GHL permissions and ensure the target location has Voice AI enabled.

### Issue: Assistants cloned but not appearing
**Solution:** Refresh the GHL dashboard. It may take a few seconds for changes to reflect.

### Issue: Workflows not cloned
**Solution:** This is expected. Workflows must be manually exported/imported through GHL UI.

---

## 🔗 Related Endpoints

- `GET /ghl/list-locations` - List all GHL sub-accounts
- `GET /ghl/get-location?location_id=X` - Get specific location details
- `POST /park-config/create` - Create park configuration (for booking integration)

---

**Implementation Status:** ✅ Complete and Ready to Use  
**Last Updated:** November 10, 2025  
**Version:** 1.0.0

