import mysql.connector
import os
import json
import base64
import requests
import datetime

from datetime import datetime, timedelta  # add this at the top
from config import REGION, API_KEY, NEWBOOK_API_BASE, GHL_API_KEY, GHL_LOCATION_ID, GHL_PIPELINE_ID, GHL_CLIENT_ID, GHL_CLIENT_SECRET,  DBUSERNAME, DBPASSWORD, DBHOST, DATABASENAME
from .logger import get_logger

log = get_logger("GHLIntegration")

USERNAME = "ParkPA"
PASSWORD = "ZEVaWP4ZaVT@MDTb"
GHL_API_VERSION = "2021-07-28"
GHL_OPPORTUNITY_URL = "https://services.leadconnectorhq.com/opportunities/"
CACHE_FILE = "bookings_cache.json"

# --- Helper to write bucket bookings to file ---
def write_bucket_file(bucket, bookings):
    """
    Writes bookings for a specific bucket to its own file.
    If the file doesn't exist, it is created automatically.
    """
    filename = f"{bucket}_bookings.json"
    filepath = os.path.join(os.path.dirname(__file__), "..", filename)
    with open(filepath, "w") as f:
        json.dump(bookings, f, indent=2)
    print(f"[BUCKET FILE] {bucket}: {len(bookings)} bookings written to {filepath}")

