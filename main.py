import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Query, HTTPException, Depends
from schemas.schemas import BookingRequest, AvailabilityRequest, CheckBooking
import requests
from config.config import NEWBOOK_API_BASE, REGION, API_KEY
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
from utils.logger import get_logger
from auth.auth import authenticate_request, get_newbook_credentials
from utils.newbook import NB_HEADERS, get_tariff_information, create_tariffs_quoted
from utils.scheduler import start_scheduler_in_background
from routes.rms_routes import router as rms_router
from services.rms import rms_service, rms_cache, rms_auth
from utils.rms_db import set_current_rms_instance, get_rms_instance, create_rms_instance as create_rms_instance_db
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import signal
import sys
import os
from utils.newbook_db import create_newbook_instance
from urllib.parse import unquote


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
    period_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    period_to: str = Query(..., description="End date in YYYY-MM-DD format"),
    adults: int = Query(..., description="Number of adults"),
    daily_mode: str = Query(..., description="Daily mode value, e.g., 'true' or 'false'"),
    Children: int = Query(..., description="Number of children"),
    _: str = Depends(authenticate_request),
    newbook_creds: dict = Depends(get_newbook_credentials)
):
    # print(period_from, period_to, adults, daily_mode, Children)
    try:
        payload = {
            "region": REGION,
            "api_key": newbook_creds["api_key"],
            "period_from": period_from,
            "period_to": period_to,
            "adults": adults,
            "children": Children,
            "daily_mode": daily_mode
        }

        # print("\n📤 Payload being sent to NewBook API:")
        # print(payload)
        # print(NB_HEADERS)
        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_availability_pricing",
            headers=NB_HEADERS,
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
        # print(f"📥 Response Data: {data}")
        return data

    except Exception as e:
        print("❌ Error:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


def extract_and_validate_guest_info(response_data: dict, input_firstname: str, input_lastname: str, input_email: str, period_from: str = None, period_to: str = None) -> dict:
    """
    Extract guest information from booking response and validate against input parameters.
    Handles both single booking and multiple bookings in the response by finding the matching booking.
    
    Args:
        response_data: The booking response from NewBook API (can be single booking or array of bookings)
        input_firstname: First name passed to the API
        input_lastname: Last name passed to the API
        input_email: Email passed to the API
        period_from: Optional booking start date to validate against booking_arrival
        period_to: Optional booking end date to validate against booking_departure
    
    Returns:
        Dictionary with validation results including extracted values and mismatches
    """
    validation = {
        "matches": True,
        "mismatches": [],
        "extracted": {
            "firstname": None,
            "lastname": None,
            "email": None
        },
        "input": {
            "firstname": input_firstname.strip(),
            "lastname": input_lastname.strip(),
            "email": input_email.strip().lower()
        },
        "booking_id": None
    }
    
    try:
        # Normalize input values for comparison
        input_firstname_norm = validation["input"]["firstname"].lower()
        input_lastname_norm = validation["input"]["lastname"].lower()
        input_email_norm = validation["input"]["email"]
        
        # Handle different response structures
        bookings = []
        if isinstance(response_data, list):
            # Response is an array of bookings
            bookings = response_data
        elif isinstance(response_data, dict):
            # Check if response has a data array
            if "data" in response_data and isinstance(response_data["data"], list):
                bookings = response_data["data"]
            # Check if response has a bookings array
            elif "bookings" in response_data and isinstance(response_data["bookings"], list):
                bookings = response_data["bookings"]
            # Otherwise, treat as single booking object
            else:
                bookings = [response_data]
        else:
            validation["matches"] = False
            validation["mismatches"].append("Invalid response format")
            return validation
        
        if not bookings:
            validation["matches"] = False
            validation["mismatches"].append("No bookings found in response")
            return validation
        
        # Find the booking that matches the input guest information
        matching_booking = None
        matching_guest = None
        
        for booking in bookings:
            guests = booking.get("guests", [])
            if not guests:
                continue
            
            # Find primary guest in this booking
            primary_guest = None
            for guest in guests:
                if guest.get("primary_client") == "1" or guest.get("primary_client") == 1:
                    primary_guest = guest
                    break
            
            # If no primary client marked, use first guest
            if not primary_guest:
                primary_guest = guests[0]
            
            # Extract guest info for comparison
            guest_firstname = primary_guest.get("firstname", "").strip().lower()
            guest_lastname = primary_guest.get("lastname", "").strip().lower()
            
            # Extract email from contact_details
            guest_email = None
            contact_details = primary_guest.get("contact_details", [])
            for contact in contact_details:
                if contact.get("type") == "email":
                    guest_email = contact.get("content", "").strip().lower()
                    break
            
            # Check if this guest matches the input (email is most reliable)
            email_match = guest_email == input_email_norm if guest_email else False
            firstname_match = guest_firstname == input_firstname_norm
            lastname_match = guest_lastname == input_lastname_norm
            
            # Prioritize email match, but also check name matches
            if email_match or (firstname_match and lastname_match):
                matching_booking = booking
                matching_guest = primary_guest
                validation["booking_id"] = booking.get("booking_id")
                break
        
        # If no matching booking found, use the first booking and log warning
        if not matching_booking:
            matching_booking = bookings[0]
            guests = matching_booking.get("guests", [])
            if guests:
                for guest in guests:
                    if guest.get("primary_client") == "1" or guest.get("primary_client") == 1:
                        matching_guest = guest
                        break
                if not matching_guest:
                    matching_guest = guests[0]
            log.warning(f"Could not find exact matching booking for guest {input_firstname} {input_lastname} ({input_email}), using first booking")
        
        if not matching_guest:
            validation["matches"] = False
            validation["mismatches"].append("No guests found in matching booking")
            return validation
        
        # Extract firstname and lastname
        extracted_firstname = matching_guest.get("firstname", "").strip()
        extracted_lastname = matching_guest.get("lastname", "").strip()
        
        # Extract email from contact_details
        extracted_email = None
        contact_details = matching_guest.get("contact_details", [])
        for contact in contact_details:
            if contact.get("type") == "email":
                extracted_email = contact.get("content", "").strip().lower()
                break
        
        # Store extracted values
        validation["extracted"]["firstname"] = extracted_firstname
        validation["extracted"]["lastname"] = extracted_lastname
        validation["extracted"]["email"] = extracted_email
        
        # Compare values (case-insensitive for names, exact match for email)
        if extracted_firstname.lower() != input_firstname_norm:
            validation["matches"] = False
            validation["mismatches"].append({
                "field": "firstname",
                "input": validation["input"]["firstname"],
                "extracted": extracted_firstname
            })
        
        if extracted_lastname.lower() != input_lastname_norm:
            validation["matches"] = False
            validation["mismatches"].append({
                "field": "lastname",
                "input": validation["input"]["lastname"],
                "extracted": extracted_lastname
            })
        
        if extracted_email and extracted_email != input_email_norm:
            validation["matches"] = False
            validation["mismatches"].append({
                "field": "email",
                "input": validation["input"]["email"],
                "extracted": extracted_email
            })
        elif not extracted_email:
            validation["matches"] = False
            validation["mismatches"].append({
                "field": "email",
                "input": validation["input"]["email"],
                "extracted": "Not found in response"
            })
        
        # Validate booking dates if period_from and period_to are provided
        if period_from and period_to:
            def normalize_date(date_str: str) -> str:
                """Extract just the date part (YYYY-MM-DD) from datetime string"""
                if not date_str:
                    return ""
                # Handle formats like "2025-12-19 14:00:00" or "2025-12-19"
                return date_str.strip().split()[0] if " " in date_str else date_str.strip()
            
            booking_arrival = matching_booking.get("booking_arrival", "")
            booking_departure = matching_booking.get("booking_departure", "")
            
            normalized_arrival = normalize_date(booking_arrival)
            normalized_departure = normalize_date(booking_departure)
            normalized_period_from = normalize_date(period_from)
            normalized_period_to = normalize_date(period_to)
            
            if normalized_arrival != normalized_period_from:
                validation["matches"] = False
                validation["mismatches"].append({
                    "field": "arrival_date",
                    "input": normalized_period_from,
                    "extracted": normalized_arrival
                })
            
            if normalized_departure != normalized_period_to:
                validation["matches"] = False
                validation["mismatches"].append({
                    "field": "departure_date",
                    "input": normalized_period_to,
                    "extracted": normalized_departure
                })
        
    except Exception as e:
        log.error(f"Error extracting guest info: {str(e)}")
        validation["matches"] = False
        validation["mismatches"].append(f"Error during extraction: {str(e)}")
    
    return validation


# 2. Confirm Booking [POST]
@app.post("/confirm-booking")
def confirm_booking(
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
    # amount: int = Query(..., description="Total booking amount"),
    _: str = Depends(authenticate_request),
    newbook_creds: dict = Depends(get_newbook_credentials)
):
    try:
        # Get tariff information from availability API
        tariff_info = get_tariff_information(
            period_from=period_from,
            period_to=period_to,
            adults=adults,
            children=children,
            category_id=category_id,
            daily_mode=daily_mode,
            api_key=newbook_creds["api_key"],
            region=REGION
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
        
        # Build payload with tariff information
        payload = {
            "region": REGION,
            "api_key": newbook_creds["api_key"],
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
            # "amount": amount,
            "tariff_label": tariff_info["tariff_label"],
            "tariff_total": tariff_info["tariff_total"],
            "special_deal": tariff_info["special_deal"],
            "tariffs_quoted": tariffs_quoted
        }

        print(f"[INFO] Sending payload to NewBook: {payload}")

        # --- API Call to NewBook ---
        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_create",
            headers=NB_HEADERS,
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
def check_booking(
    first_name: str = Query(..., description="Guest first name"),
    last_name: str = Query(..., description="Guest last name"),
    email: str = Query(..., description="Guest email"),
    period_from: str = Query(..., description="Optional booking date (YYYY-MM-DD)"),
    period_to: str = Query(..., description="Optional booking date (YYYY-MM-DD)"),
    _: str = Depends(authenticate_request),
    newbook_creds: dict = Depends(get_newbook_credentials)
):
    try:
        first_name = first_name.strip()
        last_name = last_name.strip()
        email = unquote(email)

        if not first_name or not last_name or not email:
            raise HTTPException(status_code=400, detail="Missing required fields: name, email")


        # 🧾 Build request payload
        payload = {
            "region": REGION,
            "api_key": newbook_creds["api_key"],
            "period_from": period_from,
            "period_to": period_to,
            "list_type": "staying"
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
        # print("📥 Response Body:", response.text)

        response.raise_for_status()
        result = response.json()

        # Extract and validate guest information from response
        validation_result = extract_and_validate_guest_info(
            result, 
            first_name, 
            last_name, 
            email,
            period_from,
            period_to
        )
        
        # Log validation results
        booking_id = validation_result.get("booking_id") or "unknown"
        if validation_result["matches"]:
            log.info(f"✅ Guest info validation passed for booking {booking_id}")
        else:
            log.warning(f"⚠️ Guest info validation mismatch for booking {booking_id}: {validation_result['mismatches']}")

        # Return simple boolean response indicating if booking exists
        # return result
        return {"exists": validation_result["matches"]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/newbook-instances")
def create_newbook_instance_endpoint(
    location_id: str = Query(...),
    api_key: str = Query(...),
    # region: str = Query(None),
    # _: str = Depends(authenticate_request)
):
    success = create_newbook_instance(location_id, api_key)
    if success:
        return {"message": "Newbook instance created successfully"}
    else:
        raise HTTPException(status_code=400, detail="Location ID already exists")


# RMS Instance Management Endpoints
@app.post("/rms-instances")
def create_rms_instance_endpoint(
    location_id: str = Query(..., description="GHL Location ID"),
    client_id: int = Query(..., description="RMS Client ID"),
    client_pass: str = Query(..., description="RMS Client Password (will be encrypted)"),
    agent_id: int = Query(..., description="RMS Agent ID"),
    # _: str = Depends(authenticate_request)
):
    """Create a new RMS instance entry in the database"""
    success = create_rms_instance_db(location_id, client_id, client_pass, agent_id)
    if success:
        return {"message": "RMS instance created successfully"}
    else:
        raise HTTPException(status_code=400, detail="Location ID already exists or error occurred")


@app.get("/rms-instances/{location_id}")
def get_rms_instance_endpoint(
    location_id: str,
    # _: str = Depends(authenticate_request)
):
    """Get RMS instance by location_id (password will be masked)"""
    instance = get_rms_instance(location_id)
    if instance:
        # Mask the password for security
        instance['client_pass'] = '********'
        return instance
    else:
        raise HTTPException(status_code=404, detail="RMS instance not found")


@app.post("/rms-instances/{location_id}/activate")
async def activate_rms_instance(
    location_id: str,
    # _: str = Depends(authenticate_request)
):
    """
    Activate an RMS instance for use.
    This sets the current RMS credentials and reinitializes the RMS service.
    """
    # Set the current RMS instance from database
    success = set_current_rms_instance(location_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"RMS instance not found for location_id: {location_id}")
    
    # Reload credentials in auth and cache
    rms_auth.reload_credentials()
    rms_cache.reload_credentials()
    
    # Reinitialize RMS service
    try:
        await rms_service.initialize()
        stats = rms_cache.get_stats()
        return {
            "message": f"RMS instance activated for location {location_id}",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize RMS: {str(e)}")


# Include RMS routes
app.include_router(rms_router)

# Initialize scheduler
scheduler = AsyncIOScheduler()

async def daily_rms_refresh():
    """Automatically refresh RMS cache daily at 3 AM"""
    print("🔄 Running daily RMS cache refresh...")
    try:
        # Just clear the cache file to force fresh fetch on next request
        import os
        if os.path.exists("rms_cache.json"):
            os.remove("rms_cache.json")
        print("✅ Daily RMS cache cleared - will refresh on next request")
    except Exception as e:
        print(f"❌ Daily RMS cache refresh failed: {e}")

async def rms_sync_job():
    """Sync RMS bookings (GHL sending disabled - only NewBook sends to GHL)."""
    log.info("[RMS SYNC] Starting RMS fetch_and_sync_bookings job...")
    print("⏰ Running RMS fetch_and_sync_bookings job...")
    try:
        result = await rms_service.fetch_and_sync_bookings()
        log.info(f"[RMS SYNC] Job completed: {result}")
        print("✅ Sync result:", result)
    except Exception as e:
        log.error(f"[RMS SYNC] Job failed: {e}")
        print(f"❌ RMS sync job failed: {e}")


async def initialize_rms_from_db():
    """
    Initialize RMS using credentials from database.
    Uses RMS_LOCATION_ID from environment to determine which instance to use.
    """
    # Get location_id from environment variable
    location_id = os.getenv("RMS_LOCATION_ID")
    
    if not location_id:
        log.warning("⚠️ RMS_LOCATION_ID not set in environment - RMS will not be initialized from DB")
        print("⚠️ RMS_LOCATION_ID not set - falling back to env vars for RMS credentials")
        return False
    
    print(f"🔧 Initializing RMS from database for location: {location_id}")
    
    # Set the current RMS instance from database
    success = set_current_rms_instance(location_id)
    if not success:
        log.error(f"❌ RMS instance not found in database for location_id: {location_id}")
        print(f"❌ RMS instance not found for location_id: {location_id}")
        return False
    
    print(f"✅ RMS credentials loaded from database for location: {location_id}")
    return True


@app.on_event("startup")
async def startup_event():
    # RMS initialization removed - now handled per-request with credentials from headers
    # Each request creates its own RMS instance with the correct park's credentials
    print("✅ Server started - RMS will initialize per-request based on X-Location-ID header")
    
    # Schedule daily RMS refresh at 3 AM
    try:
        scheduler.add_job(daily_rms_refresh, 'cron', hour=3, minute=0)
        # Note: RMS sync job disabled - was using global instance
        # Each location now has its own credentials loaded per-request
        scheduler.start()
        log.info("✅ RMS daily refresh scheduled (3 AM)")
        print("✅ RMS daily cache cleanup scheduled (3 AM)")
    except Exception as e:
        print(f"⚠️ Scheduler error: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            print("✅ Scheduler stopped")
    except Exception as e:
        print(f"⚠️ Shutdown error: {e}")

# Handle Ctrl+C gracefully
def signal_handler(sig, frame):
    print('\n🛑 Shutting down gracefully...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Run the scheduler in a background thread
start_scheduler_in_background() # Comment out for local testing


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )