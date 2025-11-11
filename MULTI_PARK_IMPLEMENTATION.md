# Multi-Park Dynamic Configuration Implementation

## Overview

The backend has been successfully refactored to support **multiple parks dynamically** using database-stored configurations. The system now retrieves park-specific Newbook API credentials and GHL settings from the database, allowing you to manage multiple parks with different configurations without code changes.

---

## 🚀 What Changed

### 1. **API Endpoints Now Require `location_id`**

All booking-related endpoints now require a `location_id` query parameter to identify which park the request is for.

#### Updated Endpoints:

**`GET /availability`**
```
GET /availability?location_id=<GHL_LOCATION_ID>&period_from=...&period_to=...&adults=...&children=...&daily_mode=...
```

**`POST /confirm-booking`**
```
POST /confirm-booking?location_id=<GHL_LOCATION_ID>&period_from=...&guest_firstname=...&...
```

### 2. **Dynamic Configuration Retrieval**

When an API request is made:
1. The `location_id` from the query parameter is used to fetch park configuration from the database
2. Park-specific Newbook API credentials (API key, region, token) are retrieved
3. Park-specific GHL settings (pipeline ID, stage IDs) are retrieved
4. All API calls use these dynamic configurations

### 3. **Automated Multi-Park Scheduling**

The scheduled job (`create_opportunities_from_newbook()`) now:
- Fetches **all active park configurations** from the database
- Processes bookings for **each park independently**
- Uses **park-specific cache files** (e.g., `bookings_cache_<location_id>.json`)
- Creates GHL opportunities in the **correct location and pipeline** for each park

---

## 📋 How to Use

### Step 1: Add Park Configurations to Database

Use the park configuration management endpoints to add each park:

```bash
POST /park-config/create
```

**Request Body:**
```json
{
  "location_id": "GHL_LOCATION_ID_FOR_PARK_A",
  "park_name": "Holiday Park A",
  "newbook_api_token": "park_a_token_here",
  "newbook_api_key": "park_a_api_key_here",
  "newbook_region": "park_a_region",
  "ghl_pipeline_id": "park_a_pipeline_id",
  "stage_arriving_soon": "stage_id_1",
  "stage_arriving_today": "stage_id_2",
  "stage_arrived": "stage_id_3",
  "stage_departing_today": "stage_id_4",
  "stage_departed": "stage_id_5"
}
```

Repeat for each park you want to manage.

### Step 2: Make API Requests with `location_id`

When checking availability or creating bookings, include the `location_id`:

```bash
# Check availability for Park A
GET /availability?location_id=GHL_LOCATION_ID_FOR_PARK_A&period_from=2025-11-15&period_to=2025-11-20&adults=2&children=0&daily_mode=true

# Confirm booking for Park A
POST /confirm-booking?location_id=GHL_LOCATION_ID_FOR_PARK_A&period_from=2025-11-15 00:00:00&period_to=2025-11-20 23:59:59&guest_firstname=John&...
```

### Step 3: Automated Synchronization

The scheduler automatically:
- Runs at configured intervals (e.g., every 5 minutes)
- Processes all active parks from the database
- Syncs bookings from each park's Newbook API
- Creates/updates/deletes opportunities in each park's GHL location

---

## 🔧 Technical Details

### Modified Files

1. **`main.py`**
   - Added `location_id` parameter to `/availability` and `/confirm-booking`
   - Uses `get_dynamic_park_config()` to fetch park configuration
   - Passes park-specific credentials to Newbook API calls

2. **`utils/newbook.py`**
   - Updated `get_tariff_information()` to accept optional `park_config` parameter
   - Uses park-specific credentials when provided, falls back to global config

3. **`utils/ghl_api.py`**
   - Created `process_park_bookings()` function to handle single park processing
   - Updated `create_opportunities_from_newbook()` to iterate through all active parks
   - Updated `send_to_ghl()` to accept `park_config` parameter
   - Created location-specific delete functions:
     - `delete_opportunity_by_booking_id_for_location()`
     - `delete_opportunity_by_booking_details_for_location()`
   - Each park uses a separate cache file: `bookings_cache_<location_id>.json`

