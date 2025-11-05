import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from .rms_api_client import rms_client

CACHE_FILE = "rms_cache.json"
CACHE_EXPIRY_HOURS = 24

class RMSCache:
    def __init__(self):
        self.property_id: Optional[int] = None
        self.agent_id: Optional[int] = None
        self.categories_cache: Dict[int, Dict] = {}
        self.rates_cache: Dict[int, Dict] = {}
        self.agent_id = int(os.getenv("RMS_AGENT_ID", "1010"))
        self._load_from_file()
    
    def _load_from_file(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    self.property_id = data.get('property_id')
                    self.categories_cache = data.get('categories_cache', {})
                    self.rates_cache = {
                        int(k): v for k, v in data.get('rates_cache', {}).items()
                    }
                    print(f"✅ RMS cache loaded from file")
            except Exception as e:
                print(f"⚠️ Error loading RMS cache: {e}")
    
    def _save_to_file(self):
        try:
            data = {
                'property_id': self.property_id,
                'categories_cache': self.categories_cache,
                'rates_cache': {
                    str(k): v for k, v in self.rates_cache.items()
                }
            }
            with open(CACHE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving RMS cache: {e}")
    
    async def initialize(self):
        if self.property_id:
            print(f"✅ RMS already initialized: Property {self.property_id}, Agent {self.agent_id}")
            return
        
        print("🔧 Initializing RMS cache...")
        print(f"   Agent ID from config: {self.agent_id}")
        
        try:
            print("📡 Fetching property...")
            properties = await rms_client.get_properties()
            
            if not properties or len(properties) == 0:
                raise Exception("No properties returned from RMS API")
            
            self.property_id = properties[0]['id']
            print(f"✅ Property ID: {self.property_id}")
            
            self._save_to_file()
            
        except Exception as e:
            print(f"❌ RMS initialization failed: {e}")
            raise
    
    def _is_cache_expired(self, timestamp_str: str) -> bool:
        try:
            cached_time = datetime.fromisoformat(timestamp_str)
            return datetime.now() - cached_time > timedelta(hours=CACHE_EXPIRY_HOURS)
        except:
            return True
    
    async def get_category(self, category_id: int) -> Optional[Dict]:
        if category_id in self.categories_cache:
            cached_data = self.categories_cache[category_id]
            if not self._is_cache_expired(cached_data.get('timestamp', '')):
                print(f"💾 Using cached category: {category_id}")
                return cached_data['data']
        
        print(f"📡 Fetching category {category_id} from API...")
        try:
            categories = await rms_client.get_categories(self.property_id)
            
            for cat in categories:
                self.categories_cache[cat['id']] = {
                    'data': cat,
                    'timestamp': datetime.now().isoformat()
                }
            
            self._save_to_file()
            return self.categories_cache.get(category_id, {}).get('data')
            
        except Exception as e:
            print(f"❌ Error fetching category {category_id}: {e}")
            return None
    
    async def get_rates_for_category(self, category_id: int) -> List[Dict]:
        if category_id in self.rates_cache:
            cached_data = self.rates_cache[category_id]
            if not self._is_cache_expired(cached_data.get('timestamp', '')):
                print(f"💾 Using cached rates for category: {category_id}")
                return cached_data['rates']
        
        print(f"📡 Fetching rates for category {category_id}...")
        try:
            rates = await rms_client.get_rates(category_id)
            
            self.rates_cache[category_id] = {
                'rates': rates,
                'timestamp': datetime.now().isoformat()
            }
            
            self._save_to_file()
            return rates
            
        except Exception as e:
            print(f"❌ Error fetching rates for category {category_id}: {e}")
            return []
    
    async def get_all_categories(self) -> List[Dict]:
        print("📡 Fetching all categories...")
        try:
            categories = await rms_client.get_categories(self.property_id)
            
            for cat in categories:
                self.categories_cache[cat['id']] = {
                    'data': cat,
                    'timestamp': datetime.now().isoformat()
                }
            
            self._save_to_file()
            return categories
            
        except Exception as e:
            print(f"❌ Error fetching categories: {e}")
            return []
    
    async def find_categories_by_keyword(self, keyword: str) -> List[Dict]:
        categories = await self.get_all_categories()
        keyword_lower = keyword.lower().strip()
        
        matching = [
            cat for cat in categories 
            if keyword_lower in cat['name'].lower()
        ]
        
        print(f"🔍 Keyword: '{keyword}' → Found {len(matching)} matching categories")
        if matching:
            category_names = [cat['name'] for cat in matching]
            print(f"   Matched: {', '.join(category_names)}")
        
        return matching
    
    def get_property_id(self) -> Optional[int]:
        return self.property_id
    
    def get_agent_id(self) -> Optional[int]:
        return self.agent_id
    
    def get_stats(self) -> Dict:
        return {
            'property_id': self.property_id,
            'agent_id': self.agent_id,
            'cached_categories': len(self.categories_cache),
            'cached_rate_plans': len(self.rates_cache)
        }

rms_cache = RMSCache()
