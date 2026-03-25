from typing import Dict, List, Optional
import os
import json
from datetime import datetime, timedelta
import random


class RMSService:
    def __init__(self, credentials: dict = None):
        """
        Initialize RMSService with optional credentials.
        
        Args:
            credentials: dict with location_id, client_id, client_pass (decrypted), agent_id
                        If not provided, will try to load from environment variables.
        """
        self.credentials = credentials
        self._initialized = False
        self._property_id = None
        self._areas_cache = []
        self._categories_cache = {}
        self._rates_cache = {}
        self._api_client = None
        
        # Lightweight cache: remember which areas worked recently
        # Format: {"1_42_2026-08-01_2026-08-02": [25, 47, 52]}
        self._working_areas_cache = {}
        self._cache_timestamp = {}
        
    def _get_api_client(self):
        """Get or create API client with current credentials"""
        if self._api_client is None:
            from .rms_api_client import RMSApiClient
            self._api_client = RMSApiClient(self.credentials)
        return self._api_client
    
    @property
    def location_id(self) -> Optional[str]:
        if self.credentials:
            return self.credentials.get('location_id')
        return None
    
    @property
    def client_id(self) -> Optional[int]:
        if self.credentials:
            return self.credentials.get('client_id')
        return int(os.getenv("RMS_CLIENT_ID", "0"))
    
    @property
    def query_agent_id(self) -> Optional[int]:
        """Agent ID for queries - from database (was RMS_QUERY_AGENT_ID)"""
        if self.credentials:
            agent_id = self.credentials.get('agent_id')
            return int(agent_id) if agent_id else 0
        return int(os.getenv("RMS_QUERY_AGENT_ID", "0"))
    
    def _get_available_areas_for_category(self, category_id: int) -> List[int]:
        """
        Get areas for category that are likely available based on cleanStatus.
        Filters out 'Occupied' areas to maximize success rate.
        """
        # Get all areas for category
        all_category_areas = [
            area for area in self._areas_cache 
            if area.get('categoryId') == category_id
        ]
        
        # Count by status
        status_counts = {}
        for area in all_category_areas:
            status = area.get('cleanStatus', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"\n   📊 Area status breakdown for category {category_id}:")
        for status, count in sorted(status_counts.items()):
            print(f"      {status}: {count} areas")
        
        # Filter for available statuses
        available_statuses = ['Vacant Dirty', 'Vacant Clean', 'Vacant Inspect', 'Maintenance']
        
        available_areas = [
            area['id'] for area in all_category_areas
            if area.get('cleanStatus') in available_statuses
            and not area.get('inactive', False)  # Skip inactive areas
        ]
        
        occupied_count = len([a for a in all_category_areas if a.get('cleanStatus') == 'Occupied'])
        
        print(f"   ✅ Filtering out {occupied_count} Occupied areas")
        print(f"   ✅ {len(available_areas)} potentially available areas to try")
        
        # If no vacant areas, return empty list (don't try occupied ones!)
        if not available_areas:
            print(f"   ⚠️ No vacant areas found for category {category_id}")
        
        return available_areas
    
    def _get_cache_key(self, category_id: int, rate_plan_id: int, arrival: str, departure: str) -> str:
        """Generate cache key for working areas"""
        return f"{category_id}_{rate_plan_id}_{arrival}_{departure}"
    
    def _is_cache_valid(self, cache_key: str, max_age_seconds: int = 300) -> bool:
        """Check if cached data is still valid (default: 5 minutes)"""
        if cache_key not in self._cache_timestamp:
            return False
        
        age = (datetime.now() - self._cache_timestamp[cache_key]).total_seconds()
        return age < max_age_seconds
    
    def _add_working_area_to_cache(self, category_id: int, rate_plan_id: int, arrival: str, departure: str, area_id: int):
        """Add a known-working area to cache for future use"""
        cache_key = self._get_cache_key(category_id, rate_plan_id, arrival, departure)
        
        if cache_key not in self._working_areas_cache:
            self._working_areas_cache[cache_key] = []
        
        if area_id not in self._working_areas_cache[cache_key]:
            self._working_areas_cache[cache_key].append(area_id)
            self._cache_timestamp[cache_key] = datetime.now()
            print(f"   💾 Cached working area {area_id} for future bookings")
    
    def _get_strategic_areas(self, all_areas: List[int], max_count: int = 10) -> List[int]:
        """
        Get strategic sample of areas to try.
        Uses: first few + random middle + last few
        """
        strategic = []
        
        # Add first 2
        strategic.extend(all_areas[:2])
        
        # Add random 4 from middle
        if len(all_areas) > 6:
            middle_areas = all_areas[2:-2]
            if middle_areas:
                sample_size = min(4, len(middle_areas))
                strategic.extend(random.sample(middle_areas, sample_size))
        
        # Add last 2
        if len(all_areas) > 2:
            strategic.extend(all_areas[-2:])
        
        # Remove duplicates and limit
        strategic = list(dict.fromkeys(strategic))[:max_count]
        
        return strategic
    
    def _get_category_occupancy_info(self, category_id: int) -> Dict:
        """
        Get occupancy limits for a category.
        Returns dict with maxAdults, maxChildren, maxOccupancy, and occupancyMessage
        """
        category = self._categories_cache.get(category_id, {})
        
        # Debug: Print all available fields for this category (only once per category)
        if not hasattr(self, '_logged_categories'):
            self._logged_categories = set()
        
        if category_id not in self._logged_categories:
            print(f"\n🔍 DEBUG: Available fields for category {category_id} ({category.get('name', 'Unknown')}):")
            for key, value in category.items():
                if 'occup' in key.lower() or 'adult' in key.lower() or 'child' in key.lower() or 'capacity' in key.lower() or 'max' in key.lower():
                    print(f"   {key}: {value}")
            self._logged_categories.add(category_id)
        
        # RMS API field names - check multiple variations
        # Based on RMS documentation, these are possible field names:
        # - maxOccupantsPerArea / maxOccupantsPerCategory
        # - maxAdults / adultCapacity
        # - maxChildren / childCapacity / childrenCapacity
        # - maxOccupancy / totalCapacity / capacity
        
        max_adults = (
            category.get('maxAdults', 0) or 
            category.get('adultCapacity', 0) or
            category.get('maxAdultsPerArea', 0) or
            category.get('adultsMax', 0) or
            0
        )
        
        max_children = (
            category.get('maxChildren', 0) or 
            category.get('childCapacity', 0) or
            category.get('childrenCapacity', 0) or
            category.get('maxChildrenPerArea', 0) or
            category.get('childrenMax', 0) or
            0
        )
        
        max_occupancy = (
            category.get('maxOccupancy', 0) or 
            category.get('totalCapacity', 0) or
            category.get('capacity', 0) or
            category.get('maxOccupantsPerArea', 0) or
            category.get('maxOccupantsPerCategory', 0) or
            category.get('maxGuests', 0) or
            category.get('maximumOccupancy', 0) or
            0
        )
        
        # If maxOccupancy not set but maxAdults is, calculate from adults + children
        if not max_occupancy and max_adults:
            max_occupancy = max_adults + max_children
        
        # If still no occupancy info, try to get from areas in this category
        if not max_occupancy and self._areas_cache:
            # Find areas for this category and get their occupancy
            category_areas = [area for area in self._areas_cache if area.get('categoryId') == category_id]
            if category_areas:
                # Get max from first area (they should all be the same for a category)
                first_area = category_areas[0]
                area_max = (
                    first_area.get('maxOccupants', 0) or
                    first_area.get('maxOccupancy', 0) or
                    first_area.get('capacity', 0) or
                    0
                )
                if area_max:
                    max_occupancy = area_max
                    print(f"   ℹ️ Using area-level occupancy for category {category_id}: {area_max}")
        
        return {
            'maxAdults': max_adults,
            'maxChildren': max_children,
            'maxOccupancy': max_occupancy,
            'occupancyMessage': f"Max {max_adults} adults, {max_children} children (Total: {max_occupancy})" if max_occupancy else "Occupancy limits not configured"
        }
    
    def _validate_occupancy(self, category_id: int, adults: int, children: Optional[int]) -> tuple:
        """
        Validate if the requested adults and children fit within category limits.
        Returns (is_valid, error_message)
        """
        children = 0 if children is None else children
        occupancy_info = self._get_category_occupancy_info(category_id)
        max_adults = occupancy_info['maxAdults']
        max_children = occupancy_info['maxChildren']
        max_occupancy = occupancy_info['maxOccupancy']
        
        # If no limits are configured, allow the booking
        if not max_occupancy:
            print(f"   ⚠️ Category {category_id}: No occupancy limits configured - allowing booking")
            return True, ""
        
        # IMPROVED: Only validate individual limits if they're actually set (> 0)
        # Site categories often have maxAdults=0, maxChildren=0 but maxOccupancy=6
        if max_adults > 0 and adults > max_adults:
            return False, f"Number of adults ({adults}) exceeds maximum allowed ({max_adults})"
        
        if max_children > 0 and children > max_children:
            return False, f"Number of children ({children}) exceeds maximum allowed ({max_children})"
        
        # Check total occupancy (this is the main validation for site categories)
        total_guests = adults + children
        if total_guests > max_occupancy:
            return False, f"Total guests ({total_guests}) exceeds maximum occupancy ({max_occupancy})"
        
        print(f"   ✅ Occupancy valid for category {category_id}: {total_guests} guests <= {max_occupancy} max")
        return True, ""
    
    async def initialize(self):
        """Initialize RMS service with property data"""
        if self._initialized and self._property_id:
            print(f"✅ RMS already initialized: Property {self._property_id}, Query Agent {self.query_agent_id}, Client {self.client_id}")
            return
        
        print("🔧 Initializing RMS service...")
        print(f"   Location ID: {self.location_id}")
        print(f"   Client ID: {self.client_id}")
        print(f"   Query Agent ID (from DB): {self.query_agent_id}")
        
        client = self._get_api_client()
        
        try:
            print("📡 Fetching property...")
            properties = await client.get_properties()
            
            if not properties or len(properties) == 0:
                raise Exception("No properties returned from RMS API")
            
            self._property_id = properties[0]['id']
            print(f"✅ Property ID: {self._property_id}")
            
            # Fetch areas/rooms for caching
            print("📡 Fetching areas/rooms...")
            areas = await client.get_areas(self._property_id)
            
            if areas and len(areas) > 0:
                self._areas_cache = areas
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
            
            # Fetch and cache categories during initialization
            print("📡 Fetching categories...")
            try:
                categories = await client.get_categories(self._property_id)
                for cat in categories:
                    self._categories_cache[cat['id']] = cat
                print(f"✅ Cached {len(categories)} categories")
                
                # Debug: Log category class info for each category
                print(f"Category Class Information:")
                for cat in categories:
                    cat_id = cat.get('id')
                    cat_name = cat.get('name', 'Unknown')
                    cat_class = cat.get('categoryClass', 'Unknown')
                    print(f"   Category {cat_id} ({cat_name}): class={cat_class}")
                        
            except Exception as e:
                print(f"⚠️ Warning: Could not cache categories: {e}")
            
            self._initialized = True
            
        except Exception as e:
            print(f"❌ RMS initialization failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def _get_all_categories(self) -> List[Dict]:
        """Fetch all categories from RMS (uses cache if available)"""
        # Return cached categories if available
        if self._categories_cache:
            print("💾 Using cached categories")
            return list(self._categories_cache.values())
        
        client = self._get_api_client()
        
        print("📡 Fetching all categories...")
        try:
            categories = await client.get_categories(self._property_id)
            
            for cat in categories:
                self._categories_cache[cat['id']] = cat
            
            return categories
            
        except Exception as e:
            print(f"❌ Error fetching categories: {e}")
            return []
    
    async def _get_rates_for_category(self, category_id: int) -> List[Dict]:
        """Fetch rates for a specific category"""
        client = self._get_api_client()
        
        if category_id in self._rates_cache:
            print(f"💾 Using cached rates for category: {category_id}")
            return self._rates_cache[category_id]
        
        print(f"📡 Fetching rates for category {category_id}...")
        try:
            rates = await client.get_rates(category_id)
            self._rates_cache[category_id] = rates
            return rates
            
        except Exception as e:
            print(f"❌ Error fetching rates for category {category_id}: {e}")
            return []
    
    async def _find_categories_by_keyword(self, keyword: str) -> List[Dict]:
        """Find categories matching a keyword (uses cache if available)"""
        # Use cached categories if available
        if self._categories_cache:
            categories = list(self._categories_cache.values())
        else:
            categories = await self._get_all_categories()
        
        keyword_lower = keyword.lower().strip()
        
        matching = [
            cat for cat in categories 
            if keyword_lower in cat['name'].lower()
        ]
        
        print(f"   Keyword '{keyword}' → {len(matching)} matches")
        
        return matching
    
    async def search_availability(
        self,
        arrival: str,
        departure: str,
        adults: int = 2,
        children: int = 0,
        room_keyword: Optional[str] = None
    ) -> Dict:
        """
        Search for available rooms - WORKING VERSION
        
        This method properly:
        1. Finds matching categories (or all categories)
        2. Fetches rate plans for each category
        3. Calls rates grid API with both categoryIds AND rateIds
        4. Returns simplified results
        """
        if not self._initialized:
            raise Exception("RMS service not initialized")
        
        # Validate that at least 1 adult is required for booking
        if adults < 1:
            print(f"❌ Validation failed: At least 1 adult is required (received: {adults} adults)")
            return {
                'available': [],
                'message': "At least 1 adult is required to search for availability",
                'error': "Minimum 1 adult required"
            }
        
        client = self._get_api_client()
        
        # Step 1: Find matching categories (use cache if available)
        if room_keyword:
            print(f"🔍 Searching for categories matching: '{room_keyword}'")
            if self._categories_cache:
                categories = [cat for cat in self._categories_cache.values() 
                             if room_keyword.lower() in cat['name'].lower()]
                if not categories:
                    print(f"   No categories matched '{room_keyword}', searching all instead")
                    categories = list(self._categories_cache.values())
            else:
                categories = await self._find_categories_by_keyword(room_keyword)
                if not categories:
                    print(f"   No categories matched '{room_keyword}', searching all instead")
                    categories = await self._get_all_categories()
        else:
            print("🔍 Searching all categories (no keyword provided)")
            if self._categories_cache:
                categories = list(self._categories_cache.values())
            else:
                categories = await self._get_all_categories()
        
        # Filter to only active categories with areas
        # REMOVED IBE filter - was excluding site-type categories
        print(f"\n🔍 Filtering categories...")
        print(f"   Total categories: {len(categories)}")
        
        active_categories = [
            cat for cat in categories 
            if not cat.get('inactive', False) 
            and cat.get('numberOfAreas', 0) > 0
            # Removed: and cat.get('availableToIbe') is not False
            # This was filtering out powered/unpowered sites
        ]
        
        category_ids = [cat['id'] for cat in active_categories]
        print(f"📋 Active bookable categories ({len(active_categories)}): {category_ids}")
        
        for cat in active_categories:
            cat_class = cat.get('categoryClass', 'Unknown')
            print(f"   Category {cat['id']}: {cat.get('name', 'Unknown')} (Class: {cat_class})")
        
        # Step 2: Get all rate plans for these categories
        # CRITICAL: RMS API requires BOTH categoryIds AND rateIds or it returns 500 error!
        all_rate_ids = []
        for cat_id in category_ids:
            rates = await self._get_rates_for_category(cat_id)
            print(f"   Category {cat_id} has {len(rates)} rate plans: {[r['id'] for r in rates]}")
            all_rate_ids.extend([rate['id'] for rate in rates])
        
        all_rate_ids = list(set(all_rate_ids))  # Remove duplicates
        
        print(f"Checking availability:")
        print(f"   Categories: {len(category_ids)} -> {category_ids}")
        print(f"   Rate plans: {len(all_rate_ids)} -> {all_rate_ids}")
        print(f"   Dates: {arrival} to {departure}")
        print(f"   Guests: {adults} adults, {children} children")
        
        if not all_rate_ids:
            print("⚠️ WARNING: No rate plans found for any category!")
            return {
                'available': [],
                'message': "No rate plans configured for this property. Please check RMS rate plan setup."
            }
        
        # Step 3: Query the rates grid with BOTH categoryIds and rateIds
        print(f"   Using Query Agent ID from DB: {self.query_agent_id}")
        
        payload = {
            "propertyId": self._property_id,
            "agentId": int(self.query_agent_id),
            "arrival": arrival,
            "departure": departure,
            "adults": adults,
            "children": children,
            "categoryIds": category_ids,
            "rateIds": all_rate_ids,
            "includeEstimatedRates": False,
            "includeZeroRates": False
        }
        
        print("📡 Calling rates grid API...")
        try:
            grid_response = await client.get_rates_grid(payload)
            return await self._simplify_grid_response(grid_response, arrival, departure, adults, children)
        except Exception as e:
            print(f"⚠️ Rates grid API failed: {e}")
            print(f"   Returning error response to avoid crash")
            return {
                'available': [],
                'message': "Unable to check availability at this time. Please try again later or contact us directly.",
                'error': str(e)
            }
    
    def _is_standard_rate(self, rate_name: str) -> bool:
        """
        Determine if a rate plan is a standard/normal rate (not promotional or discount).
        
        Returns True for rates like:
        - "Normal Rate"
        - "Standard Rate" 
        - "Standard Rate 2"
        - "Standard Rate 2021 Onwards"
        - "BAR" (Best Available Rate)
        
        Returns False for promotional/discount rates like:
        - "Weekly Discount"
        - "Member 10% Disc"
        - "Stay 7 Pay 5"
        - "Bookeasy"
        - "G'Day Member"
        - "OTA" rates
        """
        rate_name_lower = rate_name.lower()
        
        # Keywords that indicate a standard rate
        standard_keywords = [
            'normal rate',
            'standard rate',
            'bar'  # Best Available Rate
        ]
        
        # Keywords that indicate promotional/discount rates (should be excluded)
        exclude_keywords = [
            'discount', 'disc', 'weekly', 'stay', 'pay',
            'member', 'bookeasy', 'ota', 'promo', 'special',
            'corporate', 'corp', 'extended', "g'day", 'hrs'
        ]
        
        # Check if it matches a standard rate keyword
        for keyword in standard_keywords:
            if keyword in rate_name_lower:
                # Make sure it doesn't also have an exclude keyword
                has_exclude = any(excl in rate_name_lower for excl in exclude_keywords)
                if not has_exclude:
                    return True
        
        return False
    
    async def _simplify_grid_response(self, grid_response: Dict, arrival: str, departure: str, adults: int, children: int) -> Dict:
        """
        Simplify the rates grid response into a clean format.
        Returns available room options with pricing.
        """
        available = []
        
        categories = grid_response.get('categories', [])
        print(f"Rates grid returned {len(categories)} categories")
        
        if not categories:
            return {
                'available': [],
                'message': "No rooms available for selected dates"
            }
        
        for category in categories:
            category_id = category.get('categoryId')
            category_name = category.get('name', 'Unknown')
            rates = category.get('rates', [])
            
            for rate in rates:
                rate_id = rate.get('rateId')
                rate_name = rate.get('name', 'Unknown')
                
                # Filter: Only include standard rate plans (not promotional/discount rates)
                # This works across all parks with different rate naming conventions
                if not self._is_standard_rate(rate_name):
                    print(f"   ⏭️  Skipping promotional rate: {rate_name} (ID: {rate_id})")
                    continue
                
                print(f"   ✓ Processing standard rate: {rate_name} (ID: {rate_id})")
                
                day_breakdown = rate.get('dayBreakdown', [])
                if not day_breakdown:
                    continue
                
                total_price = 0
                is_available = True
                available_count = None
                
                # Check each day for availability and calculate total price
                for day in day_breakdown:
                    available_areas_count = day.get('availableAreas', 0)
                    
                    if available_areas_count <= 0:
                        is_available = False
                        break
                    
                    if available_count is None:
                        available_count = available_areas_count
                    else:
                        available_count = min(available_count, available_areas_count)
                    
                    daily_rate = day.get('dailyRate', 0)
                    if daily_rate:
                        total_price += daily_rate
                print(f"IS AVAILABLE: {is_available}, TOTAL PRICE: {total_price} , AVAILABLE COUNT: {available_count}")

                # Only include if available and has a price
                if is_available and total_price > 0 and available_count > 0:
                    
                    # Validate occupancy limits for this category
                    is_valid, error_msg = self._validate_occupancy(category_id, adults, children)
                    
                    # Get occupancy info for the response
                    occupancy_info = self._get_category_occupancy_info(category_id)
                    
                    if is_valid:
                        cached_category = self._categories_cache.get(category_id, {})
                        category_class = cached_category.get('categoryClass', '')
                        
                        available.append({
                            'category_id': category_id,
                            'category_name': category_name,
                            'category_class': category_class,  # "Site" or "Accommodation"
                            'rate_plan_id': rate_id,
                            'rate_plan_name': rate_name,
                            'total_price': total_price,
                            'available_areas': available_count,
                            'max_occupancy': occupancy_info['maxOccupancy'],
                            'occupancy_message': occupancy_info['occupancyMessage']
                        })
                        print(f"   Category {category_id}, Rate {rate_id}: ✅ {available_count} areas - ${total_price} - Class: {category_class} - {occupancy_info['occupancyMessage']}")
                    else:
                        print(f"   Category {category_id}, Rate {rate_id}: ❌ Skipped - {error_msg}")

        
        # VERIFY ACTUAL AVAILABILITY - /rates/grid can be inaccurate!
        # Call /availableAreas for each unique category to get REAL availability
        print(f"\n🔍 Verifying actual availability for {len(available)} options...")
        
        client = self._get_api_client()
        unique_categories = {}  # {category_id: actual_available_count}
        
        # Get unique category IDs from results
        category_ids_to_check = list(set([item['category_id'] for item in available]))
        
        for cat_id in category_ids_to_check:
            try:
                # Call /availableAreas to get actual list
                payload = {
                    "propertyId": self._property_id,
                    "categoryId": cat_id,
                    "arrivalDate": arrival,
                    "departureDate": departure,
                    "adults": adults,
                    "children": children
                }
                
                print(f"   Checking category {cat_id}...")
                areas_response = await client.get_available_areas(payload)
                
                # Trust the /availableAreas API response - it already filters by date availability
                # cleanStatus is the CURRENT status, not the status for the requested dates
                # If the API returns an area, it means it's available for those dates
                actual_count = len(areas_response)
                unique_categories[cat_id] = actual_count
                
                print(f"      Category {cat_id}: {actual_count} available")
                    
            except Exception as e:
                print(f"      ⚠️ Could not verify category {cat_id}: {e}")
                # If we can't verify, keep the original count (benefit of doubt)
                # This prevents breaking search if one category fails
                unique_categories[cat_id] = None  # Will use grid count
        
        # Update available_areas count with ACTUAL values
        verified_available = []
        for item in available:
            cat_id = item['category_id']
            cat_class = item.get('category_class', '')
            actual_count = unique_categories.get(cat_id)
            grid_count = item['available_areas']
            
            if actual_count is not None:
                # We verified this category
                if actual_count > 0:
                    # API confirms availability
                    item['available_areas'] = actual_count
                    verified_available.append(item)
                    print(f"   ✅ Category {cat_id} verified: {actual_count} areas available")
                else:
                    # API says 0 available
                    # SPECIAL CASE: For site-type categories, trust the rates grid
                    # Agent ID might not have permission to query sites via /availableAreas
                    if cat_class == "Site" and grid_count > 0:
                        print(f"   ⚠️ Category {cat_id} (Site): /availableAreas returned 0, but rates grid says {grid_count}")
                        print(f"      → Keeping site category (agent permission issue with /availableAreas)")
                        verified_available.append(item)
                    else:
                        # For accommodation, remove if 0
                        print(f"   ❌ Removed Category {cat_id} - {item['rate_plan_name']}: Grid said {grid_count}, but 0 actually available")
            else:
                # Couldn't verify - keep it with original count
                verified_available.append(item)
                print(f"   ⚠️ Category {cat_id}: Could not verify, keeping with grid count ({grid_count})")
        
        if len(verified_available) < len(available):
            removed_count = len(available) - len(verified_available)
            print(f"   ⚠️ Removed {removed_count} options that showed in grid but had no actual availability")
        
        # Sort by price (cheapest first)
        verified_available.sort(key=lambda x: x['total_price'])
        print(f"✅ Search complete: {len(verified_available)} verified available options")
        
        return {
            'available': verified_available,
            'message': f"Found {len(verified_available)} available room(s)" if verified_available else "No rooms available"
        }
    
    # ==================== CREATE RESERVATION ====================
    # This uses the get_available_areas API for reliable bookings

    async def get_booking_price_and_details(
        self,
        category_id: int,
        rate_plan_id: int,
        arrival: str,
        departure: str,
        adults: int,
        children: int
    ) -> Dict:
        """
        Get the total price and details for a specific booking.
        Returns dict with: total_price, category_name, nights
        """
        if not self._initialized:
            raise Exception("RMS service not initialized")
        
        client = self._get_api_client()
        
        # Get category name from cache
        category = self._categories_cache.get(category_id, {})
        category_name = category.get('name', f'Category {category_id}')
        
        # Calculate nights
        from datetime import datetime
        arr_date = datetime.strptime(arrival, "%Y-%m-%d")
        dep_date = datetime.strptime(departure, "%Y-%m-%d")
        nights = (dep_date - arr_date).days
        
        # Get pricing from rates grid
        payload = {
            "propertyId": self._property_id,
            "agentId": int(self.query_agent_id),
            "arrival": arrival,
            "departure": departure,
            "adults": adults,
            "children": children,
            "categoryIds": [category_id],
            "rateIds": [rate_plan_id],
            "includeEstimatedRates": False,
            "includeZeroRates": False
        }
        
        try:
            grid_response = await client.get_rates_grid(payload)
            
            # Extract price from grid response
            categories = grid_response.get('categories', [])
            if categories:
                category_data = categories[0]
                rates = category_data.get('rates', [])
                if rates:
                    rate_data = rates[0]
                    day_breakdown = rate_data.get('dayBreakdown', [])
                    
                    total_price = 0
                    for day in day_breakdown:
                        daily_rate = day.get('dailyRate', 0)
                        if daily_rate:
                            total_price += daily_rate
                    
                    return {
                        'total_price': total_price,
                        'category_name': category_name,
                        'nights': nights,
                        'rate_name': rate_data.get('name', 'Standard Rate')
                    }
        except Exception as e:
            print(f"⚠️ Could not fetch pricing: {e}")
        
        # Fallback if pricing fetch fails
        return {
            'total_price': None,
            'category_name': category_name,
            'nights': nights,
            'rate_name': None
        }

    async def create_reservation(
        self,
        category_id: int,
        rate_plan_id: int,
        arrival: str,
        departure: str,
        adults: int,
        children: Optional[int],
        guest_firstName: str,
        guest_lastName: str,
        guest_email: str,
        guest_phone: Optional[str] = None,
        guest_membership_id: Optional[int] = None,
    ) -> Dict:
        """
        Create reservation by checking availability FIRST before attempting to book.
        
        Strategy:
        1. Call /availableAreas API to get actual available areas for this date range
        2. Try to book one of those available areas (should succeed immediately)
        3. Cache successful area for future bookings
        
        This dramatically reduces booking attempts from 8+ to typically 1-2.
        """
        if not self._initialized:
            raise Exception("RMS service not initialized")
        
        # Validate that at least 1 adult is required for booking
        if adults < 1:
            print(f"❌ Validation failed: At least 1 adult is required (received: {adults} adults)")
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400, 
                detail="At least 1 adult is required to create a reservation"
            )
        
        children = 0 if children is None else children
        
        client = self._get_api_client()
        
        print(f"\n{'='*80}")
        print(f"🎯 CREATING RESERVATION - AVAILABILITY-FIRST APPROACH")
        print(f"{'='*80}")
        
        # Step 0: Validate occupancy limits for the category
        print(f"🔍 Step 0: Validating occupancy limits...")
        is_valid, error_msg = self._validate_occupancy(category_id, adults, children)
        if not is_valid:
            print(f"❌ Occupancy validation failed: {error_msg}")
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=error_msg)
        
        occupancy_info = self._get_category_occupancy_info(category_id)
        print(f"✅ Occupancy validated: {adults} adults, {children} children - {occupancy_info['occupancyMessage']}")
        
        # Step 1: Check availability FIRST to find actually available areas
        print(f"🔍 Step 1: Checking actual availability for category {category_id}, rate {rate_plan_id}...")
        
        available_area_ids = []
        try:
            # Call /availableAreas API directly - much more reliable!
            payload = {
                "propertyId": self._property_id,
                "categoryId": category_id,
                "arrivalDate": arrival,
                "departureDate": departure,
                "adults": adults,
                "children": children
            }
            
            print(f"📡 Calling /availableAreas API for category {category_id}...")
            print(f"   Dates: {arrival} to {departure}")
            print(f"   Guests: {adults} adults, {children} children")
            
            available_areas_response = await client.get_available_areas(payload)
            
            available_area_ids = [area.get('id') for area in available_areas_response if area.get('id')]
            
            if not available_area_ids:
                raise Exception(
                    f"No areas available for category {category_id} between {arrival} and {departure}"
                )
            
            print(f"✅ Found {len(available_area_ids)} available areas from /availableAreas API")
            print(f"   Available area IDs: {available_area_ids[:10]}{'...' if len(available_area_ids) > 10 else ''}")
            
        except Exception as e:
            print(f"⚠️ /availableAreas API failed: {e}")
            print(f"   Falling back to cleanStatus filtering method...")
            
            # Fallback: use old method of filtering by cleanStatus
            available_area_ids = self._get_available_areas_for_category(category_id)
            if not available_area_ids:
                raise Exception(f"No areas found for category {category_id}")
            
            print(f"⚠️ Using {len(available_area_ids)} areas based on cleanStatus (less reliable)")
        
        # Step 2: Find or create guest
        print(f"\n🔍 Step 2: Finding or creating guest...")
        guest = {
            'firstName': guest_firstName,
            'lastName': guest_lastName,
            'email': guest_email,
            'phone': guest_phone
        }
        
        guest_id = await self._find_or_create_guest(guest)
        if not guest_id:
            raise Exception("Failed to create/find guest")
        
        print(f"✅ Guest ID: {guest_id}")
        
        # Step 3: Calculate nights
        arrival_date = datetime.fromisoformat(arrival)
        departure_date = datetime.fromisoformat(departure)
        nights = (departure_date - arrival_date).days
        
        # Step 4: Build list of areas to try (prioritize cached working areas)
        print(f"\n🔍 Step 3: Selecting area to book...")
        cache_key = self._get_cache_key(category_id, rate_plan_id, arrival, departure)
        areas_to_try = []
        
        # First, try any cached working areas that are in the available list
        if cache_key in self._working_areas_cache and self._is_cache_valid(cache_key):
            cached_areas = self._working_areas_cache[cache_key]
            cached_available = [a for a in cached_areas if a in available_area_ids]
            if cached_available:
                areas_to_try.extend(cached_available[:2])
                print(f"💾 Found {len(cached_available)} cached working areas that are available")
        
        # Determine how many areas to try based on data quality
        # If many areas (likely fallback), try more since cleanStatus is unreliable
        max_areas_to_try = 3 if len(available_area_ids) < 30 else 10
        
        # If using fallback (many areas), randomize to avoid always trying blocked ones
        if len(available_area_ids) > 30:
            print(f"   📌 Fallback mode detected: randomizing {len(available_area_ids)} areas")
            shuffled_areas = random.sample(available_area_ids, min(len(available_area_ids), 30))
            for area_id in shuffled_areas:
                if area_id not in areas_to_try:
                    areas_to_try.append(area_id)
                if len(areas_to_try) >= max_areas_to_try:
                    break
        else:
            # Using real availability data, try in order
            for area_id in available_area_ids:
                if area_id not in areas_to_try:
                    areas_to_try.append(area_id)
                if len(areas_to_try) >= max_areas_to_try:
                    break
        
        if not areas_to_try:
            raise Exception("No areas available to try")
        
        print(f"📍 Will try {len(areas_to_try)} area(s): {areas_to_try}")
        
        # Step 5: Try to book (should succeed on first or second try)
        last_error = None
        
        for idx, area_id in enumerate(areas_to_try, 1):
            print(f"\n{'─'*60}")
            print(f"Attempt {idx}/{len(areas_to_try)}: Booking area {area_id}...")
            
            payload = {
                "propertyId": self._property_id,
                "agentId": int(self.query_agent_id),
                "arrivalDate": arrival,
                "departureDate": departure,
                "adults": adults,
                "children": children,
                "infants": 0,
                "categoryId": category_id,
                "rateTypeId": rate_plan_id,
                "status": "Confirmed",
                "source": "API",
                "areaId": area_id,
                "nights": nights,
                "guestId": guest_id,
                "paymentMethod": "PayLater",
                "sendConfirmationEmail": True,
            }
            if guest_membership_id is not None:
                payload["guestMembershipId"] = guest_membership_id
            
            try:
                reservation = await client.create_reservation(payload)
                
                # Success! Cache this area for future use
                self._add_working_area_to_cache(category_id, rate_plan_id, arrival, departure, area_id)
                
                reservation_id = reservation.get('id') or reservation.get('reservationId')
                confirmation_number = reservation.get('confirmationNumber') or reservation.get('confirmationCode')
                
                print(f"\n RESERVATION SUCCESSFUL!")
                print(f"{'='*80}")
                print(f"   Reservation ID: {reservation_id}")
                print(f"   Confirmation: {confirmation_number}")
                print(f"   Assigned Room/Area: {area_id}")
                print(f"   Guest: {guest_firstName} {guest_lastName}")
                print(f"   Email: {guest_email}")
                print(f"   Succeeded on attempt {idx} of {len(areas_to_try)}")
                print(f"{'='*80}\n")
                
                return reservation
                
            except Exception as e:
                import httpx
                last_error = e
                
                error_msg = str(e)
                if isinstance(e, httpx.HTTPStatusError):
                    try:
                        response_data = e.response.json()
                        if isinstance(response_data, dict) and 'message' in response_data:
                            error_msg = response_data['message']
                    except:
                        pass
                
                error_msg_lower = error_msg.lower()
                is_area_blocked = (
                    ("site" in error_msg_lower and "not available" in error_msg_lower) or
                    ("area" in error_msg_lower and "not available" in error_msg_lower) or 
                    "blocking reservation" in error_msg_lower
                )
                
                if is_area_blocked:
                    print(f"   ❌ Area {area_id} is blocked (unexpected - should have been available)")
                    continue
                else:
                    print(f"\n❌ UNEXPECTED ERROR")
                    print(f"   Error: {error_msg}")
                    raise Exception(f"Failed to create reservation: {error_msg}")
        
        # All attempts failed (should be rare with availability-first approach)
        print(f"\n❌ RESERVATION FAILED AFTER {len(areas_to_try)} ATTEMPTS")
        print(f"{'='*80}")
        error_detail = (
            f"Failed to create reservation for category {category_id}. "
            f"Availability was confirmed but booking failed. "
        )
        if last_error:
            error_detail += f"Last error: {str(last_error)}"
        print(f"   {error_detail}")
        print(f"{'='*80}\n")
        raise Exception(error_detail)

    async def create_reservation_group(
        self,
        bookings: List[Dict],
    ) -> Dict:
        """
        Create multiple reservations in a single group (Add Reservation Group).
        Each booking dict must have: category_id, rate_plan_id, arrival, departure,
        adults, children, guest_firstName, guest_lastName, guest_email, guest_phone (optional),
        guest_membership_id (optional).
        Builds one RMS reservation payload per booking (with guest lookup and area selection),
        then calls RMS addReservationGroup in one API call.
        """
        if not self._initialized:
            raise Exception("RMS service not initialized")
        if not bookings:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="At least one booking is required for group reservation")

        client = self._get_api_client()
        reservation_payloads = []

        print(f"\n{'='*80}")
        print(f"CREATING GROUP RESERVATION ({len(bookings)} booking(s))")
        print(f"{'='*80}")

        for idx, b in enumerate(bookings, 1):
            category_id = b.get("category_id")
            rate_plan_id = b.get("rate_plan_id")
            arrival = b.get("arrival")
            departure = b.get("departure")
            adults = int(b.get("adults", 1))
            children = int(b.get("children", 0))
            guest_firstName = b.get("guest_firstName", "").strip()
            guest_lastName = b.get("guest_lastName", "").strip()
            guest_email = b.get("guest_email", "").strip()
            guest_phone = (b.get("guest_phone") or "").strip() or None
            raw_membership = b.get("guest_membership_id")
            guest_membership_id = None
            if raw_membership is not None and raw_membership != "":
                try:
                    guest_membership_id = int(raw_membership)
                except (TypeError, ValueError):
                    guest_membership_id = None

            if adults < 1:
                raise Exception(f"Booking {idx}: at least 1 adult is required")
            if not category_id or not rate_plan_id or not arrival or not departure:
                raise Exception(f"Booking {idx}: category_id, rate_plan_id, arrival, departure are required")
            if not guest_firstName or not guest_lastName or not guest_email:
                raise Exception(f"Booking {idx}: guest first name, last name and email are required")

            # Validate occupancy
            is_valid, error_msg = self._validate_occupancy(category_id, adults, children)
            if not is_valid:
                raise Exception(f"Booking {idx}: {error_msg}")

            # Get available areas for this booking
            payload_av = {
                "propertyId": self._property_id,
                "categoryId": category_id,
                "arrivalDate": arrival,
                "departureDate": departure,
                "adults": adults,
                "children": children,
            }
            try:
                areas_response = await client.get_available_areas(payload_av)
                available_area_ids = [a.get("id") for a in areas_response if a.get("id")]
            except Exception as e:
                raise Exception(f"Booking {idx}: could not check availability: {e}")
            if not available_area_ids:
                raise Exception(
                    f"Booking {idx}: no areas available for category {category_id} between {arrival} and {departure}"
                )
            area_id = available_area_ids[0]

            # Find or create guest
            guest = {
                "firstName": guest_firstName,
                "lastName": guest_lastName,
                "email": guest_email,
                "phone": guest_phone,
            }
            guest_id = await self._find_or_create_guest(guest)
            if not guest_id:
                raise Exception(f"Booking {idx}: failed to create/find guest")

            arrival_date = datetime.fromisoformat(arrival)
            departure_date = datetime.fromisoformat(departure)
            nights = (departure_date - arrival_date).days

            one = {
                "propertyId": self._property_id,
                "agentId": int(self.query_agent_id),
                "arrivalDate": arrival,
                "departureDate": departure,
                "adults": adults,
                "children": children,
                "infants": 0,
                "categoryId": category_id,
                "rateTypeId": rate_plan_id,
                "status": "Confirmed",
                "source": "API",
                "areaId": area_id,
                "nights": nights,
                "guestId": guest_id,
                "paymentMethod": "PayLater",
                "sendConfirmationEmail": True,
            }
            if guest_membership_id is not None and isinstance(guest_membership_id, int):
                one["guestMembershipId"] = guest_membership_id
            reservation_payloads.append(one)
            print(f"Booking {idx}: guest {guest_id}, area {area_id}, {arrival}–{departure}")

        try:
            result = await client.create_reservation_group(reservation_payloads)
            print(f"\n GROUP RESERVATION CREATED ({len(reservation_payloads)} reservation(s))")
            print(f"{'='*80}\n")
            return result
        except Exception as e:
            import httpx

            message = str(e)
            if isinstance(e, httpx.HTTPStatusError):
                try:
                    data = e.response.json()
                    if isinstance(data, dict) and "message" in data:
                        message = data["message"]
                except Exception:
                    pass

            msg_lower = message.lower()
            area_blocked = "area" in msg_lower and "not available" in msg_lower
            more_than_one = "more than one reservation is required" in msg_lower

            if not (area_blocked or more_than_one):
                # Unexpected error – surface it
                raise

            print(f"\n RMS group booking failed: {message}")
            print("   Falling back to creating individual reservations sequentially...")

            # Use robust single-reservation logic (rotates areas, handles blocks)
            fallback_results: List[Dict] = []
            for idx, b in enumerate(bookings, 1):
                try:
                    res = await self.create_reservation(
                        category_id=b["category_id"],
                        rate_plan_id=b["rate_plan_id"],
                        arrival=b["arrival"],
                        departure=b["departure"],
                        adults=b["adults"],
                        children=b.get("children") or 0,
                        guest_firstName=b["guest_firstName"],
                        guest_lastName=b["guest_lastName"],
                        guest_email=b["guest_email"],
                        guest_phone=b.get("guest_phone"),
                        guest_membership_id=b.get("guest_membership_id"),
                    )
                    fallback_results.append(res)
                    print(f"Fallback booking {idx} created via single reservation API")
                except Exception as sub_e:
                    print(f"Fallback booking {idx} failed: {sub_e}")
                    raise

            print(f"\n Completed {len(fallback_results)} fallback reservations (not RMS-grouped but all confirmed)")
            print(f"{'='*80}\n")
            return {"reservations": fallback_results}

    async def _find_or_create_guest(self, guest: Dict) -> Optional[int]:
        """Find existing guest by email or create new one"""
        client = self._get_api_client()
        email = guest.get('email')
        
        # Try to find existing guest by email
        if email:
            search_payload = {
                "propertyId": self._property_id,
                "email": email
            }
            
            try:
                results = await client.search_guests(search_payload)
                if results and len(results) > 0:
                    guest_id = results[0].get('id')
                    print(f"   Found existing guest: {guest_id}")
                    return guest_id
            except Exception as e:
                print(f"Guest search failed (will create new): {e}")
        
        # Create new guest
        create_payload = {
            "propertyId": self._property_id,
            "guestGiven": guest.get('firstName', 'Guest'),
            "guestSurname": guest.get('lastName', ''),
            "email": email,
            "mobile": guest.get('phone', '')
        }
        
        try:
            result = await client.create_guest(create_payload)
            guest_id = result.get('id') or result.get('guestId')
            print(f"   Created new guest: {guest_id}")
            return guest_id
        except Exception as e:
            print(f"Failed to create guest: {e}")
            return None
    
    async def get_reservation(self, reservation_id: int) -> Dict:
        """Get reservation details by ID"""
        if not self._initialized:
            raise Exception("RMS service not initialized")
        
        client = self._get_api_client()
        return await client.get_reservation(reservation_id)
    
    async def cancel_reservation(self, reservation_id: int) -> Dict:
        """Cancel a reservation"""
        if not self._initialized:
            raise Exception("RMS service not initialized")
        
        client = self._get_api_client()
        return await client.cancel_reservation(reservation_id)

    async def get_guest_memberships(self, guest_id: int) -> List[Dict]:
        """
        Fetch memberships for a guest from RMS.
        Proxies RMS GET /guests/{id}/memberships.
        """
        client = self._get_api_client()
        return await client.get_guest_memberships(guest_id)

    async def verify_membership_number(
        self,
        guest_id: int,
        membership_number: str,
        program: Optional[str] = None
    ) -> Dict:
        """
        Verify that a given membership number exists and is active for a guest.
        Optionally filter by program (e.g. 'gday', 'big4') using membershipTypeName.
        """
        memberships = await self.get_guest_memberships(guest_id)

        normalized_program = program.lower().strip() if program else None
        matched = []

        for m in memberships:
            if m.get("inactive"):
                continue
            if str(m.get("number")).strip() != membership_number.strip():
                continue

            if normalized_program:
                type_name = (m.get("membershipTypeName") or "").lower()

                if normalized_program == "gday":
                    if "g'day" not in type_name and "gday" not in type_name and "g day" not in type_name:
                        continue
                elif normalized_program == "big4":
                    if "big4" not in type_name and "big 4" not in type_name and "big-4" not in type_name:
                        continue

            matched.append(m)

        return {
            "guestId": guest_id,
            "membershipNumber": membership_number,
            "program": program,
            "is_valid": len(matched) > 0,
            "memberships": matched,
        }

    async def verify_membership_by_email(
        self,
        guest_email: str,
        membership_number: str,
        program: Optional[str] = None
    ) -> Dict:
        """
        Verify a membership number for a guest identified by email (no guest_id needed).
        Looks up the guest in RMS by email, then checks their memberships against the
        given membership_number. Returns verification result and matched membership
        details so the caller can apply the RMS discount (e.g. when creating a reservation).
        """
        await self.initialize()
        client = self._get_api_client()

        search_payload = {
            "propertyId": self._property_id,
            "email": guest_email.strip(),
        }
        try:
            results = await client.search_guests(search_payload)
        except Exception as e:
            return {
                "guestId": None,
                "membershipNumber": membership_number,
                "program": program,
                "is_valid": False,
                "memberships": [],
                "message": f"Guest lookup failed: {e}",
            }

        if not results or len(results) == 0:
            return {
                "guestId": None,
                "membershipNumber": membership_number,
                "program": program,
                "is_valid": False,
                "memberships": [],
                "message": "No guest found with this email.",
            }

        guest_id = results[0].get("id")
        if not guest_id:
            return {
                "guestId": None,
                "membershipNumber": membership_number,
                "program": program,
                "is_valid": False,
                "memberships": [],
                "message": "Guest record has no id.",
            }

        result = await self.verify_membership_number(
            guest_id=guest_id,
            membership_number=membership_number,
            program=program,
        )
        return result


# Create a default instance for backward compatibility (will use env vars)
rms_service = RMSService()