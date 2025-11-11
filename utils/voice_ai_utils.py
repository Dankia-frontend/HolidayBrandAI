"""
Voice AI Configuration Management Utilities
Handles cloning and management of GHL Voice AI configurations across locations.
"""
import requests
from typing import Dict, Any, Optional, List
from config.config import GHL_API_KEY, GHL_CLIENT_ID, GHL_CLIENT_SECRET, GHL_AGENCY_API_KEY
from .logger import get_logger
from .ghl_api import get_valid_access_token

log = get_logger("VoiceAI")

GHL_API_BASE = "https://services.leadconnectorhq.com"
GHL_API_VERSION = "2021-07-28"


def get_ghl_headers(access_token: Optional[str] = None, use_agency_key: bool = True) -> Dict[str, str]:
    """
    Generate headers for GHL API requests.
    
    Args:
        access_token: Optional OAuth access token. If not provided, tries to get a valid one.
        use_agency_key: If True and available, use Agency API Key instead of OAuth
    
    Returns:
        dict: Headers for GHL API requests
    """
    # Priority 1: Use Agency API Key if available (has broader permissions)
    if use_agency_key and GHL_AGENCY_API_KEY:
        log.info("Using GHL Agency API Key for authentication")
        return {
            "Authorization": f"Bearer {GHL_AGENCY_API_KEY}",
            "Version": GHL_API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    # Priority 2: Use provided OAuth token
    if access_token:
        return {
            "Authorization": f"Bearer {access_token}",
            "Version": GHL_API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    # Priority 3: Try to get OAuth token
    access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
    if access_token:
        return {
            "Authorization": f"Bearer {access_token}",
            "Version": GHL_API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    # Fallback: Return headers without authorization (will likely fail)
    log.error("No valid authentication method available")
    return {
        "Version": GHL_API_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def get_conversation_ai_bots(location_id: str) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch all Conversation AI bots (assistants) for a location.
    Uses Agency API Key if available, otherwise OAuth token.
    
    Args:
        location_id: GHL location ID
    
    Returns:
        list: List of AI bot configurations or None if error
    """
    try:
        # Get headers - will automatically use Agency API Key if available
        headers = get_ghl_headers()
        
        # GHL API endpoint for conversation AI
        url = f"{GHL_API_BASE}/conversations/assistants"
        params = {"locationId": location_id}
        
        log.info(f"Fetching AI assistants for location {location_id}")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            bots = data.get("assistants", [])
            log.info(f"✅ Successfully found {len(bots)} AI assistants for location {location_id}")
            return bots
        elif response.status_code == 401:
            error_detail = response.text
            if GHL_AGENCY_API_KEY:
                log.error(f"❌ Authorization error with Agency API Key. Error: {error_detail}")
            else:
                log.error(f"❌ OAuth token missing required scopes. Please add 'conversations.readonly' or 'conversations.write' scope")
            return None
        else:
            log.error(f"❌ Failed to fetch AI bots: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        log.exception(f"❌ Error fetching AI bots for location {location_id}: {e}")
        return None


def get_assistant_details(assistant_id: str, location_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed configuration of a specific AI assistant.
    Uses Agency API Key if available, otherwise OAuth token.
    
    Args:
        assistant_id: Assistant ID
        location_id: GHL location ID
    
    Returns:
        dict: Assistant configuration or None if error
    """
    try:
        headers = get_ghl_headers()
        url = f"{GHL_API_BASE}/conversations/assistants/{assistant_id}"
        params = {"locationId": location_id}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            log.info(f"✅ Successfully fetched details for assistant {assistant_id}")
            return response.json().get("assistant", {})
        else:
            log.error(f"❌ Failed to fetch assistant {assistant_id}: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        log.exception(f"❌ Error fetching assistant {assistant_id}: {e}")
        return None


def create_assistant(location_id: str, assistant_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Create a new AI assistant in a location.
    Uses Agency API Key if available, otherwise OAuth token.
    
    Args:
        location_id: Target GHL location ID
        assistant_config: Assistant configuration data
    
    Returns:
        dict: Created assistant data or None if error
    """
    try:
        headers = get_ghl_headers()
        url = f"{GHL_API_BASE}/conversations/assistants"
        
        # Prepare payload - remove fields that shouldn't be copied
        payload = {
            "locationId": location_id,
            "name": assistant_config.get("name"),
            "type": assistant_config.get("type", "voice"),
            "prompt": assistant_config.get("prompt", ""),
            "voice": assistant_config.get("voice", {}),
            "model": assistant_config.get("model", "gpt-4"),
            "temperature": assistant_config.get("temperature", 0.7),
            "tools": assistant_config.get("tools", []),
            "knowledgeBase": assistant_config.get("knowledgeBase", []),
            "settings": assistant_config.get("settings", {}),
        }
        
        log.info(f"Creating assistant '{payload['name']}' in location {location_id}")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            log.info(f"✅ Successfully created assistant '{payload['name']}' in location {location_id}")
            return response.json().get("assistant", {})
        else:
            log.error(f"❌ Failed to create assistant: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        log.exception(f"❌ Error creating assistant in location {location_id}: {e}")
        return None


def get_workflows(location_id: str) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch all workflows for a location.
    Uses Agency API Key if available, otherwise OAuth token.
    
    Args:
        location_id: GHL location ID
    
    Returns:
        list: List of workflow configurations or None if error
    """
    try:
        headers = get_ghl_headers()
        url = f"{GHL_API_BASE}/workflows"
        params = {"locationId": location_id}
        
        log.info(f"Fetching workflows for location {location_id}")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            workflows = response.json().get("workflows", [])
            log.info(f"✅ Found {len(workflows)} workflows for location {location_id}")
            return workflows
        else:
            log.error(f"❌ Failed to fetch workflows: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        log.exception(f"❌ Error fetching workflows for location {location_id}: {e}")
        return None


def clone_voice_ai_configuration(
    source_location_id: str,
    target_location_id: str,
    clone_assistants: bool = True,
    clone_workflows: bool = True,
    clone_phone_numbers: bool = False
) -> Dict[str, Any]:
    """
    Clone Voice AI configuration from source location to target location.
    
    Args:
        source_location_id: Source GHL location ID to copy from
        target_location_id: Target GHL location ID to copy to
        clone_assistants: Whether to clone AI assistants
        clone_workflows: Whether to clone workflows
        clone_phone_numbers: Whether to clone phone number configurations
    
    Returns:
        dict: Result with success status, cloned items, and any errors
    """
    result = {
        "success": True,
        "source_location_id": source_location_id,
        "target_location_id": target_location_id,
        "cloned_assistants": [],
        "cloned_workflows": [],
        "cloned_phone_numbers": [],
        "errors": []
    }
    
    log.info(f"Starting Voice AI cloning from {source_location_id} to {target_location_id}")
    
    # Clone AI Assistants
    if clone_assistants:
        try:
            source_bots = get_conversation_ai_bots(source_location_id)
            
            if source_bots is None:
                result["success"] = False
                # if GHL_AGENCY_API_KEY:
                #     result["errors"].append(
                #         "❌ Authorization Error: Failed to access Voice AI with Agency API Key. "
                #         "Please verify your GHL_AGENCY_API_KEY has the correct permissions."
                #     )
                # else:
                #     result["errors"].append(
                #         "❌ OAuth Scope Error: Your GHL access token is missing required permissions. "
                #         "Please add 'conversations.readonly' or 'conversations.write' scope to your GHL OAuth app and re-authorize."
                #     )
                # result["success"] = False
            elif len(source_bots) == 0:
                result["errors"].append("No AI assistants found in source location")
            else:
                log.info(f"Cloning {len(source_bots)} AI assistants...")
                
                for bot in source_bots:
                    bot_id = bot.get("id")
                    bot_name = bot.get("name", "Unnamed")
                    
                    # Get detailed configuration
                    detailed_config = get_assistant_details(bot_id, source_location_id)
                    
                    if detailed_config:
                        # Clone with modified name to avoid conflicts
                        detailed_config["name"] = f"{bot_name} (Cloned)"
                        
                        created_bot = create_assistant(target_location_id, detailed_config)
                        
                        if created_bot:
                            result["cloned_assistants"].append({
                                "original_id": bot_id,
                                "original_name": bot_name,
                                "new_id": created_bot.get("id"),
                                "new_name": created_bot.get("name")
                            })
                        else:
                            result["errors"].append(f"Failed to clone assistant: {bot_name}")
                    else:
                        result["errors"].append(f"Failed to get details for assistant: {bot_name}")
        
        except Exception as e:
            log.exception(f"Error cloning assistants: {e}")
            result["errors"].append(f"Error cloning assistants: {str(e)}")
            result["success"] = False
    
    # Clone Workflows (if requested)
    if clone_workflows:
        try:
            source_workflows = get_workflows(source_location_id)
            
            if source_workflows:
                # Filter workflows that contain Voice AI actions
                voice_ai_workflows = [
                    w for w in source_workflows 
                    if "voice" in w.get("name", "").lower() or 
                       "ai" in w.get("name", "").lower() or
                       "call" in w.get("name", "").lower()
                ]
                
                if voice_ai_workflows:
                    log.info(f"Found {len(voice_ai_workflows)} Voice AI related workflows")
                    result["cloned_workflows"].append({
                        "note": "Workflow cloning requires manual export/import through GHL UI",
                        "count": len(voice_ai_workflows),
                        "workflows": [{"id": w.get("id"), "name": w.get("name")} for w in voice_ai_workflows]
                    })
                else:
                    result["errors"].append("No Voice AI related workflows found")
        
        except Exception as e:
            log.exception(f"Error checking workflows: {e}")
            result["errors"].append(f"Error checking workflows: {str(e)}")
    
    # Summary
    assistants_count = len(result["cloned_assistants"])
    errors_count = len(result["errors"])
    
    log.info(f"Voice AI cloning completed: {assistants_count} assistants cloned, {errors_count} errors")
    
    if errors_count > 0:
        result["success"] = False
    
    return result


def get_voice_ai_summary(location_id: str) -> Dict[str, Any]:
    """
    Get a summary of Voice AI configuration for a location.
    
    Args:
        location_id: GHL location ID
    
    Returns:
        dict: Summary of Voice AI setup
    """
    try:
        assistants = get_conversation_ai_bots(location_id)
        workflows = get_workflows(location_id)
        
        # Filter Voice AI related workflows
        voice_workflows = []
        if workflows:
            voice_workflows = [
                w for w in workflows 
                if "voice" in w.get("name", "").lower() or 
                   "ai" in w.get("name", "").lower() or
                   "call" in w.get("name", "").lower()
            ]
        
        return {
            "location_id": location_id,
            "assistants_count": len(assistants) if assistants else 0,
            "assistants": [
                {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "type": a.get("type"),
                    "status": a.get("status", "unknown")
                }
                for a in (assistants or [])
            ],
            "voice_workflows_count": len(voice_workflows),
            "voice_workflows": [
                {
                    "id": w.get("id"),
                    "name": w.get("name"),
                    "status": w.get("status", "unknown")
                }
                for w in voice_workflows
            ]
        }
    
    except Exception as e:
        log.exception(f"Error getting Voice AI summary for {location_id}: {e}")
        return {
            "location_id": location_id,
            "error": str(e),
            "assistants_count": 0,
            "voice_workflows_count": 0
        }

