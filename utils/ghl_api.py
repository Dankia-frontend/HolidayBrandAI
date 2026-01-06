import mysql.connector
import os
import json
import base64
import requests
import datetime

from datetime import datetime, timedelta  # add this at the top
from config.config import REGION, API_KEY, NEWBOOK_API_BASE, GHL_LOCATION_ID, GHL_PIPELINE_ID, GHL_CLIENT_ID, GHL_CLIENT_SECRET,  DBUSERNAME, DBPASSWORD, DBHOST, DATABASENAME, USERNAME, PASSWORD
from .logger import get_logger
from .ghl_bucketing import bucket_bookings

log = get_logger("GHLIntegration")

GHL_API_VERSION = "2021-07-28"
GHL_OPPORTUNITY_URL = "https://services.leadconnectorhq.com/opportunities/"
CACHE_FILE = "bookings_cache.json"

def create_opportunities_from_newbook():
    """Fetch bookings from NewBook and create opportunities in GHL."""
    try:
        log.info("[OPPORTUNITY JOB] ===== Starting scheduled job to fetch bookings and create opportunities =====")
        print("[TEST] Starting job to fetch completed bookings...")
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
                # filename = f"{list_type}_bookings.json"
                # filepath = os.path.join(os.path.dirname(__file__), "..", filename)
                # with open(filepath, "w") as f:
                #     json.dump(bookings, f, indent=2)
                # print(f"[INFO] Saved {len(bookings)} bookings for {list_type} to {filepath}")
            except Exception as e:
                log.error(f"[OPPORTUNITY JOB] Failed to fetch bookings for {list_type}: {e}")
                print(f"[ERROR] Failed to fetch bookings for {list_type}: {e}")

        # --- Use all bookings from all types for further processing ---
        completed_bookings = []
        for bookings in all_bookings_by_type.values():
            completed_bookings.extend(bookings)
        if not completed_bookings:
            log.info("[OPPORTUNITY JOB] No completed bookings found.")
            print("[TEST] No completed bookings found.")
            return
        
        log.info(f"[OPPORTUNITY JOB] Processing {len(completed_bookings)} total bookings")

        # --- Deduplicate bookings by booking_id ---
        deduped_bookings_dict = {}
        for b in completed_bookings:
            deduped_bookings_dict[b["booking_id"]] = b
        completed_bookings = list(deduped_bookings_dict.values())

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
        removed = [b for b_id, b in old_bookings.items() if b_id not in new_bookings]

        # --- Track deleted booking_ids to avoid duplicate deletes ---
        deleted_booking_ids = set()

        # --- Remove opportunities for bookings that are no longer present or changed stage ---
        for b in removed + updated:
            booking_id = b["booking_id"]
            guests_list = b.get("guests", [])
            if not guests_list:
                log.warning(f"[OPPORTUNITY JOB] Booking {booking_id} has no guests, skipping deletion")
                continue
            guest = guests_list[0]
            guest_firstname = guest.get("firstname", "")
            guest_lastname = guest.get("lastname", "")
            site_name = b.get("site_name", "")
            booking_arrival = b.get("booking_arrival", "")
            # Delete by booking_id (custom field) and by details (name match)
            delete_opportunity_by_booking_id(
                booking_id,
                guest_firstname=guest_firstname,
                guest_lastname=guest_lastname,
                site_name=site_name,
                booking_arrival=booking_arrival
            )
            delete_opportunity_by_booking_details(
                guest_firstname,
                guest_lastname,
                site_name,
                booking_arrival
            )
            deleted_booking_ids.add(booking_id)

        # --- Use new bucket logic ---
        bucket_dict = bucket_bookings(completed_bookings)
        arriving_soon_ids = set()
        arriving_today_ids = set()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # --- Delete GHL opportunities for cancelled bookings (only if not already deleted) ---
        for b in bucket_dict["cancelled"]:
            booking_id = b["booking_id"]
            if booking_id in deleted_booking_ids:
                continue  # Already deleted above
            guests_list = b.get("guests", [])
            if not guests_list:
                log.warning(f"[OPPORTUNITY JOB] Cancelled booking {booking_id} has no guests, skipping deletion")
                continue
            guest = guests_list[0]
            guest_firstname = guest.get("firstname", "")
            guest_lastname = guest.get("lastname", "")
            site_name = b.get("site_name", "")
            booking_arrival = b.get("booking_arrival", "")
            print(f"[CANCELLED] Booking {booking_id} is cancelled, deleting opportunity from GHL.")
            delete_opportunity_by_booking_id(
                booking_id,
                guest_firstname=guest_firstname,
                guest_lastname=guest_lastname,
                site_name=site_name,
                booking_arrival=booking_arrival
            )
            delete_opportunity_by_booking_details(
                guest_firstname,
                guest_lastname,
                site_name,
                booking_arrival
            )
            deleted_booking_ids.add(booking_id)

        # --- Filter out bookings not for today or future in arriving_today ---
        filtered_arriving_today = []
        for b in bucket_dict["arriving_today"]:
            arrival_str = b.get("booking_arrival")
            if arrival_str:
                arrival_dt = datetime.strptime(arrival_str, "%Y-%m-%d %H:%M:%S")
                # Only keep bookings where arrival is today
                if arrival_dt.date() == today.date():
                    filtered_arriving_today.append(b)
                    arriving_today_ids.add(b["booking_id"])
                else:
                    print(f"[CLEANUP] Booking {b['booking_id']} in arriving_today is for previous/future day ({arrival_dt.date()}), deleting opportunity.")
                    delete_opportunity_by_booking_id(b["booking_id"])
            else:
                print(f"[CLEANUP] Booking {b['booking_id']} in arriving_today has no arrival date, deleting opportunity.")
                delete_opportunity_by_booking_id(b["booking_id"])
        bucket_dict["arriving_today"] = filtered_arriving_today

        # --- Filter out bookings not for future in arriving_soon ---
        filtered_arriving_soon = []
        for b in bucket_dict["arriving_soon"]:
            arrival_str = b.get("booking_arrival")
            if arrival_str:
                arrival_dt = datetime.strptime(arrival_str, "%Y-%m-%d %H:%M:%S")
                # Only keep bookings where arrival is after today
                if arrival_dt.date() > today.date():
                    filtered_arriving_soon.append(b)
                    arriving_soon_ids.add(b["booking_id"])
                else:
                    print(f"[CLEANUP] Booking {b['booking_id']} in arriving_soon is for today/past ({arrival_dt.date()}), deleting opportunity.")
                    delete_opportunity_by_booking_id(b["booking_id"])
            else:
                print(f"[CLEANUP] Booking {b['booking_id']} in arriving_soon has no arrival date, deleting opportunity.")
                delete_opportunity_by_booking_id(b["booking_id"])
        bucket_dict["arriving_soon"] = filtered_arriving_soon

        # --- Remove from arriving_soon if now in arriving_today ---
        for booking_id in arriving_soon_ids & arriving_today_ids:
            print(f"[CLEANUP] Booking {booking_id} moved from arriving_soon to arriving_today, deleting from arriving_soon stage.")
            delete_opportunity_by_booking_id(booking_id)

        # --- Remove from arriving_today if person was supposed to arrive yesterday but did not ---
        yesterday = today - timedelta(days=1)
        for b in bucket_dict["arriving_today"]:
            arrival_str = b.get("booking_arrival")
            if arrival_str:
                arrival_dt = datetime.strptime(arrival_str, "%Y-%m-%d %H:%M:%S")
                if arrival_dt.date() == yesterday.date() and b.get("booking_status", "").lower() != "arrived":
                    print(f"[CLEANUP] Booking {b['booking_id']} was supposed to arrive yesterday but did not, deleting from arriving_today stage.")
                    delete_opportunity_by_booking_id(b["booking_id"])

        # --- Process Changes ---
        if not (added or updated):
            log.info("[OPPORTUNITY JOB] No new or updated bookings detected — cache is up to date.")
            print("[TEST] No new or updated bookings detected — cache is up to date.")
        else:
            log.info(f"[OPPORTUNITY JOB] Found {len(added)} new bookings and {len(updated)} updated bookings")
            all_changes = added + updated
            bucket_dict_changes = bucket_bookings(all_changes)
            
            opportunities_created = 0
            opportunities_failed = 0
            
            for bucket, bookings in bucket_dict_changes.items():
                if bookings:
                    # write_bucket_file(bucket, bookings)
                    for b in bookings:
                        if bucket != "cancelled":
                            # --- Delete from GHL if already exists before sending ---
                            guests_list = b.get("guests", [])
                            if not guests_list:
                                log.warning(f"[OPPORTUNITY JOB] Booking {b.get('booking_id', 'unknown')} has no guests, skipping")
                                opportunities_failed += 1
                                continue
                            guest = guests_list[0]
                            guest_firstname = guest.get("firstname", "")
                            guest_lastname = guest.get("lastname", "")
                            site_name = b.get("site_name", "")
                            booking_arrival = b.get("booking_arrival", "")
                            # Delete by booking_id (custom field) and by details (name match) before sending
                            delete_opportunity_by_booking_id(
                                b["booking_id"],
                                guest_firstname=guest_firstname,
                                guest_lastname=guest_lastname,
                                site_name=site_name,
                                booking_arrival=booking_arrival
                            )
                            delete_opportunity_by_booking_details(
                                guest_firstname,
                                guest_lastname,
                                site_name,
                                booking_arrival
                            )
                            access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
                            if not access_token:
                                log.error(f"[OPPORTUNITY JOB] Failed to get valid access token for booking {b['booking_id']}. Skipping GHL sync.")
                                print(f"[GHL ERROR] No valid access token available. Skipping booking {b['booking_id']}")
                                opportunities_failed += 1
                                continue  # Skip this booking instead of sending with None token
                            
                            try:
                                send_to_ghl(b, access_token)
                                opportunities_created += 1
                                log.info(f"[OPPORTUNITY JOB] Successfully sent booking {b['booking_id']} to GHL")
                            except Exception as e:
                                log.error(f"[OPPORTUNITY JOB] Failed to send booking {b['booking_id']} to GHL: {e}")
                                opportunities_failed += 1
                        else:
                            log.debug(f"[OPPORTUNITY JOB] Skipping cancelled booking {b['booking_id']}")
                            print(f"[SKIP] Booking {b['booking_id']} is cancelled or no-show, skipping...")

            log.info(f"[OPPORTUNITY JOB] Job completed: {opportunities_created} opportunities created, {opportunities_failed} failed")

            # --- Update Cache ---
            with open(CACHE_FILE, "w") as f:
                json.dump({"bookings": completed_bookings}, f, indent=2)
            log.info("[OPPORTUNITY JOB] Cache updated with latest data.")
            print("[TEST] Cache updated with latest data.")
        
        log.info(f"[OPPORTUNITY JOB] ===== Job finished. Total bookings processed: {len(completed_bookings)} =====")
        print(f"[TEST] Total Bookings Fetched: {len(completed_bookings)}")
    except Exception as e:
        log.exception(f"[OPPORTUNITY JOB] CRITICAL: Job failed with exception: {e}")
        print(f"[CRITICAL ERROR] Job failed: {e}")
        raise  # Re-raise to ensure scheduler knows it failed


