import requests
import os

GHL_API_BASE = os.getenv("GHL_API_BASE", "https://services.leadconnectorhq.com")
GHL_ACCESS_TOKEN = os.getenv("GHL_ACCESS_TOKEN")
GHL_API_VERSION = os.getenv("GHL_API_VERSION", "2021-07-28")
GHL_PIPELINE_ID = os.getenv("GHL_PIPELINE_ID")
GHL_STAGE_ID = os.getenv("GHL_STAGE_ID")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID")
GHL_ASSIGNED_USER_ID = os.getenv("GHL_ASSIGNED_USER_ID")

def create_opportunity(contact_id, name, value):
    """Create a new opportunity in GHL."""
    url = f"{GHL_API_BASE}/opportunities/"
    headers = {
        "Authorization": f"Bearer {GHL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Version": GHL_API_VERSION,
    }

    payload = {
        "pipelineId": GHL_PIPELINE_ID,
        "pipelineStageId": GHL_STAGE_ID,
        "locationId": GHL_LOCATION_ID,
        "name": name,
        "status": "open",
        "contactId": contact_id,
        "monetaryValue": value,
        "assignedTo": GHL_ASSIGNED_USER_ID,
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        return {"success": True, "data": response.json()}
    else:
        return {"success": False, "error": response.text}
