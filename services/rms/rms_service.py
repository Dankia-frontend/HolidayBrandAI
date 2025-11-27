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
        
        # Lightweight cache: just remember which areas worked recently
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
        
        # If no vacant areas, fall back to all areas (shouldn't happen)
        if not available_areas:
            print(f"   ⚠️ No vacant areas found, trying all areas as fallback")
            available_areas = [area['id'] for area in all_category_areas]
        
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
        Uses: first few + random middle + last few + any cached working areas
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
        Search for available rooms - ULTRA FAST VERSION
        Only 1-2 API calls total!
        """
        if not self._initialized:
            raise Exception("RMS service not initialized")
        
        client = self._get_api_client()
        
        # Get category IDs (use cache if available to avoid API call)
        if room_keyword:
            print(f"🔍 Searching: '{room_keyword}'")
            if self._categories_cache:
                # Use cached categories
                categories = [cat for cat in self._categories_cache.values() 
                             if room_keyword.lower() in cat['name'].lower()]
                if not categories:
                    categories = list(self._categories_cache.values())
            else:
                # Fetch if not cached
                categories = await self._find_categories_by_keyword(room_keyword)
                if not categories:
                    categories = await self._get_all_categories()
        else:
            print("🔍 Searching all categories")
            if self._categories_cache:
                categories = list(self._categories_cache.values())
            else:
                categories = await self._get_all_categories()
        
        category_ids = [cat['id'] for cat in categories]
        print(f"   Categories: {category_ids}")
        
        # IMPORTANT: Don't fetch rates separately!
        # The rates grid API returns all available rates automatically
        # We just pass the category IDs and it gives us back available rates
        
        print(f"   Dates: {arrival} to {departure}")
        print(f"   Guests: {adults} adults, {children} children")
        
        # Filter to only active categories with areas (prevent 500 error)
        active_category_ids = []
        for cat in categories:
            if not cat.get('inactive', False) and cat.get('numberOfAreas', 0) > 0:
                active_category_ids.append(cat['id'])
        
        print(f"   Filtered to {len(active_category_ids)} active categories (from {len(category_ids)} total)")
        
        payload = {
            "propertyId": self._property_id,
            "agentId": int(self.query_agent_id),
            "arrival": arrival,
            "departure": departure,
            "adults": adults,
            "children": children,
            "categoryIds": active_category_ids,  # Use filtered categories
            # Don't specify rateIds - let API return all available rates
            "includeEstimatedRates": False,
            "includeZeroRates": False
        }
        
        print("📡 Calling rates grid API...")
        grid_response = await client.get_rates_grid(payload)
        return self._simplify_grid_response(grid_response)
    
    def _simplify_grid_response(self, grid_response: Dict) -> Dict:
        """Simplify the rates grid response - FAST, NO DISCOVERY"""
        available = []
        
        categories = grid_response.get('categories', [])
        print(f"📊 Rates grid returned {len(categories)} categories")
        
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
                
                day_breakdown = rate.get('dayBreakdown', [])
                if not day_breakdown:
                    continue
                
                total_price = 0
                is_available = True
                available_count = None
                
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
                
                if is_available and total_price > 0 and available_count > 0:
                    available.append({
                        'category_id': category_id,
                        'category_name': category_name,
                        'rate_plan_id': rate_id,
                        'total_price': total_price,
                        'available_areas': available_count
                    })
                    print(f"   Category {category_id}, Rate {rate_id}: ✅ {available_count} areas - ${total_price}")
        
        available.sort(key=lambda x: x['total_price'])
        print(f"✅ Search complete: {len(available)} available options")
        
        return {
            'available': available,
            'message': f"Found {len(available)} available room(s)" if available else "No rooms available"
        }
    
    async def create_reservation(
        self,
        category_id: int,
        rate_plan_id: int,
        arrival: str,
        departure: str,
        adults: int,
        children: int,
        guest_firstName: str,
        guest_lastName: str,
        guest_email: str,
        guest_phone: Optional[str] = None
    ) -> Dict:
        """
        Create reservation by checking availability FIRST before attempting to book.
        
        Strategy:
        1. Call rates grid API to get actual available areas for this date range
        2. Try to book one of those available areas (should succeed immediately)
        3. Cache successful area for future bookings
        
        This dramatically reduces booking attempts from 8+ to typically 1-2.
        """
        if not self._initialized:
            raise Exception("RMS service not initialized")
        
        client = self._get_api_client()
        
        print(f"\n{'='*80}")
        print(f"🎯 CREATING RESERVATION - AVAILABILITY-FIRST APPROACH")
        print(f"{'='*80}")
        
        # Step 1: Check availability FIRST to find actually available areas
        print(f"🔍 Step 1: Checking actual availability for category {category_id}, rate {rate_plan_id}...")
        
        available_area_ids = []
        try:
            # Call /availableAreas API directly - much more reliable!
            client = self._get_api_client()
            
            payload = {
                "propertyId": self._property_id,
                "categoryId": category_id,
                "arrival": arrival,
                "departure": departure,
                "adults": adults,
                "children": children
            }
            
            print(f"📡 Calling /availableAreas API for category {category_id}...")
            print(f"   Dates: {arrival} to {departure}")
            print(f"   Guests: {adults} adults, {children} children")
            
            available_areas_response = await client.get_available_areas(payload)
            
            # Extract area IDs from response
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
            import random
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
            
            try:
                reservation = await client.create_reservation(payload)
                
                # Success! Cache this area for future use
                self._add_working_area_to_cache(category_id, rate_plan_id, arrival, departure, area_id)
                
                reservation_id = reservation.get('id') or reservation.get('reservationId')
                confirmation_number = reservation.get('confirmationNumber') or reservation.get('confirmationCode')
                
                print(f"\n🎉 RESERVATION SUCCESSFUL!")
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



    async def _find_or_create_guest(self, guest: Dict) -> Optional[int]:
        """Find existing guest by email or create new one"""
        client = self._get_api_client()
        email = guest.get('email')
        
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
                print(f"   ⚠️ Guest search failed: {e}")
        
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
            print(f"   ❌ Failed to create guest: {e}")
            return None
    
    async def get_reservation(self, reservation_id: int) -> Dict:
        """Get reservation details"""
        client = self._get_api_client()
        return await client.get_reservation(reservation_id)
    
    async def cancel_reservation(self, reservation_id: int) -> Dict:
        """Cancel a reservation"""
        client = self._get_api_client()
        return await client.cancel_reservation(reservation_id)


# Create a default instance for backward compatibility
rms_service = RMSService()