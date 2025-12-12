from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Optional
from services.newbook.newbook_service import NewbookService
from auth.auth import authenticate_request
from auth.auth import get_newbook_credentials
from urllib.parse import unquote
from pydantic import BaseModel

router = APIRouter(prefix="/api/newbook", tags=["Newbook"])


# Pydantic models for booking log CRUD operations
class BookingLogCreate(BaseModel):
    location_id: str
    park_name: str
    guest_firstname: str
    guest_lastname: str
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

class BookingLogUpdate(BaseModel):
    location_id: Optional[str] = None
    park_name: Optional[str] = None
    guest_firstname: Optional[str] = None
    guest_lastname: Optional[str] = None
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


@router.get("/availability")
def get_availability(
    period_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    period_to: str = Query(..., description="End date in YYYY-MM-DD format"),
    adults: int = Query(..., description="Number of adults"),
    daily_mode: str = Query(..., description="Daily mode value, e.g., 'true' or 'false'"),
    Children: int = Query(..., description="Number of children"),
    _: str = Depends(authenticate_request),
    newbook_creds: dict = Depends(get_newbook_credentials)
):
    """Get availability and pricing for specified dates and guests"""
    try:
        service = NewbookService(newbook_creds)
        return service.get_availability(
            period_from=period_from,
            period_to=period_to,
            adults=adults,
            children=Children,
            daily_mode=daily_mode
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm-booking")
def confirm_booking(
    period_from: str = Query(..., description="Booking start date, e.g. 2025-10-10 00:00:00"),
    period_to: str = Query(..., description="Booking end date, e.g. 2025-10-15 23:59:59"),
    guest_firstname: str = Query(..., description="Guest first name"),
    guest_lastname: str = Query(..., description="Guest last name"),
    guest_email: str = Query(..., description="Guest email address"),
    guest_phone: str = Query(..., description="Guest phone number"),
    adults: int = Query(..., description="Number of adults"),
    children: str = Query(..., description="Number of children"),
    category_id: int = Query(..., description="Category ID of the room or package"),
    daily_mode: str = Query(..., description="Daily booking mode (yes/no)"),
    # amount: int = Query(..., description="Total booking amount"),
    _: str = Depends(authenticate_request),
    newbook_creds: dict = Depends(get_newbook_credentials)
):
    """Create a new booking in Newbook"""
    try:
        service = NewbookService(newbook_creds)
        result = service.create_booking(
            period_from=period_from,
            period_to=period_to,
            guest_firstname=guest_firstname,
            guest_lastname=guest_lastname,
            guest_email=guest_email,
            guest_phone=guest_phone,
            adults=adults,
            children=children,
            category_id=category_id,
            daily_mode=daily_mode,
            # amount=amount
        )
        
        # Log the booking
        from utils.newbook_db import log_newbook_booking
        
        # Extract data from API response structure
        # Response structure: { "success": "true", "data": { ... } }
        data = result.get("data", {}) if isinstance(result, dict) else {}
        
        # Extract booking_id from data.booking_id
        booking_id = data.get("booking_id")
        
        # Extract status from data.booking_status
        status = data.get("booking_status")
        
        # Extract amount from data.booking_total
        booking_total = data.get("booking_total")
        amount_value = None
        if booking_total:
            try:
                amount_value = float(booking_total)
            except (ValueError, TypeError):
                amount_value = None
        
        # Extract adults and children from data
        adults_value = None
        children_value = None
        if data.get("booking_adults"):
            try:
                adults_value = int(data.get("booking_adults"))
            except (ValueError, TypeError):
                adults_value = None
        if data.get("booking_children"):
            try:
                children_value = int(data.get("booking_children"))
            except (ValueError, TypeError):
                children_value = None
        
        # Extract category_id and category_name from Newbook response
        category_id_value = data.get("category_id")
        category_name_value = data.get("category_name")
        
        log_newbook_booking(
            location_id=newbook_creds.get("location_id"),
            park_name=newbook_creds.get("park_name"),
            guest_firstname=guest_firstname,
            guest_lastname=guest_lastname,
            guest_email=guest_email,
            guest_phone=guest_phone,
            arrival_date=period_from,
            departure_date=period_to,
            adults=adults_value if adults_value is not None else adults,
            children=children_value if children_value is not None else (int(children) if children else None),
            category_id=str(category_id_value) if category_id_value else None,
            category_name=category_name_value if category_name_value else None,
            amount=amount_value if amount_value is not None else None,
            booking_id=str(booking_id) if booking_id else None,
            status=str(status) if status else None
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-booking")
def check_booking(
    first_name: str = Query(..., description="Guest first name"),
    last_name: str = Query(..., description="Guest last name"),
    email: str = Query(..., description="Guest email"),
    period_from: Optional[str] = Query(None, description="Optional booking date (YYYY-MM-DD)"),
    period_to: Optional[str] = Query(None, description="Optional booking date (YYYY-MM-DD)"),
    _: str = Depends(authenticate_request),
    newbook_creds: dict = Depends(get_newbook_credentials)
):
    """Check if a booking exists for the given guest information"""
    try:
        email = unquote(email)
        service = NewbookService(newbook_creds)
        return service.check_booking(
            first_name=first_name,
            last_name=last_name,
            email=email,
            period_from=period_from,
            period_to=period_to
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# CRUD operations for booking logs
@router.get("/park-names")
def get_park_names(
    _: str = Depends(authenticate_request)
):
    """Get all unique park names from booking logs"""
    try:
        from utils.newbook_db import get_all_park_names
        park_names = get_all_park_names()
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
        from utils.newbook_db import get_all_newbook_booking_logs
        logs = get_all_newbook_booking_logs(location_id=location_id, park_name=park_name, month=month, year=year)
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
        from utils.newbook_db import get_newbook_booking_log
        log_entry = get_newbook_booking_log(log_id)
        if not log_entry:
            raise HTTPException(status_code=404, detail=f"Booking log with id {log_id} not found")
        return log_entry
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/booking-logs")
def create_booking_log(
    log_data: BookingLogCreate = Body(...),
    _: str = Depends(authenticate_request)
):
    """Manually create a new booking log entry"""
    try:
        from utils.newbook_db import create_newbook_booking_log
        result = create_newbook_booking_log(
            location_id=log_data.location_id,
            park_name=log_data.park_name,
            guest_firstname=log_data.guest_firstname,
            guest_lastname=log_data.guest_lastname,
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
    log_data: BookingLogUpdate = Body(...),
    _: str = Depends(authenticate_request)
):
    """Update an existing booking log entry"""
    try:
        from utils.newbook_db import update_newbook_booking_log
        result = update_newbook_booking_log(
            log_id=log_id,
            location_id=log_data.location_id,
            park_name=log_data.park_name,
            guest_firstname=log_data.guest_firstname,
            guest_lastname=log_data.guest_lastname,
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
        from utils.newbook_db import delete_newbook_booking_log
        success = delete_newbook_booking_log(log_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Booking log with id {log_id} not found")
        return {"message": f"Booking log {log_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

