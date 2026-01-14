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

# Test mode configuration - set to True to enable test mode
TEST_MODE = os.getenv("GHL_TEST_MODE", "false").lower() == "true"
DRY_RUN_MODE = os.getenv("GHL_DRY_RUN_MODE", "false").lower() == "true"  # Simulate without making changes
TEST_PIPELINE_ID = os.getenv("GHL_TEST_PIPELINE_ID", None)  # Optional: Use test pipeline if provided
TEST_LOCATION_ID = os.getenv("GHL_TEST_LOCATION_ID", None)  # Optional: Use test location if provided

# If test mode is enabled but no test IDs provided, use production (with warnings)
if TEST_MODE and not TEST_PIPELINE_ID:
    TEST_PIPELINE_ID = GHL_PIPELINE_ID
if TEST_MODE and not TEST_LOCATION_ID:
    TEST_LOCATION_ID = GHL_LOCATION_ID

def create_opportunities_from_newbook():
    """Fetch bookings from NewBook and create opportunities in GHL."""
    # Initialize counters at the start to ensure they're always defined
    opportunities_created = 0
    opportunities_updated = 0
    opportunities_failed = 0
    
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
            log.info(f"[OPPORTUNITY JOB] Job completed: {opportunities_created} opportunities created, {opportunities_updated} opportunities updated, {opportunities_failed} failed")
            print(f"[TEST] Job completed: {opportunities_created} created, {opportunities_updated} updated, {opportunities_failed} failed")
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

        # --- Remove opportunities for bookings that are no longer present in NewBook ---
        # Only delete if booking was completely removed, not if it was updated
        for b in removed:
            booking_id = b["booking_id"]
            guests_list = b.get("guests", [])
            if not guests_list:
                log.warning(f"[OPPORTUNITY JOB] Removed booking {booking_id} has no guests, skipping deletion")
                continue
            guest = guests_list[0]
            guest_firstname = guest.get("firstname", "")
            guest_lastname = guest.get("lastname", "")
            site_name = b.get("site_name", "")
            booking_arrival = b.get("booking_arrival", "")
            log.info(f"[OPPORTUNITY JOB] Booking {booking_id} no longer exists in NewBook, deleting opportunity")
            print(f"[CLEANUP] Booking {booking_id} removed from NewBook, deleting opportunity")
            delete_opportunity_by_booking_id(
                booking_id,
                guest_firstname=guest_firstname,
                guest_lastname=guest_lastname,
                site_name=site_name,
                booking_arrival=booking_arrival
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
        # Note: Opportunities will be automatically moved to correct stage by send_to_ghl()
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
                    # Booking moved to different stage - will be handled by send_to_ghl()
                    log.debug(f"[OPPORTUNITY JOB] Booking {b['booking_id']} in arriving_today is for {arrival_dt.date()}, will be moved to correct stage")
            else:
                log.warning(f"[OPPORTUNITY JOB] Booking {b['booking_id']} in arriving_today has no arrival date")
        bucket_dict["arriving_today"] = filtered_arriving_today

        # --- Filter out bookings not for future in arriving_soon ---
        # Note: Opportunities will be automatically moved to correct stage by send_to_ghl()
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
                    # Booking moved to different stage - will be handled by send_to_ghl()
                    log.debug(f"[OPPORTUNITY JOB] Booking {b['booking_id']} in arriving_soon is for {arrival_dt.date()}, will be moved to correct stage")
            else:
                log.warning(f"[OPPORTUNITY JOB] Booking {b['booking_id']} in arriving_soon has no arrival date")
        bucket_dict["arriving_soon"] = filtered_arriving_soon

        # Note: Bookings that moved between stages will be automatically updated by send_to_ghl()
        # No need to manually delete and recreate

        # --- Process Changes ---
        # Get access token once for all bookings (more efficient)
        access_token = get_ghl_token()
        if not access_token:
            access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
        
        if not access_token:
            log.error("[OPPORTUNITY JOB] Failed to get valid access token. Skipping GHL sync.")
            print("[GHL ERROR] No valid access token available. Cannot process bookings.")
            log.info(f"[OPPORTUNITY JOB] Job completed: {opportunities_created} opportunities created, {opportunities_updated} opportunities updated, {opportunities_failed} failed")
            print(f"[TEST] Job completed: {opportunities_created} created, {opportunities_updated} updated, {opportunities_failed} failed")
            return
        
        # Process ALL bookings (not just added/updated) to handle stage transitions
        # This ensures bookings that haven't changed in NewBook but need stage updates are processed
        # IMPORTANT: send_to_ghl() will:
        #   1. Check if opportunity exists by name matching
        #   2. If exists and stage needs to change -> UPDATE via PUT request (same opportunity ID)
        #   3. If exists and stage is correct -> Skip (no API call)
        #   4. If doesn't exist -> CREATE new opportunity
        # This ensures opportunities are UPDATED (not deleted/recreated) when stages change
        if not (added or updated):
            log.info("[OPPORTUNITY JOB] No new or updated bookings detected — cache is up to date.")
            print("[TEST] No new or updated bookings detected — cache is up to date.")
            log.info("[OPPORTUNITY JOB] Processing all bookings to check for stage updates...")
        
        # Process all non-cancelled bookings to ensure stage updates happen
        # Filter out cancelled bookings (already handled above)
        bookings_to_process = [b for b in completed_bookings if b["booking_id"] not in deleted_booking_ids]
        
        # Bucket all bookings to process
        bucket_dict_to_process = bucket_bookings(bookings_to_process)
        
        for bucket, bookings in bucket_dict_to_process.items():
            if bookings:
                for b in bookings:
                    if bucket != "cancelled":
                        guests_list = b.get("guests", [])
                        if not guests_list:
                            log.warning(f"[OPPORTUNITY JOB] Booking {b.get('booking_id', 'unknown')} has no guests, skipping")
                            opportunities_failed += 1
                            continue
                        
                        # send_to_ghl will automatically check if opportunity exists and update it, or create new
                        try:
                            # Check if opportunity exists before calling send_to_ghl to track create vs update
                            booking_id = b.get('booking_id')
                            guest = guests_list[0]
                            guest_firstname = guest.get("firstname", "")
                            guest_lastname = guest.get("lastname", "")
                            site_name = b.get("site_name", "")
                            booking_arrival = b.get("booking_arrival", "")
                            
                            existing_opp_id, _ = find_opportunity_by_booking_id(
                                booking_id,
                                guest_firstname=guest_firstname,
                                guest_lastname=guest_lastname,
                                site_name=site_name,
                                booking_arrival=booking_arrival,
                                access_token=access_token
                            )
                            
                            success = send_to_ghl(b, access_token)
                            if success:
                                if existing_opp_id:
                                    opportunities_updated += 1
                                    log.info(f"[OPPORTUNITY JOB] Successfully updated booking {b['booking_id']} in GHL")
                                else:
                                    opportunities_created += 1
                                    log.info(f"[OPPORTUNITY JOB] Successfully created booking {b['booking_id']} in GHL")
                            else:
                                opportunities_failed += 1
                                log.warning(f"[OPPORTUNITY JOB] Failed to process booking {b['booking_id']} in GHL")
                        except Exception as e:
                            log.error(f"[OPPORTUNITY JOB] Exception processing booking {b['booking_id']} in GHL: {e}")
                            opportunities_failed += 1
                    else:
                        log.debug(f"[OPPORTUNITY JOB] Skipping cancelled booking {b['booking_id']}")
                        print(f"[SKIP] Booking {b['booking_id']} is cancelled or no-show, skipping...")

        log.info(f"[OPPORTUNITY JOB] Job completed: {opportunities_created} opportunities created, {opportunities_updated} opportunities updated, {opportunities_failed} failed")
        print(f"[TEST] Job completed: {opportunities_created} created, {opportunities_updated} updated, {opportunities_failed} failed")

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
def get_stage_id_for_booking(booking):
    """
    Determines the appropriate stage ID for a booking based on arrival/departure dates and status.
    Returns the stage_id string.
    """
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
            return '3aeae130-f411-4ac7-bcca-271291fdc3b9'  # arriving_soon
        elif booking.get("booking_status", "").lower() == "arrived" and departure_dt >= tomorrow:
            return '99912993-0e69-48f9-9943-096ae68408d7'  # staying_now
        elif arrival_dt >= today and arrival_dt < tomorrow:
            return 'b429a8e9-e73e-4590-b4c5-8ea1d65e0daf'  # arriving_today
        elif booking.get("booking_status", "").lower() == "arrived" and departure_dt >= today and departure_dt < day_after:
            return 'fc60b2fa-8c2d-4202-9347-ac2dd32a0e43'  # checking_out
        elif booking.get("booking_status", "").lower() == "departed":
            return '8b54e5e5-27f3-463a-9d81-890c6dfd27eb'  # checked_out
    
    return None


# ✅ Helper function to send data to GHL (creates or updates opportunity)
def send_to_ghl(booking, access_token, guest_info=None):
    """
    Creates or updates an opportunity in GHL.
    If an opportunity with the same booking_id exists, it will be updated instead of creating a new one.
    
    In DRY_RUN_MODE, simulates the operation without making actual API calls.
    """
    if not access_token:
        log.error(f"[GHL] Cannot send booking {booking.get('booking_id')} - access token is None")
        print(f"[GHL ERROR] Access token is None. Cannot send booking {booking.get('booking_id')}")
        return False
    
    # Dry run mode - simulate without making changes
    if DRY_RUN_MODE:
        booking_id = booking.get('booking_id')
        stage_id = get_stage_id_for_booking(booking)
        print(f"[DRY RUN] Would process booking {booking_id}")
        print(f"[DRY RUN]   - Stage: {stage_id}")
        
        # Get guest info for name matching
        guests_list = booking.get('guests', [])
        if guests_list:
            guest = guests_list[0]
            guest_firstname = guest.get("firstname", "")
            guest_lastname = guest.get("lastname", "")
        else:
            guest_firstname = ""
            guest_lastname = ""
        
        site_name = booking.get("site_name", "")
        booking_arrival = booking.get("booking_arrival", "")
        
        print(f"[DRY RUN]   - Guest: {guest_firstname} {guest_lastname}")
        print(f"[DRY RUN]   - Arrival: {booking_arrival}")
        
        # Check if would update or create
        opp_id, _ = find_opportunity_by_booking_id(
            booking_id,
            guest_firstname=guest_firstname,
            guest_lastname=guest_lastname,
            site_name=site_name,
            booking_arrival=booking_arrival,
            access_token=access_token
        )
        if opp_id:
            print(f"[DRY RUN]   - Action: UPDATE existing opportunity {opp_id}")
        else:
            print(f"[DRY RUN]   - Action: CREATE new opportunity")
        return True

    try:
        booking_id = booking.get('booking_id')
        
        # Use guest_info if provided, else fallback to booking['guests'][0]
        if guest_info:
            first_name = guest_info.get("firstName", "")
            last_name = guest_info.get("lastName", "")
            email = guest_info.get("email", "")
            phone = guest_info.get("phone", "")
        else:
            guests_list = booking.get('guests', [])
            if not guests_list:
                log.error(f"[GHL] Booking {booking_id or 'unknown'} has no guests, cannot create opportunity")
                print(f"[GHL ERROR] Booking has no guests, cannot create opportunity")
                return False
            guest = guests_list[0]
            first_name = guest.get("firstname", "")
            last_name = guest.get("lastname", "")
            email = next((g.get("content") for g in guest.get("contact_details", []) if g["type"] == "email"), "")
            phone = next((g.get("content") for g in guest.get("contact_details", []) if g["type"] == "mobile"), "")

        # Get or create contact in GHL
        location_id = TEST_LOCATION_ID if TEST_MODE else GHL_LOCATION_ID
        if not location_id:
            log.error(f"[GHL] GHL_LOCATION_ID is not set. Cannot create/update opportunity for booking {booking_id}")
            print(f"[GHL ERROR] GHL_LOCATION_ID is not set in .env file. Please configure it.")
            return False
        
        contact_id = get_contact_id(access_token, location_id, first_name, last_name, email, phone)
        if not contact_id:
            log.error(f"[GHL] Failed to get/create contact for booking {booking_id}")
            return False

        # Determine stage ID
        stage_id = get_stage_id_for_booking(booking)
        if not stage_id:
            log.warning(f"[GHL] Could not determine stage for booking {booking_id}")
            print(f"[GHL WARNING] Could not determine stage for booking {booking_id}")
            return False

        # Check if opportunity already exists
        guest_firstname = first_name
        guest_lastname = last_name
        site_name = booking.get("site_name", "")
        booking_arrival = booking.get("booking_arrival", "")
        
        # In dry-run mode, skip the actual API call if location_id is missing
        existing_opp_id = None
        existing_opp = None
        if not DRY_RUN_MODE or location_id:
            existing_opp_id, existing_opp = find_opportunity_by_booking_id(
                booking_id,
                guest_firstname=guest_firstname,
                guest_lastname=guest_lastname,
                site_name=site_name,
                booking_arrival=booking_arrival,
                access_token=access_token
            )

        # If opportunity exists, update it instead of creating new
        if existing_opp_id:
            current_stage = existing_opp.get('pipelineStageId') if existing_opp else None
            if current_stage == stage_id:
                log.debug(f"[GHL] Opportunity {existing_opp_id} already in correct stage {stage_id}, skipping update")
                print(f"[GHL] ✅ Opportunity {existing_opp_id} already in correct stage {stage_id}, no update needed")
                return True
            else:
                # Stage change detected - UPDATE the opportunity (not delete/recreate)
                log.info(f"[GHL UPDATE] Stage change detected for opportunity {existing_opp_id}")
                log.info(f"[GHL UPDATE]   Current stage: {current_stage}")
                log.info(f"[GHL UPDATE]   New stage: {stage_id}")
                log.info(f"[GHL UPDATE]   Booking ID: {booking_id}")
                log.info(f"[GHL UPDATE]   Action: UPDATING existing opportunity (not deleting/recreating)")
                print(f"[GHL UPDATE] 🔄 UPDATING opportunity {existing_opp_id} (STAGE CHANGE)")
                print(f"[GHL UPDATE]   From stage: {current_stage}")
                print(f"[GHL UPDATE]   To stage: {stage_id}")
                print(f"[GHL UPDATE]   Booking ID: {booking_id}")
                print(f"[GHL UPDATE]   Method: PUT request (update, not delete/recreate)")
                result = update_opportunity(existing_opp_id, booking, access_token, stage_id, contact_id, existing_opp)
                if result:
                    log.info(f"[GHL UPDATE] ✅ Successfully UPDATED opportunity {existing_opp_id} - stage changed from {current_stage} to {stage_id}")
                    print(f"[GHL UPDATE] ✅ Successfully UPDATED opportunity (same ID: {existing_opp_id})")
                    print(f"[GHL UPDATE] ✅ Opportunity was UPDATED, not deleted/recreated")
                else:
                    log.error(f"[GHL UPDATE] ❌ Failed to update opportunity {existing_opp_id}")
                    print(f"[GHL UPDATE] ❌ Failed to update opportunity")
                return result

        # Opportunity doesn't exist, create new one
        pipeline_id = TEST_PIPELINE_ID if TEST_MODE else GHL_PIPELINE_ID
        
        if not pipeline_id:
            log.error(f"[GHL] GHL_PIPELINE_ID is not set. Cannot create opportunity for booking {booking_id}")
            print(f"[GHL ERROR] GHL_PIPELINE_ID is not set in .env file. Please configure it.")
            return False
        
        ghl_payload = {
            "name": f"{first_name.strip()} {last_name.strip()} - {site_name} - {booking_arrival.split(' ')[0] if booking_arrival else ''}",
            "status": "open",
            "contactId": contact_id,
            "locationId": location_id,
            "pipelineId": pipeline_id,
            "pipelineStageId": stage_id,
            "monetaryValue": float(booking.get("booking_total", 0)),
            "customFields": [
                # Note: booking_id custom field removed - using name matching instead
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

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Version": "2021-07-28"
        }
        
        test_mode_msg = "[TEST MODE] " if TEST_MODE else ""
        print(f"{test_mode_msg}[GHL CREATE] Creating NEW opportunity for booking {booking_id}...")
        print(f"{test_mode_msg}[GHL CREATE]   Stage: {stage_id}")
        print(f"{test_mode_msg}[GHL CREATE]   Guest: {first_name} {last_name}")
        log.info(f"{test_mode_msg}Creating new opportunity in GHL for booking: {ghl_payload.get('name')}")
        response = requests.post(GHL_OPPORTUNITY_URL, json=ghl_payload, headers=headers)

        if response.status_code >= 400:
            print(f"[GHL ERROR] {response.status_code}: {response.text}")
            log.error(f"GHL Error Response: {response.text}")
            return False
        else:
            print(f"{test_mode_msg}[GHL] Booking {booking_id} opportunity created successfully ✅")
            log.info(f"{test_mode_msg}Successfully created opportunity for booking {booking_id}")
            return True

    except Exception as e:
        log.exception("Error during GHL integration")
        print(f"[GHL ERROR] Failed to send booking {booking.get('booking_id')}: {e}")
        return False

def save_opportunities_for_stage(stage_id):
    """
    Fetches all opportunities for a given stage_id (handles pagination)
    and saves them to a JSON file named {stage_id}_opportunities.json.
    """
    access_token = get_ghl_token()
    if not access_token:
        print("No valid access token. Aborting fetch.")
        return

    location_id = TEST_LOCATION_ID if TEST_MODE else GHL_LOCATION_ID
    pipeline_id = TEST_PIPELINE_ID if TEST_MODE else GHL_PIPELINE_ID

    base_url = 'https://services.leadconnectorhq.com'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Version': '2021-07-28'
    }
    url = f"{base_url}/opportunities/search?location_id={location_id}&pipeline_id={pipeline_id}&pipeline_stage_id={stage_id}&limit=100"
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

    location_id = TEST_LOCATION_ID if TEST_MODE else GHL_LOCATION_ID
    pipeline_id = TEST_PIPELINE_ID if TEST_MODE else GHL_PIPELINE_ID

    base_url = 'https://services.leadconnectorhq.com'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Version': '2021-07-28'
    }
    url = f"{base_url}/opportunities/search?location_id={location_id}&pipeline_id={pipeline_id}&pipeline_stage_id={stage_id}&limit=100"
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

def find_opportunity_by_booking_id(booking_id, guest_firstname=None, guest_lastname=None, site_name=None, booking_arrival=None, access_token=None):
    """
    Finds an existing opportunity in GHL by matching the opportunity name.
    Name format: "{firstname} {lastname} - {site_name} - {arrival_date}"
    Returns tuple (opportunity_id, opportunity_data) if found, (None, None) otherwise.
    
    Note: This function uses name matching (not booking_id custom field) since
    the custom field may not be configured in GHL.
    
    Args:
        access_token: Optional access token to use. If not provided, will use get_ghl_token()
    """
    if not access_token:
        access_token = get_ghl_token()
    if not access_token:
        log.warning(f"No valid access token. Cannot search for opportunity with booking_id: {booking_id}")
        return None, None

    location_id = TEST_LOCATION_ID if TEST_MODE else GHL_LOCATION_ID
    pipeline_id = TEST_PIPELINE_ID if TEST_MODE else GHL_PIPELINE_ID

    # Validate location_id and pipeline_id
    if not location_id:
        error_msg = f"GHL_LOCATION_ID is not set. Please set it in your .env file."
        log.error(error_msg)
        if not DRY_RUN_MODE:
            print(f"[ERROR] {error_msg}")
        return None, None
    
    if not pipeline_id:
        error_msg = f"GHL_PIPELINE_ID is not set. Please set it in your .env file."
        log.error(error_msg)
        if not DRY_RUN_MODE:
            print(f"[ERROR] {error_msg}")
        return None, None

    # Build expected name - REQUIRED for matching (since we don't use booking_id custom field)
    if not (guest_firstname and guest_lastname and site_name and booking_arrival):
        log.warning(f"[GHL SEARCH] Cannot search for booking_id {booking_id} - missing required fields for name matching")
        log.warning(f"  Required: guest_firstname, guest_lastname, site_name, booking_arrival")
        return None, None
    
    expected_name = f"{guest_firstname.strip()} {guest_lastname.strip()} - {site_name} - {booking_arrival.split(' ')[0]}"
    log.debug(f"[GHL SEARCH] Searching for opportunity with name: {expected_name}")

    base_url = 'https://services.leadconnectorhq.com'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Version': '2021-07-28'
    }
    url = f"{base_url}/opportunities/search?location_id={location_id}&pipeline_id={pipeline_id}&limit=100"

    while url:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            log.error(f"[GHL SEARCH] Failed to fetch opportunities: {resp.status_code} {resp.text}")
            break
        data = resp.json()
        for opp in data.get('opportunities', []):
            name = opp.get('name', '')
            # Primary matching: Use exact name match (required since booking_id custom field not used)
            exact_name_match = name == expected_name
            
            # Optional: Also check booking_id in custom fields if it exists (for backwards compatibility)
            custom_fields = opp.get('customFields', [])
            custom_match = any(
                (str(f.get('field_value')) == str(booking_id) or str(f.get('fieldValue')) == str(booking_id))
                for f in custom_fields
                if f.get('id') == 'booking_id'
            )
            
            # Match by exact name (primary) or custom field (optional fallback)
            if exact_name_match or custom_match:
                opp_id = opp.get('id')
                log.info(f"[GHL SEARCH] Found opportunity {opp_id} for booking_id {booking_id}")
                if exact_name_match:
                    log.debug(f"[GHL SEARCH] Matched by exact name: '{expected_name}'")
                elif custom_match:
                    log.debug(f"[GHL SEARCH] Matched by booking_id custom field (fallback)")
                return opp_id, opp
        url = data.get('meta', {}).get('nextPageUrl')
    
    log.debug(f"[GHL SEARCH] No opportunity found for booking_id {booking_id}")
    return None, None


