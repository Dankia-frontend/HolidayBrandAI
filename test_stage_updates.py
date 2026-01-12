"""
Test script to verify opportunity stage updates work correctly using name matching.

This script tests moving an opportunity between different stages to ensure:
1. Opportunities are found by name matching (no booking_id custom field needed)
2. Opportunities are updated (not deleted/recreated)
3. The same opportunity ID is maintained across stage changes
4. All stage transitions work correctly

Usage:
    # Option 1: Use full opportunity name
    python test_stage_updates.py --name "Test Test - Bush 001 - 2026-01-13" --stage-id arriving_today
    
    # Option 2: Use individual components
    python test_stage_updates.py --guest "Test Test" --site "Bush 001" --arrival "2026-01-13" --stage-id arriving_today
    
    # Test all stages sequentially
    python test_stage_updates.py --name "Test Test - Bush 001 - 2026-01-13" --test-all
    
    # Dry-run (simulate only)
    python test_stage_updates.py --name "Test Test - Bush 001 - 2026-01-13" --stage-id arriving_today --dry-run
"""

import os
import sys
import argparse
import base64
import requests
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.ghl_api import (
    find_opportunity_by_booking_id, get_ghl_token, get_valid_access_token,
    update_opportunity, get_contact_id, DRY_RUN_MODE, TEST_MODE
)
from config.config import (
    REGION, API_KEY, NEWBOOK_API_BASE, GHL_LOCATION_ID, GHL_PIPELINE_ID,
    GHL_CLIENT_ID, GHL_CLIENT_SECRET, USERNAME, PASSWORD
)
from utils.ghl_api import TEST_LOCATION_ID, TEST_PIPELINE_ID

# Stage IDs for testing
STAGE_IDS = {
    "arriving_soon": "3aeae130-f411-4ac7-bcca-271291fdc3b9",
    "arriving_today": "b429a8e9-e73e-4590-b4c5-8ea1d65e0daf",
    "staying_now": "99912993-0e69-48f9-9943-096ae68408d7",
    "checking_out": "fc60b2fa-8c2d-4202-9347-ac2dd32a0e43",
    "checked_out": "8b54e5e5-27f3-463a-9d81-890c6dfd27eb"
}

STAGE_NAMES = {v: k for k, v in STAGE_IDS.items()}


def parse_opportunity_name(full_name):
    """
    Parse opportunity name into components.
    Format: "{firstname} {lastname} - {site_name} - {arrival_date}"
    Example: "Test Test - Bush 001 - 2026-01-13"
    """
    if not full_name:
        return None, None, None, None
    
    parts = full_name.split(" - ")
    if len(parts) != 3:
        return None, None, None, None
    
    guest_name = parts[0].strip()
    site_name = parts[1].strip()
    arrival_date = parts[2].strip()
    
    # Split guest name into first and last
    guest_parts = guest_name.split(" ", 1)
    if len(guest_parts) == 2:
        firstname = guest_parts[0].strip()
        lastname = guest_parts[1].strip()
    else:
        firstname = guest_parts[0].strip()
        lastname = ""
    
    return firstname, lastname, site_name, arrival_date


def get_stage_name(stage_id):
    """Get human-readable stage name from stage ID."""
    return STAGE_NAMES.get(stage_id, stage_id)


