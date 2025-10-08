import datetime
from fastapi import FastAPI, Query, Body, HTTPException
from pydantic import BaseModel
from schemas.schemas import BookingRequest, AvailabilityRequest, CheckBooking
import requests
from config import NEWBOOK_API_BASE, headers,REGION,API_KEY
import base64

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )