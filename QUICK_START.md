# Quick Start Guide - Park Configuration System

## TL;DR

You now have a database table that stores park-specific configurations (Newbook credentials + GHL pipeline/stage IDs). Each park is identified by its `location_id`.

---

## Step 1: Start Your Server

```bash
cd D:\Projects\HolidayBrandAI
python main.py
```

The `park_configurations` table is **automatically created** on startup.

---

## Step 2: Add Your First Park Configuration

### Option A: Using curl (API)

```bash
curl -X POST "http://localhost:8000/park-config/create" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -d '{
    "location_id": "YOUR_GHL_LOCATION_ID",
    "park_name": "Your Park Name",
    "newbook_api_token": "YOUR_NEWBOOK_TOKEN",
    "newbook_api_key": "YOUR_NEWBOOK_KEY",
    "newbook_region": "US",
    "ghl_pipeline_id": "YOUR_GHL_PIPELINE_ID",
    "stage_arriving_soon": "YOUR_STAGE_ID_1",
    "stage_arriving_today": "YOUR_STAGE_ID_2",
    "stage_arrived": "YOUR_STAGE_ID_3",
    "stage_departing_today": "YOUR_STAGE_ID_4",
    "stage_departed": "YOUR_STAGE_ID_5"
  }'
```

### Option B: Using Python Script (Interactive)

```bash
python -m utils.populate_park_configs
```

Follow the prompts to enter your configuration details.

### Option C: Using FastAPI Docs (Browser)

1. Open: `http://localhost:8000/docs`
2. Find `/park-config/create` endpoint
3. Click "Try it out"
4. Fill in the JSON body
5. Click "Execute"

---

## Step 3: Verify Configuration Was Added

```bash
curl -X GET "http://localhost:8000/park-config/list" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

You should see your park configuration in the response.

---

## Step 4: Update Your Endpoints to Use Dynamic Config

### Before (Hardcoded):
```python
@app.get("/availability")
def get_availability(
    period_from: str = Query(...),
    # ... other params
):
    payload = {
        "region": REGION,  # ❌ Hardcoded
        "api_key": API_KEY,  # ❌ Hardcoded
        # ...
    }
    response = requests.post(url, headers=NB_HEADERS, json=payload)
```

### After (Dynamic):
```python
from utils.dynamic_config import get_dynamic_park_config

@app.get("/availability")
def get_availability(
    location_id: str = Query(...),  # ✅ NEW PARAMETER
    period_from: str = Query(...),
    # ... other params
):
    park_config = get_dynamic_park_config(location_id)  # ✅ Get config
    
    payload = {
        "region": park_config.newbook_region,  # ✅ Dynamic
        "api_key": park_config.newbook_api_key,  # ✅ Dynamic
        # ...
    }
    response = requests.post(url, headers=park_config.get_newbook_headers(), json=payload)
```

---

## Step 5: Test Your Updated Endpoint

```bash
curl -X GET "http://localhost:8000/availability?location_id=YOUR_LOCATION_ID&period_from=2025-12-01&period_to=2025-12-05&adults=2&children=0&daily_mode=true" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

---

## Quick Commands Cheat Sheet

### List All Configurations
```bash
curl -X GET "http://localhost:8000/park-config/list" -H "Authorization: Bearer TOKEN"
```

### Get Single Configuration
```bash
curl -X GET "http://localhost:8000/park-config/get/{location_id}" -H "Authorization: Bearer TOKEN"
```

### Update Configuration
```bash
curl -X PUT "http://localhost:8000/park-config/update/{location_id}" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{"park_name": "New Name"}'
```

### Delete Configuration (Soft Delete)
```bash
curl -X DELETE "http://localhost:8000/park-config/delete/{location_id}?soft_delete=true" \
  -H "Authorization: Bearer TOKEN"
```

---

## What Changes You Need to Make

For **each endpoint** that calls Newbook or GHL:

1. **Add** `location_id` as a parameter
2. **Add** this line at the top:
   ```python
   park_config = get_dynamic_park_config(location_id)
   ```
3. **Replace**:
   - `REGION` → `park_config.newbook_region`
   - `API_KEY` → `park_config.newbook_api_key`
   - `NB_HEADERS` → `park_config.get_newbook_headers()`
   - `GHL_PIPELINE_ID` → `park_config.ghl_pipeline_id`
   - Hardcoded stage IDs → `park_config.stage_arriving_soon`, etc.

---

## Database Direct Access (if needed)

```sql
-- View all configurations
SELECT * FROM park_configurations WHERE is_active = TRUE;

-- Add configuration manually
INSERT INTO park_configurations (
    location_id, park_name, newbook_api_token, newbook_api_key, 
    newbook_region, ghl_pipeline_id
) VALUES (
    'loc_123', 'Park Name', 'token', 'key', 'US', 'pipeline_id'
);

-- Update configuration
UPDATE park_configurations 
SET newbook_api_key = 'new_key' 
WHERE location_id = 'loc_123';

-- Deactivate configuration
UPDATE park_configurations 
SET is_active = FALSE 
WHERE location_id = 'loc_123';
```

---

## File Structure

```
HolidayBrandAI/
├── main.py                          # ✅ Updated with new endpoints
├── schemas/schemas.py               # ✅ Updated with new schemas
├── utils/
│   ├── db_park_config.py           # ✅ NEW - Database operations
│   ├── dynamic_config.py           # ✅ NEW - Dynamic config retrieval
│   └── populate_park_configs.py   # ✅ NEW - Setup utility
├── migrations/
│   └── create_park_configurations_table.sql  # ✅ NEW - SQL schema
├── PARK_CONFIG_SETUP.md            # ✅ Complete setup guide
├── MIGRATION_EXAMPLE.md            # ✅ Code migration examples
├── IMPLEMENTATION_SUMMARY.md       # ✅ What was built
└── QUICK_START.md                  # ✅ This file
```

---

## Common Scenarios

### Scenario 1: Add Configuration for All Your GHL Sub-Accounts

1. Get list of all your GHL locations:
   ```bash
   curl -X GET "http://localhost:8000/ghl/list-locations"
   ```

2. For each location, create a park configuration with its unique:
   - Newbook credentials
   - GHL pipeline ID
   - GHL stage IDs

### Scenario 2: Test with One Park Before Rolling Out

1. Add config for one park
2. Update one endpoint (e.g., `/availability`)
3. Test thoroughly
4. Once working, update remaining endpoints
5. Add configs for other parks

### Scenario 3: Update API Credentials for a Park

```bash
curl -X PUT "http://localhost:8000/park-config/update/loc_123" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "newbook_api_token": "new_token",
    "newbook_api_key": "new_key"
  }'
```

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| `No configuration found for location_id` | Add the configuration using `/park-config/create` |
| `Location ID already exists` | Use `/park-config/update` instead |
| `Database connection error` | Check `.env` file for correct DB credentials |
| `Table doesn't exist` | Restart the server (auto-creates table) |

---

## Need More Details?

- **Setup Instructions**: See `PARK_CONFIG_SETUP.md`
- **Code Examples**: See `MIGRATION_EXAMPLE.md`
- **Implementation Details**: See `IMPLEMENTATION_SUMMARY.md`
- **SQL Reference**: See `migrations/create_park_configurations_table.sql`

---

## Summary

✅ Database table for park configurations  
✅ API endpoints to manage configurations  
✅ Dynamic config retrieval by `location_id`  
✅ Helper utilities for setup  

**Next Action**: Add your first park configuration and update one endpoint to test!