def update_opportunity(opportunity_id, booking, access_token, stage_id, contact_id, existing_opportunity=None):
    """
    Updates an existing opportunity in GHL with new stage and booking details.
    Uses minimal payload approach - only sends what needs to change (like GHL's own updates).
    Returns True if successful, False otherwise.
    
    Args:
        opportunity_id: The GHL opportunity ID to update
        booking: The booking data
        access_token: GHL access token
        stage_id: The new stage ID
        contact_id: Contact ID (for reference, may not be needed in minimal update)
        existing_opportunity: Optional existing opportunity data to preserve custom fields
    """
    if not access_token:
        log.error(f"[GHL UPDATE] Cannot update opportunity {opportunity_id} - access token is None")
        return False

    try:
        # Option 1: Minimal update (like GHL's own updates) - only change stage
        # This is the most efficient and matches what GHL does internally
        minimal_payload = {
            "pipelineStageId": stage_id
        }
        
        # Option 2: Full update with all fields (if you need to update custom fields too)
        # Uncomment this if you need to update custom fields, name, monetary value, etc.
        guests_list = booking.get('guests', [])
        if guests_list:
            guest = guests_list[0]
            full_payload = {
                "name": f"{guest.get('firstname', '').strip()} {guest.get('lastname', '').strip()} - {booking.get('site_name', '')} - {booking.get('booking_arrival', '').split(' ')[0] if booking.get('booking_arrival') else ''}",
                "pipelineStageId": stage_id,
                "monetaryValue": float(booking.get("booking_total", 0)),
                "status": "open",
                # Note: booking_id custom field removed - using name matching instead
                # Custom fields format - GHL may use either field_value or fieldValue
                "customFields": [
                    {
                        "id": "arrival_date",
                        "fieldValue": (
                            datetime.strptime(booking.get("booking_arrival"), "%Y-%m-%d %H:%M:%S").date().isoformat()
                            if booking.get("booking_arrival") else ""
                        )
                    },
                    {
                        "id": "departure_date",
                        "fieldValue": (
                            datetime.strptime(booking.get("booking_departure"), "%Y-%m-%d %H:%M:%S").date().isoformat()
                            if booking.get("booking_departure") else ""
                        )
                    },
                    {"id": "adults", "fieldValue": str(booking.get("booking_adults", ""))},
                    {"id": "children", "fieldValue": str(booking.get("booking_children", ""))},
                    {"id": "infants", "fieldValue": str(booking.get("booking_infants", ""))},
                    {"id": "site_id", "fieldValue": str(booking.get("site_name", ""))},
                    {"id": "total_spend", "fieldValue": str(booking.get("booking_total", ""))},
                    {"id": "promo_code", "fieldValue": booking.get("discount_code", "")},
                    {"id": "booking_status", "fieldValue": booking.get("booking_status", "")},
                    {"id": "pets", "fieldValue": booking.get("pets", "")},
                ]
            }
        else:
            full_payload = minimal_payload
        
        # Use minimal payload for stage-only updates (faster, matches GHL's approach)
        # This matches what GHL does internally - only sends what needs to change
        # If you need to update custom fields, name, or monetary value, use full_payload instead
        ghl_payload = minimal_payload
        
        # Uncomment the line below to update all fields including custom fields
        # ghl_payload = full_payload if guests_list else minimal_payload

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Version": "2021-07-28"
        }

        update_url = f"{GHL_OPPORTUNITY_URL}{opportunity_id}"
        log.info(f"[GHL UPDATE] Updating opportunity {opportunity_id} for booking {booking.get('booking_id')} to stage {stage_id}")
        print(f"[GHL UPDATE] Updating opportunity {opportunity_id} for booking {booking.get('booking_id')}...")
        print(f"[GHL UPDATE] Payload: {ghl_payload}")  # Debug: show what we're sending
        
        response = requests.put(update_url, json=ghl_payload, headers=headers)

        if response.status_code >= 400:
            log.error(f"[GHL UPDATE] Failed to update opportunity {opportunity_id}: {response.status_code} - {response.text}")
            print(f"[GHL UPDATE ERROR] {response.status_code}: {response.text}")
            return False
        else:
            log.info(f"[GHL UPDATE] Successfully updated opportunity {opportunity_id} for booking {booking.get('booking_id')}")
            print(f"[GHL UPDATE] Opportunity {opportunity_id} updated successfully ✅")
            return True

    except Exception as e:
        log.exception(f"[GHL UPDATE] Error updating opportunity {opportunity_id}: {e}")
        print(f"[GHL UPDATE ERROR] Failed to update opportunity {opportunity_id}: {e}")
        return False


