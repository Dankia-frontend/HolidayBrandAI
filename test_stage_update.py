#!/usr/bin/env python3
"""
Manual test script to trigger stage updates for a specific booking/opportunity.

Usage:
    python test_stage_update.py <booking_id>
    python test_stage_update.py  # Will prompt for booking_id

This script will:
1. Fetch the booking from NewBook
2. Determine the correct stage based on current dates/status
3. Update the opportunity in GHL (or create if it doesn't exist)
4. Show detailed information about what happened
"""

import sys
import os
import base64
import requests
from datetime import datetime, timedelta

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.ghl_api import (
    send_to_ghl,
    find_opportunity_by_booking_id,
    get_ghl_token,
    get_valid_access_token,
    get_stage_id_for_booking
)
from config.config import (
    REGION,
    API_KEY,
    NEWBOOK_API_BASE,
    GHL_CLIENT_ID,
    GHL_CLIENT_SECRET,
    USERNAME,
    PASSWORD,
    GHL_LOCATION_ID,
    GHL_PIPELINE_ID
)
from utils.logger import get_logger

log = get_logger("StageUpdateTest")

# Stage ID to name mapping for better readability
STAGE_NAMES = {
    '3aeae130-f411-4ac7-bcca-271291fdc3b9': 'arriving_soon',
    'b429a8e9-e73e-4590-b4c5-8ea1d65e0daf': 'arriving_today',
    '99912993-0e69-48f9-9943-096ae68408d7': 'staying_now',
    'fc60b2fa-8c2d-4202-9347-ac2dd32a0e43': 'checking_out',
    '8b54e5e5-27f3-463a-9d81-890c6dfd27eb': 'checked_out'
}


def fetch_booking_from_newbook(booking_id):
    """Fetch a specific booking from NewBook API."""
    print(f"\n{'='*70}")
    print(f"Fetching booking {booking_id} from NewBook...")
    print(f"{'='*70}")
    
    user_pass = f"{USERNAME}:{PASSWORD}"
    encoded_credentials = base64.b64encode(user_pass.encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_credentials}"
    }
    
    # Fetch bookings from a wide date range to find the booking
    period_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00")
    period_to = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d 23:59:59")
    
    list_types = ["all", "arrived", "arriving", "placed", "staying", "departed", "departing"]
    
    for list_type in list_types:
        payload = {
            "region": REGION,
            "api_key": API_KEY,
            "list_type": list_type,
            "period_from": period_from,
            "period_to": period_to
        }
        
        try:
            response = requests.post(
                f"{NEWBOOK_API_BASE}/bookings_list",
                json=payload,
                headers=headers,
                verify=False,
                timeout=15
            )
            response.raise_for_status()
            bookings = response.json().get("data", [])
            
            # Search for the booking
            booking = next((b for b in bookings if str(b.get("booking_id")) == str(booking_id)), None)
            if booking:
                print(f"✅ Found booking {booking_id} in list_type: {list_type}")
                return booking
        except Exception as e:
            log.warning(f"Failed to fetch bookings for {list_type}: {e}")
            continue
    
    print(f"❌ Booking {booking_id} not found in NewBook")
    return None


def display_booking_info(booking):
    """Display booking information in a readable format."""
    print(f"\n{'='*70}")
    print("BOOKING INFORMATION")
    print(f"{'='*70}")
    print(f"Booking ID: {booking.get('booking_id')}")
    print(f"Site Name: {booking.get('site_name', 'N/A')}")
    print(f"Arrival: {booking.get('booking_arrival', 'N/A')}")
    print(f"Departure: {booking.get('booking_departure', 'N/A')}")
    print(f"Status: {booking.get('booking_status', 'N/A')}")
    print(f"Total: ${booking.get('booking_total', 0)}")
    
    guests = booking.get('guests', [])
    if guests:
        guest = guests[0]
        print(f"\nGuest:")
        print(f"  Name: {guest.get('firstname', '')} {guest.get('lastname', '')}")
        contact_details = guest.get('contact_details', [])
        for contact in contact_details:
            print(f"  {contact.get('type', '').title()}: {contact.get('content', '')}")
    else:
        print("\n⚠️  No guest information found")
    
    # Calculate expected stage
    stage_id = get_stage_id_for_booking(booking)
    stage_name = STAGE_NAMES.get(stage_id, 'unknown')
    print(f"\nExpected Stage: {stage_name} ({stage_id})")
    print(f"{'='*70}")


def check_existing_opportunity(booking, access_token):
    """Check if opportunity already exists in GHL."""
    guests = booking.get('guests', [])
    if not guests:
        return None, None
    
    guest = guests[0]
    guest_firstname = guest.get("firstname", "")
    guest_lastname = guest.get("lastname", "")
    site_name = booking.get("site_name", "")
    booking_arrival = booking.get("booking_arrival", "")
    
    opp_id, opp_data = find_opportunity_by_booking_id(
        booking.get('booking_id'),
        guest_firstname=guest_firstname,
        guest_lastname=guest_lastname,
        site_name=site_name,
        booking_arrival=booking_arrival,
        access_token=access_token
    )
    
    return opp_id, opp_data


