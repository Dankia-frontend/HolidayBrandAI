from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict
from services.rms import rms_service, rms_cache
from middleware.auth import verify_token

router = APIRouter(prefix="/api/rms", tags=["RMS"])

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
    guest_firstName: str
    guest_lastName: str
    guest_email: str
    guest_phone: Optional[str] = None

@router.post("/search")
async def search_availability(
    request: AvailabilityRequest,
    token: str = Depends(verify_token)
):
    """Search for available rooms"""
    try:
        results = await rms_service.search_availability(
            arrival=request.arrival,
            departure=request.departure,
            adults=request.adults,
            children=request.children,
            room_keyword=request.room_keyword
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reservations")
async def create_reservation(
    request: ReservationRequest,
    token: str = Depends(verify_token)
):
    """Create a new reservation"""
    try:
        reservation = await rms_service.create_reservation(
            category_id=request.category_id,
            rate_plan_id=request.rate_plan_id,
            arrival=request.arrival,
            departure=request.departure,
            adults=request.adults,
            children=request.children,
            guest_firstName=request.guest_firstName,
            guest_lastName=request.guest_lastName,
            guest_email=request.guest_email,
            guest_phone=request.guest_phone
        )
        return reservation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reservations/{reservation_id}")
async def get_reservation(
    reservation_id: int,
    token: str = Depends(verify_token)
):
    """Get reservation details"""
    try:
        return await rms_service.get_reservation(reservation_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/reservations/{reservation_id}")
async def cancel_reservation(
    reservation_id: int,
    token: str = Depends(verify_token)
):
    """Cancel a reservation"""
    try:
        return await rms_service.cancel_reservation(reservation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Cache endpoints removed - handled automatically by background jobs