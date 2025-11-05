# filepath: utils/create_ghl_subaccount.py
import requests
import json
from config.config import GHL_AGENCY_API_KEY
from .logger import get_logger

log = get_logger("GHLSubAccount")

def create_ghl_subaccount(
    name: str,
    address: str = None,
    city: str = None,
    state: str = None,
    postal_code: str = None,
    country: str = "US",
    website: str = None,
    timezone: str = "America/New_York",
    first_name: str = None,
    last_name: str = None,
    email: str = None,
    phone: str = None,
    snapshot_id: str = None,
    settings: dict = None
):
    """
    Creates a new sub-account (location) in GoHighLevel using Agency API Key.
    
    Note: companyId is NOT required when using Agency API Key.
    
    Args:
        name: Required. Business name for the sub-account
        address: Street address
        city: City name
        state: State/Province code (e.g., "CA", "NY", "VIC")
        postal_code: ZIP/Postal code
        country: Country code (default: "US")
        website: Business website URL
        timezone: Timezone (default: "America/New_York")
        first_name: Primary contact first name
        last_name: Primary contact last name
        email: Primary contact email
        phone: Primary contact phone (E.164 format recommended, e.g., "+1234567890")
        snapshot_id: Optional snapshot ID to apply template
        settings: Optional dict with settings like:
            {
                "allowDuplicateContact": False,
                "allowDuplicateOpportunity": False,
                "allowFacebookNameMerge": False
            }
    
    Returns:
        dict: Response from GHL API with location details including 'id', or None on error
    """
    
    if not GHL_AGENCY_API_KEY:
        error_msg = "GHL_AGENCY_API_KEY not configured. Get it from Agency Dashboard → Settings → API Keys"
        log.error(error_msg)
        print(f"❌ Error: {error_msg}")
        return None
    
    if not name:
        error_msg = "name is required"
        log.error(error_msg)
        print(f"❌ Error: {error_msg}")
        return None
    
    # API endpoint for creating locations
    url = "https://rest.gohighlevel.com/v1/locations/"
    
    headers = {
        "Authorization": f"Bearer {GHL_AGENCY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Build request body
    data = {
        "name": name
    }
    
    # Add optional fields
    if address:
        data["address"] = address
    if city:
        data["city"] = city
    if state:
        data["state"] = state
    if postal_code:
        data["postalCode"] = postal_code
    if country:
        data["country"] = country
    if website:
        data["website"] = website
    if timezone:
        data["timezone"] = timezone
    if first_name:
        data["firstName"] = first_name
    if last_name:
        data["lastName"] = last_name
    if email:
        data["email"] = email
    if phone:
        data["phone"] = phone
    if snapshot_id:
        data["snapshotId"] = snapshot_id
    if settings:
        data["settings"] = settings
    
    try:
        log.info(f"Creating GHL sub-account: {name}")
        print(f"[GHL] Creating sub-account: {name}")
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            location_id = result.get("id")
            location_name = result.get("name")
            
            log.info(f"Successfully created sub-account: {location_name} (ID: {location_id})")
            print(f"✅ Successfully created sub-account: {location_name}")
            print(f"   Location ID: {location_id}")
            
            return result
        else:
            error_msg = f"Failed to create sub-account: {response.status_code} - {response.text}"
            log.error(error_msg)
            print(f"❌ {error_msg}")
            return None
            
    except Exception as e:
        error_msg = f"Exception while creating sub-account: {str(e)}"
        log.exception(error_msg)
        print(f"❌ {error_msg}")
        return None


def create_ghl_subaccount_simple(
    name: str,
    email: str = None,
    phone: str = None,
    city: str = None,
    state: str = None,
    country: str = "US"
):
    """
    Simplified function to create a sub-account with minimal required fields.
    
    Args:
        name: Business name (required)
        email: Primary contact email (optional)
        phone: Primary contact phone (optional)
        city: City name (optional)
        state: State/Province code (optional)
        country: Country code (default: "US")
    
    Returns:
        dict: Response from GHL API, or None on error
    """
    return create_ghl_subaccount(
        name=name,
        email=email,
        phone=phone,
        city=city,
        state=state,
        country=country
    )


def delete_ghl_subaccount(location_id: str):
    """
    Deletes a sub-account (location) by its ID.
    
    Args:
        location_id: The ID of the location to delete
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not GHL_AGENCY_API_KEY:
        log.error("GHL_AGENCY_API_KEY not configured")
        print("❌ Error: GHL_AGENCY_API_KEY not configured")
        return False
    
    if not location_id:
        log.error("location_id is required")
        print("❌ Error: location_id is required")
        return False
    
    url = f"https://rest.gohighlevel.com/v1/locations/{location_id}"
    headers = {
        "Authorization": f"Bearer {GHL_AGENCY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        log.info(f"Deleting GHL sub-account: {location_id}")
        response = requests.delete(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            log.info(f"Successfully deleted sub-account: {location_id}")
            print(f"✅ Successfully deleted sub-account: {location_id}")
            return True
        else:
            error_msg = f"Failed to delete sub-account: {response.status_code} - {response.text}"
            log.error(error_msg)
            print(f"❌ {error_msg}")
            return False
            
    except Exception as e:
        error_msg = f"Exception while deleting sub-account: {str(e)}"
        log.exception(error_msg)
        print(f"❌ {error_msg}")
        return False


# Example usage
if __name__ == "__main__":
    # Example: Create a simple sub-account
    result = create_ghl_subaccount_simple(
        name="My New Business",
        email="admin@mynewbusiness.com",
        phone="+1234567890",
        city="San Francisco",
        state="CA",
        country="US"
    )
    
    if result:
        print(f"\n📋 Location Details:")
        print(json.dumps(result, indent=2))
        
        # Uncomment to delete the test location
        # location_id = result.get('id')
        # if location_id:
        #     delete_ghl_subaccount(location_id)