db_config = {
    "host":DBHOST,
    "user":DBUSERNAME,            # your DB user
    "password":DBPASSWORD,
    "database":DATABASENAME,   # your database name
    "port":3306
}

# # 🧱 --- DATABASE HELPERS ---

def get_ghl_token():
    """
    Get the GoHighLevel Private Integration Token.
    This is a static token that doesn't expire.
    """
    from config.config import GHL_PRIVATE_INTEGRATION_TOKEN
    
    if not GHL_PRIVATE_INTEGRATION_TOKEN:
        error_msg = "⚠️ GHL_PRIVATE_INTEGRATION_TOKEN is not set in .env file"
        log.error(error_msg)
        print(error_msg)
        return None
    
    return GHL_PRIVATE_INTEGRATION_TOKEN


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
    log.info("♻️ Refreshing GoHighLevel access token...")
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
    log.info(f"Token refresh response status: {response.status_code}")
    print("\n📥 Raw Response Status:", response.status_code)
    print("📥 Raw Response Body:", response.text)

    if response.status_code != 200:
        error_msg = f"Error refreshing token: {response.status_code} - {response.text}"
        log.error(error_msg)
        print(f"❌ {error_msg}")
        return None

    try:
        new_tokens = response.json()
        log.info("✅ Token refreshed successfully")
        print("✅ Token refreshed successfully.", new_tokens)
        update_tokens(new_tokens)
        log.info("✅ Token refreshed and updated in DB")
        print("✅ Token refreshed and updated in DB.")
        return new_tokens.get("access_token")
    except Exception as e:
        error_msg = f"Failed to parse token response: {e}"
        log.error(error_msg)
        print(f"❌ {error_msg}")
        return None


