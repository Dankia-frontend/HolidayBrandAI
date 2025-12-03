import httpx
from typing import Dict, List, Optional
import os
from datetime import datetime, timedelta


class RMSApiClient:
    def __init__(self, credentials: dict = None):
        """
        Initialize RMS API Client with optional credentials.
        
        Args:
            credentials: dict with location_id, client_id, client_pass (decrypted), agent_id
                        If not provided, will try to load from environment variables.
        """
        self.base_url = os.getenv("RMS_BASE_URL", "https://restapi8.rmscloud.com")
        self.credentials = credentials
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
    
    @property
    def auth_agent_id(self) -> int:
        """Agent ID for authentication - always from env var RMS_AGENT_ID"""
        return int(os.getenv("RMS_AGENT_ID", "0"))
    
    @property
    def query_agent_id(self) -> int:
        """Agent ID for queries (availability, reservations) - from database credentials"""
        if self.credentials:
            return self.credentials.get('agent_id')
        return int(os.getenv("RMS_QUERY_AGENT_ID", "0"))
    
    @property
    def agent_password(self) -> str:
        return os.getenv("RMS_AGENT_PASSWORD", "")
    
    @property
    def client_id(self) -> int:
        if self.credentials:
            return self.credentials.get('client_id')
        return int(os.getenv("RMS_CLIENT_ID", "0"))
    
    @property
    def client_password(self) -> str:
        if self.credentials:
            return self.credentials.get('client_pass')  # Already decrypted
        return os.getenv("RMS_CLIENT_PASSWORD", "")
    
    @property
    def use_training_db(self) -> bool:
        return os.getenv("RMS_USE_TRAINING", "false").lower() == "true"
    
    async def _get_token(self) -> str:
        """Get or generate authentication token"""
        if self._token and self._token_expiry:
            if datetime.now() < self._token_expiry:
                print(f"🔒 Using cached token (expires: {self._token_expiry})")
                return self._token
        
        print("🔄 Token expired or missing, generating new token...")
        return await self._generate_token()
    
    async def _generate_token(self) -> str:
        """Generate a new authentication token"""
        url = f"{self.base_url}/authToken"
        payload = {
            "agentId": self.auth_agent_id,  # Use auth agent ID from env (RMS_AGENT_ID)
            "agentPassword": self.agent_password,
            "clientId": self.client_id,
            "clientPassword": self.client_password,
            "useTrainingDatabase": self.use_training_db,
            "moduleType": ["guestservices"]
        }
        
        print(f"📡 Requesting token from: {url}")
        print(f"   Auth Agent ID (from env RMS_AGENT_ID): {self.auth_agent_id}")
        print(f"   Agent Password: {'*' * len(self.agent_password) if self.agent_password else 'NOT SET!'}")
        print(f"   Client ID (from DB): {self.client_id}")
        print(f"   Client Password: {'*' * len(self.client_password) if self.client_password else 'NOT SET!'}")
        print(f"   Query Agent ID (from DB agent_id): {self.query_agent_id}")
        print(f"   Use Training: {self.use_training_db}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30.0)
                
                print(f"   Response Status: {response.status_code}")
                
                if response.status_code != 200:
                    print(f"   Error Response: {response.text}")
                
                response.raise_for_status()
                data = response.json()
                
                self._token = data.get("token")
                expiry_str = data.get("expiryDate")
                
                if not self._token:
                    print(f"   Response Data: {data}")
                    raise Exception("No token received from RMS API")
                
                if expiry_str:
                    try:
                        self._token_expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                    except:
                        self._token_expiry = datetime.now() + timedelta(hours=24)
                
                print(f"✅ RMS token generated successfully")
                print(f"   Token: {self._token[:20]}...")
                print(f"   Expires: {self._token_expiry}")
                
                return self._token
                
        except httpx.HTTPError as e:
            print(f"❌ HTTP error during token generation: {e}")
            if hasattr(e, 'response'):
                print(f"   Response body: {e.response.text}")
            raise
        except Exception as e:
            print(f"❌ Error generating token: {e}")
            raise
    
    def _clear_token_cache(self):
        """Clear the token cache"""
        self._token = None
        self._token_expiry = None
        print("🗑️ Token cache cleared")
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        token = await self._get_token()
        
        headers = {
            "authtoken": token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        url = f"{self.base_url}{endpoint}"
        
        print(f"📤 {method} {url}")
        print(f"   Using token: {token[:20]}...")
        
        if method in ["POST", "PUT", "PATCH"] and "json" in kwargs:
            import json as json_lib
            payload_str = json_lib.dumps(kwargs["json"], indent=2)
            print(f"   📦 Payload:")
            print(f"{payload_str}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=30.0,
                    **kwargs
                )
                
                print(f"📥 Response: {response.status_code}")
                
                if response.status_code == 401:
                    print("⚠️ 401 Unauthorized - clearing token cache and retrying...")
                    self._clear_token_cache()
                    
                    new_token = await self._get_token()
                    headers["authtoken"] = new_token
                    
                    print(f"🔄 Retrying {method} {url}")
                    print(f"   Using new token: {new_token[:20]}...")
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        timeout=30.0,
                        **kwargs
                    )
                    print(f"📥 Retry Response: {response.status_code}")
                
                # Print full response body for debugging
                try:
                    response_body = response.text
                    print(f"📄 Response Body: {response_body}")
                except:
                    pass
                
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP {e.response.status_code}: {e.response.text}")
            try:
                error_data = e.response.json()
                print(f"❌ Error details: {error_data}")
            except:
                pass
            raise
        except Exception as e:
            print(f"❌ Request failed: {e}")
            raise
    
    async def get_properties(self) -> List[Dict]:
        return await self._make_request("GET", "/properties")
    
    async def get_categories(self, property_id: int) -> List[Dict]:
        return await self._make_request("GET", f"/categories?propertyId={property_id}")
    
    async def get_rates(self, category_id: int) -> List[Dict]:
        return await self._make_request("GET", f"/rates?categoryId={category_id}")
    
    async def get_rates_grid(self, payload: Dict) -> Dict:
        return await self._make_request("POST", "/rates/grid", json=payload)
    
    async def create_reservation(self, payload: Dict) -> Dict:
        endpoint = "/reservations?ignoreMandatoryFieldWarnings=true&useIbeDepositRules=true"
        return await self._make_request("POST", endpoint, json=payload)
    
    async def get_reservation(self, reservation_id: int) -> Dict:
        return await self._make_request("GET", f"/reservations/{reservation_id}")
    
    async def cancel_reservation(self, reservation_id: int) -> Dict:
        return await self._make_request("DELETE", f"/reservations/{reservation_id}")
    
    async def search_reservations(self, payload: Dict) -> List[Dict]:
        return await self._make_request("POST", "/reservations/search", json=payload)
    
    async def search_guests(self, payload: Dict) -> List[Dict]:
        return await self._make_request("POST", "/guests/search", json=payload)
    
    async def create_guest(self, payload: Dict) -> Dict:
        return await self._make_request("POST", "/guests", json=payload)
    
    async def get_areas(self, property_id: int) -> List[Dict]:
        return await self._make_request("GET", f"/areas?propertyId={property_id}")
    
    async def get_available_areas(self, payload: Dict) -> List[Dict]:
        """
        Get available areas/rooms for a specific date range and category.
        Uses dateFrom/dateTo format which works for most RMS instances.
        
        Payload example:
        {
            "propertyId": 123,
            "categoryId": 5,
            "arrivalDate": "2026-08-01",  # Will be converted to dateFrom
            "departureDate": "2026-08-02",  # Will be converted to dateTo
            "adults": 2,
            "children": 0
        }
        """
        # Use dateFrom/dateTo format (works for this RMS instance)
        # Convert the payload to the working format
        api_payload = {
            "propertyId": payload.get("propertyId"),
            "adults": payload.get("adults"),
            "children": payload.get("children"),
            "dateFrom": payload.get("arrivalDate"),
            "dateTo": payload.get("departureDate"),
            "categoryIds": [payload.get("categoryId")]
        }
        
        try:
            print(f"📡 Calling /availableAreas API...")
            return await self._make_request("POST", "/availableAreas", json=api_payload)
        except httpx.HTTPStatusError as e:
            # If the dateFrom/dateTo format fails, try the alternative format as fallback
            if e.response.status_code == 400:
                print(f"⚠️ dateFrom/dateTo format failed, trying arrivalDate/departureDate...")
                
                # Try original format as fallback
                fallback_payload = {
                    "propertyId": payload.get("propertyId"),
                    "categoryId": payload.get("categoryId"),
                    "arrivalDate": payload.get("arrivalDate"),
                    "departureDate": payload.get("departureDate"),
                    "adults": payload.get("adults"),
                    "children": payload.get("children")
                }
                
                return await self._make_request("POST", "/availableAreas", json=fallback_payload)
            else:
                # Re-raise for other status codes
                raise


# Create a default instance for backward compatibility
rms_client = RMSApiClient()