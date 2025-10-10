# import requests
# from config import GHL_CLIENT_ID, GHL_CLIENT_SECRET

# GHL_API_VERSION = "2021-07-28"
# GHL_OPPORTUNITY_URL = "https://services.leadconnectorhq.com/opportunities/"


# def get_ghl_access_token() -> str:
#     try:
#         data = {
#             "client_id": GHL_CLIENT_ID,
#             "client_secret": GHL_CLIENT_SECRET,
#             "grant_type": "client_credentials"
#         }
#         resp = requests.post("https://api.gohighlevel.com/oauth/token", data=data)
#         resp.raise_for_status()
#         return resp.json()["access_token"]
#     except Exception as e:
#         print(f"[ERROR] Failed to get GHL token: {e}")
#         return ""


# def create_opportunity(opportunity_data: dict, ghl_access_token: str) -> bool:
#     headers = {
#         "Accept": "application/json",
#         "Authorization": f"Bearer {ghl_access_token}",
#         "Content-Type": "application/json",
#         "Version": GHL_API_VERSION
#     }

#     try:
#         resp = requests.post(GHL_OPPORTUNITY_URL, headers=headers, json=opportunity_data)
#         if resp.status_code == 201:
#             return True
#         print(f"[ERROR] GHL opportunity creation failed: {resp.text}")
#         return False
#     except Exception as e:
#         print(f"[ERROR] Exception creating GHL opportunity: {e}")
#         return False


import datetime
import requests
import base64
from config import REGION, API_KEY, NEWBOOK_API_BASE, USERNAME, PASSWORD



def create_opportunities_from_newbook():
    print("[TEST] Starting job to fetch completed bookings...")

    try:

        user_pass = f"{USERNAME}:{PASSWORD}"
        encoded_credentials = base64.b64encode(user_pass.encode()).decode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_credentials}"
        }
        # Get today's date and the date 7 days later
        today = datetime.datetime.now()
        period_from = today.strftime("%Y-%m-%d 00:00:00")
        period_to = (today + datetime.timedelta(days=7)).strftime("%Y-%m-%d 23:59:59")

        payload = {
            "region": REGION,
            "api_key": API_KEY,
            "period_from": period_from,
            "period_to": period_to,
            "list_type": "all"
        }

        print(f"[TEST] Sending request to: {NEWBOOK_API_BASE}/bookings_list")
        print(f"[TEST] Payload: {payload}")

        response = requests.post(f"{NEWBOOK_API_BASE}/bookings_list", json=payload,headers=headers, verify=False)
        response.raise_for_status()

        completed_bookings = response.json().get("data", [])

    except Exception as e:
        print(f"[ERROR] Failed to fetch completed bookings: {e}")
        return

    if not completed_bookings:
        print("[TEST] No completed bookings found.")
        return

    print("[DEBUG] Raw bookings response:", completed_bookings)

    print(f"[TEST] Fetched {len(completed_bookings)} bookings:")
    for booking in completed_bookings:
        guest_id = booking.get("guests")[0]["guest_id"] if booking.get("guests") else None
        print(f"Booking ID: {booking.get('booking_id')}, Guest ID: {guest_id}, Data: {booking}")

    print("[TEST] Skipping GHL opportunity creation for testing.")