def get_valid_access_token(client_id, client_secret):
    token_data = get_token_row()
    if not token_data or not token_data["access_token"]:
        error_msg = "⚠️ No token found in DB. Run initial authorization first."
        log.error(error_msg)
        print(error_msg)
        return None

    created_at = token_data["created_at"]
    expire_in = token_data["expire_in"]
    expiry_time = created_at + timedelta(seconds=expire_in)

    # Only refresh if expired
    if datetime.now() < expiry_time:
        log.debug("✅ Access token still valid.")
        print("✅ Access token still valid.")
        return token_data["access_token"]
    else:
        log.info("⏰ Access token expired, refreshing...")
        print("⏰ Access token expired, refreshing...")
        refreshed_token = refresh_access_token(client_id, client_secret, token_data["refresh_token"])
        if not refreshed_token:
            log.error("⚠️ Failed to refresh access token. Token refresh returned None.")
            print("⚠️ Failed to refresh access token. Token refresh returned None.")
        return refreshed_token
    
# access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
access_token = get_ghl_token()

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
def send_to_ghl(booking, access_token, guest_info=None):
    if not access_token:
        log.error(f"[GHL] Cannot send booking {booking.get('booking_id')} - access token is None")
        print(f"[GHL ERROR] Access token is None. Cannot send booking {booking.get('booking_id')}")
        return

    try:
        # Use guest_info if provided, else fallback to booking['guests'][0]
        if guest_info:
            first_name = guest_info.get("firstName", "")
            last_name = guest_info.get("lastName", "")
            email = guest_info.get("email", "")
            phone = guest_info.get("phone", "")
        else:
            guests_list = booking.get('guests', [])
            if not guests_list:
                log.error(f"[GHL] Booking {booking.get('booking_id', 'unknown')} has no guests, cannot create opportunity")
                print(f"[GHL ERROR] Booking has no guests, cannot create opportunity")
                return
            guest = guests_list[0]
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
            elif booking.get("booking_status", "").lower() == "arrived" and departure_dt >= tomorrow:
                stage_id = '99912993-0e69-48f9-9943-096ae68408d7'
            elif arrival_dt >= today and arrival_dt < tomorrow:
                stage_id = 'b429a8e9-e73e-4590-b4c5-8ea1d65e0daf'
            elif booking.get("booking_status", "").lower() == "arrived" and departure_dt >= today and departure_dt < day_after:
                stage_id = 'fc60b2fa-8c2d-4202-9347-ac2dd32a0e43'
            elif booking.get("booking_status", "").lower() == "departed":
                stage_id = '8b54e5e5-27f3-463a-9d81-890c6dfd27eb'
        print(f"Contact ID: {contact_id}, Stage ID: {stage_id}")
        ghl_payload = {
            "name": f"{guest.get('firstname', '').strip()} {guest.get('lastname', '').strip()} - {booking.get('site_name', '')} - {booking.get('booking_arrival', '').split(' ')[0]}",
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
                {"id": "site_id", "field_value": str(booking.get("site_name", ""))},
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
    access_token = get_ghl_token()
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
    access_token = get_ghl_token()
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

def delete_opportunity_by_booking_id(booking_id, guest_firstname=None, guest_lastname=None, site_name=None, booking_arrival=None):
    """
    Deletes all opportunities in GHL that match the booking_id in name or custom fields.
    If guest_firstname, guest_lastname, site_name, and booking_arrival are provided,
    will match the exact opportunity name format.
    """
    access_token = get_ghl_token()
    if not access_token:
        print("No valid access token. Aborting opportunity deletion for booking_id:", booking_id)
        return

    base_url = 'https://services.leadconnectorhq.com'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Version': '2021-07-28'
    }
    url = f"{base_url}/opportunities/search?location_id={GHL_LOCATION_ID}&pipeline_id={GHL_PIPELINE_ID}&limit=100"
    found = False

    # Build expected name if all info provided
    expected_name = None
    if guest_firstname and guest_lastname and site_name and booking_arrival:
        expected_name = f"{guest_firstname.strip()} {guest_lastname.strip()} - {site_name} - {booking_arrival.split(' ')[0]}"

    while url:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"[GHL DELETE] Failed to fetch opportunities: {resp.status_code} {resp.text}")
            break
        data = resp.json()
        for opp in data.get('opportunities', []):
            name = opp.get('name', '')
            # Match by expected name if possible, otherwise fallback to booking_id in name or custom fields
            exact_name_match = expected_name and name == expected_name
            custom_match = any(
                (str(f.get('field_value')) == str(booking_id))
                for f in opp.get('customFields', [])
                if f.get('id') == 'site_id' or f.get('id') == 'booking_id'
            )
            # Remove fallback to booking_id in name, only use exact name or custom field match
            if exact_name_match or custom_match:
                opp_id = opp.get('id')
                del_url = f"{base_url}/opportunities/{opp_id}"
                del_resp = requests.delete(del_url, headers=headers)
                print(f"Deleted opportunity for booking_id {booking_id} ({name}): {'Success' if del_resp.status_code == 200 else 'Failed'}")
                found = True
        url = data.get('meta', {}).get('nextPageUrl')
    if not found:
        print(f"No GHL opportunity found for booking_id {booking_id}.")

