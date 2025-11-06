from typing import Dict, List, Optional
from .rms_api_client import rms_client
from .rms_cache import rms_cache

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

rms_service = RMSService()
