from datetime import datetime, timedelta
from fastapi import FastAPI, Query, HTTPException, Depends, Body
from schemas.schemas import (
    BookingRequest, AvailabilityRequest, CheckBooking,
    ParkConfigurationCreate, ParkConfigurationUpdate, ParkConfigurationResponse,
    VoiceAICloneRequest, VoiceAIConfigResponse,
    VoiceAIAgentsCloneRequest, VoiceAIAgentCreateRequest, VoiceAIAgentUpdateRequest
)
import requests
from config.config import NEWBOOK_API_BASE,REGION,API_KEY
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
from utils.logger import get_logger
from auth.auth import authenticate_request
from utils.newbook import NB_HEADERS, get_tariff_information, create_tariffs_quoted
from utils.scheduler import start_scheduler_in_background
from test_script import create_ghl_subaccount, create_ghl_subaccount_simple, delete_ghl_subaccount, list_ghl_locations, get_ghl_location
from utils.db_park_config import (
    create_park_configurations_table,
    add_park_configuration,
    update_park_configuration,
    get_park_configuration,
    get_all_park_configurations,
    delete_park_configuration
)
from utils.dynamic_config import get_dynamic_park_config
from utils.voice_ai_utils import (
    clone_voice_ai_configuration,
    get_voice_ai_summary,
    get_conversation_ai_bots
)
from utils.voice_ai_agents import (
    list_voice_ai_agents,
    get_voice_ai_agent,
    create_voice_ai_agent,
    patch_voice_ai_agent,
    delete_voice_ai_agent,
    clone_voice_ai_agents,
    get_voice_ai_agents_summary,
    compare_voice_ai_agents
)

app = FastAPI()
log = get_logger("FastAPI")

# Allow origins (add your frontend URL)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # <-- allow all origins
    allow_credentials=True,
    allow_methods=["*"],       # <-- allow all HTTP methods
    allow_headers=["*"],       # <-- allow all headers
)


