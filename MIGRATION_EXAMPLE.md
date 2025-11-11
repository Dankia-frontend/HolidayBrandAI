# Migration Example: Converting to Dynamic Configurations

This document shows how to update your existing endpoints to use dynamic park configurations.

## Example 1: Availability Endpoint

### BEFORE (Hardcoded Configuration)

```python
@app.get("/availability")
def get_availability(
    period_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    period_to: str = Query(..., description="End date in YYYY-MM-DD format"),
    adults: int = Query(..., description="Number of adults"),
    daily_mode: str = Query(..., description="Daily mode value, e.g., 'true' or 'false'"),
    Children: int = Query(..., description="Number of children"),
    _: str = Depends(authenticate_request)
):
    try:
        payload = {
            "region": REGION,  # ❌ Hardcoded from config
            "api_key": API_KEY,  # ❌ Hardcoded from config
            "period_from": period_from,
            "period_to": period_to,
            "adults": adults,
            "children": Children,
            "daily_mode": daily_mode
        }

        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_availability_pricing",
            headers=NB_HEADERS,  # ❌ Hardcoded headers
            json=payload,
            verify=False,
            timeout=15
        )

        response.raise_for_status()
        data = response.json()
        
        # ... rest of processing logic
        
        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### AFTER (Dynamic Configuration)

```python
from utils.dynamic_config import get_dynamic_park_config

@app.get("/availability")
def get_availability(
    location_id: str = Query(..., description="GHL Location ID"),  # ✅ NEW parameter
    period_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    period_to: str = Query(..., description="End date in YYYY-MM-DD format"),
    adults: int = Query(..., description="Number of adults"),
    daily_mode: str = Query(..., description="Daily mode value, e.g., 'true' or 'false'"),
    Children: int = Query(..., description="Number of children"),
    _: str = Depends(authenticate_request)
):
    try:
        # ✅ Get park-specific configuration
        park_config = get_dynamic_park_config(location_id)
        
        payload = {
            "region": park_config.newbook_region,  # ✅ Dynamic from DB
            "api_key": park_config.newbook_api_key,  # ✅ Dynamic from DB
            "period_from": period_from,
            "period_to": period_to,
            "adults": adults,
            "children": Children,
            "daily_mode": daily_mode
        }

        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_availability_pricing",
            headers=park_config.get_newbook_headers(),  # ✅ Dynamic headers
            json=payload,
            verify=False,
            timeout=15
        )

        response.raise_for_status()
        data = response.json()
        
        # ... rest of processing logic (unchanged)
        
        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Changes Made:**
1. Added `location_id` as a required query parameter
2. Replaced `REGION` with `park_config.newbook_region`
3. Replaced `API_KEY` with `park_config.newbook_api_key`
4. Replaced `NB_HEADERS` with `park_config.get_newbook_headers()`

---

## Example 2: Confirm Booking Endpoint

### BEFORE

```python
@app.post("/confirm-booking")
def confirm_booking(
    period_from: str = Query(...),
    period_to: str = Query(...),
    guest_firstname: str = Query(...),
    # ... other parameters
    _: str = Depends(authenticate_request)
):
    try:
        # ... tariff logic ...
        
        payload = {
            "region": REGION,  # ❌ Hardcoded
            "api_key": API_KEY,  # ❌ Hardcoded
            "period_from": period_from,
            # ... other fields
        }

        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_create",
            headers=NB_HEADERS,  # ❌ Hardcoded
            json=payload,
            verify=False,
            timeout=15
        )
        
        # ... rest of logic
```

### AFTER

```python
from utils.dynamic_config import get_dynamic_park_config

@app.post("/confirm-booking")
def confirm_booking(
    location_id: str = Query(..., description="GHL Location ID"),  # ✅ NEW
    period_from: str = Query(...),
    period_to: str = Query(...),
    guest_firstname: str = Query(...),
    # ... other parameters
    _: str = Depends(authenticate_request)
):
    try:
        # ✅ Get park-specific configuration
        park_config = get_dynamic_park_config(location_id)
        
        # ... tariff logic (may need location_id for dynamic lookup) ...
        
        payload = {
            "region": park_config.newbook_region,  # ✅ Dynamic
            "api_key": park_config.newbook_api_key,  # ✅ Dynamic
            "period_from": period_from,
            # ... other fields
        }

        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_create",
            headers=park_config.get_newbook_headers(),  # ✅ Dynamic
            json=payload,
            verify=False,
            timeout=15
        )
        
        # ... rest of logic
```