def delete_opportunity_by_booking_details(guest_firstname, guest_lastname, site_name, booking_arrival):
    """
    Deletes all opportunities in GHL that match the exact opportunity name format.
    """
    access_token = get_ghl_token()
    if not access_token:
        print("No valid access token. Aborting opportunity deletion for details:", guest_firstname, guest_lastname, site_name, booking_arrival)
        return

    base_url = 'https://services.leadconnectorhq.com'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Version': '2021-07-28'
    }
    url = f"{base_url}/opportunities/search?location_id={GHL_LOCATION_ID}&pipeline_id={GHL_PIPELINE_ID}&limit=100"
    found = False

    expected_name = f"{guest_firstname.strip()} {guest_lastname.strip()} - {site_name} - {booking_arrival.split(' ')[0]}"

    while url:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"[GHL DELETE] Failed to fetch opportunities: {resp.status_code} {resp.text}")
            break
        data = resp.json()
        for opp in data.get('opportunities', []):
            name = opp.get('name', '')
            if name == expected_name:
                opp_id = opp.get('id')
                del_url = f"{base_url}/opportunities/{opp_id}"
                del_resp = requests.delete(del_url, headers=headers)
                print(f"Deleted opportunity ({name}): {'Success' if del_resp.status_code == 200 else 'Failed'}")
                found = True
        url = data.get('meta', {}).get('nextPageUrl')
    if not found:
        print(f"No GHL opportunity found for name: {expected_name}")

def daily_cleanup():
    """
    Call at the start of each day to clean up GHL pipeline stages.
    """
    print("[DAILY CLEANUP] Removing all opportunities from arriving_soon and arriving_today stages.")
    delete_opportunities_in_stage('3aeae130-f411-4ac7-bcca-271291fdc3b9')  # arriving_soon
    delete_opportunities_in_stage('b429a8e9-e73e-4590-b4c5-8ea1d65e0daf')  # arriving_today
