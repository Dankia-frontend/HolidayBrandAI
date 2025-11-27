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
                    print(f"   Category {cat_id}: {len(area_ids)} rooms")
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
            print(f"   Found {len(all_areas)} total rooms for category {category_id}")
        else:
            print(f"   ⚠️ No rooms found for category {category_id}")
        
        return all_areas
    
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
                    print(f"      Rate {rate_id} ({rate_name}): ✅ AVAILABLE - ${total_price}")
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
        guest: Dict
    ) -> Dict:
        """
        Create a reservation - MATCHES ORIGINAL WORKING LOGIC
        Tries multiple areas until one succeeds
        """
        if not self._initialized:
            raise Exception("RMS service not initialized")
        
        client = self._get_api_client()
        
<<<<<<< Updated upstream
        # Step 1: Search for existing guest or create new one
        print(f"Searching for guest: {guest.get('email')}")
        guest_id = await self.search_or_create_guest(guest)
=======
        # Step 1: Find or create guest
        guest = {
            'firstName': guest_firstName,
            'lastName': guest_lastName,
            'email': guest_email,
            'phone': guest_phone
        }
        
        guest_id = await self._find_or_create_guest(guest)
>>>>>>> Stashed changes
        
        if not guest_id:
            raise Exception("Failed to create/find guest")
        
        print(f"Using guest ID: {guest_id}")
        
<<<<<<< Updated upstream
        # Step 2: Calculate number of nights
=======
        # Step 2: Calculate nights
>>>>>>> Stashed changes
        arrival_date = datetime.fromisoformat(arrival)
        departure_date = datetime.fromisoformat(departure)
        nights = (departure_date - arrival_date).days
        
<<<<<<< Updated upstream
        # Step 3: Verify availability using rates grid
        print(f"Verifying availability for category {category_id} and rate {rate_plan_id}...")
        
        # Build the rates grid request
        categories = await rms_cache.get_all_categories()
        category_ids = [cat['id'] for cat in categories]
        
        all_rate_ids = []
        for cat_id in category_ids:
            rates = await rms_cache.get_rates_for_category(cat_id)
            all_rate_ids.extend([rate['id'] for rate in rates])
        
        all_rate_ids = list(set(all_rate_ids))
        
        # using query agent for availability checks (typically agent ID 2 in RMS) which is now added in .env instead of hardcode.
        # This agent has full visibility into availability across all channels
        # now the booking agent (agent_id) is used for actual reservation creation
        import os
        query_agent_id = int(os.getenv("RMS_QUERY_AGENT_ID", "2"))
        
        payload = {
            "propertyId": property_id,
            "agentId": query_agent_id,  
            "arrival": arrival,
            "departure": departure,
            "adults": adults,
            "children": children,
            "categoryIds": category_ids,
            "rateIds": all_rate_ids,
            "includeEstimatedRates": False,
            "includeZeroRates": False
        }
        
        grid_response = await rms_client.get_rates_grid(payload)
        
        # Check if this category + rate combination is available
        is_available = False
        available_count = 0
        
        categories_in_response = grid_response.get('categories', [])
        for category in categories_in_response:
            if category.get('categoryId') != category_id:
                continue
            
            for rate in category.get('rates', []):
                if rate.get('rateId') != rate_plan_id:
                    continue
                
                # Found the matching category and rate
                day_breakdown = rate.get('dayBreakdown', [])
                if not day_breakdown:
                    break
                
                # Check if all days have availability
                all_days_available = True
                for day in day_breakdown:
                    areas = day.get('availableAreas', 0)
                    if areas <= 0:
                        all_days_available = False
                        break
                    available_count = areas
                
                if all_days_available:
                    is_available = True
                break
        
        if not is_available or available_count == 0:
            raise Exception(
                f"No available rooms found for category {category_id} with rate {rate_plan_id} "
                f"for dates {arrival} to {departure}. The room may be blocked or fully booked."
            )
        
        print(f"Confirmed: {available_count} room(s) available for these dates")
        
        # Step 4: Get all areas for this category from cache
        all_areas = await rms_cache.get_all_areas_for_category(category_id)
=======
        # Step 3: Get all areas for this category
        all_areas = await self._get_all_areas_for_category(category_id)
>>>>>>> Stashed changes
        
        if not all_areas:
            raise Exception(f"No rooms/areas found for category {category_id}. Cannot create reservation.")
        
        print(f"Found {len(all_areas)} total area(s) in category {category_id}")
        
