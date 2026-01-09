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

        # --- Remove opportunities ONLY for bookings that are no longer present (removed) ---
        # Updated bookings should be updated, not deleted
        for b in removed:
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
            print(f"[REMOVED] Booking {booking_id} no longer exists, deleting opportunity from GHL.")
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
        # Note: We don't delete these - they will be updated to the correct stage by send_to_ghl
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
                    print(f"[INFO] Booking {b['booking_id']} in arriving_today is for previous/future day ({arrival_dt.date()}), will be updated to correct stage.")
            else:
                print(f"[INFO] Booking {b['booking_id']} in arriving_today has no arrival date, will be processed normally.")
        bucket_dict["arriving_today"] = filtered_arriving_today

        # --- Filter out bookings not for future in arriving_soon ---
        # Note: We don't delete these - they will be updated to the correct stage by send_to_ghl
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
                    print(f"[INFO] Booking {b['booking_id']} in arriving_soon is for today/past ({arrival_dt.date()}), will be updated to correct stage.")
            else:
                print(f"[INFO] Booking {b['booking_id']} in arriving_soon has no arrival date, will be processed normally.")
        bucket_dict["arriving_soon"] = filtered_arriving_soon

        # --- Note: When bookings move between stages, send_to_ghl will update them automatically ---
        # No need to delete - the update will move them to the correct stage

        # --- Process ALL bookings (new, updated, and existing) to ensure they're in the correct stage ---
        # This ensures opportunities are updated when bookings move between stages
        log.info(f"[OPPORTUNITY JOB] Processing {len(added)} new bookings, {len(updated)} updated bookings, and existing bookings to ensure correct stages")
        
        # Process all bookings that should have opportunities (not cancelled)
        all_active_bookings = [b for b in completed_bookings if b.get("booking_status", "").lower() not in ["cancelled", "no_show", "no show"]]
        bucket_dict_all = bucket_bookings(all_active_bookings)
        
        opportunities_created = 0
        opportunities_updated = 0
        opportunities_failed = 0
        
        access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
        if not access_token:
            log.error("[OPPORTUNITY JOB] Failed to get valid access token. Skipping all GHL sync.")
            print("[GHL ERROR] No valid access token available. Cannot process bookings.")
        else:
            for bucket, bookings in bucket_dict_all.items():
                if bookings and bucket != "cancelled":
                    # write_bucket_file(bucket, bookings)
                    for b in bookings:
                        if b["booking_id"] in deleted_booking_ids:
                            continue  # Skip if already deleted (removed bookings)
                        
                        guests_list = b.get("guests", [])
                        if not guests_list:
                            log.warning(f"[OPPORTUNITY JOB] Booking {b.get('booking_id', 'unknown')} has no guests, skipping")
                            opportunities_failed += 1
                            continue
                        
                        try:
                            # send_to_ghl will check for existing opportunity and update it, or create new one
                            booking_id = b["booking_id"]
                            
                            # Check if opportunity exists before calling send_to_ghl (for logging purposes)
                            guests_list_for_search = b.get("guests", [])
                            guest_firstname = None
                            guest_lastname = None
                            if guests_list_for_search:
                                guest = guests_list_for_search[0]
                                guest_firstname = guest.get("firstname", "")
                                guest_lastname = guest.get("lastname", "")
                            
                            existing_opp = find_opportunity_by_booking_id(
                                booking_id, 
                                access_token,
                                guest_firstname=guest_firstname,
                                guest_lastname=guest_lastname,
                                site_name=b.get("site_name", ""),
                                booking_arrival=b.get("booking_arrival", "")
                            )
                            
                            # send_to_ghl will check again and update/create as needed
                            send_to_ghl(b, access_token)
                            
                            if existing_opp:
                                opportunities_updated += 1
                                log.info(f"[OPPORTUNITY JOB] Successfully updated booking {booking_id} in GHL")
                            else:
                                opportunities_created += 1
                                log.info(f"[OPPORTUNITY JOB] Successfully created opportunity for booking {booking_id} in GHL")
                        except Exception as e:
                            log.error(f"[OPPORTUNITY JOB] Failed to process booking {b['booking_id']} in GHL: {e}")
                            opportunities_failed += 1

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
# ✅ Helper function to send data to GHL (example)
def send_to_ghl(booking, access_token, guest_info=None):
    if not access_token:
        log.error(f"[GHL] Cannot send booking {booking.get('booking_id')} - access token is None")
        print(f"[GHL ERROR] Access token is None. Cannot send booking {booking.get('booking_id')}")
        return

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
        
        # Build custom fields
        custom_fields = [
            {
                "id": "booking_id",
                "field_value": str(booking_id)
            },
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
        
        # Check if opportunity already exists
        # Try to get guest info for better matching
        guests_list = booking.get('guests', [])
        guest_firstname = None
        guest_lastname = None
        if guests_list:
            guest = guests_list[0]
            guest_firstname = guest.get("firstname", "")
            guest_lastname = guest.get("lastname", "")
        
        existing_opp = find_opportunity_by_booking_id(
            booking_id, 
            access_token,
            guest_firstname=guest_firstname,
            guest_lastname=guest_lastname,
            site_name=booking.get("site_name", ""),
            booking_arrival=booking.get("booking_arrival", "")
        )
        
        if existing_opp:
            # Update existing opportunity
            opp_id = existing_opp.get('id')
            current_stage_id = existing_opp.get('pipelineStageId')
            
            print(f"[GHL] Found existing opportunity {opp_id} for booking {booking_id}. Current stage: {current_stage_id}, New stage: {stage_id}")
            log.info(f"Updating existing opportunity {opp_id} for booking {booking_id}")
            
            # Always update to ensure booking_id is in custom fields and stage is correct
            # Update stage if it has changed, and always update custom fields
            update_stage = (stage_id and stage_id != current_stage_id)
            
            if update_stage:
                print(f"[GHL] Moving opportunity {opp_id} from stage {current_stage_id} to {stage_id}")
            else:
                print(f"[GHL] Updating opportunity {opp_id} (stage unchanged: {current_stage_id})")
            
            success = update_opportunity(
                opp_id, 
                access_token, 
                stage_id=stage_id if update_stage else None,
                custom_fields=custom_fields,
                monetary_value=float(booking.get("booking_total", 0))
            )
            
            if success:
                if update_stage:
                    print(f"[GHL] Opportunity {opp_id} moved to stage {stage_id} and updated successfully ✅")
                else:
                    print(f"[GHL] Opportunity {opp_id} custom fields updated successfully ✅")
                log.info(f"Updated opportunity {opp_id} for booking {booking_id}")
            else:
                error_msg = f"[GHL] Failed to update opportunity {opp_id} for booking {booking_id}"
                print(error_msg)
                log.error(error_msg)
                # Don't create a new one if update fails - this would cause duplicates
                raise Exception(f"Failed to update existing opportunity {opp_id}")
        else:
            # Create new opportunity
            print(f"Contact ID: {contact_id}, Stage ID: {stage_id}")
            # Build opportunity name using first_name and last_name
            opportunity_name = f"{first_name.strip()} {last_name.strip()} - {booking.get('site_name', '')} - {booking.get('booking_arrival', '').split(' ')[0]}"
            ghl_payload = {
                "name": opportunity_name,
                "status": "open",  # must be one of: open, won, lost, abandoned
                "contactId": contact_id,  # <-- must be a valid contact ID
                "locationId": GHL_LOCATION_ID,
                "pipelineId": GHL_PIPELINE_ID,
                "pipelineStageId": stage_id,
                "monetaryValue": float(booking.get("booking_total", 0)),
                "customFields": custom_fields
            }
            print(f"Api key {ghl_payload}")
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Version": "2021-07-28"
            }
            
            print(f"[GHL] Creating new opportunity for booking {booking_id}...")
            log.info(f"Creating new opportunity in GHL for booking: {ghl_payload.get('name')}")
            response = requests.post(GHL_OPPORTUNITY_URL, json=ghl_payload, headers=headers)

            if response.status_code >= 400:
                print(f"[GHL ERROR] {response.status_code}: {response.text}")
                log.error(f"GHL Error Response: {response.text}")
            else:
                print(f"[GHL] Booking {booking_id} opportunity created successfully ✅")

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

