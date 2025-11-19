import httpx
from typing import Dict, List
from .rms_auth import rms_auth
import os

class RMSApiClient:
    def __init__(self):
        self.base_url = os.getenv("RMS_BASE_URL", "https://restapi8.rmscloud.com")
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        token = await rms_auth.get_token()
        
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
                    rms_auth.clear_cache()
                    
                    new_token = await rms_auth.get_token()
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
            # Try to parse error response for field names
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
        # CRITICAL FIX: Set ignoreMandatoryFieldWarnings=TRUE to bypass area requirement
        endpoint = "/reservations?ignoreMandatoryFieldWarnings=true&useIbeDepositRules=true"
        return await self._make_request("POST", endpoint, json=payload)
    
    async def get_reservation(self, reservation_id: int) -> Dict:
        return await self._make_request("GET", f"/reservations/{reservation_id}")
    
    async def cancel_reservation(self, reservation_id: int) -> Dict:
        return await self._make_request("DELETE", f"/reservations/{reservation_id}")
    
    async def search_reservations(self, payload: Dict) -> List[Dict]:
        return await self._make_request("POST", "/reservations/search", json=payload)
    
    async def get_account(self, account_id: int) -> Dict:
        payload = {
            "accountClass": "Guest",
            "ids": [account_id]
        }
        results = await self._make_request("POST", "/accounts/search", json=payload)
        # The API may return a list or dict; normalize to a single account dict
        if isinstance(results, list) and results:
            return results[0]
        elif isinstance(results, dict):
            # Some APIs return {"items": [...]}
            items = results.get("items") or results.get("accounts") or results.get("data") or []
            if isinstance(items, list) and items:
                return items[0]
            return results
        return {}
    
    async def search_guests(self, payload: Dict) -> List[Dict]:
        return await self._make_request("POST", "/guests/search", json=payload)
    
    async def create_guest(self, payload: Dict) -> Dict:
        """
        Create a new guest account in RMS.
        
        Args:
            payload: Guest information including:
                - propertyId (required)
                - guestGiven (required)
                - guestSurname (required)
                - email (required)
                - mobile (optional)
                - address1, city, state, postcode, country (optional)
        
        Returns:
            Created guest data with guest ID
        """
        return await self._make_request("POST", "/guests", json=payload)
    
    async def get_areas(self, property_id: int) -> List[Dict]:
        """
        Get all areas/channels for a property.
        Areas represent booking sources/channels (e.g., Direct, Online, Walk-in, etc.)
        
        Args:
            property_id: The property ID
            
        Returns:
            List of area/channel objects with id, name, etc.
        """
        return await self._make_request("GET", f"/areas?propertyId={property_id}")

rms_client = RMSApiClient()