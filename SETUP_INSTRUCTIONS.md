# GHL Integration Setup Instructions

## Required Environment Variables

Before running the GHL integration, you **must** set the following in your `.env` file:

### Required Variables

```env
# GoHighLevel Configuration
GHL_LOCATION_ID=your-location-id-here
GHL_PIPELINE_ID=your-pipeline-id-here
GHL_PRIVATE_INTEGRATION_TOKEN=your-private-integration-token-here
```

### How to Find These Values

#### 1. GHL_LOCATION_ID
1. Log into your GoHighLevel account
2. Go to **Settings** → **Locations**
3. Click on your location
4. The Location ID is in the URL or in the location settings page

#### 2. GHL_PIPELINE_ID
1. In GoHighLevel, go to **Pipelines**
2. Click on the pipeline you want to use
3. The Pipeline ID is in the URL (format: `https://app.gohighlevel.com/pipeline/[PIPELINE_ID]`)
4. Or check the pipeline settings

#### 3. GHL_PRIVATE_INTEGRATION_TOKEN
1. In GoHighLevel, go to **Settings** → **Integrations**
2. Find or create a Private Integration
3. Copy the Private Integration Token

### Example .env File

```env
# NewBook API Configuration
NEWBOOK_API_BASE=https://api.newbook.com
API_KEY=your-api-key
REGION=your-region
NEWBOOK_USERNAME=your-username
NEWBOOK_PASSWORD=your-password

# GoHighLevel Configuration
GHL_LOCATION_ID=abc123xyz
GHL_PIPELINE_ID=def456uvw
GHL_PRIVATE_INTEGRATION_TOKEN=your-token-here

# Optional: Test Mode
GHL_TEST_MODE=false
GHL_DRY_RUN_MODE=false
```

## Verifying Configuration

After setting up your `.env` file, verify your configuration by checking the logs when the integration runs. Make sure:
1. The variable names are exactly as shown (case-sensitive)
2. There are no extra spaces around the `=` sign
3. The values don't have quotes (unless they contain spaces)

## Common Issues

### Error: "location_id can't be undefined"
- **Cause**: `GHL_LOCATION_ID` is not set or is empty in your `.env` file
- **Fix**: Add `GHL_LOCATION_ID=your-location-id` to your `.env` file

### Error: "pipeline_id can't be undefined"
- **Cause**: `GHL_PIPELINE_ID` is not set or is empty in your `.env` file
- **Fix**: Add `GHL_PIPELINE_ID=your-pipeline-id` to your `.env` file

### Error: "No valid access token"
- **Cause**: `GHL_PRIVATE_INTEGRATION_TOKEN` is not set or invalid
- **Fix**: Add `GHL_PRIVATE_INTEGRATION_TOKEN=your-token` to your `.env` file

## Next Steps

Once your configuration is verified:
1. Review the logs when the integration runs to ensure everything looks correct
2. Check GHL to verify opportunities are being created/updated correctly
3. Monitor for any errors in the logs

## How Opportunity Matching Works

The integration uses **exact name matching** to find existing opportunities:
- Format: `"{firstname} {lastname} - {site_name} - {arrival_date}"`
- Example: `"John Doe - Chalet 3 - 2026-01-13"`

This means:
- ✅ No custom fields required in GHL
- ✅ Works with existing opportunities
- ✅ Reliable matching based on guest name, site, and arrival date