@app.get("/availability")
def get_availability(
    location_id: str = Query(..., description="GHL Location ID for the park"),
    period_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    period_to: str = Query(..., description="End date in YYYY-MM-DD format"),
    adults: int = Query(..., description="Number of adults"),
    daily_mode: str = Query(..., description="Daily mode value, e.g., 'true' or 'false'"),
    Children: int = Query(..., description="Number of children"),
    _: str = Depends(authenticate_request)
):
    try:
        # Get park-specific configuration from database
        park_config = get_dynamic_park_config(location_id)
        log.info(f"Processing availability request for park: {park_config.park_name} (Location ID: {location_id})")
        
        # Build payload with park-specific settings
        payload = {
            "region": park_config.newbook_region,
            "api_key": park_config.newbook_api_key,
            "period_from": period_from,
            "period_to": period_to,
            "adults": adults,
            "children": Children,
            "daily_mode": daily_mode
        }

        print(f"\n📤 Payload being sent to NewBook API for {park_config.park_name}:")
        print(payload)
        
        # Use park-specific headers
        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_availability_pricing",
            headers=park_config.get_newbook_headers(),
            json=payload,
            verify=False,  # ⚠️ Only for local testing
            timeout=15
        )

        # print("📥 Response Code:", response.status_code)
        # print("📥 Response Body:", response.text)

        response.raise_for_status()
        data = response.json()

        # Sort categories by highest amount first (descending order)
        if "data" in data and isinstance(data["data"], dict):
            # Convert categories to list of tuples (category_id, category_data, max_amount)
            categories_with_amounts = []
            
            for category_id, category_data in data["data"].items():
                tariffs_available = category_data.get("tariffs_available", [])
                
                # Find the highest amount among all tariffs for this category
                max_amount = 0
                if tariffs_available:
                    for tariff in tariffs_available:
                        tariffs_quoted = tariff.get("tariffs_quoted", {})
                        if isinstance(tariffs_quoted, dict):
                            # Get the maximum amount from all dates in tariffs_quoted
                            for date_key, quote_data in tariffs_quoted.items():
                                if isinstance(quote_data, dict):
                                    amount = quote_data.get("amount", 0)
                                    # Ensure amount is treated as a number
                                    try:
                                        amount = float(amount) if amount is not None else 0
                                        max_amount = max(max_amount, amount)
                                    except (ValueError, TypeError):
                                        continue
                
                categories_with_amounts.append((category_id, category_data, max_amount))
            
            # Sort by max_amount in descending order (highest first)
            categories_with_amounts.sort(key=lambda x: float(x[2]), reverse=True)
            
            # This ensures the order is preserved in the JSON response
            new_data = {
                "success": data.get("success", "true"),
                "data": {}
            }
            
            # Add categories in sorted order
            for category_id, category_data, _ in categories_with_amounts:
                new_data["data"][category_id] = category_data
            
            # Copy any other fields from original response
            for key, value in data.items():
                if key not in ["success", "data"]:
                    new_data[key] = value

            # Filter to only required fields per category
            filtered = {
                "success": new_data.get("success", "true"),
                "data": {}
            }

            for category_id, category_data in new_data["data"].items():
                category_name = category_data.get("category_name")
                sites_message = category_data.get("sites_message", {})

                # Derive price: prefer average_nightly_tariff from first tariff; fallback to first quoted amount
                price = None
                tariffs_available = category_data.get("tariffs_available", [])
                if tariffs_available:
                    first_tariff = tariffs_available[0]
                    price = first_tariff.get("average_nightly_tariff")
                    if price is None:
                        tariffs_quoted = first_tariff.get("tariffs_quoted", {})
                        if isinstance(tariffs_quoted, dict) and tariffs_quoted:
                            first_date_key = next(iter(tariffs_quoted.keys()))
                            quote = tariffs_quoted.get(first_date_key) or {}
                            price = quote.get("amount")

                filtered["data"][category_id] = {
                    "category_name": category_name,
                    "price": price,
                    "sites_message": sites_message,
                }

            data = filtered
        print(f"📥 Response Data: {data}")
        return data

    except Exception as e:
        print("❌ Error:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
# 2. Confirm Booking [POST]
@app.post("/confirm-booking")
def confirm_booking(
    location_id: str = Query(..., description="GHL Location ID for the park"),
    period_from: str = Query(..., description="Booking start date, e.g. 2025-10-10 00:00:00"),
    period_to: str = Query(..., description="Booking end date, e.g. 2025-10-15 23:59:59"),
    guest_firstname: str = Query(..., description="Guest first name"),
    guest_lastname: str = Query(..., description="Guest last name"),
    guest_email: str = Query(..., description="Guest email address"),
    guest_phone: str = Query(..., description="Guest phone number"),
    adults: int = Query(..., description="Number of adults"),
    children: str = Query(..., description="Number of children"),
    category_id: int = Query(..., description="Category ID of the room or package"),
    daily_mode: str = Query(..., description="Daily booking mode (yes/no)"),
    amount: int = Query(..., description="Total booking amount"),
    _: str = Depends(authenticate_request)
):
    try:
        # Get park-specific configuration from database
        park_config = get_dynamic_park_config(location_id)
        log.info(f"Processing booking confirmation for park: {park_config.park_name} (Location ID: {location_id})")
        
        # Get tariff information from availability API with park-specific config
        tariff_info = get_tariff_information(
            period_from=period_from,
            period_to=period_to,
            adults=adults,
            children=children,
            category_id=category_id,
            daily_mode=daily_mode,
            park_config=park_config
        )
        
        if not tariff_info:
            raise HTTPException(status_code=400, detail="No tariff information found for the specified category and dates")
        
        # Create tariffs_quoted using the actual tariff ID from availability
        tariffs_quoted = create_tariffs_quoted(
            period_from=period_from,
            period_to=period_to,
            tariff_total=tariff_info["tariff_total"],
            tariff_id=tariff_info["tariff_id"]  # Use the actual tariff ID
        )
        
        # Build payload with park-specific tariff information
        payload = {
            "region": park_config.newbook_region,
            "api_key": park_config.newbook_api_key,
            "period_from": period_from,
            "period_to": period_to,
            "guest_firstname": guest_firstname,
            "guest_lastname": guest_lastname,
            "guest_email": guest_email,
            "guest_phone": guest_phone,
            "adults": adults,
            "children": children,
            "category_id": category_id,
            "daily_mode": daily_mode,
            "amount": amount,
            "tariff_label": tariff_info["tariff_label"],
            "tariff_total": tariff_info["tariff_total"],
            "special_deal": tariff_info["special_deal"],
            "tariffs_quoted": tariffs_quoted
        }

        print(f"[INFO] Sending payload to NewBook for {park_config.park_name}: {payload}")

        # --- API Call to NewBook with park-specific headers ---
        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_create",
            headers=park_config.get_newbook_headers(),
            json=payload,
            verify=False,
            timeout=15
        )

        print(f"[DEBUG] Response Status Code: {response.status_code}")
        print(f"[DEBUG] Response Text: {response.text}")

        response.raise_for_status()
        result = response.json()

        # Remove api_key from response (if present)
        result.pop("api_key", None)

        return result

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    
# 3. Check Booking [GET]
@app.get("/check-booking")
def confirm_booking(
    name: str = Query(..., description="Guest name"),
    email: str = Query(..., description="Guest email"),
    booking_date: str | None = Query(None, description="Optional booking date (YYYY-MM-DD)"),
    _: str = Depends(authenticate_request)
):
    try:
        name = name.strip()
        email = email.strip()
        booking_date = booking_date.strip() if booking_date else None

        if not name or not email:
            raise HTTPException(status_code=400, detail="Missing required fields: name, email")

        # 🗓 Determine date range (period_from / period_to)
        if booking_date:
            try:
                date_obj = datetime.strptime(booking_date, "%Y-%m-%d")
                period_from = date_obj.strftime("%Y-%m-%d 00:00:00")
                period_to = date_obj.strftime("%Y-%m-%d 23:59:59")
            except ValueError:
                # Invalid date → fallback to current week
                today = datetime.now()
                monday = today - datetime.timedelta(days=today.weekday())
                sunday = monday + datetime.timedelta(days=6)
                period_from = monday.strftime("%Y-%m-%d 00:00:00")
                period_to = sunday.strftime("%Y-%m-%d 23:59:59")
        else:
            # No date → current month
            today = datetime.now()
            first_day = today.replace(day=1)
            next_month = first_day + datetime.timedelta(days=32)
            last_day = next_month.replace(day=1) - datetime.timedelta(days=1)
            period_from = first_day.strftime("%Y-%m-%d 00:00:00")
            period_to = last_day.strftime("%Y-%m-%d 23:59:59")

        # 🧾 Build request payload
        payload = {
            "region": REGION,
            "api_key": API_KEY,
            "period_from": period_from,
            "period_to": period_to,
            "list_type": "all"
        }

        print("\n📤 Payload being sent to Newbook API:")
        print(payload)

        # 🔗 Send request to NewBook
        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_list",
            headers=NB_HEADERS,
            json=payload,
            verify=False,  # Disable SSL for local testing only
            timeout=15
        )

        print("📥 Response Code:", response.status_code)
        print("📥 Response Body:", response.text)

        response.raise_for_status()
        return response.json()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 4. Create GHL Sub-Account [POST]
