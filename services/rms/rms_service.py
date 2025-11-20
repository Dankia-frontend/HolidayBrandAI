from typing import Dict, List, Optional
from .rms_api_client import rms_client
from .rms_cache import rms_cache
import os
import httpx
import json
import asyncio
from datetime import datetime, timedelta
from utils.ghl_api import send_to_ghl, get_contact_id, get_valid_access_token, GHL_LOCATION_ID, GHL_CLIENT_ID, GHL_CLIENT_SECRET

class RMSService:
    async def initialize(self):
        await rms_cache.initialize()
    
    async def search_availability(
        self,
        arrival: str,
        departure: str,
        adults: int = 2,
        children: int = 0,
        room_keyword: Optional[str] = None
    ) -> Dict:
        """
        Search for available rooms - EXACT WORKING LOGIC FROM ORIGINAL PREVIOUS CODE
        """
        property_id = rms_cache.get_property_id()
        agent_id = rms_cache.get_agent_id()
        
        if not property_id or not agent_id:
            raise Exception("RMS not initialized")
        
        if room_keyword:
            print(f"🔍 Searching for categories matching: '{room_keyword}'")
            categories = await rms_cache.find_categories_by_keyword(room_keyword)
            
            if not categories:
                print(f"No categories matched '{room_keyword}', searching all categories instead")
                categories = await rms_cache.get_all_categories()
        else:
            print("Searching all categories (no keyword provided)")
            categories = await rms_cache.get_all_categories()
        
        category_ids = [cat['id'] for cat in categories]
        
        all_rate_ids = []
        for cat_id in category_ids:
            rates = await rms_cache.get_rates_for_category(cat_id)
            all_rate_ids.extend([rate['id'] for rate in rates])
        
        all_rate_ids = list(set(all_rate_ids))
        
        print(f"Checking availability:")
        print(f"   Categories: {len(category_ids)}")
        print(f"   Rate plans: {len(all_rate_ids)}")
        print(f"   Dates: {arrival} to {departure}")
        print(f"   Guests: {adults} adults, {children} children")
        
        # Use query agent for availability checks (configurable via env)
        # Default is 2, which typically has full visibility in RMS systems
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
        return self._simplify_grid_response(grid_response)
    
    def _simplify_grid_response(self, grid_response: Dict) -> Dict:
        """
        EXACT simplification logic from original previous code that was working
        """
        available = []
        
        categories = grid_response.get('categories', [])
        for category in categories:
            category_id = category.get('categoryId')
            category_name = category.get('name', 'Unknown')
            
            # Use 'rates' key as in original previous code
            for rate in category.get('rates', []):
                rate_id = rate.get('rateId')
                rate_name = rate.get('name', 'Unknown')
                
                # Use 'dayBreakdown' key as in original previous code
                day_breakdown = rate.get('dayBreakdown', [])
                if not day_breakdown:
                    continue
                
                total_price = 0
                is_available = True
                
                for day in day_breakdown:
                    available_areas = day.get('availableAreas', 0)
                    
                    if available_areas <= 0:
                        is_available = False
                        break
                    
                    daily_rate = day.get('dailyRate', 0)
                    if daily_rate:
                        total_price += daily_rate
                
                if is_available and total_price > 0:
                    available.append({
                        'category_id': category_id,
                        'category_name': category_name,
                        'rate_plan_id': rate_id,
                        'rate_plan_name': rate_name,
                        'price': day_breakdown[0].get('dailyRate', 0) if day_breakdown else 0,
                        'total_price': total_price,
                        'currency': 'AUD',
                        'available_areas': day_breakdown[0].get('availableAreas', 0) if day_breakdown else 0
                    })
        
        available.sort(key=lambda x: x['total_price'])
        
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
        Create a reservation - Verifies availability and gets an available room
        """
        property_id = rms_cache.get_property_id()
        agent_id = rms_cache.get_agent_id()
        
        if not property_id or not agent_id:
            raise Exception("RMS not initialized - missing property or agent ID")
        
        # Step 1: Construct guest dictionary from flat parameters
        guest = {
            'firstName': guest_firstName,
            'lastName': guest_lastName,
            'email': guest_email,
            'phone': guest_phone
        }
        
        # Step 2: Search for existing guest or create new one
        print(f"Searching for guest: {guest.get('email')}")
        guest_id = await self.search_or_create_guest(guest)
        
        if not guest_id:
            raise Exception("Failed to find or create guest account")
        
        print(f"Using guest ID: {guest_id}")
        
        # Step 3: Calculate number of nights
        arrival_date = datetime.fromisoformat(arrival)
        departure_date = datetime.fromisoformat(departure)
        nights = (departure_date - arrival_date).days
        
        # Step 4: Verify availability using rates grid
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
        
        # Step 5: Get all areas for this category from cache
        all_areas = await rms_cache.get_all_areas_for_category(category_id)
        
        if not all_areas:
            raise Exception(f"No rooms/areas found for category {category_id}. Cannot create reservation.")
        
        print(f"Found {len(all_areas)} total area(s) in category {category_id}")
        
        # Step 6: Try to create reservation with each area until one succeeds
        last_error = None
        
        for idx, area_id in enumerate(all_areas):
            if idx > 0:
                print(f"Trying alternate area {idx + 1}/{len(all_areas)}: {area_id}")
            else:
                print(f"Trying area ID {area_id} from category {category_id}")
            
            # Create reservation payload
            payload = {
                "propertyId": property_id,
                "agentId": agent_id,
                "arrivalDate": arrival,
                "departureDate": departure,
                "adults": adults,
                "children": children,
                "infants": 0,
                "categoryId": category_id,
                "rateId": rate_plan_id,
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
                print(f"   Property: {property_id}")
                print(f"   Agent: {agent_id}")
                print(f"   Category: {category_id}")
                print(f"   Rate: {rate_plan_id}")
                print(f"   Area/Room: {area_id}")
                print(f"   Dates: {arrival} to {departure} ({nights} nights)")
                print(f"   Guest ID: {guest_id}")
                print(f"   Guests: {adults} adults, {children} children")
            
            try:
                reservation = await rms_client.create_reservation(payload)
                
                # Extract reservation details
                reservation_id = reservation.get('id') or reservation.get('reservationId')
                confirmation_number = reservation.get('confirmationNumber') or reservation.get('confirmationCode')
                
                print(f"Reservation created successfully!")
                print(f"   ID: {reservation_id}")
                print(f"   Confirmation: {confirmation_number}")
                print(f"   Assigned Room: {area_id}")
                
                return reservation
                
            except Exception as e:
                last_error = e
                
                # Extract the actual error message from the exception
                error_msg = str(e)
                
                # For HTTP errors, try to extract the message from the response
                if hasattr(e, 'response'):
                    try:
                        # Try to parse JSON response
                        error_data = e.response.json()
                        if isinstance(error_data, dict) and 'message' in error_data:
                            error_msg = error_data['message']
                            print(f"Extracted error message from response: '{error_msg}'")
                    except:
                        # If JSON parsing fails, use response text
                        try:
                            error_msg = e.response.text
                            print(f"Using response text: '{error_msg[:200]}'")
                        except:
                            pass
                
                # Convert to lowercase for case-insensitive matching
                error_msg_lower = error_msg.lower()
                
                # Check if this is an "Area Not Available" error (case-insensitive)
                # Matches: "Area 'ES03' Is Not Available" or "Area Not Available" or "Blocking Reservation" etc.
                is_area_blocked = ("area" in error_msg_lower and "not available" in error_msg_lower) or "blocking reservation" in error_msg_lower
                
                print(f"Error check - 'area' found: {'area' in error_msg_lower}, 'not available' found: {'not available' in error_msg_lower}, 'blocking' found: {'blocking reservation' in error_msg_lower}")
                print(f"Is area blocked: {is_area_blocked}")
                
                if is_area_blocked:
                    print(f"Area {area_id} is blocked for these dates - trying next area")
                    # Continue to try next area
                    continue
                else:
                    # For other errors, raise immediately
                    print(f"Reservation creation failed with unexpected error: {str(e)}")
                    raise Exception(f"Failed to create reservation: {str(e)}")
        
        # If we've tried all areas and none worked
        if last_error:
            print(f"All {len(all_areas)} area(s) in category {category_id} are blocked for these dates")
            raise Exception(
                f"All rooms in category {category_id} are blocked for dates {arrival} to {departure}. "
                f"The availability count ({available_count}) may not reflect actual bookable rooms. "
                f"Please try a different category or dates."
            )
        
        raise Exception("Unexpected error: No areas were tried")
    
    async def search_or_create_guest(self, guest_data: Dict) -> Optional[int]:
        """Search for an existing guest by email or create a new one - FROM CURRENT CODE"""
        email = guest_data.get('email')
        
        if not email:
            print("No email provided, cannot search for guest")
            return None
        
        try:
            print(f"Searching for guest with email: {email}")
            search_payload = {"email": email}
            
            results = await rms_client.search_guests(search_payload)
            
            guest_id = None
            if isinstance(results, list) and len(results) > 0:
                guest_id = results[0].get('id')
            elif isinstance(results, dict):
                items = results.get('items') or results.get('guests') or []
                if len(items) > 0:
                    guest_id = items[0].get('id')
            
            if guest_id:
                print(f"Found existing guest: {guest_id}")
                return guest_id
            
            print(f"🔧 Creating new guest account for: {email}")
            new_guest = await self._create_guest_account(guest_data)
            
            if new_guest:
                new_guest_id = new_guest.get('id') or new_guest.get('guestId')
                print(f"Created new guest: {new_guest_id}")
                return new_guest_id
            
            print(f"Failed to create guest account")
            return None
            
        except Exception as e:
            print(f"Error in search_or_create_guest: {e}")
            raise Exception(f"Guest operation failed: {str(e)}")
    
    async def _create_guest_account(self, guest_data: Dict) -> Optional[Dict]:
        """Create a new guest account in RMS - FROM CURRENT CODE"""
        property_id = rms_cache.get_property_id()
        
        if not property_id:
            raise Exception("RMS not initialized")
        
        guest_payload = {
            "propertyId": property_id,
            "guestGiven": guest_data.get('firstName', ''),
            "guestSurname": guest_data.get('lastName', ''),
            "email": guest_data.get('email', ''),
        }
        
        if guest_data.get('phone'):
            guest_payload['mobile'] = guest_data.get('phone')
        
        address = guest_data.get('address', {})
        if address:
            if address.get('address1'):
                guest_payload['address1'] = address.get('address1')
            if address.get('address2'):
                guest_payload['address2'] = address.get('address2')
            if address.get('city'):
                guest_payload['city'] = address.get('city')
            if address.get('state'):
                guest_payload['state'] = address.get('state')
            if address.get('postcode'):
                guest_payload['postcode'] = address.get('postcode')
            if address.get('country'):
                guest_payload['country'] = address.get('country')
        
        print(f"Creating guest account...")
        print(f"   Name: {guest_data.get('firstName')} {guest_data.get('lastName')}")
        print(f"   Email: {guest_data.get('email')}")
        
        try:
            guest = await rms_client.create_guest(guest_payload)
            guest_id = guest.get('id') or guest.get('guestId')
            print(f"Guest created successfully: ID {guest_id}")
            return guest
            
        except Exception as e:
            print(f"Failed to create guest: {e}")
            raise Exception(f"Guest creation failed: {str(e)}")

    async def get_reservation(self, reservation_id: int) -> Dict:
        """Get reservation details by ID"""
        return await rms_client.get_reservation(reservation_id)
    
    async def cancel_reservation(self, reservation_id: int) -> Dict:
        """Cancel a reservation by ID"""
        return await rms_client.cancel_reservation(reservation_id)
    
    def get_cache_stats(self) -> Dict:
        """Get RMS cache statistics"""
        return rms_cache.get_stats()
    
    async def fetch_reservations(
        self,
        arrival_from: Optional[str] = None,
        arrival_to: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        include_guests: bool = True,
        limit: int = 200,
        offset: int = 0,
        model_type: str = "basic",
        sort: Optional[str] = None,
        include_room_move_headers: bool = True,
        include_group_master_reservations: str = "excludeGroupMasters"
    ) -> Dict:
        """
        Fetch existing bookings from RMS via /reservations/search - FROM PREVIOUS CODE
        """
        await rms_cache.initialize()
        property_id = rms_cache.get_property_id()
        if not property_id:
            raise Exception("RMS not initialized")

        # Build request body for filters and options
        body: Dict = {
            "propertyIds": [property_id],
            "includeGuests": include_guests,
        }
        # Always use a date range, default to current month if not provided
        if not arrival_from or not arrival_to:
            today = datetime.utcnow()
            first_day = today.replace(day=1)
            next_month = first_day + timedelta(days=32)
            last_day = next_month.replace(day=1) - timedelta(days=1)
            arrival_from = arrival_from or first_day.strftime("%Y-%m-%d")
            arrival_to = arrival_to or last_day.strftime("%Y-%m-%d")
        body["arriveFrom"] = arrival_from
        body["arriveTo"] = arrival_to

        if statuses:
            body["listOfStatus"] = statuses

        # Add advanced options to body
        body["limit"] = limit
        body["offset"] = offset
        body["modelType"] = model_type
        body["includeRoomMoveHeaders"] = include_room_move_headers
        body["includeGroupMasterReservations"] = include_group_master_reservations
        if sort:
            body["sort"] = sort

        print(f"📡 RMS search reservations: body={body}")

        # Use the API client for the request
        results = await rms_client.search_reservations(body)

        # The API may return either a list or an object with items/total; normalize:
        if isinstance(results, dict):
            items = results.get("items") or results.get("reservations") or results.get("data") or []
            total = results.get("total") or len(items)
            return {"items": items, "total": total, "limit": limit, "offset": offset}
        elif isinstance(results, list):
            return {"items": results, "total": len(results), "limit": limit, "offset": offset}
        else:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

    def _extract_primary_guest(self, booking: Dict) -> Dict:
        """
        Best-effort extraction of a primary guest from various shapes - FROM PREVIOUS CODE
        """
        guests = booking.get("guests") or booking.get("guestList") or []
        if isinstance(guests, list) and guests:
            g = guests[0]
        elif isinstance(guests, dict):
            g = guests
        else:
            g = {}

        def pick(*keys):
            for k in keys:
                v = g.get(k)
                if v:
                    return v
            return None

        first = pick("firstName", "firstname", "FirstName", "First", "first_name")
        last = pick("lastName", "lastname", "LastName", "Last", "last_name")
        email = pick("email", "Email")
        phone = pick("phone", "Phone", "mobile", "Mobile")
        return {
            "firstName": first or "Guest",
            "lastName": last or "",
            "email": email,
            "phone": phone
        }

    def _booking_summary(self, booking: Dict) -> Dict:
        """
        Normalize common booking fields for opportunity naming/value - FROM PREVIOUS CODE
        """
        bid = booking.get("booking_id") or booking.get("id") or booking.get("reservationId")
        status = booking.get("booking_status") or booking.get("status") or "Unknown"
        arrival = booking.get("booking_arrival") or booking.get("arrival")
        departure = booking.get("booking_departure") or booking.get("departure")
        total = booking.get("booking_total") or booking.get("total") or booking.get("amount") or 0
        try:
            val = float(total)
        except Exception:
            val = 0.0
        return {
            "id": bid,
            "status": status,
            "arrival": arrival,
            "departure": departure,
            "value": val
        }

    def _save_ghl_payloads_by_status(self, ghl_payloads_by_status: Dict[str, list]):
        """
        Save each status list to its own JSON file for GHL payload auditing - FROM PREVIOUS CODE
        """
        for status, bookings in ghl_payloads_by_status.items():
            filename = f"rms_ghl_payload_{status}.json"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(bookings, f, indent=2, ensure_ascii=False)
                print(f"Saved {len(bookings)} bookings to {filename}")
            except Exception as e:
                print(f"Failed to save {filename}: {e}")

    async def fetch_and_sync_bookings(
        self,
        arrival_from: Optional[str] = None,
        arrival_to: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        limit: int = 200,
        offset: int = 0
    ) -> Dict:
        
        fetched = await self.fetch_reservations(arrival_from, arrival_to, statuses, True, limit, offset)
        items = fetched.get("items", [])
        synced_contacts = 0
        created_opps = 0
        errors = 0

        # Prepare dict to collect bookings by status for GHL payload tracking
        ghl_payloads_by_status = {}

        # Collect all unique guest IDs
        guest_ids = set()
        for item in items:
            guest_id = item.get("guestId")
            if guest_id:
                guest_ids.add(guest_id)

        all_guests = {}

        # Batch fetch all guest infos at once using the API client
        if guest_ids:
            try:
                payload = {
                    "ids": list(guest_ids)
                }
                results = await rms_client.search_guests(payload)
                # Only cache GHL-relevant fields
                def extract_ghl_guest(g):
                    return {
                        "id": g.get("id"),
                        "firstName": g.get("guestGiven"),
                        "lastName": g.get("guestSurname"),
                        "email": g.get("email"),
                        "phone": g.get("mobile"),
                    }
                if isinstance(results, list):
                    for guest in results:
                        gid = guest.get("id")
                        if gid:
                            all_guests[gid] = extract_ghl_guest(guest)
                elif isinstance(results, dict):
                    items_list = results.get("items") or results.get("guests") or results.get("data") or []
                    for guest in items_list:
                        gid = guest.get("id")
                        if gid:
                            all_guests[gid] = extract_ghl_guest(guest)
                print(f"Batch fetched {len(all_guests)} RMS guests")
            except Exception as e:
                print(f"Failed to batch fetch guest info: {e}")

        # Attach guest_info to each item
        for item in items:
            guest_id = item.get("guestId")
            if guest_id and guest_id in all_guests:
                item["guest_info"] = all_guests[guest_id]

   
        # using ghl_api helpers for GHL sync
        # access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
        for b in items:
            try:
                guest = b.get("guest_info") or {}
                # Ensure booking_status is present for GHL logic
                if "booking_status" not in b and "status" in b:
                    b["booking_status"] = b["status"]
                # Map RMS date fields to GHL fields if needed
                if "booking_arrival" not in b and "arrivalDate" in b:
                    b["booking_arrival"] = b["arrivalDate"]
                if "booking_departure" not in b and "departureDate" in b:
                    b["booking_departure"] = b["departureDate"]

                # if firstName is missing or empty then skip
                if not guest.get("firstName"):
                    continue

                # Track by status for reporting
                status_key = b.get("booking_status", "unknown").lower()
                if status_key not in ghl_payloads_by_status:
                    ghl_payloads_by_status[status_key] = []
                # Save a copy of the guest info and dates as sent to GHL
                ghl_payloads_by_status[status_key].append({
                    "guest_info": {
                        "firstName": guest.get("firstName"),
                        "lastName": guest.get("lastName"),
                        "email": guest.get("email"),
                        "phone": guest.get("phone"),
                        "status": b.get("booking_status"),
                        "booking_arrival": b.get("booking_arrival"),
                        "booking_departure": b.get("booking_departure")
                    }
                })

                # contact_id = get_contact_id(
                #     access_token,
                #     GHL_LOCATION_ID,
                #     guest.get("firstName"),
                #     guest.get("lastName"),
                #     guest.get("email"),
                #     guest.get("phone")
                # )
                # if contact_id:
                #     synced_contacts += 1
                #     send_to_ghl(b, access_token, guest_info=guest)
                #     created_opps += 1
            except Exception as e:
                errors += 1
                print(f"Sync failed for booking: {e}")

        # Save each status list to its own JSON file (now via helper)
        self._save_ghl_payloads_by_status(ghl_payloads_by_status)

        return {
            "fetched": len(items),
            "contacts_upserted": synced_contacts,
            "opportunities_created": created_opps,
            "errors": errors,
            "limit": fetched.get("limit"),
            "offset": fetched.get("offset"),
            "total": fetched.get("total")
        }

rms_service = RMSService()