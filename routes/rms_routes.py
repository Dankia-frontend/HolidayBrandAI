from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from services.rms import rms_service, rms_cache
from middleware.auth import verify_token
from utils.rms_db import get_rms_instance

router = APIRouter(prefix="/api/rms", tags=["RMS"])

@router.get("/search")
async def search_availability(
    arrival: str = Query(..., description="Arrival date (YYYY-MM-DD)"),
    departure: str = Query(..., description="Departure date (YYYY-MM-DD)"),
    adults: int = Query(2, description="Number of adults"),
    children: int = Query(0, description="Number of children"),
    room_keyword: Optional[str] = Query(None, description="Optional room keyword to filter by"),
    token: str = Depends(verify_token)
):
    """Search for available rooms"""
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
    children: int = Query(..., description="Number of children"),
    guest_firstName: str = Query(..., description="Guest first name"),
    guest_lastName: str = Query(..., description="Guest last name"),
    guest_email: str = Query(..., description="Guest email"),
    guest_phone: Optional[str] = Query(None, description="Guest phone number"),
    token: str = Depends(verify_token)
):
    """Create a new reservation"""
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