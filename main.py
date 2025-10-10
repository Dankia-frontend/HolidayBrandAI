import datetime
from fastapi import FastAPI, Query, Body, HTTPException
from pydantic import BaseModel
from schemas.schemas import BookingRequest, AvailabilityRequest, CheckBooking
import requests
from config import NEWBOOK_API_BASE,REGION,API_KEY
import base64
# from utils.ghl_api import create_opportunity
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import requests
# from utils.ghl_api import get_ghl_access_token, create_opportunity
from utils.ghl_api import create_opportunities_from_newbook

import time

app = FastAPI()


USERNAME = "ParkPA"
PASSWORD = "X14UrJa8J5UUpPNv"
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
    daily_mode: str = Query(..., description="Daily mode value, e.g., 'yes' or 'no'"),
    Children: int = Query(..., description="Number of children")
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
        return response.json()

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
    amount: int = Query(..., description="Total booking amount")
):
    try:
        # --- Build payload ---
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
            "amount": amount
        }

        print(f"[INFO] Sending payload to NewBook: {payload}")

        # --- API Call to NewBook ---
        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_create",
            headers=headers,
            json=payload,
            verify=False,  # ⚠️ Use verify=True in production
            timeout=15
        )

        response.raise_for_status()
        result = response.json()

        # Remove api_key from response (if present)
        result.pop("api_key", None)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
# 3. Check Booking [GET]
@app.get("/check-booking")
def check_booking(
    period_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    period_to: str = Query(..., description="End date in YYYY-MM-DD format"),
    guest_firstname: str = Query(...),
    guest_lastname: str = Query(...),
    guest_email: str = Query(...),
    guest_phone: str = Query(...),
    adults: int = Query(...),
    children: str = Query(...),
    category_id: int = Query(...),
    daily_mode: str = Query(...),
    amount: int = Query(...)
):
    try:
        # 🧾 Format the period dates to include time
        period_from_fmt = f"{period_from} 00:00:00"
        period_to_fmt = f"{period_to} 23:59:59"

        headers = {"Content-Type": "application/json"}
        # 🧱 Build payload for Newbook API
        payload = {
            "region": REGION,
            "api_key": API_KEY,
            "period_from": period_from_fmt,
            "period_to": period_to_fmt,
            "guest_firstname": guest_firstname,
            "guest_lastname": guest_lastname,
            "guest_email": guest_email,
            "guest_phone": guest_phone,
            "adults": adults,
            "children": children,
            "category_id": category_id,
            "daily_mode": daily_mode,
            "amount": amount,
        }

        print("\n📤 Sending payload to Newbook API:")
        print(payload)

        headers = {"Content-Type": "application/json"}

        # 🔗 Send request to Newbook API
        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_list",
            headers=headers,
            json=payload,
            verify=False,  # ❗ For local only — enable SSL in production
            timeout=15
        )

        print("📥 Response Code:", response.status_code)
        print("📥 Response Body:", response.text)

        # ✅ Raise error if not success
        response.raise_for_status()
        return response.json()

    except Exception as e:
        print("❌ Error:", str(e))
        raise HTTPException(status_code=500, detail=str(e))

# def create_opportunities_from_newbook():
#     print("[INFO] Starting GHL opportunity job...")

#     try:
#         # Step 1: Fetch completed bookings
#         payload = {
#             "region": REGION,
#             "api_key": API_KEY,
#             "period_from": "2025-01-01 00:00:00",  # customize as needed
#             "period_to": "2025-12-31 23:59:59"
#         }
#         response = requests.post(f"{NEWBOOK_API_BASE}/bookings_list", json=payload)
#         response.raise_for_status()
#         completed_bookings = response.json()

#     except Exception as e:
#         print(f"[ERROR] Failed to fetch completed bookings: {e}")
#         return

#     if not completed_bookings:
#         print("[INFO] No completed bookings found.")
#         return

#     # Step 2: Authenticate with GHL
#     ghl_access_token = get_ghl_access_token()
#     if not ghl_access_token:
#         print("[ERROR] GHL authentication failed.")
#         return

#     results = []

#     # Step 3: Create opportunities
#     for booking in completed_bookings:
#         try:
#             opportunity_data = {
#                 "pipelineId": "xxxx",              # Replace with your pipeline ID
#                 "locationId": "xxxx",              # Replace with your location ID
#                 "name": "NewBook Opportunity",
#                 "pipelineStageId": "xxxx",         # Replace with pipeline stage ID
#                 "status": "open",
#                 "contactId": booking.get("contact_id", "xxxx"),  
#                 "monetaryValue": booking.get("monetary_value", 220),
#                 "assignedTo": "xxxx",              # Replace with assigned user ID
#                 "customFields": [
#                     {
#                         "id": "xxxxx",             # Replace with custom field ID
#                         "field_value": "xxxxxx"
#                     }
#                 ]
#             }

#             success = create_opportunity(opportunity_data, ghl_access_token)
#             if success:
#                 results.append(f"Opportunity created for booking ID: {booking.get('booking_id')}")
#             else:
#                 results.append(f"Failed to create opportunity for booking ID: {booking.get('booking_id')}")

#         except Exception as e:
#             results.append(f"Error for booking ID {booking.get('booking_id')}: {e}")

#     for r in results:
#         print(r)


# # ------------------------
# # Scheduler
# # ------------------------
# def start_scheduler():
#     scheduler = BackgroundScheduler()
#     scheduler.add_job(create_opportunities_from_newbook, "interval", minutes=5)
#     scheduler.start()
#     try:
#         while True:
#             time.sleep(2)
#     except (KeyboardInterrupt, SystemExit):
#         scheduler.shutdown()


# # Run scheduler in background thread
# import threading
# threading.Thread(target=start_scheduler, daemon=True).start()


# def start_scheduler():
#     scheduler = BackgroundScheduler()
#     scheduler.add_job(create_opportunities_from_newbook, "interval", minutes=5)
#     scheduler.start()
#     try:
#         while True:
#             time.sleep(2)
#     except (KeyboardInterrupt, SystemExit):
#         scheduler.shutdown()

# threading.Thread(target=start_scheduler, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )