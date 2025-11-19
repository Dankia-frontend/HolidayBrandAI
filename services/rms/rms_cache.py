import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

CACHE_FILE = "rms_cache.json"
CACHE_EXPIRY_HOURS = 24

class RMSCache:
    def __init__(self):
        self.property_id: Optional[int] = None
        self.agent_id: Optional[int] = None
        self.categories_cache: Dict[int, Dict] = {}
        self.rates_cache: Dict[int, Dict] = {}
        self.areas_cache: List[Dict] = []
        self.agent_id = int(os.getenv("RMS_AGENT_ID", "1010"))
        self._load_from_file()
    
    def _get_client(self):
        """Lazy import to avoid circular dependency"""
        from .rms_api_client import rms_client
        return rms_client
    
    def _load_from_file(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    self.property_id = data.get('property_id')
                    self.areas_cache = data.get('areas_cache', [])
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
                'areas_cache': self.areas_cache,
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
        """Initialize RMS cache with property data"""
        if self.property_id:
            print(f"✅ RMS already initialized: Property {self.property_id}, Agent {self.agent_id}")
            return
        
        print("🔧 Initializing RMS cache...")
        print(f"   Agent ID from config: {self.agent_id}")
        
        client = self._get_client()
        
        try:
            print("📡 Fetching property...")
            properties = await client.get_properties()
            
            if not properties or len(properties) == 0:
                raise Exception("No properties returned from RMS API")
            
            self.property_id = properties[0]['id']
            print(f"✅ Property ID: {self.property_id}")
            
            # Fetch areas/rooms for caching
            print("📡 Fetching areas/rooms...")
            areas = await client.get_areas(self.property_id)
            
            if areas and len(areas) > 0:
                self.areas_cache = areas
                print(f"✅ Cached {len(areas)} areas/rooms")
                
                # Show areas by category
                categories_map = {}
                for area in areas:
                    cat_id = area.get('categoryId')
                    if cat_id not in categories_map:
                        categories_map[cat_id] = []
                    categories_map[cat_id].append(area['id'])
                
                print(f"   Areas by category:")
                for cat_id, area_ids in categories_map.items():
                    print(f"   Category {cat_id}: {len(area_ids)} rooms")
            else:
                print("⚠️ No areas returned - this will cause issues!")
                raise Exception("No areas/rooms found in RMS")
            
            self._save_to_file()
            
        except Exception as e:
            print(f"❌ RMS initialization failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _is_cache_expired(self, timestamp_str: str) -> bool:
        try:
            cached_time = datetime.fromisoformat(timestamp_str)
            return datetime.now() - cached_time > timedelta(hours=CACHE_EXPIRY_HOURS)
        except:
            return True
    
    async def get_category(self, category_id: int) -> Optional[Dict]:
        client = self._get_client()
        
        if category_id in self.categories_cache:
            cached_data = self.categories_cache[category_id]
            if not self._is_cache_expired(cached_data.get('timestamp', '')):
                print(f"💾 Using cached category: {category_id}")
                return cached_data['data']
        
        print(f"📡 Fetching category {category_id} from API...")
        try:
            categories = await client.get_categories(self.property_id)
            
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
        client = self._get_client()
        
        if category_id in self.rates_cache:
            cached_data = self.rates_cache[category_id]
            if not self._is_cache_expired(cached_data.get('timestamp', '')):
                print(f"💾 Using cached rates for category: {category_id}")
                return cached_data['rates']
        
        print(f"📡 Fetching rates for category {category_id}...")
        try:
            rates = await client.get_rates(category_id)
            
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
        client = self._get_client()
        
        print("📡 Fetching all categories...")
        try:
            categories = await client.get_categories(self.property_id)
            
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
    
    async def get_available_areas_for_category(self, category_id: int) -> List[int]:
        """
        Get available area/room IDs for a given category (vacant rooms only).
        Returns list of area IDs that belong to this category and are not occupied.
        """
        available_areas = [
            area['id'] for area in self.areas_cache 
            if area.get('categoryId') == category_id and 
            area.get('cleanStatus') != 'Occupied'
        ]
        
        if available_areas:
            print(f"   Found {len(available_areas)} available areas for category {category_id}")
        else:
            print(f"   No available areas found for category {category_id}")
        
        return available_areas
    
    async def get_all_areas_for_category(self, category_id: int) -> List[int]:
        """
        Get ALL area/room IDs for a given category (regardless of occupancy).
        RMS will check actual availability when creating the reservation.
        Returns list of area IDs that belong to this category.
        """
        all_areas = [
            area['id'] for area in self.areas_cache 
            if area.get('categoryId') == category_id
        ]
        
        if all_areas:
            print(f"   Found {len(all_areas)} total rooms for category {category_id}")
        else:
            print(f"   ⚠️ No rooms found for category {category_id}")
        
        return all_areas
    
    def get_property_id(self) -> Optional[int]:
        return self.property_id
    
    def get_agent_id(self) -> Optional[int]:
        return self.agent_id
    
    def get_stats(self) -> Dict:
        return {
            'property_id': self.property_id,
            'agent_id': self.agent_id,
            'cached_areas': len(self.areas_cache),
            'cached_categories': len(self.categories_cache),
            'cached_rate_plans': len(self.rates_cache)
        }

rms_cache = RMSCache()