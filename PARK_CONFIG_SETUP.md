# Park Configuration System - Setup Guide

## Overview

The park configuration system allows you to manage multiple parks (sub-accounts) with different configurations for:
- **Newbook API** credentials (token, key, region)
- **GHL Pipeline and Stage IDs** for each park
- Dynamic configuration retrieval based on `location_id`

## Database Schema

The `park_configurations` table stores the following information:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT | Primary key (auto-increment) |
| `location_id` | VARCHAR(255) | GHL location ID (unique) |
| `park_name` | VARCHAR(255) | Human-readable park name |
| `newbook_api_token` | VARCHAR(500) | Newbook API token for this park |
| `newbook_api_key` | VARCHAR(500) | Newbook API key for this park |
| `newbook_region` | VARCHAR(100) | Newbook region code (e.g., 'US', 'AU') |
| `ghl_pipeline_id` | VARCHAR(255) | GHL pipeline ID for this park |
| `stage_arriving_soon` | VARCHAR(255) | Stage ID for "arriving soon" bookings |
| `stage_arriving_today` | VARCHAR(255) | Stage ID for "arriving today" bookings |
| `stage_arrived` | VARCHAR(255) | Stage ID for "arrived" bookings |
| `stage_departing_today` | VARCHAR(255) | Stage ID for "departing today" bookings |
| `stage_departed` | VARCHAR(255) | Stage ID for "departed" bookings |
| `is_active` | BOOLEAN | Whether the configuration is active |
| `created_at` | TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | Last update timestamp |

---

## Setup Instructions

### 1. Initialize the Database Table

The table is automatically created when the FastAPI app starts. However, you can manually create it:

**Option A: Run from Python**
```bash
python -c "from utils.db_park_config import create_park_configurations_table; create_park_configurations_table()"
```

**Option B: Run SQL directly**
```sql
CREATE TABLE IF NOT EXISTS park_configurations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    location_id VARCHAR(255) NOT NULL UNIQUE,
    park_name VARCHAR(255) NOT NULL,
    newbook_api_token VARCHAR(500) NOT NULL,
    newbook_api_key VARCHAR(500) NOT NULL,
    newbook_region VARCHAR(100) NOT NULL,
    ghl_pipeline_id VARCHAR(255) NOT NULL,
    
    stage_arriving_soon VARCHAR(255),
    stage_arriving_today VARCHAR(255),
    stage_arrived VARCHAR(255),
    stage_departing_today VARCHAR(255),
    stage_departed VARCHAR(255),
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_location_id (location_id),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 2. Add Park Configurations

#### Method A: Using API Endpoints (Recommended)

**Create a new park configuration:**
```bash
curl -X POST "http://localhost:8000/park-config/create" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -d '{
    "location_id": "loc_xyz123",
    "park_name": "Sunny Meadows RV Park",
    "newbook_api_token": "your_newbook_token",
    "newbook_api_key": "your_newbook_key",
    "newbook_region": "US",
    "ghl_pipeline_id": "pipeline_abc123",
    "stage_arriving_soon": "stage_id_1",
    "stage_arriving_today": "stage_id_2",
    "stage_arrived": "stage_id_3",
    "stage_departing_today": "stage_id_4",
    "stage_departed": "stage_id_5"
  }'
```

**List all configurations:**
```bash
curl -X GET "http://localhost:8000/park-config/list" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

**Get a specific configuration:**
```bash
curl -X GET "http://localhost:8000/park-config/get/loc_xyz123" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

**Update a configuration:**
```bash
curl -X PUT "http://localhost:8000/park-config/update/loc_xyz123" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -d '{
    "park_name": "Updated Park Name",
    "ghl_pipeline_id": "new_pipeline_id"
  }'
```

**Delete/Deactivate a configuration:**
```bash
curl -X DELETE "http://localhost:8000/park-config/delete/loc_xyz123?soft_delete=true" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

#### Method B: Interactive Script

Run the interactive setup script:
```bash
cd D:\Projects\HolidayBrandAI
python -m utils.populate_park_configs
```

This will guide you through adding configurations interactively.

#### Method C: Bulk Import from Python

Create a script to bulk import configurations:

```python
from utils.populate_park_configs import bulk_import_from_dict

configs = [
    {
        "location_id": "loc_park1",
        "park_name": "Park 1",
        "newbook_api_token": "token1",
        "newbook_api_key": "key1",
        "newbook_region": "US",
        "ghl_pipeline_id": "pipeline1",
        "stage_arriving_soon": "stage1",
        "stage_arriving_today": "stage2",
        "stage_arrived": "stage3",
        "stage_departing_today": "stage4",
        "stage_departed": "stage5"
    },
    {
        "location_id": "loc_park2",
        "park_name": "Park 2",
        "newbook_api_token": "token2",
        "newbook_api_key": "key2",
        "newbook_region": "AU",
        "ghl_pipeline_id": "pipeline2",
        # Stage IDs optional
    }
]

bulk_import_from_dict(configs)
```

