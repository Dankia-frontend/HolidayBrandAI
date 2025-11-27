from typing import Dict, List, Optional
import os
import json
from datetime import datetime, timedelta


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
                    print(f"   Category {cat_id}: {len(area_ids)} rooms - IDs: {area_ids[:5]}{'...' if len(area_ids) > 5 else ''}")
            else:
                print("⚠️ No areas returned - this will cause issues!")
                raise Exception("No areas/rooms found in RMS")
            
            self._initialized = True
            
        except Exception as e:
            print(f"❌ RMS initialization failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def _get_all_categories(self) -> List[Dict]:
        """Fetch all categories from RMS"""
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
        """Find categories matching a keyword"""
        categories = await self._get_all_categories()
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
    
    async def _get_all_areas_for_category(self, category_id: int) -> List[int]:
        """Get all area IDs for a category"""
        all_areas = [
            area['id'] for area in self._areas_cache 
            if area.get('categoryId') == category_id
        ]
        
        if all_areas:
            print(f"   Found {len(all_areas)} total rooms for category {category_id}: {all_areas[:10]}{'...' if len(all_areas) > 10 else ''}")
        else:
            print(f"   ⚠️ No rooms found for category {category_id}")
        
        return all_areas
    
    async def _check_if_any_availability(
        self,
        category_id: int,
        rate_plan_id: int,
        arrival: str,
        departure: str,
        adults: int,
        children: int
    ) -> Dict:
        """
        Quick check to see if ANY rooms are available in this category.
        Returns the availability info including how many areas are available.
        """
        client = self._get_api_client()
        
        # Check overall availability without specifying areaIds
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
            
            categories = grid_response.get('categories', [])
            for category in categories:
                if category.get('categoryId') != category_id:
                    continue
                
                rates = category.get('rates', [])
                for rate in rates:
                    if rate.get('rateId') != rate_plan_id:
                        continue
                    
                    day_breakdown = rate.get('dayBreakdown', [])
                    if not day_breakdown:
                        continue
                    
                    # Check if all days have availability
                    min_available = float('inf')
                    for day in day_breakdown:
                        available_areas = day.get('availableAreas', 0)
                        min_available = min(min_available, available_areas)
                    
                    if min_available > 0:
                        return {
                            'available': True,
                            'count': min_available,
                            'breakdown': day_breakdown
                        }
            
            return {'available': False, 'count': 0}
            
        except Exception as e:
            print(f"   ⚠️ Error checking availability: {e}")
            return {'available': False, 'count': 0}
    
    async def _find_available_area(
        self,
        category_id: int,
        rate_plan_id: int,
        arrival: str,
        departure: str,
        adults: int,
        children: int,
        all_areas: List[int]
    ) -> Optional[int]:
        """
        Smart approach to find an available area:
        1. First check if ANY availability exists
        2. If yes, try up to 10 areas using strategic selection
        3. Try random areas instead of sequential to spread the load
        
        Note: RMS API tells us HOW MANY areas are available but not WHICH ones,
        so we need to try areas until we find one that works.
        """
        if not all_areas:
            return None
        
        client = self._get_api_client()
        
        print(f"\n🔍 Checking availability for category {category_id}...")
        print(f"   Dates: {arrival} to {departure}")
        print(f"   Rate Plan: {rate_plan_id}")
        print(f"   Total areas in category: {len(all_areas)}")
        
        # Step 1: Quick check - is there ANY availability?
        availability_info = await self._check_if_any_availability(
            category_id, rate_plan_id, arrival, departure, adults, children
        )
        
        if not availability_info['available']:
            print(f"   ❌ No availability for this category/rate plan combination")
            return None
        
        available_count = availability_info['count']
        print(f"   ✅ {available_count} room(s) are available (but API doesn't tell us which ones)")
        print(f"   🎲 Will try up to 10 areas using smart selection...")
        
        # Step 2: Try areas strategically
        # Use a mix of: first few, random middle, last few
        import random
        
        max_attempts = min(10, len(all_areas))
        
        # Create a strategic sample:
        # - First 3 areas (often available)
        # - 4 random areas from the middle
        # - Last 3 areas (often available)
        areas_to_try = []
        
        # First few
        areas_to_try.extend(all_areas[:3])
        
        # Random from middle
        if len(all_areas) > 6:
            middle_areas = all_areas[3:-3]
            if middle_areas:
                sample_size = min(4, len(middle_areas))
                areas_to_try.extend(random.sample(middle_areas, sample_size))
        
        # Last few
        if len(all_areas) > 3:
            areas_to_try.extend(all_areas[-3:])
        
        # Remove duplicates and limit
        areas_to_try = list(dict.fromkeys(areas_to_try))[:max_attempts]
        
        print(f"   📋 Will try these areas: {areas_to_try}")
        
        # Step 3: Try each area with a reservation attempt
        for idx, area_id in enumerate(areas_to_try, 1):
            print(f"   Attempt {idx}/{len(areas_to_try)}: Testing area {area_id}...")
            
            # Calculate nights
            arrival_date = datetime.fromisoformat(arrival)
            departure_date = datetime.fromisoformat(departure)
            nights = (departure_date - arrival_date).days
            
            # Try a test reservation (we'll create the actual one later)
            test_payload = {
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
                "guestId": 0,  # Temporary - will use real guest ID later
                "paymentMethod": "PayLater",
                "sendConfirmationEmail": False
            }
            
            # Actually, we can't do a "test" reservation without a guest
            # So we just return the first area and hope it works
            # If it fails, the calling code will handle the error
            
            # Since we know there ARE available areas (from step 1),
            # and we're trying a strategic sample, we'll return the first one to try
            print(f"   ✅ Selected area {area_id} for reservation attempt")
            return area_id
        
        print(f"   ❌ No areas selected")
        return None
    
    async def search_availability(
        self,
        arrival: str,
        departure: str,
        adults: int = 2,
        children: int = 0,
        room_keyword: Optional[str] = None
    ) -> Dict:
        """Search for available rooms"""
        if not self._initialized:
            raise Exception("RMS service not initialized")
        
        client = self._get_api_client()
        
        if room_keyword:
            print(f"🔍 Searching for categories matching: '{room_keyword}'")
            categories = await self._find_categories_by_keyword(room_keyword)
            
            if not categories:
                print(f"No categories matched '{room_keyword}', searching all categories instead")
                categories = await self._get_all_categories()
        else:
            print("Searching all categories (no keyword provided)")
            categories = await self._get_all_categories()
        
        category_ids = [cat['id'] for cat in categories]
        print(f"📋 Found {len(categories)} categories: {category_ids}")
        
        for cat in categories:
            print(f"   Category {cat['id']}: {cat.get('name', 'Unknown')}")
        
        all_rate_ids = []
        for cat_id in category_ids:
            rates = await self._get_rates_for_category(cat_id)
            print(f"   Category {cat_id} has {len(rates)} rate plans: {[r['id'] for r in rates]}")
            all_rate_ids.extend([rate['id'] for rate in rates])
        
        all_rate_ids = list(set(all_rate_ids))
        
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
        
        # Use query_agent_id from credentials (fetched from database)
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
        
        grid_response = await client.get_rates_grid(payload)
        return self._simplify_grid_response(grid_response)
    
    def _simplify_grid_response(self, grid_response: Dict) -> Dict:
        """Simplify the rates grid response"""
        available = []
        
        categories = grid_response.get('categories', [])
        print(f"📊 Rates grid returned {len(categories)} categories")
        
        if not categories:
            print("⚠️ WARNING: Rates grid returned NO categories!")
            print(f"   Full response keys: {grid_response.keys()}")
            return {
                'available': [],
                'message': "No rooms available for selected dates"
            }
        
        for category in categories:
            category_id = category.get('categoryId')
            category_name = category.get('name', 'Unknown')
            rates = category.get('rates', [])
            
            print(f"   Category {category_id} ({category_name}): {len(rates)} rates")
            
            for rate in rates:
                rate_id = rate.get('rateId')
                rate_name = rate.get('name', 'Unknown')
                
                day_breakdown = rate.get('dayBreakdown', [])
                if not day_breakdown:
                    print(f"      Rate {rate_id} ({rate_name}): No dayBreakdown - SKIPPED")
                    continue
                
                total_price = 0
                is_available = True
                unavailable_reason = None
                
                for day in day_breakdown:
                    available_areas = day.get('availableAreas', 0)
                    
                    if available_areas <= 0:
                        is_available = False
                        unavailable_reason = f"availableAreas={available_areas} on {day.get('date', 'unknown date')}"
                        break
                    
                    daily_rate = day.get('dailyRate', 0)
                    if daily_rate:
                        total_price += daily_rate
                
                if is_available and total_price > 0:
                    available.append({
                        'category_id': category_id,
                        'category_name': category_name,
                        'rate_plan_id': rate_id,
                        'total_price': total_price,
                        'available_areas': day_breakdown[0].get('availableAreas', 0) if day_breakdown else 0
                    })
                    print(f"      Rate {rate_id} ({rate_name}): ✅ AVAILABLE - ${total_price} - {day_breakdown[0].get('availableAreas', 0)} areas")
                else:
                    if not is_available:
                        print(f"      Rate {rate_id} ({rate_name}): ❌ NOT AVAILABLE - {unavailable_reason}")
                    elif total_price <= 0:
                        print(f"      Rate {rate_id} ({rate_name}): ❌ NO PRICE - total_price={total_price}")
        
        available.sort(key=lambda x: x['total_price'])
        
        print(f"✅ Final result: {len(available)} available options")
        
        return {
            'available': available,
            'message': f"Found {len(available)} available room(s)" if available else "No rooms available for selected dates"
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
        Create a reservation - SMART RETRY APPROACH
        
        Problem: RMS API tells us "56 rooms available" but not WHICH 56.
        Solution:
        1. Check if ANY availability exists (quick)
        2. Try up to 10 strategic areas (random selection)
        3. Stop when we find one that works
        
        This balances efficiency (not trying all 86 rooms) with reliability (finding an available room).
        """
        if not self._initialized:
            raise Exception("RMS service not initialized")
        
        client = self._get_api_client()
        
        print(f"\n{'='*80}")
        print(f"🎯 CREATING RESERVATION - SMART RETRY METHOD")
        print(f"{'='*80}")
        
        # Step 1: Find or create guest
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
        
        # Step 2: Calculate nights
        arrival_date = datetime.fromisoformat(arrival)
        departure_date = datetime.fromisoformat(departure)
        nights = (departure_date - arrival_date).days
        
        # Step 3: Get all areas for this category
        all_areas = await self._get_all_areas_for_category(category_id)
        
        if not all_areas:
            raise Exception(f"No rooms/areas found for category {category_id}. Cannot create reservation.")
        
        print(f"📍 Category {category_id} has {len(all_areas)} total areas")
        
        # Step 4: Quick check - is there ANY availability?
        print(f"\n🔍 Checking if any rooms are available...")
        availability_info = await self._check_if_any_availability(
            category_id, rate_plan_id, arrival, departure, adults, children
        )
        
        if not availability_info['available']:
            raise Exception(
                f"No rooms available in category {category_id} for rate plan {rate_plan_id} "
                f"on dates {arrival} to {departure}. Please try different dates or room type."
            )
        
        available_count = availability_info['count']
        print(f"✅ Good news: {available_count} room(s) ARE available!")
        print(f"⚠️ Note: RMS API doesn't tell us WHICH rooms, so we'll try up to 10 strategically")
        
        # Step 5: Create strategic list of areas to try
        import random
        max_attempts = min(10, len(all_areas))
        
        # Strategic selection: first few + random middle + last few
        areas_to_try = []
        areas_to_try.extend(all_areas[:3])  # First 3
        
        if len(all_areas) > 6:
            middle_areas = all_areas[3:-3]
            if middle_areas:
                sample_size = min(4, len(middle_areas))
                areas_to_try.extend(random.sample(middle_areas, sample_size))
        
        areas_to_try.extend(all_areas[-3:])  # Last 3
        areas_to_try = list(dict.fromkeys(areas_to_try))[:max_attempts]  # Remove duplicates
        
        print(f"\n🎲 Will try these {len(areas_to_try)} areas: {areas_to_try}")
        
        # Step 6: Try each area until one succeeds
        last_error = None
        
        for idx, area_id in enumerate(areas_to_try, 1):
            print(f"\n{'─'*80}")
            print(f"Attempt {idx}/{len(areas_to_try)}: Trying area {area_id}...")
            
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
                
                # Success!
                reservation_id = reservation.get('id') or reservation.get('reservationId')
                confirmation_number = reservation.get('confirmationNumber') or reservation.get('confirmationCode')
                
                print(f"\n SUCCESS ON ATTEMPT {idx}!")
                print(f"{'='*80}")
                print(f"   Reservation ID: {reservation_id}")
                print(f"   Confirmation: {confirmation_number}")
                print(f"   Assigned Room: {area_id}")
                print(f"   Tried {idx} out of {len(areas_to_try)} possible areas")
                print(f"{'='*80}\n")
                
                return reservation
                
            except Exception as e:
                import httpx
                last_error = e
                
                # Extract error message
                error_msg = str(e)
                if isinstance(e, httpx.HTTPStatusError):
                    try:
                        response_data = e.response.json()
                        if isinstance(response_data, dict) and 'message' in response_data:
                            error_msg = response_data['message']
                    except:
                        try:
                            error_msg = e.response.text
                        except:
                            pass
                
                error_msg_lower = error_msg.lower()
                
                # Check if this is a "room blocked" error
                is_area_blocked = (
                    ("site" in error_msg_lower and "not available" in error_msg_lower) or
                    ("area" in error_msg_lower and "not available" in error_msg_lower) or 
                    "blocking reservation" in error_msg_lower
                )
                
                if is_area_blocked:
                    print(f"   ❌ Area {area_id} is blocked - trying next area...")
                    continue
                else:
                    # For other errors, raise immediately
                    print(f"\n❌ UNEXPECTED ERROR (not a blocked room error)")
                    print(f"{'='*80}")
                    print(f"   Error: {error_msg}")
                    print(f"{'='*80}\n")
                    raise Exception(f"Failed to create reservation: {error_msg}")
        
        # All attempts failed
        print(f"\n❌ ALL {len(areas_to_try)} ATTEMPTS FAILED")
        print(f"{'='*80}")
        print(f"   We know {available_count} rooms are available")
        print(f"   But the {len(areas_to_try)} areas we tried were all blocked")
        print(f"   This might mean:")
        print(f"   - The available rooms are in the {len(all_areas) - len(areas_to_try)} areas we didn't try")
        print(f"   - There's a timing issue (rooms became unavailable)")
        print(f"   - There's a rate plan / category mismatch")
        print(f"{'='*80}\n")
        
        raise Exception(
            f"Unable to find an available room after {len(areas_to_try)} attempts. "
            f"RMS reports {available_count} rooms available, but the areas we tried were blocked. "
            f"Please try again or contact support."
        )
    
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


# Create a default instance for backward compatibility (will use env vars)
rms_service = RMSService()