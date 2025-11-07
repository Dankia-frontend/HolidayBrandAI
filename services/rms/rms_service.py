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
        offset: int = 0,
        model_type: str = "basic",
        sort: Optional[str] = None,
        include_room_move_headers: bool = True,
        include_group_master_reservations: str = "excludeGroupMasters"
    ) -> Dict:
        """
        Fetch existing bookings from RMS via /reservations/search.
        Mirrors the Newbook 'fetch bookings' step, but calls RMS.
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

        # Collect all unique account IDs
        account_ids = set()
        for item in items:
            account_id = item.get("accountId")
            if account_id:
                account_ids.add(account_id)

        all_accounts = {}

        # Batch fetch all account infos at once
        if account_ids:
            try:
                payload = {
                    "accountClass": "Guest",
                    "ids": list(account_ids)
                }
                results = await rms_client._make_request("POST", "/accounts/search", json=payload)
                # Normalize results to a dict keyed by accountId
                if isinstance(results, list):
                    for acc in results:
                        acc_id = acc.get("id") or acc.get("accountId")
                        if acc_id:
                            all_accounts[acc_id] = acc
                elif isinstance(results, dict):
                    items_list = results.get("items") or results.get("accounts") or results.get("data") or []
                    for acc in items_list:
                        acc_id = acc.get("id") or acc.get("accountId")
                        if acc_id:
                            all_accounts[acc_id] = acc
                print(f"✅ Batch fetched {len(all_accounts)} RMS accounts")
            except Exception as e:
                print(f"⚠️ Failed to batch fetch account info: {e}")

        # Attach account_info to each item
        for item in items:
            account_id = item.get("accountId")
            if account_id and account_id in all_accounts:
                item["account_info"] = all_accounts[account_id]

        # Save all accounts info to a JSON file
        try:
            with open("rms_accounts_cache.json", "w", encoding="utf-8") as f:
                json.dump(all_accounts, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved {len(all_accounts)} RMS accounts to rms_accounts_cache.json")
        except Exception as e:
            print(f"⚠️ Failed to save RMS accounts cache: {e}")

        # Use your ghl_api helpers for GHL sync
        # access_token = get_valid_access_token(GHL_CLIENT_ID, GHL_CLIENT_SECRET)
        # for b in items:
        #     try:
        #         # Prepare guest info
        #         guest = self._extract_primary_guest(b)
        #         if "account_info" in b:
        #             guest.update({
        #                 "firstName": b["account_info"].get("firstName") or guest.get("firstName"),
        #                 "lastName": b["account_info"].get("lastName") or guest.get("lastName"),
        #                 "email": b["account_info"].get("email") or guest.get("email"),
        #                 "phone": b["account_info"].get("phone") or guest.get("phone"),
        #             })
        #         # Use your GHL API helper to get/create contact
        #         contact_id = get_contact_id(
        #             access_token,
        #             GHL_LOCATION_ID,
        #             guest.get("firstName"),
        #             guest.get("lastName"),
        #             guest.get("email"),
        #             guest.get("phone")
        #         )
        #         if contact_id:
        #             synced_contacts += 1
        #             # Use your GHL API helper to send opportunity
        #             send_to_ghl(b, access_token)
        #             created_opps += 1
        #     except Exception as e:
        #         errors += 1
        #         print(f"❌ Sync failed for booking: {e}")

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
