from fastapi import APIRouter, HTTPException, Depends, Query, Header, Body
from typing import Optional, List
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


class RMSGuestMembership(BaseModel):
    guestId: int
    id: int
    inactive: bool
    level: Optional[int] = None
    membershipTypeId: Optional[int] = None
    membershipTypeName: Optional[str] = None
    number: str


class RMSMembershipVerifyResponse(BaseModel):
    guestId: Optional[int] = None
    membershipNumber: str
    program: Optional[str] = None
    is_valid: bool
    memberships: List[RMSGuestMembership]


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


@router.get("/booking-sources")
async def list_booking_sources(
    x_ai_agent_key: str = Depends(authenticate_request),
    rms_credentials: dict = Depends(get_rms_credentials),
):
    try:
        rms_service = RMSService(rms_credentials)
        await rms_service.initialize()
        return await rms_service.fetch_booking_sources()
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
    guest_town: Optional[str] = Query(None, description="Optional guest town/suburb"),
    guest_state: Optional[str] = Query(None, description="Optional guest state/region"),
    guest_postCode: Optional[str] = Query(None, description="Optional guest post code"),
    guest_membership_id: Optional[int] = Query(None, description="Optional RMS guest membership id from /memberships/verify to apply member discount"),
    booking_source_id: Optional[int] = Query(None, description="Optional override; otherwise ParkPA (or RMS_DEFAULT_BOOKING_SOURCE_NAME) is resolved automatically at init"),
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
    print(f"   Town/State/PostCode: {guest_town or '-'} / {guest_state or '-'} / {guest_postCode or '-'}")
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
            guest_phone=guest_phone,
            guest_town=guest_town,
            guest_state=guest_state,
            guest_postCode=guest_postCode,
            guest_membership_id=guest_membership_id,
            booking_source_id=booking_source_id,
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


MAX_GROUP_BOOKINGS = 5


