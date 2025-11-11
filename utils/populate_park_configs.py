"""
Script to populate park configurations for all GHL sub-accounts.
This can be run to initialize configurations for existing locations.
"""
import sys
from db_park_config import (
    create_park_configurations_table,
    add_park_configuration,
    get_all_park_configurations
)
from logger import get_logger

log = get_logger("PopulateParkConfigs")


def populate_park_configurations():
    """
    Interactive script to add park configurations.
    You can modify this function to bulk-import configurations from a CSV or JSON file.
    """
    
    print("\n" + "="*60)
    print("🏞️  PARK CONFIGURATION SETUP")
    print("="*60)
    
    # First, ensure the table exists
    create_park_configurations_table()
    
    # Show existing configurations
    existing_configs = get_all_park_configurations(include_inactive=True)
    if existing_configs:
        print(f"\n📋 Found {len(existing_configs)} existing configuration(s):")
        for config in existing_configs:
            status = "✅ Active" if config['is_active'] else "❌ Inactive"
            print(f"  • {config['park_name']} ({config['location_id']}) - {status}")
    else:
        print("\n📋 No existing configurations found.")
    
    print("\n" + "-"*60)
    print("Add new park configuration (press Ctrl+C to exit)")
    print("-"*60 + "\n")
    
    while True:
        try:
            # Get park details
            location_id = input("GHL Location ID: ").strip()
            if not location_id:
                print("❌ Location ID is required!")
                continue
            
            park_name = input("Park Name (e.g., 'Sunny Meadows RV Park'): ").strip()
            if not park_name:
                print("❌ Park Name is required!")
                continue
            
            newbook_api_token = input("Newbook API Token: ").strip()
            if not newbook_api_token:
                print("❌ Newbook API Token is required!")
                continue
            
            newbook_api_key = input("Newbook API Key: ").strip()
            if not newbook_api_key:
                print("❌ Newbook API Key is required!")
                continue
            
            newbook_region = input("Newbook Region (e.g., 'US', 'AU'): ").strip()
            if not newbook_region:
                print("❌ Newbook Region is required!")
                continue
            
            ghl_pipeline_id = input("GHL Pipeline ID: ").strip()
            if not ghl_pipeline_id:
                print("❌ GHL Pipeline ID is required!")
                continue
            
            # Optional stage IDs
            print("\n📌 Stage IDs (press Enter to skip):")
            stage_arriving_soon = input("  Stage ID - Arriving Soon: ").strip() or None
            stage_arriving_today = input("  Stage ID - Arriving Today: ").strip() or None
            stage_arrived = input("  Stage ID - Arrived: ").strip() or None
            stage_departing_today = input("  Stage ID - Departing Today: ").strip() or None
            stage_departed = input("  Stage ID - Departed: ").strip() or None
            
            # Add configuration
            success = add_park_configuration(
                location_id=location_id,
                park_name=park_name,
                newbook_api_token=newbook_api_token,
                newbook_api_key=newbook_api_key,
                newbook_region=newbook_region,
                ghl_pipeline_id=ghl_pipeline_id,
                stage_arriving_soon=stage_arriving_soon,
                stage_arriving_today=stage_arriving_today,
                stage_arrived=stage_arrived,
                stage_departing_today=stage_departing_today,
                stage_departed=stage_departed
            )
            
            if success:
                print(f"\n✅ Successfully added configuration for {park_name}!\n")
            else:
                print(f"\n❌ Failed to add configuration. Location ID may already exist.\n")
            
            # Ask if they want to add another
            another = input("Add another configuration? (y/n): ").strip().lower()
            if another != 'y':
                break
                
        except KeyboardInterrupt:
            print("\n\n👋 Exiting setup...")
            break
        except Exception as e:
            log.error(f"Error adding park configuration: {e}")
            print(f"\n❌ Error: {e}\n")
    
    # Show final summary
    all_configs = get_all_park_configurations(include_inactive=True)
    print("\n" + "="*60)
    print(f"📊 FINAL SUMMARY - {len(all_configs)} Total Configuration(s)")
    print("="*60)
    for config in all_configs:
        status = "✅ Active" if config['is_active'] else "❌ Inactive"
        print(f"  • {config['park_name']} ({config['location_id']}) - {status}")
    print()


def bulk_import_from_dict(configs_list):
    """
    Bulk import configurations from a list of dictionaries.
    
    Example usage:
        configs = [
            {
                "location_id": "loc_123",
                "park_name": "Park A",
                "newbook_api_token": "token1",
                "newbook_api_key": "key1",
                "newbook_region": "US",
                "ghl_pipeline_id": "pipeline1",
                "stage_arriving_soon": "stage1",
                ...
            },
            ...
        ]
        bulk_import_from_dict(configs)
    """
    create_park_configurations_table()
    
    print(f"\n📦 Bulk importing {len(configs_list)} configuration(s)...")
    
    success_count = 0
    failed_count = 0
    
    for config in configs_list:
        try:
            success = add_park_configuration(**config)
            if success:
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            log.error(f"Error importing config for {config.get('park_name', 'Unknown')}: {e}")
            failed_count += 1
    
    print(f"\n✅ Successfully imported: {success_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"📊 Total: {len(configs_list)}\n")


if __name__ == "__main__":
    """
    Run this script to interactively add park configurations:
        python -m utils.populate_park_configs
    """
    populate_park_configurations()

