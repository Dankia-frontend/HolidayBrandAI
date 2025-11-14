from fastapi import Header, HTTPException
from config.config import AI_AGENT_KEY
from utils.newbook_db import get_newbook_instance


def authenticate_request(x_ai_agent_key: str = Header(None)):
    """
    Authentication helper that validates the AI agent key.
    Logic intentionally identical to the previous implementation.
    """
    if not x_ai_agent_key:
        raise HTTPException(status_code=401, detail="Missing AI_AGENT_KEY in headers")

    if x_ai_agent_key != AI_AGENT_KEY:
        raise HTTPException(status_code=401, detail="Invalid AI_AGENT_KEY")

    return x_ai_agent_key


def get_newbook_credentials(x_location_id: str = Header(..., alias="X-Location-ID")):
    """
    Dependency function that fetches Newbook API credentials from database based on location_id header.
    Returns: dict with 'api_key' and 'region' (if available)
    """
    if not x_location_id:
        raise HTTPException(status_code=400, detail="Missing X-Location-ID header")
    
    instance = get_newbook_instance(x_location_id)
    
    if not instance:
        raise HTTPException(
            status_code=404, 
            detail=f"Newbook instance not found for location_id: {x_location_id}"
        )
    
    if not instance.get("api_key"):
        raise HTTPException(
            status_code=500,
            detail=f"API key not configured for location_id: {x_location_id}"
        )
    
    return {
        "api_key": instance["api_key"],
        # "region": instance.get("region"),
        "location_id": x_location_id
    }