def bucket_bookings(bookings):
    """
    Classifies bookings into buckets based on arrival/departure/status.
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    dayafter = today + timedelta(days=2)
    seven_days = today + timedelta(days=7)

    buckets = {
        "arriving_soon": [],
        "arriving_today": [],
        "staying_now": [],
        "checking_out": [],
        "checked_out": [],
        "cancelled": []
    }

    for b in bookings:
        st = (b.get("booking_status") or "").lower().strip()
        arr_str = b.get("booking_arrival")
        dep_str = b.get("booking_departure")
        arr = datetime.strptime(arr_str, "%Y-%m-%d %H:%M:%S") if arr_str else None
        dep = datetime.strptime(dep_str, "%Y-%m-%d %H:%M:%S") if dep_str else None

        if st in ["cancelled", "no_show", "no show"]:
            buckets["cancelled"].append(b)
        elif st == "departed":
            buckets["checked_out"].append(b)
        elif st == "arrived" and dep and dep >= tomorrow:
            buckets["staying_now"].append(b)
        elif st == "arrived" and dep and dep >= today and dep < dayafter:
            buckets["checking_out"].append(b)
        elif arr and arr >= today and arr < tomorrow:
            buckets["arriving_today"].append(b)
        elif arr and arr >= tomorrow and arr <= seven_days:
            buckets["arriving_soon"].append(b)
    return buckets

def create_opportunities_from_newbook():
    # delete_opportunities_in_stage('3aeae130-f411-4ac7-bcca-271291fdc3b9')
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
        period_to = (today + timedelta(days=30)).strftime("%Y-%m-%d 23:59:59")

        list_types = [
            "arrived",
            "arriving",
            "cancelled",
            "departed",
            "departing",
            "inhouse",
            "placed",
            "staying",
            "no_show",
            "all"
        ]

        all_bookings_by_type = {}

        for list_type in list_types:
            payload = {
                "region": REGION,
                "api_key": API_KEY,
                "list_type": list_type
            }
            if list_type != "inhouse":
                payload["period_from"] = period_from
                payload["period_to"] = period_to

            try:
                print(f"[INFO] Fetching bookings for list_type: {list_type}")
                response = requests.post(
                    f"{NEWBOOK_API_BASE}/bookings_list",
                    json=payload,
                    headers=headers,
                    verify=False,  # ⚠️ set to True in production
                    timeout=15
                )
                response.raise_for_status()
                bookings = response.json().get("data", [])
                all_bookings_by_type[list_type] = bookings
                # Optionally save each type to its own file:
                filename = f"{list_type}_bookings.json"
                filepath = os.path.join(os.path.dirname(__file__), "..", filename)
                with open(filepath, "w") as f:
                    json.dump(bookings, f, indent=2)
                print(f"[INFO] Saved {len(bookings)} bookings for {list_type} to {filepath}")
            except Exception as e:
                print(f"[ERROR] Failed to fetch bookings for {list_type}: {e}")

    except Exception as e:
        log.exception(f"Failed to fetch completed bookings: {e}")
        print(f"[ERROR] Failed to fetch completed bookings: {e}")
        return

    # --- Use all bookings from all types for further processing ---
    completed_bookings = []
    for bookings in all_bookings_by_type.values():
        completed_bookings.extend(bookings)
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
    updated = [b for b_id, b in new_bookings.items() if b_id in old_bookings and b != old_bookings[b_id]]

    # --- Process Changes ---
    if not (added or updated):
        print("[TEST] No new or updated bookings detected — cache is up to date.")
    else:
        all_changes = added + updated

        # --- Use new bucket logic ---
        bucket_dict = bucket_bookings(all_changes)

        for bucket, bookings in bucket_dict.items():
            if bookings:
                # write_bucket_file(bucket, bookings)
                for b in bookings:
                    # Only send non-cancelled bookings to GHL
                    if bucket != "cancelled":
                        access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
                        send_to_ghl(b, access_token)
                    else:
                        print(f"[SKIP] Booking {b['booking_id']} is cancelled or no-show, skipping...")

        # --- Update Cache ---
        with open(CACHE_FILE, "w") as f:
            json.dump({"bookings": completed_bookings}, f, indent=2)
        print("[TEST] Cache updated with latest data.")
    print(f"[TEST] Total Bookings Fetched: {len(completed_bookings)}")


db_config = {
    "host":DBHOST,
    "user":DBUSERNAME,            # your DB user
    "password":DBPASSWORD,
    "database":DATABASENAME,   # your database name
    "port":3306
}

# # 🧱 --- DATABASE HELPERS ---



def get_token_row():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
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
            expire_in = %s,
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
    print("✅ Token refreshed successfully.", response.json())
    update_tokens(new_tokens)
    print("✅ Token refreshed and updated in DB.")
    return new_tokens.get("access_token")


def get_valid_access_token(client_id, client_secret):
    token_data = get_token_row()



    if not token_data or not token_data["access_token"]:
        print("⚠️ No token found in DB. Run initial authorization first.")
        return None

    created_at = token_data["created_at"]
    expire_in = token_data["expire_in"]
    expiry_time = created_at + timedelta(seconds=expire_in)

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
        stage_id = None
        arrival = booking.get("booking_arrival")
        departure = booking.get("booking_departure")
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)
        seven_days = today + timedelta(days=7)

        
        if arrival:
            arrival_dt = datetime.strptime(arrival, "%Y-%m-%d %H:%M:%S")
            departure_dt = datetime.strptime(departure, "%Y-%m-%d %H:%M:%S") if departure else arrival_dt
            if arrival_dt >= tomorrow and arrival_dt <= seven_days:
                stage_id = '3aeae130-f411-4ac7-bcca-271291fdc3b9'
            elif arrival_dt >= today and arrival_dt < tomorrow:
                stage_id = 'b429a8e9-e73e-4590-b4c5-8ea1d65e0daf'
            elif booking.get("booking_status", "").lower() == "arrived" and departure_dt >= tomorrow:
                stage_id = '99912993-0e69-48f9-9943-096ae68408d7'
            elif booking.get("booking_status", "").lower() == "arrived" and departure_dt >= today and departure_dt < day_after:
                stage_id = 'fc60b2fa-8c2d-4202-9347-ac2dd32a0e43'
            elif booking.get("booking_status", "").lower() == "departed":
                stage_id = '8b54e5e5-27f3-463a-9d81-890c6dfd27eb'
        print(f"Contact ID: {contact_id}, Stage ID: {stage_id}")
        ghl_payload = {
            "name": f"{guest.get('firstname', '').strip()} {guest.get('lastname', '').strip()} - {booking.get('site_id', '')} - {booking.get('booking_arrival', '').split(' ')[0]}",
            "status": "open",  # must be one of: open, won, lost, abandoned
            "contactId": contact_id,  # <-- must be a valid contact ID
            "locationId": GHL_LOCATION_ID,
            "pipelineId": GHL_PIPELINE_ID,
            "pipelineStageId": stage_id,
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
        
        print(f"[GHL] Sending booking {booking.get('booking_id')} to GHL...")
        log.info(f"Sending data to GHL for booking: {ghl_payload.get('name')}")
        response = requests.post(GHL_OPPORTUNITY_URL, json=ghl_payload, headers=headers)

        if response.status_code >= 400:
            print(f"[GHL ERROR] {response.status_code}: {response.text}")
            log.error(f"GHL Error Response: {response.text}")
        else:
            print(f"[GHL] Booking {booking.get('booking_id')} sent successfully ✅")

    except Exception as e:
        log.exception("Error during GHL integration")
        print(f"[GHL ERROR] Failed to send booking {booking.get('booking_id')}: {e}")

def save_opportunities_for_stage(stage_id):
    """
    Fetches all opportunities for a given stage_id (handles pagination)
    and saves them to a JSON file named {stage_id}_opportunities.json.
    """
    access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
    if not access_token:
        print("No valid access token. Aborting fetch.")
        return

    base_url = 'https://services.leadconnectorhq.com'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Version': '2021-07-28'
    }
    url = f"{base_url}/opportunities/search?location_id={GHL_LOCATION_ID}&pipeline_id={GHL_PIPELINE_ID}&pipeline_stage_id={stage_id}&limit=100"
    opportunities = []
    while url:
        resp = requests.get(url, headers=headers)
        data = resp.json()
        opportunities.extend(data.get('opportunities', []))
        url = data.get('meta', {}).get('nextPageUrl')
    filename = f"{stage_id}_opportunities.json"
    filepath = os.path.join(os.path.dirname(__file__), "..", filename)
    with open(filepath, "w") as f:
        json.dump(opportunities, f, indent=2)
    print(f"Saved {len(opportunities)} opportunities for stage {stage_id} to {filepath}")

def delete_opportunities_in_stage(stage_id):
    """
    Deletes all opportunities in the given pipeline stage.
    Also saves the opportunities to a JSON file before deletion.
    """
    save_opportunities_for_stage(stage_id)
    access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
    if not access_token:
        print("No valid access token. Aborting opportunity deletion.")
        return

    base_url = 'https://services.leadconnectorhq.com'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Version': '2021-07-28'
    }
    url = f"{base_url}/opportunities/search?location_id={GHL_LOCATION_ID}&pipeline_id={GHL_PIPELINE_ID}&pipeline_stage_id={stage_id}&limit=100"
    opportunities = []
    while url:
        resp = requests.get(url, headers=headers)
        data = resp.json()
        opportunities.extend(data.get('opportunities', []))
        url = data.get('meta', {}).get('nextPageUrl')
    print(f"Found {len(opportunities)} opportunities in stage {stage_id}.")
    for opp in opportunities:
        opp_id = opp.get('id')
        name = opp.get('name')
        if opp_id:
            del_url = f"{base_url}/opportunities/{opp_id}"
            resp = requests.delete(del_url, headers=headers)
            print(f"Deleted {name} (ID: {opp_id}): {'Success' if resp.status_code == 200 else 'Failed'}")

      # <-- replace with actual stage id or call as needed