def test_stage_updates(guest_firstname=None, guest_lastname=None, site_name=None, arrival_date=None, 
                       full_name=None, stage_id=None, test_all=False, dry_run=False):
    """
    Test moving an opportunity through different stages using name matching.
    
    Args:
        guest_firstname: Guest first name
        guest_lastname: Guest last name
        site_name: Site name
        arrival_date: Arrival date (YYYY-MM-DD format)
        full_name: Full opportunity name (alternative to individual components)
        stage_id: Specific stage ID to test (if None and test_all=False, uses current stage)
        test_all: If True, tests all stage transitions sequentially
        dry_run: If True, only simulates the operations
    """
    global DRY_RUN_MODE
    
    # Set dry-run mode
    if dry_run:
        import utils.ghl_api
        utils.ghl_api.DRY_RUN_MODE = True
        print("\n" + "=" * 70)
        print("DRY-RUN MODE: Simulating operations (no actual changes)")
        print("=" * 70 + "\n")
    else:
        import utils.ghl_api
        utils.ghl_api.DRY_RUN_MODE = False
        print("\n" + "=" * 70)
        print("LIVE MODE: Will make actual changes to GHL")
        print("=" * 70 + "\n")
    
    # Validate configuration
    if not GHL_LOCATION_ID:
        print("❌ ERROR: GHL_LOCATION_ID is not set in .env file")
        return False
    
    if not GHL_PIPELINE_ID:
        print("❌ ERROR: GHL_PIPELINE_ID is not set in .env file")
        return False
    
    # Parse name if full_name provided, otherwise use individual components
    if full_name:
        parsed_firstname, parsed_lastname, parsed_site, parsed_arrival = parse_opportunity_name(full_name)
        if not parsed_firstname:
            print(f"❌ ERROR: Could not parse opportunity name: {full_name}")
            print("   Expected format: 'Firstname Lastname - Site Name - YYYY-MM-DD'")
            return False
        guest_firstname = guest_firstname or parsed_firstname
        guest_lastname = guest_lastname or parsed_lastname
        site_name = site_name or parsed_site
        arrival_date = arrival_date or parsed_arrival
    
    # Validate required fields
    if not (guest_firstname and guest_lastname and site_name and arrival_date):
        print("❌ ERROR: Missing required fields for name matching")
        print("   Required: guest_firstname, guest_lastname, site_name, arrival_date")
        print("   Or provide: --name 'Firstname Lastname - Site - YYYY-MM-DD'")
        return False
    
    # Format arrival date (ensure it's just the date part)
    if " " in arrival_date:
        arrival_date = arrival_date.split(" ")[0]
    
    # Build expected opportunity name
    expected_name = f"{guest_firstname.strip()} {guest_lastname.strip()} - {site_name.strip()} - {arrival_date.strip()}"
    
    # Show details
    print("\n" + "=" * 70)
    print("Opportunity Search Details:")
    print("=" * 70)
    print(f"Guest: {guest_firstname} {guest_lastname}")
    print(f"Site: {site_name}")
    print(f"Arrival: {arrival_date}")
    print(f"Expected Opportunity Name: {expected_name}")
    print("=" * 70 + "\n")
    
    # Create a minimal booking object for update_opportunity function
    # (We don't need full booking data, just enough for the update)
    booking = {
        "booking_id": "TEST",  # Not used for name matching
        "site_name": site_name,
        "booking_arrival": f"{arrival_date} 14:00:00",
        "booking_departure": f"{arrival_date} 11:00:00",
        "booking_status": "placed",
        "booking_total": 0,
        "booking_adults": 2,
        "booking_children": 0,
        "booking_infants": 0,
        "discount_code": "",
        "pets": "",
        "guests": [{
            "firstname": guest_firstname,
            "lastname": guest_lastname,
            "contact_details": []
        }]
    }
    
    # Get access token
    print("[TOKEN] Getting access token...")
    access_token = get_ghl_token()
    if not access_token:
        access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
    
    if not access_token:
        print("❌ ERROR: Could not get access token")
        return False
    print("[TOKEN] ✅ Access token obtained\n")
    
    # Find existing opportunity by name
    print("[STEP 1] Finding opportunity by name matching...")
    print("-" * 70)
    opp_id, opp_data = find_opportunity_by_booking_id(
        "TEST",  # booking_id not used for name matching
        guest_firstname=guest_firstname,
        guest_lastname=guest_lastname,
        site_name=site_name,
        booking_arrival=f"{arrival_date} 14:00:00"
    )
    
    if not opp_id:
        print("❌ ERROR: Could not find existing opportunity")
        print("   Make sure the opportunity exists in GHL with the expected name format")
        return False
    
    print(f"✅ Found opportunity: {opp_id}")
    if opp_data:
        current_stage = opp_data.get('pipelineStageId', 'Unknown')
        current_stage_name = get_stage_name(current_stage)
        print(f"   Current Stage: {current_stage_name} ({current_stage})")
        print(f"   Name: {opp_data.get('name', 'Unknown')}")
    print("-" * 70 + "\n")
    
    # Get contact ID (we don't have email/phone from name matching, so use empty)
    # The contact should already exist in GHL from the opportunity
    email = ""
    phone = ""
    location_id = TEST_LOCATION_ID if TEST_MODE else GHL_LOCATION_ID
    
    # Try to get contact ID from the existing opportunity if available
    contact_id = None
    if opp_data and opp_data.get('contactId'):
        contact_id = opp_data.get('contactId')
        print(f"[CONTACT] Using contact ID from opportunity: {contact_id}")
    else:
        # Create/get contact (will find existing by name if it exists)
        contact_id = get_contact_id(access_token, location_id, guest_firstname, guest_lastname, email, phone)
        if not contact_id:
            print("⚠️  WARNING: Could not get/create contact, but continuing with update")
    
    if not contact_id:
        print("❌ ERROR: Could not get/create contact")
        return False
    
    # Test moving through different stages
    print("[STEP 2] Testing stage updates...")
    print("=" * 70)
    
    original_opp_id = opp_id
    results = []
    
    # Determine which stages to test
    if test_all:
        # Test all stages in order
        test_stages = [
            ("arriving_soon", STAGE_IDS["arriving_soon"]),
            ("arriving_today", STAGE_IDS["arriving_today"]),
            ("staying_now", STAGE_IDS["staying_now"]),
            ("checking_out", STAGE_IDS["checking_out"]),
            ("checked_out", STAGE_IDS["checked_out"]),
        ]
    elif stage_id:
        # Test specific stage
        stage_name = None
        for name, sid in STAGE_IDS.items():
            if sid == stage_id or name == stage_id:
                stage_name = name
                stage_id = sid
                break
        if not stage_name:
            print(f"❌ ERROR: Invalid stage ID: {stage_id}")
            return False
        test_stages = [(stage_name, stage_id)]
    else:
        print("❌ ERROR: Must specify either --stage-id or --test-all")
        return False
    
    for stage_name, stage_id in test_stages:
        print(f"\n[TEST] Moving to stage: {stage_name} ({stage_id})")
        print("-" * 70)
        
        if dry_run:
            print(f"[DRY RUN] Would update opportunity {opp_id} to stage {stage_name}")
            results.append((stage_name, True, "DRY_RUN"))
            continue
        
        # Update the opportunity
        try:
            success = update_opportunity(opp_id, booking, access_token, stage_id, contact_id, opp_data)
            
            if success:
                print(f"✅ Successfully updated to {stage_name}")
                results.append((stage_name, True, "SUCCESS"))
                
                # Wait a moment for GHL to process
                time.sleep(2)
                
                # Verify the opportunity still exists with same ID
                print(f"[VERIFY] Verifying opportunity ID is unchanged...")
                new_opp_id, new_opp_data = find_opportunity_by_booking_id(
                    "TEST",  # booking_id not used
                    guest_firstname=guest_firstname,
                    guest_lastname=guest_lastname,
                    site_name=site_name,
                    booking_arrival=f"{arrival_date} 14:00:00"
                )
                
                if new_opp_id == opp_id:
                    print(f"✅ VERIFIED: Same opportunity ID ({opp_id}) - was UPDATED, not recreated!")
                    if new_opp_data:
                        new_stage = new_opp_data.get('pipelineStageId', 'Unknown')
                        if new_stage == stage_id:
                            print(f"✅ VERIFIED: Stage correctly set to {stage_name}")
                        else:
                            print(f"⚠️  WARNING: Stage mismatch (expected {stage_id}, got {new_stage})")
                    opp_data = new_opp_data  # Update for next iteration
                else:
                    print(f"❌ ERROR: Opportunity ID changed! ({opp_id} -> {new_opp_id})")
                    print(f"   This means it was deleted and recreated (not what we want)")
                    results.append((stage_name, False, "ID_CHANGED"))
                    break
            else:
                print(f"❌ Failed to update to {stage_name}")
                results.append((stage_name, False, "UPDATE_FAILED"))
                break
                
        except Exception as e:
            print(f"❌ ERROR: Exception during update: {e}")
            import traceback
            traceback.print_exc()
            results.append((stage_name, False, f"EXCEPTION: {e}"))
            break
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    print(f"\nResults: {passed}/{total} stage transitions successful")
    print("\nStage Transitions:")
    for stage_name, success, status in results:
        status_icon = "✅" if success else "❌"
        print(f"  {status_icon} {stage_name}: {status}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED: Opportunity updates are working correctly!")
        print(f"   Opportunity ID remained constant: {original_opp_id}")
        print("   All stage transitions completed without delete/recreate")
    else:
        print(f"\n⚠️  SOME TESTS FAILED: {total - passed} stage transition(s) failed")
    
    print("=" * 70)
    
    return passed == total