def display_opportunity_info(opp_data):
    """Display existing opportunity information."""
    if not opp_data:
        return
    
    print(f"\n{'='*70}")
    print("EXISTING OPPORTUNITY IN GHL")
    print(f"{'='*70}")
    print(f"Opportunity ID: {opp_data.get('id', 'N/A')}")
    print(f"Name: {opp_data.get('name', 'N/A')}")
    
    current_stage_id = opp_data.get('pipelineStageId', 'N/A')
    current_stage_name = STAGE_NAMES.get(current_stage_id, 'unknown')
    print(f"Current Stage: {current_stage_name} ({current_stage_id})")
    
    print(f"Status: {opp_data.get('status', 'N/A')}")
    print(f"Monetary Value: ${opp_data.get('monetaryValue', 0)}")
    print(f"{'='*70}")


def main():
    """Main test function."""
    print("\n" + "="*70)
    print("MANUAL STAGE UPDATE TEST SCRIPT")
    print("="*70)
    
    # Get booking_id from command line or prompt
    if len(sys.argv) > 1:
        booking_id = sys.argv[1]
    else:
        booking_id = input("\nEnter booking_id to test: ").strip()
    
    if not booking_id:
        print("❌ No booking_id provided. Exiting.")
        return
    
    # Get access token
    print("\n[1/5] Getting access token...")
    access_token = get_ghl_token()
    if not access_token:
        access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
    
    if not access_token:
        print("❌ ERROR: No valid access token available")
        print("   Please ensure GHL_PRIVATE_INTEGRATION_TOKEN is set or OAuth tokens are configured")
        return
    
    print("✅ Access token obtained")
    
    # Fetch booking from NewBook
    print("\n[2/5] Fetching booking from NewBook...")
    booking = fetch_booking_from_newbook(booking_id)
    if not booking:
        return
    
    # Display booking info
    display_booking_info(booking)
    
    # Check if opportunity exists
    print("\n[3/5] Checking for existing opportunity in GHL...")
    opp_id, opp_data = check_existing_opportunity(booking, access_token)
    
    if opp_id:
        print(f"✅ Found existing opportunity: {opp_id}")
        display_opportunity_info(opp_data)
        
        # Show what will change
        current_stage_id = opp_data.get('pipelineStageId')
        expected_stage_id = get_stage_id_for_booking(booking)
        
        if current_stage_id == expected_stage_id:
            print(f"\n{'='*70}")
            print("ℹ️  OPPORTUNITY ALREADY IN CORRECT STAGE")
            print(f"{'='*70}")
            print(f"Current stage: {STAGE_NAMES.get(current_stage_id, 'unknown')}")
            print(f"Expected stage: {STAGE_NAMES.get(expected_stage_id, 'unknown')}")
            print("\nNo update needed. The opportunity is already in the correct stage.")
            
            response = input("\nDo you want to force an update anyway? (yes/no): ").strip().lower()
            if response != 'yes':
                print("Test cancelled.")
                return
        else:
            print(f"\n{'='*70}")
            print("🔄 STAGE CHANGE DETECTED")
            print(f"{'='*70}")
            print(f"Current stage: {STAGE_NAMES.get(current_stage_id, 'unknown')} ({current_stage_id})")
            print(f"New stage: {STAGE_NAMES.get(expected_stage_id, 'unknown')} ({expected_stage_id})")
    else:
        print("ℹ️  No existing opportunity found - will create new one")
        expected_stage_id = get_stage_id_for_booking(booking)
        print(f"Will create in stage: {STAGE_NAMES.get(expected_stage_id, 'unknown')} ({expected_stage_id})")
    
    # Confirm before proceeding
    print(f"\n{'='*70}")
    response = input("Proceed with update/create? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Test cancelled.")
        return
    
    # Send to GHL
    print("\n[4/5] Sending booking to GHL...")
    try:
        success = send_to_ghl(booking, access_token)
        
        if success:
            print("✅ Successfully processed booking in GHL")
        else:
            print("❌ Failed to process booking in GHL")
            return
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        log.exception("Error during send_to_ghl")
        return
    
    # Verify the result
    print("\n[5/5] Verifying result...")
    new_opp_id, new_opp_data = check_existing_opportunity(booking, access_token)
    
    if new_opp_id:
        print(f"\n{'='*70}")
        print("✅ VERIFICATION SUCCESSFUL")
        print(f"{'='*70}")
        print(f"Opportunity ID: {new_opp_id}")
        
        if opp_data:
            old_stage = STAGE_NAMES.get(opp_data.get('pipelineStageId'), 'unknown')
            new_stage = STAGE_NAMES.get(new_opp_data.get('pipelineStageId'), 'unknown')
            print(f"Stage changed from: {old_stage} → {new_stage}")
            
            if old_stage == new_stage:
                print("⚠️  Note: Stage did not change (opportunity was already in correct stage)")
            else:
                print("✅ Stage successfully updated!")
        else:
            new_stage = STAGE_NAMES.get(new_opp_data.get('pipelineStageId'), 'unknown')
            print(f"New opportunity created in stage: {new_stage}")
            print("✅ Opportunity successfully created!")
        
        print(f"\nYou can verify this in your GHL pipeline:")
        print(f"  Location ID: {GHL_LOCATION_ID}")
        print(f"  Pipeline ID: {GHL_PIPELINE_ID}")
        print(f"  Opportunity ID: {new_opp_id}")
    else:
        print(f"\n{'='*70}")
        print("⚠️  VERIFICATION WARNING")
        print(f"{'='*70}")
        print("Could not find the opportunity after creation/update.")
        print("This might be due to:")
        print("  - API delay (opportunity may appear shortly)")
        print("  - Name matching issue")
        print("  - Different location/pipeline")
    
    print(f"\n{'='*70}")
    print("TEST COMPLETE")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        log.exception("Unexpected error in test script")
        raise