@router.post("/reservations/group")
async def create_reservation_group(
    booking_count: int = Query(..., ge=1, le=MAX_GROUP_BOOKINGS, description="Number of bookings in the group (1–5)"),
    booking_source_id: Optional[int] = Query(None, description="Optional override; otherwise ParkPA (or RMS_DEFAULT_BOOKING_SOURCE_NAME) is resolved automatically at init"),
    guest_firstName: str = Query(..., description="Guest first name (shared for all bookings)"),
    guest_lastName: str = Query(..., description="Guest last name (shared for all bookings)"),
    guest_email: str = Query(..., description="Guest email (shared for all bookings)"),
    guest_phone: Optional[str] = Query(None, description="Guest phone number (shared for all bookings)"),
    guest_membership_id: Optional[int] = Query(None, description="Optional RMS guest membership id from /memberships/verify (shared for all bookings)"),
    category_id_1: int = Query(..., description="Category ID (booking 1)"),
    rate_plan_id_1: int = Query(..., description="Rate plan ID (booking 1)"),
    arrival_1: str = Query(..., description="Arrival date (YYYY-MM-DD) (booking 1)"),
    departure_1: str = Query(..., description="Departure date (YYYY-MM-DD) (booking 1)"),
    adults_1: int = Query(..., description="Number of adults (booking 1)"),
    children_1: Optional[int] = Query(None, description="Number of children (booking 1)"),
    category_id_2: Optional[int] = Query(None, description="Category ID (booking 2)"),
    rate_plan_id_2: Optional[int] = Query(None, description="Rate plan ID (booking 2)"),
    arrival_2: Optional[str] = Query(None, description="Arrival date (YYYY-MM-DD) (booking 2)"),
    departure_2: Optional[str] = Query(None, description="Departure date (YYYY-MM-DD) (booking 2)"),
    adults_2: Optional[int] = Query(None, description="Number of adults (booking 2)"),
    children_2: Optional[int] = Query(None, description="Number of children (booking 2)"),
    category_id_3: Optional[int] = Query(None, description="Category ID (booking 3)"),
    rate_plan_id_3: Optional[int] = Query(None, description="Rate plan ID (booking 3)"),
    arrival_3: Optional[str] = Query(None, description="Arrival date (YYYY-MM-DD) (booking 3)"),
    departure_3: Optional[str] = Query(None, description="Departure date (YYYY-MM-DD) (booking 3)"),
    adults_3: Optional[int] = Query(None, description="Number of adults (booking 3)"),
    children_3: Optional[int] = Query(None, description="Number of children (booking 3)"),
    category_id_4: Optional[int] = Query(None, description="Category ID (booking 4)"),
    rate_plan_id_4: Optional[int] = Query(None, description="Rate plan ID (booking 4)"),
    arrival_4: Optional[str] = Query(None, description="Arrival date (YYYY-MM-DD) (booking 4)"),
    departure_4: Optional[str] = Query(None, description="Departure date (YYYY-MM-DD) (booking 4)"),
    adults_4: Optional[int] = Query(None, description="Number of adults (booking 4)"),
    children_4: Optional[int] = Query(None, description="Number of children (booking 4)"),
    category_id_5: Optional[int] = Query(None, description="Category ID (booking 5)"),
    rate_plan_id_5: Optional[int] = Query(None, description="Rate plan ID (booking 5)"),
    arrival_5: Optional[str] = Query(None, description="Arrival date (YYYY-MM-DD) (booking 5)"),
    departure_5: Optional[str] = Query(None, description="Departure date (YYYY-MM-DD) (booking 5)"),
    adults_5: Optional[int] = Query(None, description="Number of adults (booking 5)"),
    children_5: Optional[int] = Query(None, description="Number of children (booking 5)"),
    x_ai_agent_key: str = Depends(authenticate_request),
    rms_credentials: dict = Depends(get_rms_credentials)
):
    """
    Create multiple reservations in a single group (Add Reservation Group).
    Booking-specific fields use _1.._5 suffixes (category/rate/date/pax).
    Guest fields are shared once for all bookings: guest_firstName, guest_lastName,
    guest_email, guest_phone, guest_membership_id.
    """
    n = booking_count
    if n > MAX_GROUP_BOOKINGS:
        raise HTTPException(status_code=400, detail=f"booking_count must be 1–{MAX_GROUP_BOOKINGS}")
    keys = ["category_id", "rate_plan_id", "arrival", "departure", "adults", "children"]
    loc = locals()
    bookings = []
    for i in range(1, n + 1):
        b = {}
        for k in keys:
            key = f"{k}_{i}"
            val = loc.get(key)
            if k == "children":
                if val is None:
                    b[k] = None
                else:
                    b[k] = val
            else:
                if val is None or (isinstance(val, str) and not val.strip()):
                    raise HTTPException(status_code=400, detail=f"Missing or empty required field for booking {i}: {k}")
                b[k] = val
        # Apply shared guest details to each booking
        b["guest_firstName"] = guest_firstName
        b["guest_lastName"] = guest_lastName
        b["guest_email"] = guest_email
        b["guest_phone"] = guest_phone if guest_phone and guest_phone.strip() else None
        b["guest_membership_id"] = guest_membership_id
        bookings.append(b)

    print(f"\n{'='*80}")
    print(f"📥 CREATE GROUP RESERVATION REQUEST ({n} booking(s))")
    print(f"{'='*80}")
    print(f"Location: {rms_credentials.get('location_id')}")
    for i, b in enumerate(bookings, 1):
        print(f"   {i}. {b['guest_firstName']} {b['guest_lastName']} | {b['arrival']}–{b['departure']} | cat={b['category_id']} rate={b['rate_plan_id']}")
    print(f"{'='*80}\n")

    try:
        rms_service = RMSService(rms_credentials)
        await rms_service.initialize()

        result = await rms_service.create_reservation_group(bookings, booking_source_id=booking_source_id)

        # Log each reservation to booking log when possible
        from utils.rms_db import log_rms_booking
        park_name = rms_credentials.get("park_name") or None
        reservations_list = result if isinstance(result, list) else (result.get("reservations") or result.get("reservationIds") or [])
        if isinstance(reservations_list, list) and reservations_list and bookings:
            for idx, res in enumerate(reservations_list):
                if idx >= len(bookings):
                    break
                b = bookings[idx]
                reservation_id = res.get("id") or res.get("reservationId") if isinstance(res, dict) else res
                booking_id = str(reservation_id) if reservation_id else None
                status = res.get("status") or res.get("reservationStatus") if isinstance(res, dict) else None
                status_str = str(status) if status else None
                arrival_dt = f"{b['arrival']} 00:00:00" if len(b['arrival']) == 10 else b['arrival']
                departure_dt = f"{b['departure']} 00:00:00" if len(b['departure']) == 10 else b['departure']
                try:
                    details = await rms_service.get_booking_price_and_details(
                        category_id=b["category_id"],
                        rate_plan_id=b["rate_plan_id"],
                        arrival=b["arrival"],
                        departure=b["departure"],
                        adults=b["adults"],
                        children=b.get("children") or 0,
                    )
                    total_amount = details.get("total_price")
                    category_name = details.get("category_name")
                except Exception:
                    total_amount = None
                    category_name = None
                log_rms_booking(
                    location_id=rms_credentials.get("location_id"),
                    park_name=park_name,
                    guest_firstName=b["guest_firstName"],
                    guest_lastName=b["guest_lastName"],
                    guest_email=b["guest_email"],
                    guest_phone=b.get("guest_phone") or None,
                    arrival_date=arrival_dt,
                    departure_date=departure_dt,
                    adults=b["adults"],
                    children=b.get("children") or 0,
                    category_id=str(b["category_id"]),
                    category_name=category_name,
                    amount=total_amount,
                    booking_id=booking_id,
                    status=status_str,
                )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reservations")