def delete_opportunity_by_booking_id(booking_id, guest_firstname=None, guest_lastname=None, site_name=None, booking_arrival=None):
    """
    Deletes opportunities in GHL that match by exact name.
    Name format: "{firstname} {lastname} - {site_name} - {arrival_date}"
    NOTE: This function uses name matching (not booking_id custom field).
    NOTE: This function is kept for cleanup purposes (cancelled bookings, etc.)
    """
    access_token = get_ghl_token()
    if not access_token:
        print("No valid access token. Aborting opportunity deletion for booking_id:", booking_id)
        return

    location_id = TEST_LOCATION_ID if TEST_MODE else GHL_LOCATION_ID
    pipeline_id = TEST_PIPELINE_ID if TEST_MODE else GHL_PIPELINE_ID

    base_url = 'https://services.leadconnectorhq.com'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Version': '2021-07-28'
    }
    url = f"{base_url}/opportunities/search?location_id={location_id}&pipeline_id={pipeline_id}&limit=100"
    found = False

    # Build expected name - REQUIRED for matching
    if not (guest_firstname and guest_lastname and site_name and booking_arrival):
        log.warning(f"[GHL DELETE] Cannot delete opportunity for booking_id {booking_id} - missing required fields for name matching")
        return
    
    expected_name = f"{guest_firstname.strip()} {guest_lastname.strip()} - {site_name} - {booking_arrival.split(' ')[0]}"

    while url:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"[GHL DELETE] Failed to fetch opportunities: {resp.status_code} {resp.text}")
            break
        data = resp.json()
        for opp in data.get('opportunities', []):
            name = opp.get('name', '')
            # Primary matching: Use exact name match (required since booking_id custom field not used)
            exact_name_match = name == expected_name
            
            # Optional fallback: Check booking_id in custom fields if it exists
            custom_match = any(
                (str(f.get('field_value')) == str(booking_id) or str(f.get('fieldValue')) == str(booking_id))
                for f in opp.get('customFields', [])
                if f.get('id') == 'booking_id'
            )
            
            # Match by exact name (primary) or custom field (optional fallback)
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

    location_id = TEST_LOCATION_ID if TEST_MODE else GHL_LOCATION_ID
    pipeline_id = TEST_PIPELINE_ID if TEST_MODE else GHL_PIPELINE_ID

    if not location_id or not pipeline_id:
        log.error(f"Cannot delete opportunity: GHL_LOCATION_ID or GHL_PIPELINE_ID not set")
        return

    base_url = 'https://services.leadconnectorhq.com'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Version': '2021-07-28'
    }
    url = f"{base_url}/opportunities/search?location_id={location_id}&pipeline_id={pipeline_id}&limit=100"
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


