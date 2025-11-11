"""
Voice AI Agents Management Utilities
Handles cloning and management of GHL Voice AI Agents across locations.
This uses the Voice AI Agents API (different from Conversation AI Assistants).
"""
import requests
from typing import Dict, Any, Optional, List
from config.config import GHL_API_KEY, GHL_CLIENT_ID, GHL_CLIENT_SECRET, GHL_AGENCY_API_KEY
from .logger import get_logger
from .ghl_api import get_valid_access_token

log = get_logger("VoiceAIAgents")

GHL_API_BASE = "https://services.leadconnectorhq.com"
GHL_API_VERSION = "2021-07-28"


def get_ghl_headers(access_token: Optional[str] = None, use_agency_key: bool = True) -> Dict[str, str]:
    """
    Generate headers for GHL API requests.
    Voice AI Agents API requires proper authentication with specific scopes.
    
    Authentication Priority:
    1. Provided OAuth/Private Integration token
    2. OAuth token from database (auto-generated and refreshed)
    3. GHL_AGENCY_API_KEY (Private Integration key as fallback)
    
    Args:
        access_token: Optional OAuth/Private Integration token
        use_agency_key: If True, tries Agency API Key as fallback
    
    Returns:
        dict: Headers for GHL API requests
        
    Required Scopes:
        - voiceai.agents.read
        - voiceai.agents.write
        - locations.readonly (optional but recommended)
    """
    # Priority 1: Use provided OAuth/Private Integration token
    if access_token:
        log.info("✅ Using provided access token for Voice AI Agents")
        return {
            "Authorization": f"Bearer {access_token}",
            "Version": GHL_API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    # Priority 2: Try OAuth token from database (PREFERRED - auto-refreshes)
    db_access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
    if db_access_token:
        log.info("✅ Using OAuth access token from database for Voice AI Agents")
        return {
            "Authorization": f"Bearer {db_access_token}",
            "Version": GHL_API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    # Priority 3: Try Agency API Key / Private Integration Key (FALLBACK)
    if use_agency_key and GHL_AGENCY_API_KEY:
        log.info("⚠️ Using GHL Agency/Private Integration API Key for Voice AI Agents (fallback)")
        return {
            "Authorization": f"Bearer {GHL_AGENCY_API_KEY}",
            "Version": GHL_API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    # Fallback: Return headers without authorization (will fail)
    log.error("❌ No valid authentication method available for Voice AI Agents")
    log.error("")
    log.error("📋 SOLUTION:")
    log.error("Option 1 (Recommended): Set up OAuth with correct scopes")
    log.error("  - Add scopes: voiceai.agents.read, voiceai.agents.write")
    log.error("  - Re-authorize your app to get tokens with these scopes")
    log.error("")
    log.error("Option 2: Create a Private Integration in GHL")
    log.error("  - Go to GHL Settings → Integrations → Create Integration")
    log.error("  - Select scopes: voiceai.agents.read, voiceai.agents.write")
    log.error("  - Add the key to your .env as GHL_AGENCY_API_KEY")
    log.error("")
    log.error("📖 See: VOICE_AI_AGENTS_CORRECT_SCOPES.md")
    return {
        "Version": GHL_API_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def list_voice_ai_agents(location_id: str, limit: int = 100, offset: int = 0) -> Optional[Dict[str, Any]]:
    """
    Retrieve a paginated list of Voice AI agents for a given location.
    
    Args:
        location_id: GHL location ID
        limit: Number of agents to retrieve (default: 100)
        offset: Pagination offset (default: 0)
    
    Returns:
        dict: Response containing agents list and metadata, or None if error
        
    API Documentation: https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents/list-agents
    """
    try:
        headers = get_ghl_headers()
        url = f"{GHL_API_BASE}/voice-ai/agents"
        params = {
            "locationId": location_id,
            "limit": limit,
            "offset": offset
        }
        
        log.info(f"Fetching Voice AI agents for location {location_id} (limit: {limit}, offset: {offset})")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", [])
            log.info(f"✅ Successfully found {len(agents)} Voice AI agents for location {location_id}")
            return data
        elif response.status_code == 401:
            error_detail = response.text
            log.error(f"❌ Authorization error: {error_detail}")
            log.error("=" * 80)
            log.error("🔐 AUTHENTICATION REQUIRED:")
            log.error("The Voice AI Agents API requires authentication with specific scopes.")
            log.error("")
            log.error("📋 YOUR OAUTH TOKEN IS MISSING REQUIRED SCOPES")
            log.error("")
            log.error("🔧 HOW TO FIX:")
            log.error("1. Go to GHL Marketplace → My Apps → Your OAuth App")
            log.error("2. Edit your OAuth app settings")
            log.error("3. In the 'Scopes' section, add these scopes:")
            log.error("   ✅ voiceai.agents.read")
            log.error("   ✅ voiceai.agents.write")
            log.error("   ✅ locations.readonly (optional)")
            log.error("4. Save the changes")
            log.error("5. Re-authorize your application:")
            log.error("   - Delete old tokens: DELETE FROM tokens WHERE id = 1;")
            log.error("   - Run: python test_ghl_auth.py")
            log.error("   - Complete the OAuth authorization flow")
            log.error("6. Restart your backend server")
            log.error("")
            log.error("📖 See: VOICE_AI_AGENTS_CORRECT_SCOPES.md")
            log.error("=" * 80)
            return None
        elif response.status_code == 404:
            log.warning(f"⚠️ No Voice AI agents found for location {location_id}")
            return {"agents": [], "total": 0}
        else:
            log.error(f"❌ Failed to fetch Voice AI agents: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        log.exception(f"❌ Error fetching Voice AI agents for location {location_id}: {e}")
        return None


def get_voice_ai_agent(agent_id: str, location_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve detailed configuration and settings for a specific Voice AI agent.
    
    Args:
        agent_id: Voice AI agent ID
        location_id: GHL location ID
    
    Returns:
        dict: Agent configuration or None if error
        
    API Documentation: https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents/get-agent
    """
    try:
        headers = get_ghl_headers()
        url = f"{GHL_API_BASE}/voice-ai/agents/{agent_id}"
        params = {"locationId": location_id}
        
        log.info(f"Fetching Voice AI agent details: {agent_id} from location {location_id}")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            log.info(f"✅ Successfully fetched details for Voice AI agent {agent_id}")
            return data.get("agent", {})
        elif response.status_code == 404:
            log.error(f"❌ Voice AI agent {agent_id} not found in location {location_id}")
            return None
        else:
            log.error(f"❌ Failed to fetch Voice AI agent {agent_id}: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        log.exception(f"❌ Error fetching Voice AI agent {agent_id}: {e}")
        return None


def create_voice_ai_agent(location_id: str, agent_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Create a new Voice AI agent in a location.
    
    Args:
        location_id: Target GHL location ID
        agent_config: Agent configuration data
    
    Returns:
        dict: Created agent data or None if error
        
    API Documentation: https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents/create-agent
    """
    try:
        headers = get_ghl_headers()
        url = f"{GHL_API_BASE}/voice-ai/agents"
        
        # Prepare payload - remove fields that shouldn't be copied
        payload = {
            "locationId": location_id,
            "name": agent_config.get("name", "Cloned Voice AI Agent"),
        }
        
        # Copy all relevant configuration fields
        copyable_fields = [
            "prompt", "systemPrompt", "firstMessage", "voiceId", "provider",
            "language", "model", "temperature", "maxTokens", "endCallAfterSilence",
            "endCallAfterSilenceDuration", "enableBackchannel", "backchannelWords",
            "enableVoicemailDetection", "voicemailMessage", "endCallOnGoodbye",
            "callRecording", "endCallPhrases", "interruptionThreshold",
            "keywords", "webhookUrl", "enableTranscription", "actions",
            "tools", "settings", "silenceTimeout", "responseDelay", "boostedKeywords"
        ]
        
        for field in copyable_fields:
            if field in agent_config:
                payload[field] = agent_config[field]
        
        log.info(f"Creating Voice AI agent '{payload['name']}' in location {location_id}")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            data = response.json()
            created_agent = data.get("agent", {})
            log.info(f"✅ Successfully created Voice AI agent '{payload['name']}' in location {location_id}")
            return created_agent
        else:
            log.error(f"❌ Failed to create Voice AI agent: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        log.exception(f"❌ Error creating Voice AI agent in location {location_id}: {e}")
        return None


def patch_voice_ai_agent(agent_id: str, location_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Partially update an existing Voice AI agent.
    
    Args:
        agent_id: Voice AI agent ID to update
        location_id: GHL location ID
        updates: Dictionary of fields to update
    
    Returns:
        dict: Updated agent data or None if error
        
    API Documentation: https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents/patch-agent
    """
    try:
        headers = get_ghl_headers()
        url = f"{GHL_API_BASE}/voice-ai/agents/{agent_id}"
        params = {"locationId": location_id}
        
        log.info(f"Updating Voice AI agent {agent_id} in location {location_id}")
        response = requests.patch(url, headers=headers, params=params, json=updates, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            log.info(f"✅ Successfully updated Voice AI agent {agent_id}")
            return data.get("agent", {})
        else:
            log.error(f"❌ Failed to update Voice AI agent {agent_id}: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        log.exception(f"❌ Error updating Voice AI agent {agent_id}: {e}")
        return None


def delete_voice_ai_agent(agent_id: str, location_id: str) -> bool:
    """
    Delete a Voice AI agent and all its configurations.
    
    Args:
        agent_id: Voice AI agent ID to delete
        location_id: GHL location ID
    
    Returns:
        bool: True if deleted successfully, False otherwise
        
    API Documentation: https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents/delete-agent
    """
    try:
        headers = get_ghl_headers()
        url = f"{GHL_API_BASE}/voice-ai/agents/{agent_id}"
        params = {"locationId": location_id}
        
        log.info(f"Deleting Voice AI agent {agent_id} from location {location_id}")
        response = requests.delete(url, headers=headers, params=params, timeout=30)
        
        if response.status_code in [200, 204]:
            log.info(f"✅ Successfully deleted Voice AI agent {agent_id}")
            return True
        else:
            log.error(f"❌ Failed to delete Voice AI agent {agent_id}: {response.status_code} - {response.text}")
            return False
    
    except Exception as e:
        log.exception(f"❌ Error deleting Voice AI agent {agent_id}: {e}")
        return False


def clone_voice_ai_agents(
    source_location_id: str,
    target_location_id: str,
    clone_all: bool = True,
    specific_agent_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Clone Voice AI agent configurations from source location to target location.
    
    Args:
        source_location_id: Source GHL location ID to copy from
        target_location_id: Target GHL location ID to copy to
        clone_all: If True, clones all agents. If False, only clones specific_agent_ids
        specific_agent_ids: List of specific agent IDs to clone (used when clone_all=False)
    
    Returns:
        dict: Result with success status, cloned agents, and any errors
    """
    result = {
        "success": True,
        "source_location_id": source_location_id,
        "target_location_id": target_location_id,
        "cloned_agents": [],
        "errors": []
    }
    
    log.info(f"Starting Voice AI agents cloning from {source_location_id} to {target_location_id}")
    
    try:
        # Fetch all agents from source location
        source_data = list_voice_ai_agents(source_location_id)
        
        if source_data is None:
            result["errors"].append(
                "❌ AUTHENTICATION ERROR: Failed to fetch Voice AI agents from source location."
            )
            result["errors"].append("")
            result["errors"].append(
                "🔐 YOUR OAUTH TOKEN IS MISSING REQUIRED SCOPES"
            )
            result["errors"].append("")
            result["errors"].append("📋 Required Scopes:")
            result["errors"].append("   • voiceai.agents.read")
            result["errors"].append("   • voiceai.agents.write")
            result["errors"].append("   • locations.readonly (optional)")
            result["errors"].append("")
            result["errors"].append("🔧 How to Fix:")
            result["errors"].append("1. Go to GHL Marketplace → My Apps → Edit your OAuth app")
            result["errors"].append("2. Add the scopes above")
            result["errors"].append("3. Re-authorize your application (delete tokens, run test_ghl_auth.py)")
            result["errors"].append("4. Restart backend")
            result["errors"].append("")
            result["errors"].append(
                "📖 See: VOICE_AI_AGENTS_CORRECT_SCOPES.md for detailed instructions"
            )
            result["success"] = False
            return result
        
        source_agents = source_data.get("agents", [])
        
        if not source_agents:
            result["errors"].append(f"No Voice AI agents found in source location {source_location_id}")
            return result
        
        log.info(f"Found {len(source_agents)} Voice AI agents in source location")
        
        # Filter agents if specific IDs are provided
        agents_to_clone = source_agents
        if not clone_all and specific_agent_ids:
            agents_to_clone = [agent for agent in source_agents if agent.get("id") in specific_agent_ids]
            log.info(f"Filtering to {len(agents_to_clone)} specific agents")
        
        # Clone each agent
        for agent in agents_to_clone:
            agent_id = agent.get("id")
            agent_name = agent.get("name", "Unnamed Agent")
            
            try:
                # Get detailed configuration
                detailed_config = get_voice_ai_agent(agent_id, source_location_id)
                
                if not detailed_config:
                    result["errors"].append(f"Failed to get details for agent: {agent_name} (ID: {agent_id})")
                    continue
                
                # Modify name to indicate it's a clone
                detailed_config["name"] = f"{agent_name} (Cloned)"
                
                # Create agent in target location
                created_agent = create_voice_ai_agent(target_location_id, detailed_config)
                
                if created_agent:
                    result["cloned_agents"].append({
                        "original_id": agent_id,
                        "original_name": agent_name,
                        "new_id": created_agent.get("id"),
                        "new_name": created_agent.get("name"),
                        "voice_id": created_agent.get("voiceId"),
                        "provider": created_agent.get("provider"),
                        "model": created_agent.get("model")
                    })
                    log.info(f"✅ Successfully cloned agent: {agent_name} → {created_agent.get('name')}")
                else:
                    result["errors"].append(f"Failed to create agent: {agent_name} (ID: {agent_id})")
            
            except Exception as e:
                log.exception(f"Error cloning agent {agent_name}: {e}")
                result["errors"].append(f"Error cloning agent {agent_name}: {str(e)}")
        
        # Summary
        cloned_count = len(result["cloned_agents"])
        errors_count = len(result["errors"])
        
        log.info(f"Voice AI agents cloning completed: {cloned_count} agents cloned, {errors_count} errors")
        
        if errors_count > 0 and cloned_count == 0:
            result["success"] = False
        
        return result
    
    except Exception as e:
        log.exception(f"Critical error during Voice AI agents cloning: {e}")
        result["errors"].append(f"Critical error: {str(e)}")
        result["success"] = False
        return result


def get_voice_ai_agents_summary(location_id: str) -> Dict[str, Any]:
    """
    Get a summary of Voice AI agents for a location.
    
    Args:
        location_id: GHL location ID
    
    Returns:
        dict: Summary of Voice AI agents
    """
    try:
        agents_data = list_voice_ai_agents(location_id)
        
        if agents_data is None:
            return {
                "location_id": location_id,
                "error": "Failed to fetch Voice AI agents",
                "agents_count": 0,
                "agents": []
            }
        
        agents = agents_data.get("agents", [])
        total = agents_data.get("total", len(agents))
        
        agents_summary = [
            {
                "id": agent.get("id"),
                "name": agent.get("name"),
                "voiceId": agent.get("voiceId"),
                "provider": agent.get("provider"),
                "model": agent.get("model"),
                "language": agent.get("language"),
                "enabled": agent.get("enabled", True)
            }
            for agent in agents
        ]
        
        return {
            "location_id": location_id,
            "agents_count": len(agents),
            "total_agents": total,
            "agents": agents_summary
        }
    
    except Exception as e:
        log.exception(f"Error getting Voice AI agents summary for {location_id}: {e}")
        return {
            "location_id": location_id,
            "error": str(e),
            "agents_count": 0,
            "agents": []
        }


def compare_voice_ai_agents(location_id_1: str, location_id_2: str) -> Dict[str, Any]:
    """
    Compare Voice AI agents between two locations.
    Useful for verifying successful cloning or identifying differences.
    
    Args:
        location_id_1: First GHL location ID
        location_id_2: Second GHL location ID
    
    Returns:
        dict: Comparison results
    """
    try:
        summary_1 = get_voice_ai_agents_summary(location_id_1)
        summary_2 = get_voice_ai_agents_summary(location_id_2)
        
        agents_1 = {agent['name']: agent for agent in summary_1.get('agents', [])}
        agents_2 = {agent['name']: agent for agent in summary_2.get('agents', [])}
        
        only_in_1 = set(agents_1.keys()) - set(agents_2.keys())
        only_in_2 = set(agents_2.keys()) - set(agents_1.keys())
        in_both = set(agents_1.keys()) & set(agents_2.keys())
        
        return {
            "location_1": {
                "id": location_id_1,
                "agents_count": summary_1.get('agents_count', 0)
            },
            "location_2": {
                "id": location_id_2,
                "agents_count": summary_2.get('agents_count', 0)
            },
            "only_in_location_1": list(only_in_1),
            "only_in_location_2": list(only_in_2),
            "in_both_locations": list(in_both),
            "summary": {
                "unique_to_location_1": len(only_in_1),
                "unique_to_location_2": len(only_in_2),
                "common_agents": len(in_both)
            }
        }
    
    except Exception as e:
        log.exception(f"Error comparing Voice AI agents: {e}")
        return {
            "error": str(e),
            "location_1": {"id": location_id_1},
            "location_2": {"id": location_id_2}
        }