---

## Using Dynamic Configurations in Your Code

### Example: Update an Existing Endpoint

**Before (hardcoded config):**
```python
@app.get("/availability")
def get_availability(
    period_from: str = Query(...),
    period_to: str = Query(...),
    adults: int = Query(...),
    children: int = Query(...),
    daily_mode: str = Query(...),
    _: str = Depends(authenticate_request)
):
    payload = {
        "region": REGION,  # Hardcoded
        "api_key": API_KEY,  # Hardcoded
        "period_from": period_from,
        "period_to": period_to,
        "adults": adults,
        "children": children,
        "daily_mode": daily_mode
    }
    
    response = requests.post(
        f"{NEWBOOK_API_BASE}/bookings_availability_pricing",
        headers=NB_HEADERS,  # Hardcoded
        json=payload,
        verify=False,
        timeout=15
    )
    
    return response.json()
```

**After (dynamic config):**
```python
from utils.dynamic_config import get_dynamic_park_config

@app.get("/availability")
def get_availability(
    location_id: str = Query(..., description="GHL Location ID"),
    period_from: str = Query(...),
    period_to: str = Query(...),
    adults: int = Query(...),
    children: int = Query(...),
    daily_mode: str = Query(...),
    _: str = Depends(authenticate_request)
):
    # Get park-specific configuration
    park_config = get_dynamic_park_config(location_id)
    
    payload = {
        "region": park_config.newbook_region,  # Dynamic
        "api_key": park_config.newbook_api_key,  # Dynamic
        "period_from": period_from,
        "period_to": period_to,
        "adults": adults,
        "children": children,
        "daily_mode": daily_mode
    }
    
    response = requests.post(
        f"{NEWBOOK_API_BASE}/bookings_availability_pricing",
        headers=park_config.get_newbook_headers(),  # Dynamic
        json=payload,
        verify=False,
        timeout=15
    )
    
    return response.json()
```

### Using Dynamic Stage IDs

```python
from utils.dynamic_config import get_dynamic_park_config
from datetime import datetime

# Get configuration
park_config = get_dynamic_park_config(location_id)

# Determine stage ID based on booking status
arrival_dt = datetime.strptime(booking['booking_arrival'], "%Y-%m-%d %H:%M:%S")
departure_dt = datetime.strptime(booking['booking_departure'], "%Y-%m-%d %H:%M:%S")

stage_id = park_config.get_stage_id_by_booking_status(
    booking_status=booking['booking_status'],
    arrival_dt=arrival_dt,
    departure_dt=departure_dt
)

# Use stage_id in GHL opportunity creation
ghl_payload = {
    "name": f"{guest_name} - {site_name}",
    "locationId": park_config.location_id,
    "pipelineId": park_config.ghl_pipeline_id,
    "pipelineStageId": stage_id,
    # ... other fields
}
```

---

## API Endpoints Reference

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/park-config/create` | Create new park configuration | Yes |
| PUT | `/park-config/update/{location_id}` | Update existing configuration | Yes |
| GET | `/park-config/get/{location_id}` | Get single configuration | Yes |
| GET | `/park-config/list` | List all configurations | Yes |
| DELETE | `/park-config/delete/{location_id}` | Delete/deactivate configuration | Yes |

---

## Best Practices

1. **Always use `location_id` as a query parameter** in endpoints that need park-specific configurations
2. **Test with one park first** before rolling out to all parks
3. **Use soft delete** (deactivate) instead of hard delete to maintain audit trail
4. **Keep stage IDs updated** when you modify GHL pipelines
5. **Secure your API tokens** - never commit them to version control

---

## Troubleshooting

### Configuration Not Found Error
```
HTTPException: No configuration found for location_id: loc_xyz
```

**Solution:** Add the configuration using one of the methods above.

### Duplicate Location ID Error
```
Failed to create park configuration. Location ID loc_xyz already exists.
```

**Solution:** Use the update endpoint instead, or delete the existing configuration first.

### Database Connection Error
```
Database connection error: Access denied
```

**Solution:** Check your `.env` file for correct database credentials:
```
DBUSERNAME=your_username
DBPASSWORD=your_password
DBHOST=your_host
DATABASENAME=your_database
```

---

## Migration Guide

If you're migrating from hardcoded configs to dynamic configs:

1. **Identify all hardcoded values** (REGION, API_KEY, GHL_PIPELINE_ID, stage IDs)
2. **Create configurations** for each location using the API or script
3. **Update endpoints** to accept `location_id` parameter
4. **Replace hardcoded values** with `park_config.property_name`
5. **Test each endpoint** with different location_ids
6. **Deploy** to production

---

## Support

For issues or questions, check:
- Application logs: `logs/app_info.log` and `logs/app_errors.log`
- Database helper logs contain detailed error information
- Use the FastAPI docs at `http://localhost:8000/docs` for interactive API testing

