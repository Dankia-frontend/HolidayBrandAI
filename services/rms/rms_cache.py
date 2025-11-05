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
        
        # On-demand cache: only store what we fetch
        self.categories_cache: Dict[int, Dict] = {}  # {category_id: {data, timestamp}}
        self.rates_cache: Dict[int, Dict] = {}  # {category_id: {rates, timestamp}}
        
        # Get agent_id from environment (we already have it)
        self.agent_id = int(os.getenv("RMS_AGENT_ID", "1010"))
        
        self._load_from_file()
    
    def _load_from_file(self):
        """Load cache from file"""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    self.property_id = data.get('property_id')
                    self.categories_cache = data.get('categories_cache', {})
                    # Convert string keys back to int
                    self.rates_cache = {
                        int(k): v for k, v in data.get('rates_cache', {}).items()
                    }
                    print(f"✅ RMS cache loaded from file")
            except Exception as e:
                print(f"⚠️ Error loading RMS cache: {e}")
    
    def _save_to_file(self):
        """Save cache to file"""
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
        """Initialize property ID only (lightweight)"""
        if self.property_id:
            print(f"✅ RMS already initialized: Property {self.property_id}, Agent {self.agent_id}")
            return
        
        print("🔧 Initializing RMS cache...")
        print(f"   Agent ID from config: {self.agent_id}")
        
        try:
            # Only get property ID - don't load all categories
            print("📡 Fetching property...")
            properties = await rms_client.get_properties()
            
            if not properties or len(properties) == 0:
                raise Exception("No properties returned from RMS API")
            
            self.property_id = properties[0]['id']
            print(f"✅ Property ID: {self.property_id}")
            
            # Save minimal initialization
            self._save_to_file()
            
        except Exception as e:
            print(f"❌ RMS initialization failed: {e}")
            raise
    
    def _is_cache_expired(self, timestamp_str: str) -> bool:
        """Check if cache entry is expired"""
        try:
            cached_time = datetime.fromisoformat(timestamp_str)
            return datetime.now() - cached_time > timedelta(hours=CACHE_EXPIRY_HOURS)
        except:
            return True
    
    async def get_category(self, category_id: int) -> Optional[Dict]:
        """Get category by ID - fetch if not cached"""
        # Check if cached and not expired
        if category_id in self.categories_cache:
            cached_data = self.categories_cache[category_id]
            if not self._is_cache_expired(cached_data.get('timestamp', '')):
                print(f"💾 Using cached category: {category_id}")
                return cached_data['data']
        
        # Fetch from API
        print(f"📡 Fetching category {category_id} from API...")
        try:
            # Note: RMS might not have a direct get-by-id endpoint
            # So we fetch all categories and cache the one we need
            categories = await rms_client.get_categories(self.property_id)
            
            # Cache all returned categories
            for cat in categories:
                self.categories_cache[cat['id']] = {
                    'data': cat,
                    'timestamp': datetime.now().isoformat()
                }
            
            self._save_to_file()
            
            # Return the requested category
            return self.categories_cache.get(category_id, {}).get('data')
            
        except Exception as e:
            print(f"❌ Error fetching category {category_id}: {e}")
            return None
    
    async def get_rates_for_category(self, category_id: int) -> List[Dict]:
        """Get rates for category - fetch if not cached"""
        # Check if cached and not expired
        if category_id in self.rates_cache:
            cached_data = self.rates_cache[category_id]
            if not self._is_cache_expired(cached_data.get('timestamp', '')):
                print(f"💾 Using cached rates for category: {category_id}")
                return cached_data['rates']
        
        # Fetch from API
        print(f"📡 Fetching rates for category {category_id}...")
        try:
            rates = await rms_client.get_rates(category_id)
            
            # Cache the rates
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
        """Get all categories - used for search when no keyword"""
        print("📡 Fetching all categories...")
        try:
            categories = await rms_client.get_categories(self.property_id)
            
            # Cache all categories
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
        """Find categories matching keyword - flexible partial matching"""
        # Get all categories (will use cache if available)
        categories = await self.get_all_categories()
        
        # Clean and normalize keyword
        keyword_lower = keyword.lower().strip()
        
        # Find partial matches (keyword appears anywhere in category name)
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

# Singleton instance
rms_cache = RMSCache()
