from typing import Dict, List, Optional
from .rms_api_client import rms_client
from .rms_cache import rms_cache

class RMSService:
    async def initialize(self):
        """Initialize RMS (one-time)"""
        await rms_cache.initialize()
    
    async def search_availability(
        self,
        arrival: str,
        departure: str,
        adults: int = 2,
        children: int = 0,
        room_keyword: Optional[str] = None
    ) -> Dict:
        """Search for available rooms"""
        property_id = rms_cache.get_property_id()
        agent_id = rms_cache.get_agent_id()
        
        if not property_id or not agent_id:
            raise Exception("RMS not initialized")
        
        # Get categories based on keyword
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
        
        # Get all rate IDs for these categories (on-demand)
        all_rate_ids = []
        for cat_id in category_ids:
            rates = await rms_cache.get_rates_for_category(cat_id)
            all_rate_ids.extend([rate['id'] for rate in rates])
        
        # Remove duplicates
        all_rate_ids = list(set(all_rate_ids))
        
        print(f"📊 Checking availability:")
        print(f"   Categories: {len(category_ids)}")
        print(f"   Rate plans: {len(all_rate_ids)}")
        print(f"   Dates: {arrival} to {departure}")
        print(f"   Guests: {adults} adults, {children} children")
        
        # Call rates grid API
        payload = {
            "propertyId": property_id,
            "agentId": agent_id,
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
        
        # Simplify response
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
        """Create a new reservation"""
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
            "guest": {
                "firstName": guest.get('firstName'),
                "lastName": guest.get('lastName'),
                "email": guest.get('email'),
                "phone": guest.get('phone'),
                "address": guest.get('address', {})
            }
        }
        
        reservation = await rms_client.create_reservation(payload)
        print(f"✅ Reservation created: {reservation.get('confirmationNumber')}")
        return reservation
    
    async def get_reservation(self, reservation_id: int) -> Dict:
        """Get reservation details"""
        return await rms_client.get_reservation(reservation_id)
    
    async def cancel_reservation(self, reservation_id: int) -> Dict:
        """Cancel a reservation"""
        return await rms_client.cancel_reservation(reservation_id)
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return rms_cache.get_stats()
    
    def _simplify_grid_response(self, grid_response: Dict) -> Dict:
        """Simplify grid response for voice AI"""
        available = []
        
        categories = grid_response.get('categories', [])
        for category in categories:
            for rate in category.get('rates', []):
                if rate.get('available'):
                    available.append({
                        'category_id': category['id'],
                        'category_name': category['name'],
                        'rate_plan_id': rate['id'],
                        'rate_plan_name': rate['name'],
                        'price': rate.get('price'),
                        'total_price': rate.get('totalPrice', rate.get('price')),
                        'currency': rate.get('currency', 'USD')
                    })
        
        # Sort by price (cheapest first)
        available.sort(key=lambda x: x['total_price'])
        
        return {
            'available': available,
            'message': f"Found {len(available)} available room(s)" if available else "No rooms available for selected dates"
        }

# Singleton instance
rms_service = RMSService()
