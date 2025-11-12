# filepath: utils/voice_ai.py
import requests
import json
from typing import Dict, List, Optional
from utils.logger import get_logger
from utils.ghl_api import get_valid_access_token
from config.config import GHL_CLIENT_ID, GHL_CLIENT_SECRET, GHL_AGENCY_API_KEY

try:
    from utils.multi_location_tokens import get_valid_location_token
    MULTI_LOCATION_ENABLED = True
except ImportError:
    MULTI_LOCATION_ENABLED = False
    print("⚠️  Multi-location tokens not available. Run: python -c 'from utils.multi_location_tokens import create_multi_token_table; create_multi_token_table()'")

log = get_logger("VoiceAI")

VOICE_AI_BASE_URL = "https://services.leadconnectorhq.com/voice-ai"
GHL_API_VERSION = "2021-07-28"

# Set to True to use Agency API Key instead of OAuth token
# NOTE: Voice AI endpoints do NOT support Agency API Keys, only OAuth tokens
USE_AGENCY_API_KEY = False  # Must use OAuth tokens for Voice AI


def get_voice_ai_headers(access_token: str, location_id: str = None) -> Dict[str, str]:
    """
    Returns headers required for Voice AI API requests.
    
    Args:
        access_token: OAuth access token
        location_id: Optional location ID for location-scoped requests
    
    Returns:
        dict: Headers dictionary
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Version": GHL_API_VERSION
    }
    
    # Add location ID to headers if provided (for location-scoped tokens)
    if location_id:
        headers["locationId"] = location_id
    
    return headers


def list_voice_ai_agents(location_id: str, access_token: Optional[str] = None, use_agency_key: bool = None) -> Optional[List[Dict]]:
    """
    Lists all Voice AI agents for a given location.
    
    Args:
        location_id: The GHL location/sub-account ID
        access_token: Optional OAuth access token or Agency API Key. If not provided, will try multi-location tokens first.
        use_agency_key: Optional override to use Agency API Key (True) or OAuth token (False). Defaults to USE_AGENCY_API_KEY global setting.
    
    Returns:
        list: List of agent dictionaries, or None on error
    """
    # Determine which authentication method to use
    if use_agency_key is None:
        use_agency_key = USE_AGENCY_API_KEY
    
    if not access_token:
        # Try multi-location token first
        if MULTI_LOCATION_ENABLED:
            access_token = get_valid_location_token(location_id)
            if access_token:
                print(f"[Voice AI] Using location-specific token for {location_id}")
        
        # Fallback to Agency API Key or global OAuth token
        if not access_token:
            if use_agency_key and GHL_AGENCY_API_KEY:
                access_token = GHL_AGENCY_API_KEY
                print(f"[Voice AI] Using Agency API Key for authentication")
            else:
                access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
                print(f"[Voice AI] Using global OAuth token for authentication")
        
        if not access_token:
            log.error(f"No valid access token for location {location_id}")
            print(f"❌ Error: No token found for location {location_id}")
            print(f"💡 Authorize this location: python authorize_location.py")
            return None
    
    url = f"{VOICE_AI_BASE_URL}/agents"
    # Pass location_id to headers for location-scoped requests
    headers = get_voice_ai_headers(access_token, location_id)
    
    # Add location_id as query parameter
    params = {"locationId": location_id}
    
    try:
        log.info(f"Fetching Voice AI agents for location: {location_id}")
        print(f"[Voice AI] Fetching agents for location: {location_id}")
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            agents = result.get("agents", [])
            
            log.info(f"Found {len(agents)} Voice AI agent(s)")
            print(f"✅ Found {len(agents)} Voice AI agent(s):")
            
            for agent in agents:
                agent_id = agent.get("id")
                agent_name = agent.get("name", "N/A")
                print(f"   - {agent_name} (ID: {agent_id})")
            
            return agents
        else:
            error_msg = f"Failed to list Voice AI agents: {response.status_code} - {response.text}"
            log.error(error_msg)
            print(f"❌ {error_msg}")
            return None
            
    except Exception as e:
        error_msg = f"Exception while listing Voice AI agents: {str(e)}"
        log.exception(error_msg)
        print(f"❌ {error_msg}")
        return None


def get_voice_ai_agent(agent_id: str, location_id: str = None, access_token: Optional[str] = None, use_agency_key: bool = None) -> Optional[Dict]:
    """
    Gets details of a specific Voice AI agent by ID.
    
    Args:
        agent_id: The Voice AI agent ID
        location_id: The location ID where the agent exists (required for Voice AI API)
        access_token: Optional OAuth access token. If not provided, will fetch from DB.
        use_agency_key: Optional override to use Agency API Key (True) or OAuth token (False).
    
    Returns:
        dict: Agent details, or None on error
    """
    if use_agency_key is None:
        use_agency_key = USE_AGENCY_API_KEY
    
    if not access_token:
        if use_agency_key and GHL_AGENCY_API_KEY:
            access_token = GHL_AGENCY_API_KEY
        else:
            access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
        
        if not access_token:
            log.error("No valid access token or API key available")
            print("❌ Error: No valid access token or API key")
            return None
    
    if not location_id:
        log.error("location_id is required for getting Voice AI agent")
        print("❌ Error: location_id is required")
        return None
    
    url = f"{VOICE_AI_BASE_URL}/agents/{agent_id}"
    headers = get_voice_ai_headers(access_token, location_id)
    
    # Add location_id as query parameter if provided
    params = {}
    if location_id:
        params["locationId"] = location_id
    
    try:
        log.info(f"Fetching Voice AI agent: {agent_id}")
        print(f"[Voice AI] Fetching agent: {agent_id} from location: {location_id or 'unknown'}")
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            agent = response.json()
            agent_name = agent.get("name", "N/A")
            
            log.info(f"Agent found: {agent_name}")
            print(f"✅ Agent found: {agent_name}")
            print(f"   Full response: {json.dumps(agent, indent=2)}")
            
            return agent
        else:
            error_msg = f"Failed to get Voice AI agent: {response.status_code} - {response.text}"
            log.error(error_msg)
            print(f"❌ {error_msg}")
            return None
            
    except Exception as e:
        error_msg = f"Exception while getting Voice AI agent: {str(e)}"
        log.exception(error_msg)
        print(f"❌ {error_msg}")
        return None


def create_voice_ai_agent(location_id: str, agent_config: Dict, access_token: Optional[str] = None, use_agency_key: bool = None, include_actions: bool = False) -> Optional[Dict]:
    """
    Creates a new Voice AI agent in the specified location.
    
    Args:
        location_id: The target GHL location/sub-account ID
        agent_config: Dictionary containing agent configuration
        access_token: Optional OAuth access token. If not provided, will fetch from DB.
        use_agency_key: Optional override to use Agency API Key (True) or OAuth token (False).
        include_actions: If True, allows actions to be included in the create request (for copying custom actions)
    
    Returns:
        dict: Created agent details, or None on error
    """
    if use_agency_key is None:
        use_agency_key = USE_AGENCY_API_KEY
    
    if not access_token:
        if use_agency_key and GHL_AGENCY_API_KEY:
            access_token = GHL_AGENCY_API_KEY
        else:
            access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
        
        if not access_token:
            log.error("No valid access token or API key available")
            print("❌ Error: No valid access token or API key")
            return None
    
    url = f"{VOICE_AI_BASE_URL}/agents"
    headers = get_voice_ai_headers(access_token, location_id)
    
    # Create a clean payload - remove fields that shouldn't be in the request
    # The API rejects: traceId, name, actions (and possibly others) during creation
    # But locationId IS required in the body
    # inboundNumber must be removed - phone numbers are location-specific
    # Actions CANNOT be included in create - they must be created separately via Actions API
    fields_to_remove = [
        "traceId", "id", "inboundNumber", "name", "actions",  # name and actions are rejected by API in create
        "createdAt", "updatedAt", "createdBy", "updatedBy", "_id"
    ]
    
    # Note: include_actions parameter is kept for backward compatibility but actions are always removed
    # Actions must be created separately using create_voice_ai_action()
    
    clean_config = {k: v for k, v in agent_config.items() if k not in fields_to_remove}
    
    # locationId is REQUIRED in the body (API error says "LocationId is missing in body")
    clean_config["locationId"] = location_id
    
    # Also add locationId as query parameter (some APIs require both)
    params = {"locationId": location_id}
    
    try:
        log.info(f"Creating Voice AI agent in location: {location_id}")
        agent_name = agent_config.get('name', 'N/A')
        print(f"[Voice AI] Creating agent: {agent_name}")
        print(f"[Voice AI] Payload fields: {list(clean_config.keys())}")
        # Note: Actions are never included in create - they must be created separately via Actions API
        
        response = requests.post(url, headers=headers, params=params, json=clean_config, timeout=30)
        
        if response.status_code in [200, 201]:
            result = response.json()
            agent_id = result.get("id")
            agent_name = result.get("name", "N/A")
            
            log.info(f"Successfully created Voice AI agent: {agent_name} (ID: {agent_id})")
            print(f"✅ Successfully created Voice AI agent: {agent_name}")
            print(f"   Agent ID: {agent_id}")
            print(f"   Full response: {json.dumps(result, indent=2)}")
            
            return result
        else:
            error_msg = f"Failed to create Voice AI agent: {response.status_code} - {response.text}"
            log.error(error_msg)
            print(f"❌ {error_msg}")
            return None
            
    except Exception as e:
        error_msg = f"Exception while creating Voice AI agent: {str(e)}"
        log.exception(error_msg)
        print(f"❌ {error_msg}")
        return None


def delete_voice_ai_agent(agent_id: str, access_token: Optional[str] = None, use_agency_key: bool = None) -> bool:
    """
    Deletes a Voice AI agent by ID.
    
    Args:
        agent_id: The Voice AI agent ID to delete
        access_token: Optional OAuth access token or Agency API Key. If not provided, will fetch based on USE_AGENCY_API_KEY setting.
        use_agency_key: Optional override to use Agency API Key (True) or OAuth token (False).
    
    Returns:
        bool: True if successful, False otherwise
    """
    if use_agency_key is None:
        use_agency_key = USE_AGENCY_API_KEY
    
    if not access_token:
        if use_agency_key and GHL_AGENCY_API_KEY:
            access_token = GHL_AGENCY_API_KEY
        else:
            access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
        
        if not access_token:
            log.error("No valid access token or API key available")
            print("❌ Error: No valid access token or API key")
            return False
    
    url = f"{VOICE_AI_BASE_URL}/agents/{agent_id}"
    headers = get_voice_ai_headers(access_token)
    
    try:
        log.info(f"Deleting Voice AI agent: {agent_id}")
        print(f"[Voice AI] Deleting agent: {agent_id}")
        
        response = requests.delete(url, headers=headers, timeout=30)
        
        if response.status_code in [200, 204]:
            log.info(f"Successfully deleted Voice AI agent: {agent_id}")
            print(f"✅ Successfully deleted Voice AI agent: {agent_id}")
            return True
        else:
            error_msg = f"Failed to delete Voice AI agent: {response.status_code} - {response.text}"
            log.error(error_msg)
            print(f"❌ {error_msg}")
            return False
            
    except Exception as e:
        error_msg = f"Exception while deleting Voice AI agent: {str(e)}"
        log.exception(error_msg)
        print(f"❌ {error_msg}")
        return False


def create_voice_ai_action(agent_id: str, location_id: str, action_config: Dict, access_token: Optional[str] = None, use_agency_key: bool = None) -> Optional[Dict]:
    """
    Creates a custom action for a Voice AI agent using the Actions API.
    
    Args:
        agent_id: The Voice AI agent ID to add the action to
        location_id: The location ID where the agent exists (required for Voice AI API)
        action_config: Dictionary containing action configuration
        access_token: Optional OAuth access token. If not provided, will fetch from DB.
        use_agency_key: Optional override to use Agency API Key (True) or OAuth token (False).
    
    Returns:
        dict: Created action details, or None on error
    """
    if use_agency_key is None:
        use_agency_key = USE_AGENCY_API_KEY
    
    if not access_token:
        # Try multi-location token first
        if MULTI_LOCATION_ENABLED:
            access_token = get_valid_location_token(location_id)
            if access_token:
                print(f"[Voice AI Actions] Using location-specific token for {location_id}")
        
        # Fallback to Agency API Key or global OAuth token
        if not access_token:
            if use_agency_key and GHL_AGENCY_API_KEY:
                access_token = GHL_AGENCY_API_KEY
            else:
                access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
        
        if not access_token:
            log.error(f"No valid access token for location {location_id}")
            print(f"❌ Error: No token found for location {location_id}")
            return None
    
    url = f"{VOICE_AI_BASE_URL}/actions"
    headers = get_voice_ai_headers(access_token, location_id)
    
    # Prepare action payload - include agentId and locationId
    action_payload = action_config.copy()
    action_payload["agentId"] = agent_id
    action_payload["locationId"] = location_id
    
    # Remove fields that shouldn't be in the request
    fields_to_remove = [
        "id", "_id", "traceId",
        "createdAt", "updatedAt", "createdBy", "updatedBy"
    ]
    
    clean_payload = {k: v for k, v in action_payload.items() if k not in fields_to_remove}
    
    # Add locationId as query parameter
    params = {"locationId": location_id}
    
    try:
        log.info(f"Creating Voice AI action for agent: {agent_id}")
        action_name = action_config.get("name", action_config.get("actionName", "N/A"))
        print(f"[Voice AI Actions] Creating action: {action_name} for agent: {agent_id}")
        
        response = requests.post(url, headers=headers, params=params, json=clean_payload, timeout=30)
        
        if response.status_code in [200, 201]:
            result = response.json()
            action_id = result.get("id")
            
            log.info(f"Successfully created Voice AI action: {action_name} (ID: {action_id})")
            print(f"✅ Successfully created action: {action_name}")
            
            return result
        else:
            error_msg = f"Failed to create Voice AI action: {response.status_code} - {response.text}"
            log.error(error_msg)
            print(f"❌ {error_msg}")
            return None
            
    except Exception as e:
        error_msg = f"Exception while creating Voice AI action: {str(e)}"
        log.exception(error_msg)
        print(f"❌ {error_msg}")
        return None


def update_voice_ai_agent(agent_id: str, location_id: str = None, agent_config: Dict = None, access_token: Optional[str] = None, use_agency_key: bool = None, include_actions: bool = False) -> Optional[Dict]:
    """
    Updates an existing Voice AI agent (PATCH).
    
    Args:
        agent_id: The Voice AI agent ID to update
        location_id: The location ID where the agent exists (required for Voice AI API)
        agent_config: Dictionary containing agent configuration updates
        access_token: Optional OAuth access token or Agency API Key. If not provided, will fetch based on USE_AGENCY_API_KEY setting.
        use_agency_key: Optional override to use Agency API Key (True) or OAuth token (False).
        include_actions: If True, allows actions to be included in the update (for copying custom actions)
    
    Returns:
        dict: Updated agent details, or None on error
    """
    if agent_config is None:
        agent_config = {}
    
    if use_agency_key is None:
        use_agency_key = USE_AGENCY_API_KEY
    
    if not access_token:
        if use_agency_key and GHL_AGENCY_API_KEY:
            access_token = GHL_AGENCY_API_KEY
        else:
            access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
        
        if not access_token:
            log.error("No valid access token or API key available")
            print("❌ Error: No valid access token or API key")
            return None
    
    url = f"{VOICE_AI_BASE_URL}/agents/{agent_id}"
    headers = get_voice_ai_headers(access_token, location_id)
    
    # Clean the config - remove fields that shouldn't be in update request
    # Allow actions if include_actions is True (for copying custom actions)
    fields_to_remove = [
        "traceId", "id", "locationId", 
        "createdAt", "updatedAt", "createdBy", "updatedBy", "_id"
    ]
    
    if not include_actions:
        fields_to_remove.append("actions")
    
    clean_config = {k: v for k, v in agent_config.items() if k not in fields_to_remove}
    
    # Add locationId as query parameter if provided
    params = {}
    if location_id:
        params["locationId"] = location_id
    
    try:
        log.info(f"Updating Voice AI agent: {agent_id} in location: {location_id}")
        print(f"[Voice AI] Updating agent: {agent_id}")
        
        response = requests.patch(url, headers=headers, params=params, json=clean_config, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            agent_name = result.get("name", "N/A")
            
            log.info(f"Successfully updated Voice AI agent: {agent_name}")
            print(f"✅ Successfully updated Voice AI agent: {agent_name}")
            print(f"   Full response: {json.dumps(result, indent=2)}")
            
            return result
        else:
            error_msg = f"Failed to update Voice AI agent: {response.status_code} - {response.text}"
            log.error(error_msg)
            print(f"❌ {error_msg}")
            return None
            
    except Exception as e:
        error_msg = f"Exception while updating Voice AI agent: {str(e)}"
        log.exception(error_msg)
        print(f"❌ {error_msg}")
        return None


def copy_voice_ai_agent(
    source_agent_id: str,
    source_location_id: str,
    target_location_id: str,
    new_agent_name: Optional[str] = None,
    access_token: Optional[str] = None,
    use_agency_key: bool = None
) -> Optional[Dict]:
    """
    Copies a Voice AI agent from one location to another.
    
    This function:
    1. Fetches the source agent configuration
    2. Removes location-specific fields (id, locationId, etc.)
    3. Creates a new agent in the target location with the same configuration
    
    Args:
        source_agent_id: The ID of the agent to copy
        source_location_id: The source location/sub-account ID where the agent currently exists
        target_location_id: The destination location/sub-account ID
        new_agent_name: Optional new name for the copied agent. If not provided, uses original name with " (Copy)" suffix
        access_token: Optional OAuth access token. If not provided, will fetch from DB.
        use_agency_key: Optional override to use Agency API Key (True) or OAuth token (False).
    
    Returns:
        dict: Created agent details in target location, or None on error
    """
    if use_agency_key is None:
        use_agency_key = USE_AGENCY_API_KEY
    
    # Get tokens for source and target locations
    # Source: Use main tokens table (company-scoped token)
    # Target: Use location_tokens table (location-scoped token)
    
    source_token = None
    target_token = None
    
    if not access_token:
        # Get source token from main tokens table (company-scoped)
        source_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
        if source_token:
            print(f"[Voice AI Copy] ✅ Using company-scoped token for SOURCE location ({source_location_id})")
        else:
            log.error(f"No valid access token for SOURCE location {source_location_id}")
            print(f"❌ Error: No token found for SOURCE location {source_location_id}")
            print(f"💡 Run: python reauthorize_oauth.py")
            return None
        
        # Get target token from location_tokens table (location-scoped)
        if MULTI_LOCATION_ENABLED:
            target_token = get_valid_location_token(target_location_id)
            if target_token:
                print(f"[Voice AI Copy] ✅ Using location-specific token for TARGET ({target_location_id})")
            else:
                log.error(f"No valid access token for TARGET location {target_location_id}")
                print(f"❌ Error: No token found for TARGET location {target_location_id}")
                print(f"💡 Authorize this location: python authorize_location.py {target_location_id}")
                return None
        else:
            log.error("Multi-location tokens not enabled")
            print(f"❌ Error: Multi-location tokens not available")
            print(f"💡 Run: python -c 'from utils.multi_location_tokens import create_multi_token_table; create_multi_token_table()'")
            return None
    else:
        # Manual token provided - use for source, but still need target token
        source_token = access_token
        if MULTI_LOCATION_ENABLED:
            target_token = get_valid_location_token(target_location_id)
            if not target_token:
                log.error(f"No valid access token for TARGET location {target_location_id}")
                print(f"❌ Error: No token found for TARGET location {target_location_id}")
                print(f"💡 Authorize this location: python authorize_location.py {target_location_id}")
                return None
        else:
            log.error("Multi-location tokens not enabled")
            print(f"❌ Error: Multi-location tokens not available")
            return None
    
    # Step 1: Get source agent configuration
    log.info(f"Step 1: Fetching source agent: {source_agent_id} from location: {source_location_id}")
    print(f"\n[Voice AI Copy] Step 1: Fetching source agent...")
    print(f"   Source Location ID: {source_location_id}")
    
    source_agent = get_voice_ai_agent(source_agent_id, source_location_id, source_token, use_agency_key)
    if not source_agent:
        log.error("Failed to fetch source agent")
        print("❌ Failed to fetch source agent")
        return None
    
    source_agent_name = source_agent.get("name", "Unknown Agent")
    print(f"✅ Source agent found: {source_agent_name}")
    
    # Step 2: Prepare agent configuration for target location
    log.info(f"Step 2: Preparing configuration for target location: {target_location_id}")
    print(f"\n[Voice AI Copy] Step 2: Preparing configuration...")
    
    # Check for actions - they need to be created separately via Actions API
    source_actions = source_agent.get("actions")
    has_actions = source_actions is not None and (
        (isinstance(source_actions, list) and len(source_actions) > 0) or 
        (not isinstance(source_actions, list) and source_actions)
    )
    
    if has_actions:
        actions_count = len(source_actions) if isinstance(source_actions, list) else 1
        print(f"   Found {actions_count} custom action(s) to create via Actions API")
    else:
        print(f"   No custom actions found in source agent")
    
    # Remove fields that shouldn't be copied or sent to create endpoint
    # Actions must be created separately via Actions API, not in agent create
    fields_to_remove = [
        "id",
        "locationId", 
        "createdAt",
        "updatedAt",
        "createdBy",
        "updatedBy",
        "_id",
        "actions",      # Must be created separately via Actions API
        "traceId",      # Response-only field
        "name",         # Will be set separately if needed (API may reject it in create)
        "inboundNumber" # Phone numbers are location-specific, must be assigned manually in target location
    ]
    
    agent_config = {k: v for k, v in source_agent.items() if k not in fields_to_remove}
    
    # Store the name separately - we'll try to set it after creation if needed
    new_name = new_agent_name if new_agent_name else f"{source_agent_name} (Copy)"
    
    print(f"   New agent name: {new_name}")
    print(f"   Configuration prepared with {len(agent_config)} fields")
    print(f"   Removed fields: {', '.join(fields_to_remove)}")
    
    # Step 3: Create agent in target location (without actions)
    log.info(f"Step 3: Creating agent in target location")
    print(f"\n[Voice AI Copy] Step 3: Creating agent in target location...")
    
    # Do NOT include actions in create request - they must be created separately
    result = create_voice_ai_agent(
        target_location_id, 
        agent_config, 
        target_token, 
        use_agency_key,
        include_actions=False  # Actions cannot be included in create
    )
    
    if not result:
        print(f"\n❌ Failed to create agent in target location")
        log.error(f"Failed to create agent in target location {target_location_id}")
        return None
    
    new_agent_id = result.get("id")
    print(f"✅ Agent created successfully: {new_agent_id}")
    
    # Step 4: Update agent name if needed
    log.info(f"Step 4: Updating agent name if needed")
    print(f"\n[Voice AI Copy] Step 4: Updating agent name if needed...")
    
    current_name = result.get("name", "")
    if new_name and current_name != new_name:
        print(f"   Attempting to update agent name from '{current_name}' to '{new_name}'")
        try:
            update_config = {"name": new_name}
            updated = update_voice_ai_agent(
                new_agent_id,
                target_location_id,
                update_config,
                target_token,
                use_agency_key,
                include_actions=False
            )
            if updated:
                result["name"] = new_name
                print(f"✅ Agent name updated to: {new_name}")
            else:
                print(f"⚠️  Could not update agent name. Agent created with name: {current_name}")
        except Exception as e:
            print(f"⚠️  Could not update agent name: {str(e)}. Agent created with name: {current_name}")
            log.warning(f"Error updating agent name: {str(e)}")
    else:
        print(f"   Agent name is correct: {current_name}")
    
    # Step 5: Create custom actions via Actions API
    if has_actions:
        log.info(f"Step 5: Creating custom actions via Actions API")
        print(f"\n[Voice AI Copy] Step 5: Creating custom actions via Actions API...")
        
        # Ensure source_actions is a list
        actions_list = source_actions if isinstance(source_actions, list) else [source_actions]
        
        created_actions = 0
        failed_actions = 0
        
        for idx, action in enumerate(actions_list, 1):
            action_name = action.get("name") or action.get("actionName") or f"Action {idx}"
            print(f"   [{idx}/{len(actions_list)}] Creating action: {action_name}")
            
            try:
                created_action = create_voice_ai_action(
                    agent_id=new_agent_id,
                    location_id=target_location_id,
                    action_config=action,
                    access_token=target_token,
                    use_agency_key=use_agency_key
                )
                
                if created_action:
                    created_actions += 1
                    print(f"      ✅ Action '{action_name}' created successfully")
                else:
                    failed_actions += 1
                    print(f"      ❌ Failed to create action '{action_name}'")
                    log.warning(f"Failed to create action '{action_name}' for agent {new_agent_id}")
            except Exception as e:
                failed_actions += 1
                error_msg = f"Exception creating action '{action_name}': {str(e)}"
                print(f"      ❌ {error_msg}")
                log.exception(error_msg)
        
        print(f"\n   Actions Summary: {created_actions} created, {failed_actions} failed")
        if created_actions == len(actions_list):
            print(f"✅ All {created_actions} custom action(s) copied successfully")
        elif created_actions > 0:
            print(f"⚠️  Partially successful: {created_actions}/{len(actions_list)} actions copied")
        else:
            print(f"❌ Failed to copy any actions")
            log.error(f"Failed to copy any actions for agent {new_agent_id}")
    else:
        print(f"\n[Voice AI Copy] Step 5: No actions to copy")
    
    if result:
        print(f"\n✅ Successfully copied Voice AI agent!")
        print(f"   Source: {source_agent_name} ({source_agent_id})")
        print(f"   Target: {result.get('name')} ({result.get('id')})")
        print(f"   Target Location: {target_location_id}")
        log.info(f"Successfully copied agent {source_agent_id} to location {target_location_id}")
    else:
        print(f"\n❌ Failed to copy Voice AI agent")
        log.error(f"Failed to copy agent {source_agent_id} to location {target_location_id}")
    
    return result


def copy_all_voice_ai_agents(
    source_location_id: str,
    target_location_id: str,
    name_suffix: Optional[str] = " (Copy)",
    access_token: Optional[str] = None,
    use_agency_key: bool = None
) -> Dict[str, any]:
    """
    Copies all Voice AI agents from one location to another.
    
    Args:
        source_location_id: The source location/sub-account ID
        target_location_id: The destination location/sub-account ID
        name_suffix: Suffix to add to copied agent names (default: " (Copy)")
        access_token: Optional OAuth access token. If not provided, will fetch from DB.
    
    Returns:
        dict: Summary of copy operation with success/failure counts and details
    """
    if use_agency_key is None:
        use_agency_key = USE_AGENCY_API_KEY
    
    # Get tokens for source and target locations
    # Source: Use main tokens table (company-scoped token)
    # Target: Use location_tokens table (location-scoped token)
    
    source_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
    if not source_token:
        log.error("No valid access token for source location")
        print("❌ Error: No valid access token for source location")
        print("💡 Run: python reauthorize_oauth.py")
        return {"success": False, "error": "No valid access token for source location"}
    
    print(f"[Voice AI Bulk Copy] ✅ Using company-scoped token for SOURCE location ({source_location_id})")
    
    # Get target token from location_tokens table
    if MULTI_LOCATION_ENABLED:
        target_token = get_valid_location_token(target_location_id)
        if not target_token:
            log.error(f"No valid access token for TARGET location {target_location_id}")
            print(f"❌ Error: No token found for TARGET location {target_location_id}")
            print(f"💡 Authorize this location: python authorize_location.py {target_location_id}")
            return {"success": False, "error": f"No valid access token for target location {target_location_id}"}
        print(f"[Voice AI Bulk Copy] ✅ Using location-specific token for TARGET ({target_location_id})")
    else:
        log.error("Multi-location tokens not enabled")
        print(f"❌ Error: Multi-location tokens not available")
        return {"success": False, "error": "Multi-location tokens not available"}
    
    print(f"\n[Voice AI Bulk Copy] Starting bulk copy operation...")
    print(f"   Source Location: {source_location_id}")
    print(f"   Target Location: {target_location_id}")
    
    # Fetch all agents from source location using source token
    source_agents = list_voice_ai_agents(source_location_id, source_token, use_agency_key)
    
    if source_agents is None:
        return {
            "success": False,
            "error": "Failed to fetch agents from source location"
        }
    
    if len(source_agents) == 0:
        print("\n⚠️  No agents found in source location")
        return {
            "success": True,
            "total_agents": 0,
            "copied": 0,
            "failed": 0,
            "details": []
        }
    
    print(f"\n[Voice AI Bulk Copy] Found {len(source_agents)} agent(s) to copy\n")
    
    results = {
        "success": True,
        "total_agents": len(source_agents),
        "copied": 0,
        "failed": 0,
        "details": []
    }
    
    # Copy each agent
    for idx, agent in enumerate(source_agents, 1):
        agent_id = agent.get("id")
        agent_name = agent.get("name", "Unknown")
        
        print(f"\n[{idx}/{len(source_agents)}] Copying: {agent_name}")
        
        new_name = f"{agent_name}{name_suffix}"
        # Pass None for access_token so copy_voice_ai_agent uses the correct tokens internally
        copied_agent = copy_voice_ai_agent(
            source_agent_id=agent_id,
            source_location_id=source_location_id,
            target_location_id=target_location_id,
            new_agent_name=new_name,
            access_token=None,  # Let function get tokens automatically
            use_agency_key=use_agency_key
        )
        
        if copied_agent:
            results["copied"] += 1
            results["details"].append({
                "source_id": agent_id,
                "source_name": agent_name,
                "target_id": copied_agent.get("id"),
                "target_name": copied_agent.get("name"),
                "status": "success"
            })
        else:
            results["failed"] += 1
            results["details"].append({
                "source_id": agent_id,
                "source_name": agent_name,
                "status": "failed"
            })
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"[Voice AI Bulk Copy] Summary:")
    print(f"   Total Agents: {results['total_agents']}")
    print(f"   Successfully Copied: {results['copied']}")
    print(f"   Failed: {results['failed']}")
    print(f"{'='*60}\n")
    
    log.info(f"Bulk copy completed: {results['copied']}/{results['total_agents']} agents copied")
    
    return results

