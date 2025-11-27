import httpx
from datetime import datetime
from typing import Optional
import os

class RMSAuth:
    def __init__(self):
        self.base_url = os.getenv("RMS_BASE_URL", "https://restapi8.rmscloud.com")
        self.agent_password = os.getenv("RMS_AGENT_PASSWORD")
        self.use_training_db = os.getenv("RMS_USE_TRAINING", "false").lower() == "true"
        
        # These will be set from database via set_credentials()
        self._agent_id: Optional[int] = None
        self._client_id: Optional[int] = None
        self._client_password: Optional[str] = None
        self._location_id: Optional[str] = None
        
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        
        # Flag to track if credentials are loaded from DB
        self._credentials_loaded: bool = False
    
    def _load_credentials_from_db(self):
        """Load credentials from database using rms_db helper"""
        if self._credentials_loaded:
            return
        
        try:
            from utils.rms_db import get_current_rms_instance
            instance = get_current_rms_instance()
            
            if instance:
                self._client_id = instance.get('client_id')
                self._client_password = instance.get('client_pass')  # Already decrypted by rms_db
                self._agent_id = instance.get('agent_id')
                self._location_id = instance.get('location_id')
                self._credentials_loaded = True
                print(f"✅ RMS Auth: Loaded credentials from DB for location {self._location_id}")
                print(f"   Client ID: {self._client_id}, Agent ID: {self._agent_id}")
            else:
                # Fallback to environment variables if no instance set
                print("⚠️ RMS Auth: No instance set in DB, falling back to env vars")
                self._agent_id = int(os.getenv("RMS_AGENT_ID", "0"))
                self._client_id = int(os.getenv("RMS_CLIENT_ID", "0"))
                self._client_password = os.getenv("RMS_CLIENT_PASSWORD", "")
        except Exception as e:
            print(f"⚠️ RMS Auth: Error loading from DB, using env vars: {e}")
            self._agent_id = int(os.getenv("RMS_AGENT_ID", "0"))
            self._client_id = int(os.getenv("RMS_CLIENT_ID", "0"))
            self._client_password = os.getenv("RMS_CLIENT_PASSWORD", "")
    
    def set_credentials(self, client_id: int, client_password: str, agent_id: int, location_id: str = None):
        """
        Manually set credentials (used when loading from database)
        """
        self._client_id = client_id
        self._client_password = client_password
        self._agent_id = agent_id
        self._location_id = location_id
        self._credentials_loaded = True
        
        # Clear token cache when credentials change
        self._token = None
        self._token_expiry = None
        
        print(f"✅ RMS Auth: Credentials set for client_id={client_id}, agent_id={agent_id}")
    
    def set_credentials_from_instance(self, instance: dict):
        """
        Set credentials from an RMS instance dictionary
        """
        if not instance:
            raise ValueError("Instance dictionary is required")
        
        self._client_id = instance.get('client_id')
        self._client_password = instance.get('client_pass')  # Already decrypted
        self._agent_id = instance.get('agent_id')
        self._location_id = instance.get('location_id')
        self._credentials_loaded = True
        
        # Clear token cache when credentials change
        self._token = None
        self._token_expiry = None
        
        print(f"✅ RMS Auth: Credentials set from instance for location={self._location_id}")
    
    @property
    def agent_id(self) -> int:
        self._load_credentials_from_db()
        return self._agent_id
    
    @property
    def client_id(self) -> int:
        self._load_credentials_from_db()
        return self._client_id
    
    @property
    def client_password(self) -> str:
        self._load_credentials_from_db()
        return self._client_password
    
    @property
    def location_id(self) -> str:
        self._load_credentials_from_db()
        return self._location_id
    
    async def get_token(self) -> str:
        # Ensure credentials are loaded
        self._load_credentials_from_db()
        
        if self._token and self._token_expiry:
            if datetime.now() < self._token_expiry:
                print(f"🔑 Using cached token (expires: {self._token_expiry})")
                return self._token
        
        print("🔄 Token expired or missing, generating new token...")
        return await self._generate_token()
    
    async def _generate_token(self) -> str:
        # Ensure credentials are loaded
        self._load_credentials_from_db()
        
        url = f"{self.base_url}/authToken"
        payload = {
            "agentId": self._agent_id,
            "agentPassword": self.agent_password,
            "clientId": self._client_id,
            "clientPassword": self._client_password,
            "useTrainingDatabase": self.use_training_db,
            "moduleType": ["guestservices"]
        }
        
        print(f"📡 Requesting token from: {url}")
        print(f"   Agent ID: {self._agent_id}, Client ID: {self._client_id}")
        print(f"   Location ID: {self._location_id}")
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
        self._token = None
        self._token_expiry = None
        print("🗑️ Token cache cleared")
    
    def reload_credentials(self):
        """Force reload credentials from database"""
        self._credentials_loaded = False
        self._token = None
        self._token_expiry = None
        self._load_credentials_from_db()

rms_auth = RMSAuth()