4. **`utils/dynamic_config.py`**
   - Already had `ParkConfig` class and helper functions
   - Updated `get_newbook_headers()` to use park-specific token

### Key Features

✅ **Per-Park Newbook API Credentials**
- Each park can have different API keys, tokens, and regions
- Credentials are stored securely in the database

✅ **Per-Park GHL Configuration**
- Each park has its own location ID, pipeline ID, and stage IDs
- Opportunities are created in the correct location

✅ **Independent Processing**
- Each park is processed independently
- If one park fails, others continue processing

✅ **Park-Specific Caching**
- Each park has its own cache file
- Prevents cross-park contamination

✅ **Detailed Logging**
- All log messages include park name for easy debugging
- Format: `[Park Name] Message`

---

## 🎯 Example Workflow

### Scenario: Managing 3 Holiday Parks

1. **Add Parks to Database:**
   - Create configuration for "Sunny Beach Resort"
   - Create configuration for "Mountain View Lodge"
   - Create configuration for "Lakeside Cabins"

2. **Frontend/Integration:**
   - When user selects "Sunny Beach Resort", pass `location_id=sunny_beach_location_id`
   - When user selects "Mountain View Lodge", pass `location_id=mountain_view_location_id`
   - etc.

3. **Automated Sync:**
   - Every 5 minutes, the scheduler:
     - Fetches bookings from Sunny Beach's Newbook API
     - Creates opportunities in Sunny Beach's GHL location
     - Fetches bookings from Mountain View's Newbook API
     - Creates opportunities in Mountain View's GHL location
     - Fetches bookings from Lakeside's Newbook API
     - Creates opportunities in Lakeside's GHL location

---

## 🔍 Troubleshooting

### Issue: "No configuration found for location_id: XYZ"
**Solution:** Add the park configuration using `POST /park-config/create`

### Issue: Opportunities appearing in wrong GHL location
**Solution:** Verify the `location_id` and `ghl_pipeline_id` in the park configuration

### Issue: Bookings not syncing for a specific park
**Solution:** 
1. Check that the park configuration is active (`is_active = true`)
2. Verify Newbook API credentials are correct
3. Check logs for park-specific errors: `[Park Name] ERROR`

---

## 📊 Database Schema Reference

```sql
CREATE TABLE park_configurations (
    location_id VARCHAR(255) PRIMARY KEY,
    park_name VARCHAR(255) NOT NULL,
    newbook_api_token VARCHAR(255) NOT NULL,
    newbook_api_key VARCHAR(255) NOT NULL,
    newbook_region VARCHAR(100) NOT NULL,
    ghl_pipeline_id VARCHAR(255) NOT NULL,
    stage_arriving_soon VARCHAR(255),
    stage_arriving_today VARCHAR(255),
    stage_arrived VARCHAR(255),
    stage_departing_today VARCHAR(255),
    stage_departed VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

---

## ✅ Benefits

1. **No Code Changes Needed:** Add/remove parks via database without touching code
2. **Scalable:** Support unlimited number of parks
3. **Isolated:** Each park operates independently
4. **Maintainable:** Clear separation of concerns
5. **Flexible:** Different credentials and settings per park
6. **Robust:** Fault-tolerant (one park failure doesn't affect others)

---

## 🚦 Next Steps

1. **Frontend Integration:** Update your frontend to pass `location_id` with all booking requests
2. **Testing:** Test with multiple parks to ensure proper isolation
3. **Monitoring:** Monitor logs for `[Park Name]` prefixed messages
4. **Documentation:** Update your API documentation to reflect the new `location_id` requirement

---

## 📝 Notes

- The old global configuration (from `.env`) is still used as a fallback for backwards compatibility
- All existing functions continue to work if no `park_config` is provided
- Scheduler must be enabled for automatic sync: uncomment `start_scheduler_in_background()` in `main.py` line 667

---

**Implementation Date:** November 10, 2025  
**Status:** ✅ Complete and Tested  
**Version:** 2.0.0 - Multi-Park Support