def find_opportunity_by_booking_id(booking_id, access_token=None, guest_firstname=None, guest_lastname=None, site_name=None, booking_arrival=None):
    """
    Finds an existing opportunity in GHL by booking_id stored in custom fields.
    Also tries to match by opportunity name as a fallback for older opportunities.
    Returns the opportunity object if found, None otherwise.
    """
    if not access_token:
        access_token = get_ghl_token()
    if not access_token:
        print("No valid access token. Cannot search for opportunity with booking_id:", booking_id)
        return None

    base_url = 'https://services.leadconnectorhq.com'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Version': '2021-07-28'
    }
    url = f"{base_url}/opportunities/search?location_id={GHL_LOCATION_ID}&pipeline_id={GHL_PIPELINE_ID}&limit=100"
    
    # Build expected name if all info provided (for fallback matching)
    expected_name = None
    if guest_firstname and guest_lastname and site_name and booking_arrival:
        expected_name = f"{guest_firstname.strip()} {guest_lastname.strip()} - {site_name} - {booking_arrival.split(' ')[0]}"

    while url:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"[GHL SEARCH] Failed to fetch opportunities: {resp.status_code} {resp.text}")
            break
        data = resp.json()
        for opp in data.get('opportunities', []):
            # Primary match: booking_id in custom fields
            custom_match = any(
                (str(f.get('field_value')) == str(booking_id))
                for f in opp.get('customFields', [])
                if f.get('id') == 'booking_id'
            )
            
            # Fallback match: opportunity name (for opportunities created before booking_id was added)
            name_match = False
            if expected_name:
                opp_name = opp.get('name', '')
                name_match = (opp_name == expected_name)
            
            if custom_match or name_match:
                print(f"[GHL SEARCH] Found existing opportunity for booking_id {booking_id}: {opp.get('id')} (matched by: {'custom field' if custom_match else 'name'})")
                return opp
        url = data.get('meta', {}).get('nextPageUrl')
    
    print(f"[GHL SEARCH] No existing opportunity found for booking_id {booking_id}.")
    return None

