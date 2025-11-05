import httpx
from typing import Dict, List, Any
from .rms_auth import rms_auth
import os

class RMSApiClient:
    def __init__(self):
        self.base_url = os.getenv("RMS_BASE_URL", "https://restapi8.rmscloud.com")
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make authenticated request to RMS API"""
        token = await rms_auth.get_token()
        
        # RMS uses 'authtoken' header, not 'Authorization: Bearer'
        headers = {
            "authtoken": token,  # Changed from Authorization: Bearer
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        url = f"{self.base_url}{endpoint}"
        
        print(f"📤 {method} {url}")
        print(f"   Using token: {token[:20]}...")
        
        # Print payload if it's a POST/PUT request
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
                
                # If 401, token might be invalid - clear cache and retry once
                if response.status_code == 401:
                    print("⚠️ 401 Unauthorized - clearing token cache and retrying...")
                    rms_auth.clear_cache()
                    
                    # Get new token
                    new_token = await rms_auth.get_token()
                    headers["authtoken"] = new_token  # Update header with new token
                    
                    # Retry request
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
                
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP {e.response.status_code}: {e.response.text}")
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
        return await self._make_request("POST", "/reservations", json=payload)
    
    async def get_reservation(self, reservation_id: int) -> Dict:
        return await self._make_request("GET", f"/reservations/{reservation_id}")
    
    async def cancel_reservation(self, reservation_id: int) -> Dict:
        return await self._make_request("DELETE", f"/reservations/{reservation_id}")
    
    async def search_reservations(self, payload: Dict) -> List[Dict]:
        return await self._make_request("POST", "/reservations/search", json=payload)

rms_client = RMSApiClient()
