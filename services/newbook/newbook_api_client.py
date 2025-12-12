import base64
import requests
from typing import Dict, Optional
from config.config import NEWBOOK_API_BASE, USERNAME, PASSWORD


class NewbookApiClient:
    """
    API Client for Newbook API requests.
    Handles authentication and API calls.
    """
    
    def __init__(self, credentials: dict = None):
        """
        Initialize Newbook API Client with optional credentials.
        
        Args:
            credentials: dict with location_id, api_key, region
                        If not provided, will try to load from environment variables.
        """
        self.base_url = NEWBOOK_API_BASE
        self.credentials = credentials
        
        # Basic Auth setup
        username = USERNAME
        password = PASSWORD
        user_pass = f"{username}:{password}"
        encoded_credentials = base64.b64encode(user_pass.encode()).decode()
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_credentials}",
        }
    
    @property
    def api_key(self) -> Optional[str]:
        """Get API key from credentials or environment"""
        if self.credentials:
            return self.credentials.get('api_key')
        from config.config import API_KEY
        return API_KEY
    
    @property
    def region(self) -> Optional[str]:
        """Get region from credentials or environment"""
        if self.credentials:
            return self.credentials.get('region')
        from config.config import REGION
        return REGION
    
    def _make_request(self, method: str, endpoint: str, json_data: dict = None, timeout: int = 15) -> Dict:
        """
        Make HTTP request to Newbook API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            json_data: JSON payload for POST requests
            timeout: Request timeout in seconds
            
        Returns:
            Response JSON data
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json_data,
                verify=False,  # Only for local testing
                timeout=timeout
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Newbook API request failed: {str(e)}")
    
    def get_availability(self, payload: dict) -> Dict:
        """Get availability and pricing"""
        return self._make_request("POST", "/bookings_availability_pricing", json_data=payload)
    
    def create_booking(self, payload: dict) -> Dict:
        """Create a new booking"""
        return self._make_request("POST", "/bookings_create", json_data=payload)
    
    def list_bookings(self, payload: dict) -> Dict:
        """List bookings"""
        return self._make_request("POST", "/bookings_list", json_data=payload)