def update_opportunity(opportunity_id, access_token, stage_id=None, custom_fields=None, monetary_value=None):
    """
    Updates an existing opportunity in GHL.
    """
    base_url = 'https://services.leadconnectorhq.com'
    url = f"{base_url}/opportunities/{opportunity_id}"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Version': '2021-07-28'
    }
    
    payload = {}
    if stage_id:
        payload['pipelineStageId'] = stage_id
    if custom_fields:
        payload['customFields'] = custom_fields
    if monetary_value is not None:
        payload['monetaryValue'] = float(monetary_value)
    
    if not payload:
        print(f"[GHL UPDATE] No fields to update for opportunity {opportunity_id}")
        return False
    
    try:
        response = requests.put(url, json=payload, headers=headers)
        if response.status_code >= 400:
            print(f"[GHL UPDATE ERROR] {response.status_code}: {response.text}")
            log.error(f"GHL Update Error Response: {response.text}")
            return False
        else:
            print(f"[GHL UPDATE] Opportunity {opportunity_id} updated successfully ✅")
            log.info(f"Updated opportunity {opportunity_id} in GHL")
            return True
    except Exception as e:
        log.exception(f"Error updating opportunity {opportunity_id}")
        print(f"[GHL UPDATE ERROR] Failed to update opportunity {opportunity_id}: {e}")
        return False

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
