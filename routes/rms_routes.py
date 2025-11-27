<<<<<<< Updated upstream
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict
from services.rms import rms_service, rms_cache
=======
from fastapi import APIRouter, HTTPException, Depends, Query, Header
from typing import Optional
from services.rms.rms_service import RMSService
>>>>>>> Stashed changes
from middleware.auth import verify_token
from utils.rms_db import get_rms_instance

router = APIRouter(prefix="/api/rms", tags=["RMS"])

<<<<<<< Updated upstream
# Request models
class AvailabilityRequest(BaseModel):
    arrival: str
    departure: str
    adults: int = 2
    children: int = 0
    room_keyword: Optional[str] = None

class ReservationRequest(BaseModel):
    category_id: int
    rate_plan_id: int
    arrival: str
    departure: str
    adults: int
    children: int
    guest: Dict

@router.post("/search")
async def search_availability(
    request: AvailabilityRequest,
    token: str = Depends(verify_token)
=======

async def get_rms_credentials(location_id: str = Header(..., description="RMS Location ID")):
    """
    Dependency to fetch RMS credentials from database based on location_id header.
    Returns the RMS instance dict with decrypted credentials.
    """
    print(f"📥 Received location_id header: {location_id}")
    
    instance = get_rms_instance(location_id)
    if not instance:
        raise HTTPException(
            status_code=404, 
            detail=f"RMS instance not found for location_id: {location_id}"
        )
    
    # Validate required fields
    if not instance.get('client_id'):
        raise HTTPException(
            status_code=400,
            detail=f"client_id not configured for location_id: {location_id}"
        )
    if not instance.get('client_pass'):
        raise HTTPException(
            status_code=400,
            detail=f"client_pass not configured or decryption failed for location_id: {location_id}"
        )
    if not instance.get('agent_id'):
        raise HTTPException(
            status_code=400,
            detail=f"agent_id not configured for location_id: {location_id}"
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
    token: str = Depends(verify_token),
    rms_credentials: dict = Depends(get_rms_credentials)
>>>>>>> Stashed changes
):
    """Search for available rooms"""
    try:
        # Create a new RMSService instance with the credentials from the header
        rms_service = RMSService(rms_credentials)
        
        # Initialize the service (fetches property, areas, etc.)
        await rms_service.initialize()
        
        results = await rms_service.search_availability(
            arrival=request.arrival,
            departure=request.departure,
            adults=request.adults,
            children=request.children,
            room_keyword=request.room_keyword
        )
        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reservations")
async def create_reservation(
<<<<<<< Updated upstream
    request: ReservationRequest,
    token: str = Depends(verify_token)
=======
    category_id: int = Query(..., description="Category ID"),
    rate_plan_id: int = Query(..., description="Rate plan ID"),
    arrival: str = Query(..., description="Arrival date (YYYY-MM-DD)"),
    departure: str = Query(..., description="Departure date (YYYY-MM-DD)"),
    adults: int = Query(..., description="Number of adults"),
    children: int = Query(..., description="Number of children"),
    guest_firstName: str = Query(..., description="Guest first name"),
    guest_lastName: str = Query(..., description="Guest last name"),
    guest_email: str = Query(..., description="Guest email"),
    guest_phone: Optional[str] = Query(None, description="Guest phone number"),
    token: str = Depends(verify_token),
    rms_credentials: dict = Depends(get_rms_credentials)
>>>>>>> Stashed changes
):
    """Create a new reservation"""
    try:
        # Create a new RMSService instance with the credentials from the header
        rms_service = RMSService(rms_credentials)
        
        # Initialize the service
        await rms_service.initialize()
        
        reservation = await rms_service.create_reservation(
            category_id=request.category_id,
            rate_plan_id=request.rate_plan_id,
            arrival=request.arrival,
            departure=request.departure,
            adults=request.adults,
            children=request.children,
            guest=request.guest
        )
        return reservation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reservations/{reservation_id}")
async def get_reservation(
    reservation_id: int,
    token: str = Depends(verify_token),
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
    token: str = Depends(verify_token),
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