async def get_reservation(
    reservation_id: int = Query(..., description="Reservation ID to retrieve"),
    x_ai_agent_key: str = Depends(authenticate_request),
    rms_credentials: dict = Depends(get_rms_credentials)
):
    """Get reservation details by ID - for Voice AI compatibility"""
    print(f"\n{'='*80}")
    print(f"🔍 GET RESERVATION REQUEST")
    print(f"{'='*80}")
    print(f"Reservation ID: {reservation_id} (type: {type(reservation_id).__name__})")
    print(f"Location: {rms_credentials.get('location_id')}")
    print(f"{'='*80}\n")
    
    try:
        # Create a new RMSService instance with the credentials from the header
        rms_service = RMSService(rms_credentials)
        await rms_service.initialize()
        
        reservation = await rms_service.get_reservation(reservation_id)
        
        # Enrich with category_name for Voice AI
        category_id = reservation.get('categoryId')
        if category_id and hasattr(rms_service, '_categories_cache'):
            category = rms_service._categories_cache.get(category_id, {})
            category_name = category.get('name', 'Unknown')
            reservation['category_name'] = category_name
            print(f"   📋 Added category_name: {category_name}")
        
        # Log key details for debugging
        print(f"✅ Reservation found:")
        print(f"   Status: {reservation.get('status')}")
        print(f"   Category: {reservation.get('category_name', 'N/A')}")
        print(f"   Arrival: {reservation.get('arrivalDate')}")
        print(f"   Departure: {reservation.get('departureDate')}")
        print(f"   Adults: {reservation.get('adults')}, Children: {reservation.get('children')}")
        print()
        
        return reservation
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving reservation: {e}")
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


@router.get(
    "/memberships/verify",
    response_model=RMSMembershipVerifyResponse,
    summary="Verify a guest membership number (e.g. G'Day / BIG4)"
)
async def verify_membership(
    membership_number: str = Query(..., description="The membership number to verify"),
    guest_email: str = Query(..., description="Guest email (used to find the guest in RMS; no guest_id needed)"),
    program: Optional[str] = Query(None, description="Optional program filter: 'gday' or 'big4'"),
    x_ai_agent_key: str = Depends(authenticate_request),
    rms_credentials: dict = Depends(get_rms_credentials)
):
    """
    Verify that a given membership number exists and is active for the guest identified by email.

    Uses the same headers as other RMS APIs (X-Location-ID, x-ai-agent-key). Looks up the guest
    in RMS by email, then checks their memberships."""
    try:
        rms_service = RMSService(rms_credentials)
        result = await rms_service.verify_membership_by_email(
            guest_email=guest_email,
            membership_number=membership_number,
            program=program,
        )
        # Cast raw dict into the response model so Swagger shows the exact shape
        return RMSMembershipVerifyResponse(
            guestId=result.get("guestId"),
            membershipNumber=result["membershipNumber"],
            program=result.get("program"),
            is_valid=result["is_valid"],
            memberships=[RMSGuestMembership(**m) for m in result["memberships"]],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/guests/{guest_id}/memberships", response_model=List[RMSGuestMembership])
async def get_guest_memberships(
    guest_id: int,
    x_ai_agent_key: str = Depends(authenticate_request),
    rms_credentials: dict = Depends(get_rms_credentials)
):
    """
    Get RMS memberships (e.g. G'Day / BIG4) for a guest by RMS guest ID.
    Proxies the RMS endpoint GET /guests/{id}/memberships.
    """
    try:
        rms_service = RMSService(rms_credentials)
        memberships = await rms_service.get_guest_memberships(guest_id)
        return memberships
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