@app.post("/ghl/create-subaccount")
def create_ghl_subaccount_endpoint(
    business_name: str = Query(..., description="Business name for the sub-account (required)"),
    address: str = Query(None, description="Street address"),
    city: str = Query(None, description="City name"),
    state: str = Query(None, description="State/Province code (e.g., 'CA', 'NY')"),
    postal_code: str = Query(None, description="ZIP/Postal code"),
    country: str = Query("US", description="Country code (default: 'US')"),
    website: str = Query(None, description="Business website URL"),
    timezone: str = Query("America/New_York", description="Timezone (default: 'America/New_York')"),
    first_name: str = Query(None, description="Primary contact first name"),
    last_name: str = Query(None, description="Primary contact last name"),
    email: str = Query(None, description="Primary contact email"),
    phone: str = Query(None, description="Primary contact phone (E.164 format recommended, e.g., '+1234567890')"),
    snapshot_id: str = Query(None, description="Optional snapshot ID to apply template"),
    # _: str = Depends(authenticate_request)
):
    """
    Creates a new sub-account (location) in GoHighLevel using Agency API Key.
    """
    try:
        result = create_ghl_subaccount(
            businessName=business_name,
            address=address,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            website=website,
            timezone=timezone,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            snapshot_id=snapshot_id
        )
        
        if result:
            return {
                "success": True,
                "message": "Sub-account created successfully",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to create sub-account")
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error creating GHL sub-account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 5. Create GHL Sub-Account (Simple) [POST]
@app.post("/ghl/create-subaccount-simple")
def create_ghl_subaccount_simple_endpoint(
    name: str = Query(..., description="Business name (required)"),
    email: str = Query(None, description="Primary contact email"),
    phone: str = Query(None, description="Primary contact phone"),
    city: str = Query(None, description="City name"),
    state: str = Query(None, description="State/Province code"),
    country: str = Query("US", description="Country code (default: 'US')"),
    _: str = Depends(authenticate_request)
):
    """
    Simplified endpoint to create a sub-account with minimal required fields.
    """
    try:
        result = create_ghl_subaccount_simple(
            name=name,
            email=email,
            phone=phone,
            city=city,
            state=state,
            country=country
        )
        
        if result:
            return {
                "success": True,
                "message": "Sub-account created successfully",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to create sub-account")
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error creating GHL sub-account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 6. Delete GHL Sub-Account [DELETE]
@app.delete("/ghl/delete-subaccount")
def delete_ghl_subaccount_endpoint(
    location_id: str = Query(..., description="The ID of the location to delete"),
    _: str = Depends(authenticate_request)
):
    """
    Deletes a sub-account (location) by its ID.
    """
    try:
        success = delete_ghl_subaccount(location_id)
        
        if success:
            return {
                "success": True,
                "message": f"Sub-account {location_id} deleted successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=f"Failed to delete sub-account {location_id}")
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error deleting GHL sub-account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 7. List GHL Locations [GET]
@app.get("/ghl/list-locations")
def list_ghl_locations_endpoint(
    # _: str = Depends(authenticate_request)
):
    """
    Lists all locations (sub-accounts) in the agency.
    """
    try:
        locations = list_ghl_locations()
        
        if locations is not None:
            return {
                "success": True,
                "count": len(locations),
                "locations": locations
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to list locations")
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error listing GHL locations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 8. Get GHL Location [GET]
@app.get("/ghl/get-location")
def get_ghl_location_endpoint(
    location_id: str = Query(..., description="The ID of the location to retrieve"),
    # _: str = Depends(authenticate_request)
):
    """
    Gets details of a specific location by ID.
    """
    try:
        location = get_ghl_location(location_id)
        
        if location:
            return {
                "success": True,
                "data": location
            }
        else:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting GHL location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Voice AI Configuration Management Endpoints ====================

@app.get("/voice-ai/summary/{location_id}")
def get_voice_ai_summary_endpoint(
    location_id: str,
    # _: str = Depends(authenticate_request)
):
    """
    Get a summary of Voice AI configuration for a specific GHL location.
    Shows all AI assistants and Voice AI related workflows.
    """
    try:
        summary = get_voice_ai_summary(location_id)
        
        return {
            "success": True,
            "data": summary
        }
    
    except Exception as e:
        log.error(f"Error getting Voice AI summary for {location_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/voice-ai/clone")
def clone_voice_ai_endpoint(
    request: VoiceAICloneRequest,
    # _: str = Depends(authenticate_request)
):
    """
    Clone Voice AI configuration from one GHL location to another.
    
    This endpoint will:
    - Copy AI assistants (conversation bots) with their configurations
    - Identify Voice AI related workflows (manual export/import required)
    - Optionally clone phone number configurations
    
    Example:
    {
        "source_location_id": "UTkbqQXAR7A3UsirpOje",
        "target_location_id": "target_location_id_here",
        "clone_assistants": true,
        "clone_workflows": true,
        "clone_phone_numbers": false
    }
    """
    try:
        log.info(f"Cloning Voice AI from {request.source_location_id} to {request.target_location_id}")
        
        result = clone_voice_ai_configuration(
            source_location_id=request.source_location_id,
            target_location_id=request.target_location_id,
            clone_assistants=request.clone_assistants,
            clone_workflows=request.clone_workflows,
            clone_phone_numbers=request.clone_phone_numbers
        )
        
        return {
            "success": result["success"],
            "message": "Voice AI configuration cloning completed",
            "data": result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error cloning Voice AI configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voice-ai/assistants/{location_id}")
def list_ai_assistants_endpoint(
    location_id: str,
    # _: str = Depends(authenticate_request)
):
    """
    List all AI assistants for a specific GHL location.
    """
    try:
        assistants = get_conversation_ai_bots(location_id)
        
        if assistants is not None:
            return {
                "success": True,
                "location_id": location_id,
                "count": len(assistants),
                "assistants": assistants
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to fetch AI assistants for location {location_id}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error listing AI assistants: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Voice AI Agents Management Endpoints ====================

@app.get("/voice-ai-agents/list/{location_id}")
def list_voice_ai_agents_endpoint(
    location_id: str,
    limit: int = Query(100, description="Number of agents to retrieve"),
    offset: int = Query(0, description="Pagination offset"),
    # _: str = Depends(authenticate_request)
):
    """
    List all Voice AI agents for a specific GHL location.
    Uses the Voice AI Agents API (different from Conversation AI assistants).
    
    API Documentation: https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents
    """
    try:
        agents_data = list_voice_ai_agents(location_id, limit=limit, offset=offset)
        
        if agents_data is not None:
            return {
                "success": True,
                "location_id": location_id,
                "data": agents_data
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to fetch Voice AI agents for location {location_id}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error listing Voice AI agents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voice-ai-agents/get/{location_id}/{agent_id}")
def get_voice_ai_agent_endpoint(
    location_id: str,
    agent_id: str,
    # _: str = Depends(authenticate_request)
):
    """
    Get detailed configuration for a specific Voice AI agent.
    
    API Documentation: https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents/get-agent
    """
    try:
        agent = get_voice_ai_agent(agent_id, location_id)
        
        if agent:
            return {
                "success": True,
                "location_id": location_id,
                "agent_id": agent_id,
                "data": agent
            }
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"Voice AI agent {agent_id} not found in location {location_id}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error fetching Voice AI agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/voice-ai-agents/create")
def create_voice_ai_agent_endpoint(
    request: VoiceAIAgentCreateRequest,
    # _: str = Depends(authenticate_request)
):
    """
    Create a new Voice AI agent in a location.
    
    API Documentation: https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents/create-agent
    """
    try:
        agent_config = request.dict(exclude={"location_id"}, exclude_none=True)
        created_agent = create_voice_ai_agent(request.location_id, agent_config)
        
        if created_agent:
            return {
                "success": True,
                "message": f"Voice AI agent '{request.name}' created successfully",
                "data": created_agent
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to create Voice AI agent '{request.name}'"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error creating Voice AI agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/voice-ai-agents/update/{location_id}/{agent_id}")
def update_voice_ai_agent_endpoint(
    location_id: str,
    agent_id: str,
    request: VoiceAIAgentUpdateRequest,
    # _: str = Depends(authenticate_request)
):
    """
    Update an existing Voice AI agent.
    
    API Documentation: https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents/patch-agent
    """
    try:
        updates = request.dict(exclude_none=True)
        updated_agent = patch_voice_ai_agent(agent_id, location_id, updates)
        
        if updated_agent:
            return {
                "success": True,
                "message": f"Voice AI agent {agent_id} updated successfully",
                "data": updated_agent
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to update Voice AI agent {agent_id}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error updating Voice AI agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/voice-ai-agents/delete/{location_id}/{agent_id}")
def delete_voice_ai_agent_endpoint(
    location_id: str,
    agent_id: str,
    # _: str = Depends(authenticate_request)
):
    """
    Delete a Voice AI agent.
    
    API Documentation: https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents/delete-agent
    """
    try:
        success = delete_voice_ai_agent(agent_id, location_id)
        
        if success:
            return {
                "success": True,
                "message": f"Voice AI agent {agent_id} deleted successfully"
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to delete Voice AI agent {agent_id}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error deleting Voice AI agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voice-ai-agents/summary/{location_id}")
def get_voice_ai_agents_summary_endpoint(
    location_id: str,
    # _: str = Depends(authenticate_request)
):
    """
    Get a summary of Voice AI agents for a location.
    Shows agent counts and basic information.
    """
    try:
        summary = get_voice_ai_agents_summary(location_id)
        
        return {
            "success": True,
            "data": summary
        }
    
    except Exception as e:
        log.error(f"Error getting Voice AI agents summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/voice-ai-agents/clone")
def clone_voice_ai_agents_endpoint(
    request: VoiceAIAgentsCloneRequest,
    # _: str = Depends(authenticate_request)
):
    """
    Clone Voice AI agents from one location to another.
    
    This endpoint will copy all Voice AI agent configurations including:
    - Agent prompts and instructions
    - Voice settings (voice ID, provider)
    - Model configurations (GPT-4, temperature, etc.)
    - Actions and tools
    - All other agent settings
    
    Example:
    {
        "source_location_id": "source_location_id_here",
        "target_location_id": "target_location_id_here",
        "clone_all": true,
        "specific_agent_ids": null
    }
    
    API Documentation: https://marketplace.gohighlevel.com/docs/ghl/voice-ai/agents
    """
    try:
        log.info(f"Cloning Voice AI agents from {request.source_location_id} to {request.target_location_id}")
        
        result = clone_voice_ai_agents(
            source_location_id=request.source_location_id,
            target_location_id=request.target_location_id,
            clone_all=request.clone_all,
            specific_agent_ids=request.specific_agent_ids
        )
        
        return {
            "success": result["success"],
            "message": "Voice AI agents cloning completed",
            "data": result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error cloning Voice AI agents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voice-ai-agents/compare")
def compare_voice_ai_agents_endpoint(
    location_id_1: str = Query(..., description="First location ID to compare"),
    location_id_2: str = Query(..., description="Second location ID to compare"),
    # _: str = Depends(authenticate_request)
):
    """
    Compare Voice AI agents between two locations.
    Useful for verifying successful cloning or identifying differences.
    """
    try:
        comparison = compare_voice_ai_agents(location_id_1, location_id_2)
        
        return {
            "success": True,
            "data": comparison
        }
    
    except Exception as e:
        log.error(f"Error comparing Voice AI agents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Park Configuration Management Endpoints ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    log.info("Initializing database tables...")
    create_park_configurations_table()


@app.post("/park-config/create")
def create_park_config_endpoint(
    config: ParkConfigurationCreate,
    # _: str = Depends(authenticate_request)
):
    """
    Create a new park configuration.
    This endpoint stores location-specific configurations including
    Newbook API credentials and GHL pipeline/stage IDs.
    """
    try:
        success = add_park_configuration(
            location_id=config.location_id,
            park_name=config.park_name,
            newbook_api_token=config.newbook_api_token,
            newbook_api_key=config.newbook_api_key,
            newbook_region=config.newbook_region,
            ghl_pipeline_id=config.ghl_pipeline_id,
            stage_arriving_soon=config.stage_arriving_soon,
            stage_arriving_today=config.stage_arriving_today,
            stage_arrived=config.stage_arrived,
            stage_departing_today=config.stage_departing_today,
            stage_departed=config.stage_departed
        )
        
        if success:
            return {
                "success": True,
                "message": f"Park configuration created successfully for {config.park_name}"
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to create park configuration. Location ID {config.location_id} may already exist."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error creating park configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/park-config/update/{location_id}")
def update_park_config_endpoint(
    location_id: str,
    config: ParkConfigurationUpdate,
    # _: str = Depends(authenticate_request)
):
    """
    Update an existing park configuration.
    Only provided fields will be updated.
    """
    try:
        success = update_park_configuration(
            location_id=location_id,
            park_name=config.park_name,
            newbook_api_token=config.newbook_api_token,
            newbook_api_key=config.newbook_api_key,
            newbook_region=config.newbook_region,
            ghl_pipeline_id=config.ghl_pipeline_id,
            stage_arriving_soon=config.stage_arriving_soon,
            stage_arriving_today=config.stage_arriving_today,
            stage_arrived=config.stage_arrived,
            stage_departing_today=config.stage_departing_today,
            stage_departed=config.stage_departed,
            is_active=config.is_active
        )
        
        if success:
            return {
                "success": True,
                "message": f"Park configuration updated successfully for location {location_id}"
            }
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"Park configuration not found for location_id: {location_id}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error updating park configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/park-config/get/{location_id}")
def get_park_config_endpoint(
    location_id: str,
    # _: str = Depends(authenticate_request)
):
    """
    Retrieve park configuration by location_id.
    """
    try:
        config = get_park_configuration(location_id)
        
        if config:
            return {
                "success": True,
                "data": config
            }
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"Park configuration not found for location_id: {location_id}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error retrieving park configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/park-config/list")
def list_park_configs_endpoint(
    include_inactive: bool = Query(False, description="Include inactive configurations"),
    # _: str = Depends(authenticate_request)
):
    """
    List all park configurations.
    """
    try:
        configs = get_all_park_configurations(include_inactive=include_inactive)
        
        return {
            "success": True,
            "count": len(configs),
            "data": configs
        }
            
    except Exception as e:
        log.error(f"Error listing park configurations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/park-config/delete/{location_id}")
def delete_park_config_endpoint(
    location_id: str,
    soft_delete: bool = Query(True, description="If true, deactivates instead of deleting"),
    # _: str = Depends(authenticate_request)
):
    """
    Delete or deactivate a park configuration.
    """
    try:
        success = delete_park_configuration(location_id, soft_delete=soft_delete)
        
        if success:
            action = "deactivated" if soft_delete else "deleted"
            return {
                "success": True,
                "message": f"Park configuration {action} successfully for location {location_id}"
            }
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"Park configuration not found for location_id: {location_id}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error deleting park configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Run the scheduler in a background thread
# start_scheduler_in_background() # Comment out for local testing


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )