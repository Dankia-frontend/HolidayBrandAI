from fastapi import APIRouter, HTTPException, Depends, Query, Header
from typing import Optional
from services.rms.rms_service import RMSService
from middleware.auth import authenticate_request
from utils.rms_db import get_rms_instance

router = APIRouter(prefix="/api/rms", tags=["RMS"])


async def get_rms_credentials(x_location_id: str = Header(..., alias="X-Location-ID")):
    """
    Dependency to fetch RMS credentials from database based on location_id header.
    Returns the RMS instance dict with decrypted credentials.
    
    Note: Uses X-Location-ID header (matching Newbook pattern) for consistency
    """
    print(f"📥 Received X-Location-ID header: {x_location_id}")
    
    instance = get_rms_instance(x_location_id)
    if not instance:
        raise HTTPException(
            status_code=404, 
            detail=f"RMS instance not found for location_id: {x_location_id}"
        )
    
    # Validate required fields
    if not instance.get('client_id'):
        raise HTTPException(
            status_code=400,
            detail=f"client_id not configured for location_id: {x_location_id}"
        )
    if not instance.get('client_pass'):
        raise HTTPException(
            status_code=400,
            detail=f"client_pass not configured or decryption failed for location_id: {x_location_id}"
        )
    if not instance.get('agent_id'):
        raise HTTPException(
            status_code=400,
            detail=f"agent_id not configured for location_id: {x_location_id}"
        )
    
    print(f"✅ RMS credentials loaded: client_id={instance.get('client_id')}, agent_id={instance.get('agent_id')}")
    return instance


@router.get("/search")
async def search_availability(
    arrival: str = Query(..., description="Arrival date (YYYY-MM-DD)"),
    departure: str = Query(..., description="Departure date (YYYY-MM-DD)"),
    adults: int = Query(2, description="Number of adults"),
    children: int = Query(0, description="Number of children"),
    room_keyword: Optional[str] = Query(None, description="Optional room keyword to filter by"),
    x_ai_agent_key: str = Depends(authenticate_request),
    rms_credentials: dict = Depends(get_rms_credentials)
):
    """Search for available rooms"""
    print(f"\n{'='*80}")
    print(f"🔍 SEARCH AVAILABILITY REQUEST")
    print(f"{'='*80}")
    print(f"Location: {rms_credentials.get('location_id')}")
    print(f"Dates: {arrival} to {departure}")
    print(f"Guests: {adults} adults, {children} children")
    print(f"Keyword: {room_keyword or 'None'}")
    print(f"{'='*80}\n")
    
    try:
        # Create a new RMSService instance with the credentials from the header
        rms_service = RMSService(rms_credentials)
        
        # Initialize the service (fetches property, areas, etc.)
        await rms_service.initialize()
        
        results = await rms_service.search_availability(
            arrival=arrival,
            departure=departure,
            adults=adults,
            children=children,
            room_keyword=room_keyword
        )
        
        # Log summary of results
        if 'available' in results:
            print(f"\n✅ Search Results: {len(results['available'])} options found")
            for idx, option in enumerate(results['available'][:3], 1):  # Show first 3
                print(f"   {idx}. Category {option.get('category_id')} - Rate {option.get('rate_plan_id')} - ${option.get('total_price')} - {option.get('available_areas')} areas")
        else:
            print(f"\n❌ Search Results: No availability found")
        print()
        
        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reservations")
async def create_reservation(
    category_id: int = Query(..., description="Category ID"),
    rate_plan_id: int = Query(..., description="Rate plan ID"),
    arrival: str = Query(..., description="Arrival date (YYYY-MM-DD)"),
    departure: str = Query(..., description="Departure date (YYYY-MM-DD)"),
    adults: int = Query(..., description="Number of adults"),
    children: int = Query(0, description="Number of children"),
    guest_firstName: str = Query(..., description="Guest first name"),
    guest_lastName: str = Query(..., description="Guest last name"),
    guest_email: str = Query(..., description="Guest email"),
    guest_phone: Optional[str] = Query(None, description="Guest phone number"),
    x_ai_agent_key: str = Depends(authenticate_request),
    rms_credentials: dict = Depends(get_rms_credentials)
):
    """Create a new reservation"""
    # Detailed logging to diagnose Voice AI parameter issues
    print(f"\n{'='*80}")
    print(f"📥 CREATE RESERVATION REQUEST")
    print(f"{'='*80}")
    print(f"Location Info:")
    print(f"   X-Location-ID: {rms_credentials.get('location_id')}")
    print(f"   Client ID: {rms_credentials.get('client_id')}")
    print(f"   Agent ID: {rms_credentials.get('agent_id')}")
    print(f"\nReservation Parameters:")
    print(f"   category_id: {category_id} (type: {type(category_id).__name__})")
    print(f"   rate_plan_id: {rate_plan_id} (type: {type(rate_plan_id).__name__})")
    print(f"   arrival: {arrival}")
    print(f"   departure: {departure}")
    print(f"   adults: {adults}, children: {children}")
    print(f"\nGuest Info:")
    print(f"   Name: {guest_firstName} {guest_lastName}")
    print(f"   Email: {guest_email}")
    print(f"   Phone: {guest_phone}")
    print(f"{'='*80}\n")
    
    try:
        # Create a new RMSService instance with the credentials from the header
        rms_service = RMSService(rms_credentials)
        
        # Initialize the service
        await rms_service.initialize()
        
        reservation = await rms_service.create_reservation(
            category_id=category_id,
            rate_plan_id=rate_plan_id,
            arrival=arrival,
            departure=departure,
            adults=adults,
            children=children,
            guest_firstName=guest_firstName,
            guest_lastName=guest_lastName,
            guest_email=guest_email,
            guest_phone=guest_phone
        )
        return reservation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reservations/{reservation_id}")
async def get_reservation(
    reservation_id: int,
    x_ai_agent_key: str = Depends(authenticate_request),
    rms_credentials: dict = Depends(get_rms_credentials)
):
    """Get reservation details"""
    try:
        # Create a new RMSService instance with the credentials from the header
        rms_service = RMSService(rms_credentials)
        await rms_service.initialize()
        
        return await rms_service.get_reservation(reservation_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/reservations/{reservation_id}")
async def cancel_reservation(
    reservation_id: int,
    x_ai_agent_key: str = Depends(authenticate_request),
    rms_credentials: dict = Depends(get_rms_credentials)
):
    """Cancel a reservation"""
    try:
        # Create a new RMSService instance with the credentials from the header
        rms_service = RMSService(rms_credentials)
        await rms_service.initialize()
        
        return await rms_service.cancel_reservation(reservation_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))