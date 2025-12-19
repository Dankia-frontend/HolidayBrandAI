from fastapi import APIRouter, HTTPException, Depends, Query, Header, Body
from typing import Optional
from services.rms.rms_service import RMSService
from auth.auth import authenticate_request
from utils.rms_db import get_rms_instance
from pydantic import BaseModel

router = APIRouter(prefix="/api/rms", tags=["RMS"])


# Pydantic models for booking log CRUD operations
class RMSBookingLogCreate(BaseModel):
    location_id: str
    park_name: str
    guest_firstName: str
    guest_lastName: str
    guest_email: str
    guest_phone: Optional[str] = None
    arrival_date: str
    departure_date: str
    adults: Optional[int] = None
    children: Optional[int] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    amount: Optional[float] = None
    booking_id: Optional[str] = None
    status: Optional[str] = None

class RMSBookingLogUpdate(BaseModel):
    location_id: Optional[str] = None
    park_name: Optional[str] = None
    guest_firstName: Optional[str] = None
    guest_lastName: Optional[str] = None
    guest_email: Optional[str] = None
    guest_phone: Optional[str] = None
    arrival_date: Optional[str] = None
    departure_date: Optional[str] = None
    adults: Optional[int] = None
    children: Optional[int] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    amount: Optional[float] = None
    booking_id: Optional[str] = None
    status: Optional[str] = None



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
    children: Optional[int] = Query(None, description="Number of children"),
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
        
        # Log the booking
        from utils.rms_db import log_rms_booking
        
        # Extract reservation_id (booking_id) from response
        reservation_id = reservation.get('id') or reservation.get('reservationId')
        booking_id = str(reservation_id) if reservation_id else None
        
        # Extract status from reservation
        status = reservation.get('status') or reservation.get('reservationStatus')
        status_str = str(status) if status else None
        
        # Get park_name from credentials (may be None if not set)
        park_name = rms_credentials.get('park_name') or None
        
        # Format dates for database (ensure they're in DATETIME format)
        arrival_datetime = f"{arrival} 00:00:00" if len(arrival) == 10 else arrival
        departure_datetime = f"{departure} 00:00:00" if len(departure) == 10 else departure
        
        # Get pricing and category details
        try:
            booking_details = await rms_service.get_booking_price_and_details(
                category_id=category_id,
                rate_plan_id=rate_plan_id,
                arrival=arrival,
                departure=departure,
                adults=adults,
                children=children or 0
            )
            total_amount = booking_details.get('total_price')
            category_name = booking_details.get('category_name')
            print(f"📊 Booking details: {category_name} - ${total_amount}")
        except Exception as e:
            print(f"⚠️ Could not fetch booking details: {e}")
            total_amount = None
            category_name = None
        
        log_rms_booking(
            location_id=rms_credentials.get('location_id'),
            park_name=park_name,
            guest_firstName=guest_firstName,
            guest_lastName=guest_lastName,
            guest_email=guest_email,
            guest_phone=guest_phone or None,
            arrival_date=arrival_datetime,
            departure_date=departure_datetime,
            adults=adults,
            children=children or 0,
            category_id=str(category_id),
            category_name=category_name,
            amount=total_amount,
            booking_id=booking_id,
            status=status_str
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


@router.put("/instances/{location_id}")
async def update_rms_instance(
    location_id: str,
    park_name: Optional[str] = Query(None, description="Park name"),
    client_id: Optional[int] = Query(None, description="Client ID"),
    client_pass: Optional[str] = Query(None, description="Client password"),
    agent_id: Optional[int] = Query(None, description="Agent ID"),
    x_ai_agent_key: str = Depends(authenticate_request)
):
    """Update an RMS instance (e.g., add park_name)"""
    try:
        from utils.rms_db import update_rms_instance
        success = update_rms_instance(
            location_id=location_id,
            park_name=park_name,
            client_id=client_id,
            client_pass=client_pass,
            agent_id=agent_id
        )
        if not success:
            raise HTTPException(status_code=404, detail=f"RMS instance with location_id {location_id} not found")
        return {"message": "RMS instance updated successfully", "location_id": location_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/park-names")
def get_park_names(
    _: str = Depends(authenticate_request)
):
    """Get all unique park names from booking logs"""
    try:
        from utils.rms_db import get_all_rms_park_names
        park_names = get_all_rms_park_names()
        return {"park_names": park_names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/booking-logs")
def get_booking_logs(
    location_id: Optional[str] = Query(None, description="Filter by location_id"),
    park_name: Optional[str] = Query(None, description="Filter by park_name (exact match)"),
    month: Optional[int] = Query(None, description="Filter by month (1-12)"),
    year: Optional[int] = Query(None, description="Filter by year (e.g., 2024)"),
    _: str = Depends(authenticate_request)
):
    """Get all booking logs, optionally filtered by location_id, park_name, or month/year"""
    try:
        from utils.rms_db import get_all_rms_booking_logs
        logs = get_all_rms_booking_logs(location_id=location_id, park_name=park_name, month=month, year=year)
        return {"logs": logs, "count": len(logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/booking-logs/{log_id}")
def get_booking_log(
    log_id: int,
    _: str = Depends(authenticate_request)
):
    """Get a single booking log by ID"""
    try:
        from utils.rms_db import get_rms_booking_log
        log_entry = get_rms_booking_log(log_id)
        if not log_entry:
            raise HTTPException(status_code=404, detail=f"Booking log with id {log_id} not found")
        return log_entry
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/booking-logs")
def create_booking_log(
    log_data: RMSBookingLogCreate = Body(...),
    _: str = Depends(authenticate_request)
):
    """Manually create a new booking log entry"""
    try:
        from utils.rms_db import create_rms_booking_log
        result = create_rms_booking_log(
            location_id=log_data.location_id,
            park_name=log_data.park_name,
            guest_firstName=log_data.guest_firstName,
            guest_lastName=log_data.guest_lastName,
            guest_email=log_data.guest_email,
            guest_phone=log_data.guest_phone,
            arrival_date=log_data.arrival_date,
            departure_date=log_data.departure_date,
            adults=log_data.adults,
            children=log_data.children,
            category_id=log_data.category_id,
            category_name=log_data.category_name,
            amount=log_data.amount,
            booking_id=log_data.booking_id,
            status=log_data.status
        )
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create booking log")
        return {"message": "Booking log created successfully", "log": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/booking-logs/{log_id}")
def update_booking_log(
    log_id: int,
    log_data: RMSBookingLogUpdate = Body(...),
    _: str = Depends(authenticate_request)
):
    """Update an existing booking log entry"""
    try:
        from utils.rms_db import update_rms_booking_log
        result = update_rms_booking_log(
            log_id=log_id,
            location_id=log_data.location_id,
            park_name=log_data.park_name,
            guest_firstName=log_data.guest_firstName,
            guest_lastName=log_data.guest_lastName,
            guest_email=log_data.guest_email,
            guest_phone=log_data.guest_phone,
            arrival_date=log_data.arrival_date,
            departure_date=log_data.departure_date,
            adults=log_data.adults,
            children=log_data.children,
            category_id=log_data.category_id,
            category_name=log_data.category_name,
            amount=log_data.amount,
            booking_id=log_data.booking_id,
            status=log_data.status
        )
        if not result:
            raise HTTPException(status_code=404, detail=f"Booking log with id {log_id} not found")
        return {"message": "Booking log updated successfully", "log": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/booking-logs/{log_id}")
def delete_booking_log(
    log_id: int,
    _: str = Depends(authenticate_request)
):
    """Delete a booking log entry"""
    try:
        from utils.rms_db import delete_rms_booking_log
        success = delete_rms_booking_log(log_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Booking log with id {log_id} not found")
        return {"message": f"Booking log {log_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))