---

## Example 3: GHL Integration with Dynamic Stage IDs

### BEFORE (from ghl_api.py)

```python
def send_to_ghl(booking, access_token):
    try:
        # ... contact creation logic ...
        
        # ❌ Hardcoded stage IDs
        if arrival_dt >= tomorrow and arrival_dt <= seven_days:
            stage_id = '3aeae130-f411-4ac7-bcca-271291fdc3b9'
        elif booking.get("booking_status", "").lower() == "arrived" and departure_dt >= tomorrow:
            stage_id = '99912993-0e69-48f9-9943-096ae68408d7'
        # ... more hardcoded stage logic
        
        ghl_payload = {
            "name": f"{guest_name} - {site_name}",
            "contactId": contact_id,
            "locationId": GHL_LOCATION_ID,  # ❌ Hardcoded
            "pipelineId": GHL_PIPELINE_ID,  # ❌ Hardcoded
            "pipelineStageId": stage_id,
            # ... other fields
        }
        
        # ... rest of logic
```

### AFTER

```python
from utils.dynamic_config import get_dynamic_park_config

def send_to_ghl(booking, access_token, location_id):  # ✅ Added location_id parameter
    try:
        # ✅ Get park-specific configuration
        park_config = get_dynamic_park_config(location_id)
        
        # ... contact creation logic (needs location_id update) ...
        contact_id = get_contact_id(access_token, location_id, first_name, last_name, email, phone)
        
        # ✅ Use dynamic stage ID determination
        arrival_dt = datetime.strptime(arrival, "%Y-%m-%d %H:%M:%S")
        departure_dt = datetime.strptime(departure, "%Y-%m-%d %H:%M:%S") if departure else arrival_dt
        
        stage_id = park_config.get_stage_id_by_booking_status(
            booking_status=booking.get("booking_status", ""),
            arrival_dt=arrival_dt,
            departure_dt=departure_dt
        )
        
        ghl_payload = {
            "name": f"{guest_name} - {site_name}",
            "contactId": contact_id,
            "locationId": park_config.location_id,  # ✅ Dynamic
            "pipelineId": park_config.ghl_pipeline_id,  # ✅ Dynamic
            "pipelineStageId": stage_id,  # ✅ Dynamic
            # ... other fields
        }
        
        # ... rest of logic
```

**Update the caller:**

```python
# In create_opportunities_from_newbook() function
for b in bookings:
    if bucket != "cancelled":
        # Pass location_id to send_to_ghl
        send_to_ghl(b, access_token, b.get('location_id'))  # ✅ Pass location_id
```

---

## Example 4: Check Booking Endpoint

### BEFORE

```python
@app.get("/check-booking")
def confirm_booking(
    name: str = Query(..., description="Guest name"),
    email: str = Query(..., description="Guest email"),
    booking_date: str | None = Query(None, description="Optional booking date"),
    _: str = Depends(authenticate_request)
):
    try:
        # ... date logic ...
        
        payload = {
            "region": REGION,  # ❌ Hardcoded
            "api_key": API_KEY,  # ❌ Hardcoded
            "period_from": period_from,
            "period_to": period_to,
            "list_type": "all"
        }

        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_list",
            headers=NB_HEADERS,  # ❌ Hardcoded
            json=payload,
            verify=False,
            timeout=15
        )
        # ... rest of logic
```

### AFTER

```python
from utils.dynamic_config import get_dynamic_park_config

@app.get("/check-booking")
def confirm_booking(
    location_id: str = Query(..., description="GHL Location ID"),  # ✅ NEW
    name: str = Query(..., description="Guest name"),
    email: str = Query(..., description="Guest email"),
    booking_date: str | None = Query(None, description="Optional booking date"),
    _: str = Depends(authenticate_request)
):
    try:
        # ✅ Get park-specific configuration
        park_config = get_dynamic_park_config(location_id)
        
        # ... date logic (unchanged) ...
        
        payload = {
            "region": park_config.newbook_region,  # ✅ Dynamic
            "api_key": park_config.newbook_api_key,  # ✅ Dynamic
            "period_from": period_from,
            "period_to": period_to,
            "list_type": "all"
        }

        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_list",
            headers=park_config.get_newbook_headers(),  # ✅ Dynamic
            json=payload,
            verify=False,
            timeout=15
        )
        # ... rest of logic
```