def test_opportunity_update(booking_id=None, use_dry_run=True):
    """
    Test function to verify opportunity update functionality.
    This function can be used to test the update logic before deploying to production.
    
    Args:
        booking_id: Optional specific booking_id to test. If None, will test with a sample booking.
        use_dry_run: If True, uses dry-run mode (simulates without making changes). Default: True
    
    Usage:
        from utils.ghl_api import test_opportunity_update
        test_opportunity_update()  # Test with sample booking (dry-run)
        test_opportunity_update("12345")  # Test with specific booking_id (dry-run)
        test_opportunity_update("12345", use_dry_run=False)  # Actually create/update (use with caution!)
    """
    global DRY_RUN_MODE
    
    # Validate configuration first
    if not GHL_LOCATION_ID:
        print("\n" + "=" * 70)
        print("❌ CONFIGURATION ERROR")
        print("=" * 70)
        print("GHL_LOCATION_ID is not set in your .env file!")
        print("\nPlease add the following to your .env file:")
        print("  GHL_LOCATION_ID=your-location-id")
        print("\nYou can find your Location ID in your GoHighLevel account settings.")
        print("=" * 70)
        return
    
    if not GHL_PIPELINE_ID:
        print("\n" + "=" * 70)
        print("❌ CONFIGURATION ERROR")
        print("=" * 70)
        print("GHL_PIPELINE_ID is not set in your .env file!")
        print("\nPlease add the following to your .env file:")
        print("  GHL_PIPELINE_ID=your-pipeline-id")
        print("\nYou can find your Pipeline ID in your GoHighLevel pipeline settings.")
        print("=" * 70)
        return
    
    # Show current configuration
    print("\n" + "=" * 70)
    print("Current Configuration:")
    print("=" * 70)
    print(f"TEST_MODE: {TEST_MODE}")
    print(f"DRY_RUN_MODE: {DRY_RUN_MODE}")
    if TEST_MODE:
        if TEST_PIPELINE_ID == GHL_PIPELINE_ID:
            print(f"⚠️  WARNING: Using PRODUCTION Pipeline ID: {GHL_PIPELINE_ID}")
        else:
            print(f"✅ Using Test Pipeline ID: {TEST_PIPELINE_ID}")
        if TEST_LOCATION_ID == GHL_LOCATION_ID:
            print(f"⚠️  WARNING: Using PRODUCTION Location ID: {GHL_LOCATION_ID}")
        else:
            print(f"✅ Using Test Location ID: {TEST_LOCATION_ID}")
    else:
        print(f"Pipeline ID: {GHL_PIPELINE_ID}")
        print(f"Location ID: {GHL_LOCATION_ID if GHL_LOCATION_ID else '❌ NOT SET'}")
        if not GHL_LOCATION_ID:
            print("⚠️  ERROR: Location ID is required but not set!")
    
    print("=" * 70)
    
    # Enable dry run by default for safety
    if use_dry_run and not DRY_RUN_MODE:
        print("\n⚠️  DRY RUN MODE: Simulating operations without making actual changes")
        print("   Set use_dry_run=False to actually create/update opportunities")
        DRY_RUN_MODE = True
    elif not use_dry_run:
        if not TEST_MODE:
            print("\n⚠️  WARNING: You are about to make changes to PRODUCTION!")
            print("   This will create/update real opportunities in your production pipeline")
            response = input("   Are you sure you want to continue? (type 'yes' to confirm): ")
            if response.lower() != "yes":
                print("Test cancelled.")
                return
        DRY_RUN_MODE = False
    
    print("\n" + "=" * 70)
    print("Testing Opportunity Update Functionality")
    print("=" * 70)
    
    # Try to get token (prefer private integration token, fallback to OAuth)
    access_token = get_ghl_token()
    if not access_token:
        access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
    
    if not access_token:
        print("❌ ERROR: No valid access token available")
        return
    
    # If booking_id provided, fetch that booking from NewBook
    if booking_id:
        print(f"\n[TEST] Fetching booking {booking_id} from NewBook...")
        user_pass = f"{USERNAME}:{PASSWORD}"
        encoded_credentials = base64.b64encode(user_pass.encode()).decode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_credentials}"
        }
        
        try:
            # Try to fetch the specific booking
            # Note: You may need to adjust this based on your NewBook API
            response = requests.post(
                f"{NEWBOOK_API_BASE}/bookings_list",
                json={
                    "region": REGION,
                    "api_key": API_KEY,
                    "list_type": "all",
                    "period_from": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00"),
                    "period_to": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d 23:59:59")
                },
                headers=headers,
                verify=False,
                timeout=15
            )
            response.raise_for_status()
            bookings = response.json().get("data", [])
            test_booking = next((b for b in bookings if b.get("booking_id") == str(booking_id)), None)
            
            if not test_booking:
                print(f"❌ ERROR: Booking {booking_id} not found")
                return
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch booking: {e}")
            return
    else:
        # Create a sample booking for testing
        print("\n[TEST] Using sample booking data...")
        test_booking = {
            "booking_id": "TEST_" + datetime.now().strftime("%Y%m%d%H%M%S"),
            "site_name": "Test Site",
            "booking_arrival": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d 14:00:00"),
            "booking_departure": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d 11:00:00"),
            "booking_status": "placed",
            "booking_total": 500.00,
            "booking_adults": 2,
            "booking_children": 0,
            "booking_infants": 0,
            "discount_code": "",
            "pets": "",
            "guests": [{
                "firstname": "Test",
                "lastname": "Guest",
                "contact_details": [
                    {"type": "email", "content": "test@example.com"},
                    {"type": "mobile", "content": "+1234567890"}
                ]
            }]
        }
        print(f"[TEST] Created sample booking with ID: {test_booking['booking_id']}")
    
    print(f"\n[TEST] Booking Details:")
    print(f"  ID: {test_booking.get('booking_id')}")
    print(f"  Guest: {test_booking.get('guests', [{}])[0].get('firstname', '')} {test_booking.get('guests', [{}])[0].get('lastname', '')}")
    print(f"  Arrival: {test_booking.get('booking_arrival')}")
    print(f"  Status: {test_booking.get('booking_status')}")
    
    # Test 1: Create opportunity
    print("\n[TEST 1] Creating new opportunity...")
    result1 = send_to_ghl(test_booking, access_token)
    if result1:
        print("✅ TEST 1 PASSED: Opportunity created successfully")
    else:
        print("❌ TEST 1 FAILED: Failed to create opportunity")
        return
    
    # Wait a moment
    import time
    time.sleep(2)
    
    # Test 2: Update opportunity (should update, not create new)
    print("\n[TEST 2] Updating opportunity (should update existing, not create new)...")
    # Modify booking to trigger stage change
    test_booking["booking_status"] = "arrived"
    test_booking["booking_arrival"] = datetime.now().strftime("%Y-%m-%d 14:00:00")
    result2 = send_to_ghl(test_booking, access_token)
    if result2:
        print("✅ TEST 2 PASSED: Opportunity updated successfully")
    else:
        print("❌ TEST 2 FAILED: Failed to update opportunity")
    
    # Test 3: Verify only one opportunity exists
    print("\n[TEST 3] Verifying only one opportunity exists for this booking...")
    
    # Skip this test if location_id is not set (would fail anyway)
    if not (TEST_LOCATION_ID if TEST_MODE else GHL_LOCATION_ID):
        print("⚠️  TEST 3 SKIPPED: GHL_LOCATION_ID not set, cannot search for opportunities")
        print("   This test requires GHL_LOCATION_ID to be configured in .env")
    else:
        opp_id, opp_data = find_opportunity_by_booking_id(
            test_booking.get("booking_id"),
            guest_firstname=test_booking.get("guests", [{}])[0].get("firstname", ""),
            guest_lastname=test_booking.get("guests", [{}])[0].get("lastname", ""),
            site_name=test_booking.get("site_name", ""),
            booking_arrival=test_booking.get("booking_arrival", ""),
            access_token=access_token
        )
        
        if opp_id:
            print(f"✅ TEST 3 PASSED: Found opportunity {opp_id}")
            if opp_data:
                print(f"   Current Stage: {opp_data.get('pipelineStageId')}")
                print(f"   Name: {opp_data.get('name')}")
        else:
            if DRY_RUN_MODE:
                print("⚠️  TEST 3: Could not find opportunity (expected in dry-run mode)")
                print("   In dry-run mode, no opportunities are actually created")
            else:
                print("❌ TEST 3 FAILED: Could not find opportunity")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    
    if DRY_RUN_MODE:
        print("\n✅ DRY RUN MODE: No actual changes were made to GHL")
        print("   To actually create/update opportunities, run with use_dry_run=False")
    else:
        print("\n⚠️  REAL MODE: Actual changes were made to GHL")
        if opp_id:
            print(f"   Opportunity ID: {opp_id}")
            print("   You can verify this opportunity in your GHL pipeline")
    
    print("\nConfiguration:")
    print(f"   TEST_MODE: {TEST_MODE}")
    print(f"   DRY_RUN_MODE: {DRY_RUN_MODE}")
    print(f"   Pipeline ID: {TEST_PIPELINE_ID if TEST_MODE else GHL_PIPELINE_ID}")
    print(f"   Location ID: {TEST_LOCATION_ID if TEST_MODE else GHL_LOCATION_ID}")
