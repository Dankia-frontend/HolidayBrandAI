import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Query, HTTPException, Depends
from schemas.schemas import BookingRequest, AvailabilityRequest, CheckBooking
import requests
from config.config import NEWBOOK_API_BASE,REGION,API_KEY
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
from utils.logger import get_logger
from auth.auth import authenticate_request, get_newbook_credentials
from utils.newbook import NB_HEADERS, get_tariff_information, create_tariffs_quoted
from utils.scheduler import start_scheduler_in_background
from routes.rms_routes import router as rms_router
from services.rms import rms_service, rms_cache
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import signal
import sys
from utils.newbook_db import create_newbook_instance


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
def confirm_booking(
    name: str = Query(..., description="Guest name"),
    email: str = Query(..., description="Guest email"),
    booking_date: str | None = Query(None, description="Optional booking date (YYYY-MM-DD)"),
    _: str = Depends(authenticate_request),
    newbook_creds: dict = Depends(get_newbook_credentials)
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
            "api_key": newbook_creds["api_key"],
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

@app.on_event("startup")
async def startup_event():
    # Initialize RMS (lightweight - only property ID)
    try:
        print("🚀 Initializing RMS...")
        await rms_service.initialize()
        stats = rms_cache.get_stats()
        print(f"✅ RMS initialized successfully")
        print(f"   Property ID: {stats['property_id']}")
        print(f"   Agent ID: {stats['agent_id']}")
        print(f"   Cached Categories: {stats['cached_categories']}")
        print(f"   Cached Rate Plans: {stats['cached_rate_plans']}")
    except Exception as e:
        print(f"❌ RMS initialization failed: {e}")
    
    # Schedule daily RMS refresh at 3 AM
    try:
        scheduler.add_job(daily_rms_refresh, 'cron', hour=3, minute=0)
        # Add RMS sync job every 5 minutes (GHL sending disabled - only fetches data)
        scheduler.add_job(
            lambda: asyncio.run(rms_sync_job()),
            'interval',
            minutes=5
        )
        scheduler.start()
        log.info("✅ RMS daily refresh scheduled (3 AM)")
        log.info("✅ RMS sync job scheduled (every 5 minutes, GHL sending disabled)")
        print("✅ RMS daily refresh scheduled (3 AM)")
        print("✅ RMS sync job scheduled (every 5 minutes)")
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