def main():
    parser = argparse.ArgumentParser(
        description="Test opportunity stage updates using name matching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test specific stage with full name
  python test_stage_updates.py --name "Test Test - Bush 001 - 2026-01-13" --stage-id arriving_today
  
  # Test specific stage with individual components
  python test_stage_updates.py --guest "Test Test" --site "Bush 001" --arrival "2026-01-13" --stage-id arriving_today
  
  # Test all stages sequentially
  python test_stage_updates.py --name "Test Test - Bush 001 - 2026-01-13" --test-all
  
  # Dry-run (simulate only)
  python test_stage_updates.py --name "Test Test - Bush 001 - 2026-01-13" --stage-id arriving_today --dry-run
        """
    )
    
    # Name input options (mutually exclusive)
    name_group = parser.add_mutually_exclusive_group(required=True)
    name_group.add_argument(
        "--name",
        type=str,
        help="Full opportunity name: 'Firstname Lastname - Site Name - YYYY-MM-DD'"
    )
    name_group.add_argument(
        "--guest",
        type=str,
        help="Guest name: 'Firstname Lastname' (requires --site and --arrival)"
    )
    
    parser.add_argument(
        "--site",
        type=str,
        help="Site name (required if using --guest)"
    )
    parser.add_argument(
        "--arrival",
        type=str,
        help="Arrival date in YYYY-MM-DD format (required if using --guest)"
    )
    
    # Stage options (mutually exclusive)
    stage_group = parser.add_mutually_exclusive_group(required=True)
    stage_group.add_argument(
        "--stage-id",
        type=str,
        help="Stage to test: 'arriving_today', 'arriving_soon', etc. or full stage ID"
    )
    stage_group.add_argument(
        "--test-all",
        action="store_true",
        help="Test all stage transitions sequentially"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate only (don't make actual changes)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.guest and not (args.site and args.arrival):
        parser.error("--guest requires --site and --arrival")
    
    # Parse guest name if provided
    guest_firstname = None
    guest_lastname = None
    if args.guest:
        guest_parts = args.guest.split(" ", 1)
        if len(guest_parts) == 2:
            guest_firstname = guest_parts[0].strip()
            guest_lastname = guest_parts[1].strip()
        else:
            guest_firstname = guest_parts[0].strip()
            guest_lastname = ""
    
    # Resolve stage ID if using name
    stage_id = args.stage_id
    if stage_id and stage_id in STAGE_IDS:
        stage_id = STAGE_IDS[stage_id]
    
    try:
        success = test_stage_updates(
            guest_firstname=guest_firstname,
            guest_lastname=guest_lastname,
            site_name=args.site,
            arrival_date=args.arrival,
            full_name=args.name,
            stage_id=stage_id,
            test_all=args.test_all,
            dry_run=args.dry_run
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

