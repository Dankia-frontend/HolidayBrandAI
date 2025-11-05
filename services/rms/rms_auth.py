import httpx
from datetime import datetime
from typing import Optional
import os

class RMSAuth:
    def __init__(self):
        self.base_url = os.getenv("RMS_BASE_URL")
        self.agent_id = int(os.getenv("RMS_AGENT_ID"))
        self.agent_password = os.getenv("RMS_AGENT_PASSWORD")
        self.client_id = int(os.getenv("RMS_CLIENT_ID"))
        self.client_password = os.getenv("RMS_CLIENT_PASSWORD")
        self.use_training_db = os.getenv("RMS_USE_TRAINING", "false").lower() == "true"
        
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
    
    async def get_token(self) -> str:
        """Get valid auth token (from cache or generate new)"""
        # Check if cached token is still valid
        if self._token and self._token_expiry:
            if datetime.now() < self._token_expiry:
                print(f"🔑 Using cached token (expires: {self._token_expiry})")
                return self._token
        
        # Generate new token
        print("🔄 Token expired or missing, generating new token...")
        return await self._generate_token()
    
    async def _generate_token(self) -> str:
        """Generate new auth token from RMS API"""
        url = f"{self.base_url}/authToken"
        payload = {
            "agentId": self.agent_id,
            "agentPassword": self.agent_password,
            "clientId": self.client_id,
            "clientPassword": self.client_password,
            "useTrainingDatabase": self.use_training_db,
            "moduleType": ["crm/marketing"]
        }
        
        print(f"📡 Requesting token from: {url}")
        print(f"   Agent ID: {self.agent_id}, Client ID: {self.client_id}")
        print(f"   Use Training: {self.use_training_db}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30.0)
                
                print(f"   Response Status: {response.status_code}")
                
                if response.status_code != 200:
                    print(f"   Error Response: {response.text}")
                
                response.raise_for_status()
                data = response.json()
                
                # Cache token and expiry
                self._token = data.get("token")
                expiry_str = data.get("expiryDate")
                
                if not self._token:
                    print(f"   Response Data: {data}")
                    raise Exception("No token received from RMS API")
                
                if expiry_str:
                    # Handle different datetime formats
                    try:
                        self._token_expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                    except:
                        # If parsing fails, set expiry to 24 hours from now
                        from datetime import timedelta
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
    
    def clear_cache(self):
        """Clear cached token"""
        self._token = None
        self._token_expiry = None
        print("🗑️ Token cache cleared")

# Singleton instance
rms_auth = RMSAuth()
