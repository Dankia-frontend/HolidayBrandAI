"""
Dynamic configuration utility for retrieving park-specific settings.
This module provides helper functions to get location-specific configurations
for Newbook API and GHL integrations.
"""
from typing import Optional, Dict, Any
from utils.db_park_config import get_park_configuration
from utils.logger import get_logger
from fastapi import HTTPException

log = get_logger("DynamicConfig")


class ParkConfig:
    """
    Wrapper class for park configuration with easy property access.
    """
    def __init__(self, config_dict: Dict[str, Any]):
        self._config = config_dict
    
    @property
    def location_id(self) -> str:
        return self._config.get('location_id')
    
    @property
    def park_name(self) -> str:
        return self._config.get('park_name')
    
    @property
    def newbook_api_token(self) -> str:
        return self._config.get('newbook_api_token')
    
    @property
    def newbook_api_key(self) -> str:
        return self._config.get('newbook_api_key')
    
    @property
    def newbook_region(self) -> str:
        return self._config.get('newbook_region')
    
    @property
    def ghl_pipeline_id(self) -> str:
        return self._config.get('ghl_pipeline_id')
    
    @property
    def stage_arriving_soon(self) -> Optional[str]:
        return self._config.get('stage_arriving_soon')
    
    @property
    def stage_arriving_today(self) -> Optional[str]:
        return self._config.get('stage_arriving_today')
    
    @property
    def stage_arrived(self) -> Optional[str]:
        return self._config.get('stage_arrived')
    
    @property
    def stage_departing_today(self) -> Optional[str]:
        return self._config.get('stage_departing_today')
    
    @property
    def stage_departed(self) -> Optional[str]:
        return self._config.get('stage_departed')
    
    def get_newbook_headers(self) -> Dict[str, str]:
        """
        Generate Newbook API headers for this park configuration.
        Uses the park-specific API token (username) for Basic Auth.
        """
        import base64
        
        # Use newbook_api_token as the username/password for Basic Auth
        user_pass = f"{self.newbook_api_token}:{self.newbook_api_token}"
        encoded_credentials = base64.b64encode(user_pass.encode()).decode()
        
        return {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_credentials}"
        }
    
    def get_stage_id_by_booking_status(
        self, 
        booking_status: str, 
        arrival_dt=None, 
        departure_dt=None,
        today=None
    ) -> Optional[str]:
        """
        Determine the appropriate GHL stage ID based on booking status and dates.
        
        Args:
            booking_status: Status of the booking (e.g., 'arrived', 'departed')
            arrival_dt: Arrival datetime object
            departure_dt: Departure datetime object
            today: Today's datetime object
        
        Returns:
            str: The appropriate stage ID or None
        """
        from datetime import datetime, timedelta
        
        if today is None:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)
        seven_days = today + timedelta(days=7)
        
        # Arriving soon (1-7 days from now)
        if arrival_dt and arrival_dt >= tomorrow and arrival_dt <= seven_days:
            return self.stage_arriving_soon
        
        # Arrived and staying
        if booking_status.lower() == "arrived" and departure_dt and departure_dt >= tomorrow:
            return self.stage_arrived
        
        # Arriving today
        if arrival_dt and arrival_dt >= today and arrival_dt < tomorrow:
            return self.stage_arriving_today
        
        # Departing today
        if booking_status.lower() == "arrived" and departure_dt and departure_dt >= today and departure_dt < day_after:
            return self.stage_departing_today
        
        # Departed
        if booking_status.lower() == "departed":
            return self.stage_departed
        
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Return the raw configuration dictionary."""
        return self._config


def get_dynamic_park_config(location_id: str, raise_on_not_found: bool = True) -> Optional[ParkConfig]:
    """
    Retrieve park configuration dynamically based on location_id.
    
    Args:
        location_id: GHL location ID
        raise_on_not_found: If True, raises HTTPException when config not found
    
    Returns:
        ParkConfig: Configuration object for the park
    
    Raises:
        HTTPException: If configuration not found and raise_on_not_found is True
    """
    config_dict = get_park_configuration(location_id)
    
    if not config_dict:
        error_msg = f"No configuration found for location_id: {location_id}. Please add configuration first."
        log.error(error_msg)
        
        if raise_on_not_found:
            raise HTTPException(
                status_code=404,
                detail=error_msg
            )
        return None
    
    return ParkConfig(config_dict)


def get_newbook_payload_for_location(
    location_id: str,
    additional_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a Newbook API payload with dynamic configuration based on location.
    
    Args:
        location_id: GHL location ID
        additional_params: Additional parameters specific to the API call
    
    Returns:
        dict: Complete payload for Newbook API
    """
    config = get_dynamic_park_config(location_id)
    
    payload = {
        "region": config.newbook_region,
        "api_key": config.newbook_api_key,
        **additional_params
    }
    
    return payload


# Example usage in endpoints:
"""
@app.get("/availability")
def get_availability(
    location_id: str = Query(..., description="GHL Location ID"),
    period_from: str = Query(..., description="Start date"),
    period_to: str = Query(..., description="End date"),
    adults: int = Query(..., description="Number of adults"),
    children: int = Query(..., description="Number of children"),
    daily_mode: str = Query(..., description="Daily mode"),
    _: str = Depends(authenticate_request)
):
    # Get dynamic configuration
    park_config = get_dynamic_park_config(location_id)
    
    # Build payload with park-specific settings
    payload = {
        "region": park_config.newbook_region,
        "api_key": park_config.newbook_api_key,
        "period_from": period_from,
        "period_to": period_to,
        "adults": adults,
        "children": children,
        "daily_mode": daily_mode
    }
    
    # Make API call with park-specific headers
    response = requests.post(
        f"{NEWBOOK_API_BASE}/bookings_availability_pricing",
        headers=park_config.get_newbook_headers(),
        json=payload,
        verify=False,
        timeout=15
    )
    
    return response.json()
"""

