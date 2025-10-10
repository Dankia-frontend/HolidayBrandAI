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

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Basic {encoded_credentials}"
}

@app.post("/availability")
def get_availability(data: AvailabilityRequest = Body(...)):
    try:
        # merge constants with user-supplied data
        payload = {
            "region": REGION,
            "api_key": API_KEY,
            **data.dict(),   # unpack rest of fields from body
        }

        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_availability_pricing",
            headers=headers,
            json=payload,
            verify=False,  # optional, for local testing only
            timeout=15
        )

        response.raise_for_status()
        return response.json()

    except Exception as e:
        
        raise HTTPException(status_code=500, detail=str(e))


# 2. Confirm Booking [POST]
@app.post("/confirm-booking")
def confirm_booking(data: BookingRequest = Body(...)):
    try:
        payload = {
            "region": REGION,
            "api_key": API_KEY,
            **data.dict(),   # unpack rest of fields from body
        }
        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_create",
            headers=headers,
            json=payload,
            verify=False,  # optional, for local testing only
            timeout=15
        )
        response.raise_for_status()
        result = response.json()
        # Remove api_key from response if present
        result.pop("api_key", None)
        return result
    except Exception as e:
        
        raise HTTPException(status_code=500, detail=str(e))
    
    
# 2. Check Booking [GET]
@app.post("/check-booking")
def confirm_booking(data: CheckBooking = Body(...)):
    try:
        name = data.name.strip()
        email = data.email.strip()
        booking_date = data.booking_date.strip() if data.booking_date else None

        if not name or not email:
            raise HTTPException(status_code=400, detail="Missing required fields: name, email")

        # 🗓 Determine date range (period_from / period_to)
        if booking_date:
            try:
                date_obj = datetime.datetime.strptime(booking_date, "%Y-%m-%d")
                period_from = date_obj.strftime("%Y-%m-%d 00:00:00")
                period_to = date_obj.strftime("%Y-%m-%d 23:59:59")
            except ValueError:
                # Invalid date → fallback to current week
                today = datetime.datetime.now()
                monday = today - datetime.timedelta(days=today.weekday())
                sunday = monday + datetime.timedelta(days=6)
                period_from = monday.strftime("%Y-%m-%d 00:00:00")
                period_to = sunday.strftime("%Y-%m-%d 23:59:59")
        else:
            # No date → current month
            today = datetime.datetime.now()
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
            headers=headers,
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


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(create_opportunities_from_newbook, "interval", minutes=5)
    scheduler.start()
    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

threading.Thread(target=start_scheduler, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )