from datetime import datetime, timedelta
from fastapi import FastAPI, Query, Body, HTTPException
from pydantic import BaseModel
from schemas.schemas import BookingRequest, AvailabilityRequest, CheckBooking
import requests
from config import NEWBOOK_API_BASE,REGION,API_KEY,GHL_CLIENT_ID,GHL_CLIENT_SECRET,GHL_API_BASE,GHL_API_KEY,GHL_LOCATION_ID,GHL_REDIRECT_URI,AI_AGENT_KEY
import base64
# from utils.ghl_api import create_opportunity
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import requests
# from utils.ghl_api import get_ghl_access_token, create_opportunity
from utils.ghl_api import create_opportunities_from_newbook
from fastapi import FastAPI, Request, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
import os
from utils.logger import get_logger
from utils.ghl_api import daily_cleanup  # Import the function


import time

app = FastAPI()
log = get_logger("FastAPI")


def authenticate_request(x_ai_agent_key: str = Header(None)):
    """
    Authentication helper function that validates the AI_AGENT_KEY from headers.
    Returns the key if valid, raises HTTPException if invalid or missing.
    """
    if not x_ai_agent_key:
        raise HTTPException(status_code=401, detail="Missing AI_AGENT_KEY in headers")
    
    if x_ai_agent_key != AI_AGENT_KEY:
        raise HTTPException(status_code=401, detail="Invalid AI_AGENT_KEY")
    
    return x_ai_agent_key


# Allow origins (add your frontend URL)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # <-- allow all origins
    allow_credentials=True,
    allow_methods=["*"],       # <-- allow all HTTP methods
    allow_headers=["*"],       # <-- allow all headers
)


USERNAME = "ParkPA"
PASSWORD = "ZEVaWP4ZaVT@MDTb"
user_pass = f"{USERNAME}:{PASSWORD}"
encoded_credentials = base64.b64encode(user_pass.encode()).decode()

header = {
    "Content-Type": "application/json",
    "Authorization": f"Basic {encoded_credentials}"
}

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
        headers = {"Content-Type": "application/json"}

        payload = {
            "region": REGION,
            "api_key": API_KEY,
            "period_from": period_from,
            "period_to": period_to,
            "adults": adults,
            "children": Children,
            "daily_mode": daily_mode
        }

        print("\n📤 Payload being sent to NewBook API:")
        print(payload)

        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_availability_pricing",
            headers=header,
            json=payload,
            verify=False,  # ⚠️ Only for local testing
            timeout=15
        )

        print("📥 Response Code:", response.status_code)
        print("📥 Response Body:", response.text)

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
            
            data = new_data
            
            

        return data

    except Exception as e:
        print("❌ Error:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
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
    amount: int = Query(..., description="Total booking amount"),
    _: str = Depends(authenticate_request)
):
    try:
        # Get tariff information from availability API
        tariff_info = get_tariff_information(
            period_from=period_from,
            period_to=period_to,
            adults=adults,
            children=children,
            category_id=category_id,
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
            "api_key": API_KEY,
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

        print(f"[INFO] Sending payload to NewBook: {payload}")

        # --- API Call to NewBook ---
        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_create",
            headers=header,
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

        headers = {"Content-Type": "application/json"}
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
            headers=header,
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

def get_tariff_information(period_from, period_to, adults, children, category_id, tariff_label=None):
    """
    Helper function to get tariff information from NewBook availability API
    Returns tariff data that can be used for booking creation
    """
    try:
        # Call the availability API
        payload = {
            "region": REGION,
            "api_key": API_KEY,
            "period_from": period_from,
            "period_to": period_to,
            "adults": adults,
            "children": children,
            "daily_mode": "false"
        }

        print(f"[TARIFF_HELPER] Getting availability for category {category_id}")
        print(f"[TARIFF_HELPER] Payload: {payload}")

        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_availability_pricing",
            headers=header,
            json=payload,
            verify=False,
            timeout=15
        )

        response.raise_for_status()
        availability_data = response.json()

        print(f"[TARIFF_HELPER] Availability response received")

        # Extract tariff information for the specific category
        if "data" in availability_data and str(category_id) in availability_data["data"]:
            category_data = availability_data["data"][str(category_id)]
            tariffs_available = category_data.get("tariffs_available", [])
            
            print(f"[TARIFF_HELPER] Found {len(tariffs_available)} tariffs for category {category_id}")
            
            # If tariff_label is specified, find that specific tariff
            if tariff_label:
                for tariff in tariffs_available:
                    if tariff.get("tariff_label") == tariff_label:
                        print(f"[TARIFF_HELPER] Found matching tariff: {tariff_label}")
                        # Extract the tariff ID from deposits
                        tariff_id = None
                        if tariff.get("deposits") and len(tariff["deposits"]) > 0:
                            tariff_id = int(tariff["deposits"][0].get("from_type_id", 1))
                        
                        return {
                            "tariff_label": tariff["tariff_label"],
                            "tariff_total": tariff["tariff_total"],
                            "original_tariff_total": tariff["original_tariff_total"],
                            "special_deal": tariff["special_deal"],
                            "tariff_code": tariff.get("tariff_code", 0),
                            "tariff_id": tariff_id,
                            "tariffs_available": [tariff]
                        }
                print(f"[TARIFF_HELPER] Warning: Tariff '{tariff_label}' not found, using first available")
            
            # Return the first available tariff if no specific label or label not found
            if tariffs_available:
                first_tariff = tariffs_available[0]
                print(f"[TARIFF_HELPER] Using first available tariff: {first_tariff['tariff_label']}")
                
                # Extract the tariff ID from deposits
                tariff_id = None
                if first_tariff.get("deposits") and len(first_tariff["deposits"]) > 0:
                    tariff_id = int(first_tariff["deposits"][0].get("from_type_id", 1))
                
                return {
                    "tariff_label": first_tariff["tariff_label"],
                    "tariff_total": first_tariff["tariff_total"],
                    "original_tariff_total": first_tariff["original_tariff_total"],
                    "special_deal": first_tariff["special_deal"],
                    "tariff_code": first_tariff.get("tariff_code", 0),
                    "tariff_id": tariff_id,
                    "tariffs_available": [first_tariff]
                }
        
        print(f"[TARIFF_HELPER] No tariffs found for category {category_id}")
        return None

    except Exception as e:
        print(f"[TARIFF_HELPER] Error getting tariff information: {str(e)}")
        return None

def create_tariffs_quoted(period_from, period_to, tariff_total, tariff_id):
    """
    Helper function to create tariffs_quoted in the correct format
    """
    from datetime import datetime, timedelta
    
    try:
        # Extract dates
        start_date = datetime.strptime(period_from.split()[0], "%Y-%m-%d")
        end_date = datetime.strptime(period_to.split()[0], "%Y-%m-%d")
        
        # Calculate number of nights
        nights = (end_date - start_date).days
        if nights <= 0:
            nights = 1
        
        # Calculate price per night
        price_per_night = tariff_total // nights
        
        # Create tariffs_quoted for each date
        tariffs_quoted = {}
        current_date = start_date
        
        while current_date < end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            tariffs_quoted[date_str] = {
                "tariff_applied_id": tariff_id,  # Use the actual tariff ID from availability
                "price": price_per_night
            }
            current_date += timedelta(days=1)
        
        print(f"[TARIFF_HELPER] Created tariffs_quoted: {tariffs_quoted}")
        return tariffs_quoted
        
    except Exception as e:
        print(f"[TARIFF_HELPER] Error creating tariffs_quoted: {str(e)}")
        return {}
    
def daily_cleanup_with_cache():
    """
    Deletes the local cache file (bookings_cache.json) and then runs the GHL cleanup.
    """
    print("[DAILY CLEANUP] Running cache cleanup...")
    cache_path = os.path.join(os.path.dirname(__file__), "bookings_cache.json")
    try:
        if os.path.exists(cache_path):
            os.remove(cache_path)
            print("[CACHE CLEANUP] Deleted bookings_cache.json successfully.")
        else:
            print("[CACHE CLEANUP] No bookings_cache.json file found.")
    except Exception as e:
        print(f"[ERROR] Could not delete cache file: {e}")
    
    # Run GHL cleanup after cache cleanup
    try:
        daily_cleanup()
        print("[DAILY CLEANUP] Completed GHL pipeline cleanup successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to run daily_cleanup(): {e}")

def start_scheduler():
    """
    Starts background scheduler for:
      - Daily cleanup (midnight)
      - Opportunity creation job every 15 minutes
    """
    scheduler = BackgroundScheduler()

    # Run daily cleanup every day at midnight
    scheduler.add_job(daily_cleanup_with_cache, "cron", hour=0, minute=0)

    # Run another task every 15 minutes
    scheduler.add_job(create_opportunities_from_newbook, "interval", minutes=10)

    scheduler.start()
    print("[SCHEDULER] Started successfully. Running background tasks...")

    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("[SCHEDULER] Stopped gracefully.")

# Run the scheduler in a background thread
threading.Thread(target=start_scheduler, daemon=True).start()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )