import mysql.connector
import os
import json
import base64
import requests
import datetime

from datetime import datetime, timedelta  # add this at the top
from config import REGION, API_KEY, NEWBOOK_API_BASE, GHL_API_KEY, GHL_LOCATION_ID, GHL_PIPELINE_ID, GHL_CLIENT_ID, GHL_CLIENT_SECRET,  DBUSERNAME, DBPASSWORD, DBHOST, DATABASENAME

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
        today = datetime.now()
        period_from = today.strftime("%Y-%m-%d 00:00:00")
        period_to = (today + timedelta(days=7)).strftime("%Y-%m-%d 23:59:59")

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
                access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
                send_to_ghl(b, access_token)


        if updated:
            print(f"[TEST] Updated {len(updated)} bookings:")
            for b in updated:
                print(f"  🔄 Booking ID: {b.get('booking_id')}")
                access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
                send_to_ghl(b, access_token)


        # --- Update Cache ---
        with open(CACHE_FILE, "w") as f:
            json.dump({"bookings": completed_bookings}, f, indent=2)

        print("[TEST] Cache updated with latest data.")

    print(f"[TEST] Total Bookings Fetched: {len(completed_bookings)}")

db_config = {
    "host":'127.0.0.1',
    "user":DBUSERNAME,            # your DB user
    "password":DBPASSWORD,
    "database":DATABASENAME,   # your database name
}

# # 🧱 --- DATABASE HELPERS ---

print(db_config)


def get_token_row():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tokens WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return row


def update_tokens(tokens):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    query = """
        UPDATE tokens
        SET access_token = %s,
            refresh_token = %s,
            expires_in = %s,
            created_at = NOW()
        WHERE id = 1
    """
    cursor.execute(query, (
        tokens.get("access_token"),
        tokens.get("refresh_token"),
        tokens.get("expires_in")
    ))
    conn.commit()
    conn.close()


# # 🔄 --- TOKEN LOGIC ---

def refresh_access_token(client_id, client_secret, refresh_token):
    print("♻️ Refreshing GoHighLevel access token...")
    token_url = "https://services.leadconnectorhq.com/oauth/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(token_url, data=data, headers=headers)

    print("\n📥 Raw Response Status:", response.status_code)
    print("📥 Raw Response Body:", response.text)
    print("📥 Raw Response Body:", response)

    if response.status_code != 200:
        print("❌ Error refreshing token:", response.text)
        return None

    new_tokens = response.json()
    update_tokens(new_tokens)
    print("✅ Token refreshed and updated in DB.")
    return new_tokens.get("access_token")


def get_valid_access_token(client_id, client_secret):
    token_data = get_token_row()

    if not token_data or not token_data["access_token"]:
        print("⚠️ No token found in DB. Run initial authorization first.")
        return None

    created_at = token_data["created_at"]
    expires_in = token_data["expires_in"]
    expiry_time = created_at + timedelta(seconds=expires_in)

    if datetime.now() < expiry_time:
        print("✅ Access token still valid.")
        return token_data["access_token"]
    else:
        print("⏰ Access token expired, refreshing...")
        return refresh_access_token(client_id, client_secret, token_data["refresh_token"])
    
access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)

def get_contact_id(token, location_id, first=None, last=None, email=None, phone=None):
    """
    Creates or retrieves a contact in GoHighLevel and returns the contact ID.
    """
    url = "https://services.leadconnectorhq.com/contacts/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json"
    }

    body = {"locationId": location_id}
    if first:
        body["firstName"] = first
    if last:
        body["lastName"] = last
    if email:
        body["email"] = email
    if phone:
        body["phone"] = phone

    try:
        response = requests.post(url, headers=headers, json=body)
        print(f"[GHL CONTACT] Request Payload: {body}")
        print(f"[GHL CONTACT] Response Status: {response.status_code}")
        print(f"[GHL CONTACT] Response Body: {response.text}")

        data = response.json()

        # 🧠 Handle both creation and "already exists" cases
        if response.status_code == 400 and "meta" in data and "contactId" in data["meta"]:
            return data["meta"]["contactId"]
        elif "contact" in data and "id" in data["contact"]:
            return data["contact"]["id"]
        elif "meta" in data and "contactId" in data["meta"]:
            return data["meta"]["contactId"]
        else:
            print("[GHL CONTACT] Could not extract contact ID from response.")
            return None

    except Exception as e:
        print(f"[GHL CONTACT ERROR] Failed to create/get contact: {e}")
        return None
# ✅ Helper function to send data to GHL (example)
def send_to_ghl(booking, access_token):

    try:
        guest = booking['guests'][0]

        first_name = guest.get("firstname", "")
        last_name = guest.get("lastname", "")
        email = next((g.get("content") for g in guest.get("contact_details", []) if g["type"] == "email"), "")
        phone = next((g.get("content") for g in guest.get("contact_details", []) if g["type"] == "mobile"), "")


        # 🔹 Get or create contact in GHL
        contact_id = get_contact_id(access_token, GHL_LOCATION_ID, first_name, last_name, email, phone)
        arrival_date = (
    datetime.strptime(booking.get("booking_arrival"), "%Y-%m-%d %H:%M:%S").date().isoformat()
    if booking.get("booking_arrival") else ""
)
        ghl_payload = {
            "name": f"{guest.get('firstname', '').strip()} {guest.get('lastname', '').strip()} - {booking.get('site_id', '')} - {booking.get('booking_arrival', '').split(' ')[0]}",
            "status": "open",  # must be one of: open, won, lost, abandoned
            "contactId": contact_id,  # <-- must be a valid contact ID
            "locationId": GHL_LOCATION_ID,
            "pipelineId": GHL_PIPELINE_ID,
            # "stageId": GHL_STAGE_ID,
            "monetaryValue": float(booking.get("booking_total", 0)),

            # ✅ All custom fields must go here
            "customFields": [
                {
                    "id": "arrival_date",
                    "field_value": (
                        datetime.strptime(booking.get("booking_arrival"), "%Y-%m-%d %H:%M:%S").date().isoformat()
                        if booking.get("booking_arrival") else ""
                    )
                },
                {
                    "id": "departure_date",
                    "field_value": (
                        datetime.strptime(booking.get("booking_departure"), "%Y-%m-%d %H:%M:%S").date().isoformat()
                        if booking.get("booking_departure") else ""
                    )
                },
                {"id": "adults", "field_value": str(booking.get("booking_adults", ""))},
                {"id": "children", "field_value": str(booking.get("booking_children", ""))},
                {"id": "infants", "field_value": str(booking.get("booking_infants", ""))},
                {"id": "site_id", "field_value": str(booking.get("site_id", ""))},
                {"id": "total_spend", "field_value": str(booking.get("booking_total", ""))},
                {"id": "promo_code", "field_value": booking.get("discount_code", "")},
                {"id": "booking_status", "field_value": booking.get("booking_status", "")},
                {"id": "pets", "field_value": booking.get("pets", "")},
            ]
        }
        print(f"Api key {ghl_payload}")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Version": "2021-07-28"
        }
        # print(f"Api key {GHL_API_KEY}")
        # print(f"GHL_OPPORTUNITY_URL key {GHL_OPPORTUNITY_URL}")
        print(f"header {headers}")
        print(f"[GHL] Sending booking {booking.get('booking_id')} to GHL...")
        response = requests.post(GHL_OPPORTUNITY_URL, json=ghl_payload, headers=headers)

        if response.status_code >= 400:
            print(f"[GHL ERROR] {response.status_code}: {response.text}")
        else:
            print(f"[GHL] Booking {booking.get('booking_id')} sent successfully ✅")

    except Exception as e:
        print(f"[GHL ERROR] Failed to send booking {booking.get('booking_id')}: {e}")