---

## Step-by-Step Migration Checklist

### Phase 1: Setup (One-time)
- [ ] Run database migration to create `park_configurations` table
- [ ] Add configurations for all your parks/locations using API or script
- [ ] Test retrieving configurations via `/park-config/list` endpoint

### Phase 2: Update Endpoints (For each endpoint)
- [ ] Import `get_dynamic_park_config` from `utils.dynamic_config`
- [ ] Add `location_id` as a query parameter
- [ ] Call `park_config = get_dynamic_park_config(location_id)` at the start
- [ ] Replace `REGION` with `park_config.newbook_region`
- [ ] Replace `API_KEY` with `park_config.newbook_api_key`
- [ ] Replace `NB_HEADERS` with `park_config.get_newbook_headers()`
- [ ] Replace `GHL_PIPELINE_ID` with `park_config.ghl_pipeline_id`
- [ ] Replace hardcoded stage IDs with `park_config.stage_*` or `get_stage_id_by_booking_status()`

### Phase 3: Update GHL Integration
- [ ] Update `send_to_ghl()` to accept `location_id` parameter
- [ ] Replace hardcoded `GHL_LOCATION_ID` with `park_config.location_id`
- [ ] Replace hardcoded `GHL_PIPELINE_ID` with `park_config.ghl_pipeline_id`
- [ ] Replace stage ID logic with `park_config.get_stage_id_by_booking_status()`
- [ ] Update all callers of `send_to_ghl()` to pass `location_id`

### Phase 4: Update Scheduler/Background Jobs
- [ ] Update `create_opportunities_from_newbook()` to iterate through all locations
- [ ] For each location, get its config and process bookings
- [ ] Ensure each booking has `location_id` associated with it

### Phase 5: Testing
- [ ] Test each endpoint with valid `location_id`
- [ ] Test with invalid `location_id` (should get 404 error)
- [ ] Test with different locations to ensure correct configs are used
- [ ] Monitor logs for any issues

### Phase 6: Cleanup
- [ ] Remove hardcoded config values from `.env` (optional - keep as fallback)
- [ ] Update API documentation
- [ ] Update frontend to pass `location_id` parameter

---

## Frontend Integration

Update your frontend API calls to include `location_id`:

### JavaScript Example

```javascript
// BEFORE
const response = await fetch(
  `${API_BASE}/availability?period_from=${from}&period_to=${to}&adults=${adults}&children=${children}&daily_mode=true`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);

// AFTER
const response = await fetch(
  `${API_BASE}/availability?location_id=${locationId}&period_from=${from}&period_to=${to}&adults=${adults}&children=${children}&daily_mode=true`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);
```

---

## Testing Your Migration

### Test Case 1: Availability Check
```bash
# Replace with your actual location_id and dates
curl -X GET "http://localhost:8000/availability?location_id=loc_xyz123&period_from=2025-12-01&period_to=2025-12-05&adults=2&children=0&daily_mode=true" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

### Test Case 2: Create Configuration
```bash
curl -X POST "http://localhost:8000/park-config/create" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -d '{
    "location_id": "loc_test123",
    "park_name": "Test Park",
    "newbook_api_token": "test_token",
    "newbook_api_key": "test_key",
    "newbook_region": "US",
    "ghl_pipeline_id": "test_pipeline"
  }'
```

### Test Case 3: Verify Configuration
```bash
curl -X GET "http://localhost:8000/park-config/get/loc_test123" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

---

## Rollback Plan

If you need to rollback to hardcoded configs:

1. Keep the old endpoints (rename them with `_v1` suffix)
2. Create new endpoints with dynamic config (use `_v2` suffix)
3. Test v2 endpoints thoroughly
4. Once stable, remove v1 endpoints
5. Alternatively, use feature flags to switch between hardcoded and dynamic

```python
from config.config import USE_DYNAMIC_CONFIG  # Add to .env

if USE_DYNAMIC_CONFIG:
    park_config = get_dynamic_park_config(location_id)
    region = park_config.newbook_region
    api_key = park_config.newbook_api_key
else:
    region = REGION
    api_key = API_KEY
```