<<<<<<< Updated upstream
        # Step 5: Try to create reservation with each area until one succeeds
=======
        # Step 4: Try to create reservation with each area until one succeeds
>>>>>>> Stashed changes
        last_error = None
        
        for idx, area_id in enumerate(all_areas):
            if idx > 0:
                print(f"Trying alternate area {idx + 1}/{len(all_areas)}: {area_id}")
            else:
                print(f"Trying area ID {area_id} from category {category_id}")
            
<<<<<<< Updated upstream
            # Create reservation payload
=======
            # Create reservation payload - MATCHING ORIGINAL WORKING CODE
>>>>>>> Stashed changes
            payload = {
                "propertyId": self._property_id,
                "agentId": int(self.query_agent_id),
                "arrivalDate": arrival,
                "departureDate": departure,
                "adults": adults,
                "children": children,
                "infants": 0,
                "categoryId": category_id,
<<<<<<< Updated upstream
                "rateId": rate_plan_id,
=======
                "rateTypeId": rate_plan_id,  # RMS uses rateTypeId for pricing (not rateId!)
>>>>>>> Stashed changes
                "status": "Confirmed",
                "source": "API",
                "areaId": area_id,
                "nights": nights,
                "guestId": guest_id,
                "paymentMethod": "PayLater",
                "sendConfirmationEmail": True,
            }
            
            if idx == 0:
                print(f"Creating reservation:")
                print(f"   Property: {self._property_id}")
                print(f"   Agent: {self.query_agent_id}")
                print(f"   Category: {category_id}")
                print(f"   Rate: {rate_plan_id}")
                print(f"   Area/Room: {area_id}")
                print(f"   Dates: {arrival} to {departure} ({nights} nights)")
                print(f"   Guest ID: {guest_id}")
                print(f"   Guests: {adults} adults, {children} children")
            
            try:
                reservation = await client.create_reservation(payload)
                
                # Extract reservation details
                reservation_id = reservation.get('id') or reservation.get('reservationId')
                confirmation_number = reservation.get('confirmationNumber') or reservation.get('confirmationCode')
                
                print(f"✅ Reservation created successfully!")
                print(f"   ID: {reservation_id}")
                print(f"   Confirmation: {confirmation_number}")
                print(f"   Assigned Room: {area_id}")
                
                return reservation
                
            except Exception as e:
                import httpx
                last_error = e
                
                # Extract the actual error message from the response body
                error_msg = str(e)
                
                # If this is an HTTP error, try to get the actual message from the response
                if isinstance(e, httpx.HTTPStatusError):
                    try:
                        response_data = e.response.json()
                        if isinstance(response_data, dict) and 'message' in response_data:
                            error_msg = response_data['message']
                        elif isinstance(response_data, dict):
                            error_msg = str(response_data)
                    except:
                        try:
                            error_msg = e.response.text
                        except:
                            pass
                
                error_msg_lower = error_msg.lower()
                
                # Check if this is an "Area/Site Not Available" error
                # Matches: "Site '002' Is Not Available" or "Area Not Available" or "Blocking Reservation"
                is_area_blocked = (
                    ("site" in error_msg_lower and "not available" in error_msg_lower) or
                    ("area" in error_msg_lower and "not available" in error_msg_lower) or 
                    "blocking reservation" in error_msg_lower or
                    ("not available between selected dates" in error_msg_lower)
                )
                
                if is_area_blocked:
                    print(f"   ❌ Area {area_id} is blocked for these dates - trying next area")
                    print(f"      Error: {error_msg}")
                    continue
                else:
                    # For other errors, raise immediately
                    print(f"❌ Reservation creation failed with unexpected error: {error_msg}")
                    raise Exception(f"Failed to create reservation: {error_msg}")
        
        # All areas failed
        if last_error:
            print(f"❌ All {len(all_areas)} area(s) in category {category_id} are blocked for these dates")
            raise Exception(
                f"All rooms in category {category_id} are blocked for dates {arrival} to {departure}. "
                f"Please try a different category or dates."
            )
        
        raise Exception("Unexpected error: No areas were tried")
    
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
                    print(f"✅ Found existing guest: {guest_id}")
                    return guest_id
            except Exception as e:
                print(f"⚠️ Guest search failed: {e}")
        
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
            print(f"✅ Created new guest: {guest_id}")
            return guest_id
        except Exception as e:
            print(f"❌ Failed to create guest: {e}")
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