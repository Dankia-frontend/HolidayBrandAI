from typing import Dict, List, Optional
from .rms_api_client import rms_client
from .rms_cache import rms_cache
import os
import httpx
from datetime import datetime

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
        property_id = rms_cache.get_property_id()
        agent_id = rms_cache.get_agent_id()
        
        if not property_id or not agent_id:
            raise Exception("RMS not initialized")
        
        if room_keyword:
            print(f"🔍 Searching for categories matching: '{room_keyword}'")
            categories = await rms_cache.find_categories_by_keyword(room_keyword)
            
            if not categories:
                print(f"⚠️ No categories matched '{room_keyword}', searching all categories instead")
                categories = await rms_cache.get_all_categories()
        else:
            print("🔍 Searching all categories (no keyword provided)")
            categories = await rms_cache.get_all_categories()
        
        category_ids = [cat['id'] for cat in categories]
        
        all_rate_ids = []
        for cat_id in category_ids:
            rates = await rms_cache.get_rates_for_category(cat_id)
            all_rate_ids.extend([rate['id'] for rate in rates])
        
        all_rate_ids = list(set(all_rate_ids))
        
        print(f"📊 Checking availability:")
        print(f"   Categories: {len(category_ids)}")
        print(f"   Rate plans: {len(all_rate_ids)}")
        print(f"   Dates: {arrival} to {departure}")
        print(f"   Guests: {adults} adults, {children} children")
        
        payload = {
            "propertyId": property_id,
            "agentId": 2,
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
        property_id = rms_cache.get_property_id()
        agent_id = rms_cache.get_agent_id()
        
        payload = {
            "propertyId": property_id,
            "agentId": agent_id,
            "categoryId": category_id,
            "ratePlanId": rate_plan_id,
            "arrival": arrival,
            "departure": departure,
            "adults": adults,
            "children": children,
            "status": "Confirmed",  # Add reservation status
            "source": "API",  # Add source
            "guest": {
                "firstName": guest.get('firstName'),
                "lastName": guest.get('lastName'),
                "email": guest.get('email'),
                "phone": guest.get('phone'),
                "address": guest.get('address', {})
            },
            "payment": {  # Add payment object even if empty
                "method": "PayLater"
            }
        }
        
        print(f"📤 Payload being sent: {payload}")
        
        reservation = await rms_client.create_reservation(payload)
        print(f"✅ Reservation created: {reservation.get('confirmationNumber')}")
        return reservation
    
    async def get_reservation(self, reservation_id: int) -> Dict:
        return await rms_client.get_reservation(reservation_id)
    
    async def cancel_reservation(self, reservation_id: int) -> Dict:
        return await rms_client.cancel_reservation(reservation_id)
    
    def get_cache_stats(self) -> Dict:
        return rms_cache.get_stats()
    
    def _simplify_grid_response(self, grid_response: Dict) -> Dict:
        available = []
        
        categories = grid_response.get('categories', [])
        for category in categories:
            category_id = category.get('categoryId')
            category_name = category.get('name', 'Unknown')
            
            for rate in category.get('rates', []):
                rate_id = rate.get('rateId')
                rate_name = rate.get('name', 'Unknown')
                
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
    
    async def fetch_reservations(
        self,
        arrival_from: Optional[str] = None,
        arrival_to: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        include_guests: bool = True,
        limit: int = 200,
        offset: int = 0
    ) -> Dict:
        """
        Fetch existing bookings from RMS via /reservations/search.
        Mirrors the Newbook 'fetch bookings' step, but calls RMS.
        """
        await rms_cache.initialize()
        property_id = rms_cache.get_property_id()
        if not property_id:
            raise Exception("RMS not initialized")

        payload: Dict = {
            "propertyId": property_id,
            "includeGuests": include_guests,
            "limit": limit,
            "offset": offset
        }
        if arrival_from:
            payload["arrivalFrom"] = arrival_from  # ISO date YYYY-MM-DD
        if arrival_to:
            payload["arrivalTo"] = arrival_to      # ISO date YYYY-MM-DD
        if statuses:
            payload["status"] = statuses           # e.g., ["Confirmed", "Arrived"]

        print(f"📡 RMS search reservations: {payload}")
        results = await rms_client.search_reservations(payload)
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
        Best-effort extraction of a primary guest from various shapes.
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
        Normalize common booking fields for opportunity naming/value.
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

    async def _ghl_upsert_contact(self, client: httpx.AsyncClient, guest: Dict) -> Optional[str]:
        api_key = os.getenv("GHL_API_KEY")
        location_id = os.getenv("GHL_LOCATION_ID")
        if not api_key or not location_id:
            print("⚠️ Missing GHL_API_KEY or GHL_LOCATION_ID; skipping contact upsert")
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
        payload = {
            "firstName": guest.get("firstName") or "Guest",
            "lastName": guest.get("lastName") or "",
            "email": guest.get("email"),
            "phone": guest.get("phone"),
            "source": "RMS",
            "locationId": location_id
        }
        # Remove empty keys to avoid API complaints
        clean_payload = {k: v for k, v in payload.items() if v}
        r = await client.post(f"{os.getenv('GHL_API_BASE', 'https://services.leadconnectorhq.com')}/contacts/upsert",
                              headers=headers, json=clean_payload, timeout=30.0)
        print(f"📥 GHL upsert contact: {r.status_code}")
        r.raise_for_status()
        data = r.json()
        contact = data.get("contact") or data.get("data") or data
        return contact.get("id")

    async def _ghl_create_opportunity(
        self,
        client: httpx.AsyncClient,
        contact_id: str,
        booking_info: Dict
    ) -> Optional[str]:
        api_key = os.getenv("GHL_API_KEY")
        location_id = os.getenv("GHL_LOCATION_ID")
        pipeline_id = os.getenv("GHL_PIPELINE_ID")
        stage_id = os.getenv("GHL_STAGE_ID")
        if not all([api_key, location_id, pipeline_id, stage_id, contact_id]):
            print("⚠️ Missing GHL config; skipping opportunity create")
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
        name = f"RMS Booking {booking_info['id']}" if booking_info.get("id") else "RMS Booking"
        payload = {
            "name": name,
            "pipelineId": pipeline_id,
            "pipelineStageId": stage_id,
            "locationId": location_id,
            "contactId": contact_id,
            "status": "open",
            "monetaryValue": booking_info.get("value") or 0,
            "source": "RMS",
            "notes": self._format_booking_note(booking_info)
        }
        r = await client.post(f"{os.getenv('GHL_API_BASE', 'https://services.leadconnectorhq.com')}/opportunities/",
                              headers=headers, json=payload, timeout=30.0)
        print(f"📥 GHL create opportunity: {r.status_code}")
        r.raise_for_status()
        data = r.json()
        opp = data.get("opportunity") or data.get("data") or data
        return opp.get("id")

    def _format_booking_note(self, booking_info: Dict) -> str:
        a = booking_info.get("arrival")
        d = booking_info.get("departure")
        try:
            a_str = datetime.fromisoformat(a.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M") if a else str(a)
        except Exception:
            a_str = str(a)
        try:
            d_str = datetime.fromisoformat(d.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M") if d else str(d)
        except Exception:
            d_str = str(d)
        return f"Status: {booking_info.get('status')}\nArrival: {a_str}\nDeparture: {d_str}"

    async def fetch_and_sync_bookings(
        self,
        arrival_from: Optional[str] = None,
        arrival_to: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        limit: int = 200,
        offset: int = 0
    ) -> Dict:
        """
        End-to-end job:
        1) Fetch bookings from RMS
        2) Upsert contacts and create opportunities in GHL
        """
        fetched = await self.fetch_reservations(arrival_from, arrival_to, statuses, True, limit, offset)
        items = fetched.get("items", [])
        synced_contacts = 0
        created_opps = 0
        errors = 0

        async with httpx.AsyncClient() as client:
            for b in items:
                try:
                    guest = self._extract_primary_guest(b)
                    booking_info = self._booking_summary(b)
                    contact_id = await self._ghl_upsert_contact(client, guest)
                    if contact_id:
                        synced_contacts += 1
                        opp_id = await self._ghl_create_opportunity(client, contact_id, booking_info)
                        if opp_id:
                            created_opps += 1
                except Exception as e:
                    errors += 1
                    print(f"❌ Sync failed for booking: {e}")

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
