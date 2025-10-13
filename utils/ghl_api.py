import mysql.connector
import os
import json
import base64
import datetime
import requests

from config import REGION, API_KEY, NEWBOOK_API_BASE, GHL_API_KEY, GHL_LOCATION_ID, GHL_PIPELINE_ID, GHL_STAGE_ID, GHL_CLIENT_ID, GHL_CLIENT_SECRET, GHL_AUTHORIZATION_CODE, GHL_REDIRECT_URI

USERNAME = "ParkPA"
PASSWORD = "ZEVaWP4ZaVT@MDTb"
GHL_API_VERSION = "2021-07-28"
GHL_OPPORTUNITY_URL = "https://services.leadconnectorhq.com/opportunities/"
CACHE_FILE = "bookings_cache.json"

def create_opportunities_from_newbook():
    print("[TEST] Starting job to fetch completed bookings...")

    try:
        # --- Authentication ---
        user_pass = f"{USERNAME}:{PASSWORD}"
        encoded_credentials = base64.b64encode(user_pass.encode()).decode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_credentials}"
        }

        # --- Date Range (Next 7 Days) ---
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

        response = requests.post(f"{NEWBOOK_API_BASE}/bookings_list", json=payload, headers=headers, verify=False)
        response.raise_for_status()

        completed_bookings = response.json().get("data", [])

    except Exception as e:
        print(f"[ERROR] Failed to fetch completed bookings: {e}")
        return

    if not completed_bookings:
        print("[TEST] No completed bookings found.")
        return

    # --- Load Cache ---
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cached_data = json.load(f)
    else:
        cached_data = {}

    # --- Handle both old (list) and new (dict) formats ---
    if isinstance(cached_data, list):
        old_bookings = {b["booking_id"]: b for b in cached_data}
    else:
        old_bookings = {b["booking_id"]: b for b in cached_data.get("bookings", [])}

    # --- New bookings dict ---
    new_bookings = {b["booking_id"]: b for b in completed_bookings}

    # --- Detect Changes ---
    added = [b for b_id, b in new_bookings.items() if b_id not in old_bookings]
    updated = [
        b
        for b_id, b in new_bookings.items()
        if b_id in old_bookings and b != old_bookings[b_id]
    ]

    # --- Print & Send Only Changes to GHL ---
    if not (added or updated):
        print("[TEST] No new or updated bookings detected — cache is up to date.")
    else:
        if added:
            print(f"[TEST] Added {len(added)} new bookings:")
            for b in added:
                print(f"  ➕ Booking ID: {b.get('booking_id')}")
                send_to_ghl(b)

        if updated:
            print(f"[TEST] Updated {len(updated)} bookings:")
            for b in updated:
                print(f"  🔄 Booking ID: {b.get('booking_id')}")
                send_to_ghl(b)

        # --- Update Cache ---
        with open(CACHE_FILE, "w") as f:
            json.dump({"bookings": completed_bookings}, f, indent=2)

        print("[TEST] Cache updated with latest data.")

    print(f"[TEST] Total Bookings Fetched: {len(completed_bookings)}")

# db_config = {
#     "host": "localhost",
#     "user": "root",            # your DB user
#     "password": "your_password",
#     "database": "ghl_tokens"   # your database name
# }

# # 🧱 --- DATABASE HELPERS ---

# def get_latest_token():
#     """Fetch the latest stored token from DB"""
#     conn = mysql.connector.connect(**db_config)
#     cursor = conn.cursor(dictionary=True)
#     cursor.execute("SELECT * FROM tokens ORDER BY id DESC LIMIT 1")
#     row = cursor.fetchone()
#     conn.close()
#     return row


# def save_tokens(tokens):
#     """Insert new tokens into DB"""
#     conn = mysql.connector.connect(**db_config)
#     cursor = conn.cursor()
#     query = """
#         INSERT INTO tokens (access_token, refresh_token, expires_in, created_at)
#         VALUES (%s, %s, %s, NOW())
#     """
#     cursor.execute(query, (
#         tokens.get("access_token"),
#         tokens.get("refresh_token"),
#         tokens.get("expires_in"),
#     ))
#     conn.commit()
#     conn.close()


# # 🔄 --- TOKEN LOGIC ---

# def refresh_access_token(client_id, client_secret, refresh_token):
#     """Refresh token using refresh_token"""
#     token_url = "https://services.leadconnectorhq.com/oauth/token"
#     data = {
#         "client_id": client_id,
#         "client_secret": client_secret,
#         "grant_type": "refresh_token",
#         "refresh_token": refresh_token
#     }
#     headers = {"Content-Type": "application/x-www-form-urlencoded"}
#     response = requests.post(token_url, data=data, headers=headers)

#     if response.status_code != 200:
#         print("❌ Error refreshing token:", response.text)
#         return None

#     new_tokens = response.json()
#     save_tokens(new_tokens)  # store new access + refresh tokens
#     print("✅ Token refreshed successfully.")
#     return new_tokens.get("access_token")


# def get_valid_access_token(client_id, client_secret):
#     """Main function to always return a valid token"""
#     token_data = get_latest_token()

#     if not token_data:
#         print("⚠️ No token found in DB. You must run authorization first.")
#         return None

#     # Calculate token expiry
#     created_at = token_data["created_at"]
#     expires_in = token_data["expires_in"]
#     expiry_time = created_at + timedelta(seconds=expires_in)

#     if datetime.now() < expiry_time:
#         # 🟢 Still valid
#         print("✅ Access token still valid.")
#         return token_data["access_token"]
#     else:
#         # 🔄 Expired — refresh it
#         print("♻️ Access token expired. Refreshing...")
#         return refresh_access_token(client_id, client_secret, token_data["refresh_token"])

# ✅ Helper function to send data to GHL (example)
# def send_to_ghl(booking):
#     try:
#         ghl_payload = {
#             "name": 'NewBook Opportunity',
#             "status": booking.get("booking_status"),
#             "booking_id": booking.get("booking_id"),
#             "locationId": GHL_LOCATION_ID,
#             "pipelineId": GHL_PIPELINE_ID,
#             "stageId": GHL_STAGE_ID,
#             "monetaryValue": booking.get("booking_total", 0),
#             "customFields": [
#                 {
#                     "id": '6dvNaf7VhkQ9snc5vnjJ',
#                     "field_value": '9039160788'
#                 }
#             ]
#         }

#         headers = {
#             "Authorization": f"Bearer {access_token}",
#             "Content-Type": "application/json",
#             "Accept": "application/json",
#             "Version": "2021-07-28"
#         }
#         # print(f"Api key {GHL_API_KEY}")
#         # print(f"GHL_OPPORTUNITY_URL key {GHL_OPPORTUNITY_URL}")
#         print(f"header {headers}")
#         print(f"[GHL] Sending booking {booking.get('booking_id')} to GHL...")
#         response = requests.post(GHL_OPPORTUNITY_URL, json=ghl_payload, headers=headers)

#         if response.status_code >= 400:
#             print(f"[GHL ERROR] {response.status_code}: {response.text}")
#         else:
#             print(f"[GHL] Booking {booking.get('booking_id')} sent successfully ✅")

#     except Exception as e:
#         print(f"[GHL ERROR] Failed to send booking {booking.get('booking_id')}: {e}")
