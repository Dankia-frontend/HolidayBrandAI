from datetime import datetime, timedelta
from fastapi import FastAPI, Query, HTTPException, Depends
from schemas.schemas import BookingRequest, AvailabilityRequest, CheckBooking
import requests
from config.config import NEWBOOK_API_BASE,REGION,API_KEY
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
from utils.logger import get_logger
from auth.auth import authenticate_request
from utils.newbook import NB_HEADERS, get_tariff_information, create_tariffs_quoted
from utils.scheduler import start_scheduler_in_background
from test_script import create_ghl_subaccount, create_ghl_subaccount_simple, delete_ghl_subaccount, list_ghl_locations, get_ghl_location

app = FastAPI()
log = get_logger("FastAPI")

# Allow origins (add your frontend URL)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # <-- allow all origins
    allow_credentials=True,
    allow_methods=["*"],       # <-- allow all HTTP methods
    allow_headers=["*"],       # <-- allow all headers
)


@app.get("/availability")
def get_availability(
    period_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    period_to: str = Query(..., description="End date in YYYY-MM-DD format"),
    adults: int = Query(..., description="Number of adults"),
    daily_mode: str = Query(..., description="Daily mode value, e.g., 'true' or 'false'"),
    Children: int = Query(..., description="Number of children"),
    _: str = Depends(authenticate_request)
):
    # print(period_from, period_to, adults, daily_mode, Children)
    try:
        payload = {
            "region": REGION,
            "api_key": API_KEY,
            "period_from": period_from,
            "period_to": period_to,
            "adults": adults,
            "children": Children,
            "daily_mode": daily_mode
        }

        # print("\n📤 Payload being sent to NewBook API:")
        # print(payload)
        # print(NB_HEADERS)
        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_availability_pricing",
            headers=NB_HEADERS,
            json=payload,
            verify=False,  # ⚠️ Only for local testing
            timeout=15
        )

        # print("📥 Response Code:", response.status_code)
        # print("📥 Response Body:", response.text)

        response.raise_for_status()
        data = response.json()

        # Sort categories by highest amount first (descending order)
        if "data" in data and isinstance(data["data"], dict):
            # Convert categories to list of tuples (category_id, category_data, max_amount)
            categories_with_amounts = []
            
            for category_id, category_data in data["data"].items():
                tariffs_available = category_data.get("tariffs_available", [])
                
                # Find the highest amount among all tariffs for this category
                max_amount = 0
                if tariffs_available:
                    for tariff in tariffs_available:
                        tariffs_quoted = tariff.get("tariffs_quoted", {})
                        if isinstance(tariffs_quoted, dict):
                            # Get the maximum amount from all dates in tariffs_quoted
                            for date_key, quote_data in tariffs_quoted.items():
                                if isinstance(quote_data, dict):
                                    amount = quote_data.get("amount", 0)
                                    # Ensure amount is treated as a number
                                    try:
                                        amount = float(amount) if amount is not None else 0
                                        max_amount = max(max_amount, amount)
                                    except (ValueError, TypeError):
                                        continue
                
                categories_with_amounts.append((category_id, category_data, max_amount))
            
            # Sort by max_amount in descending order (highest first)
            categories_with_amounts.sort(key=lambda x: float(x[2]), reverse=True)
            
            # This ensures the order is preserved in the JSON response
            new_data = {
                "success": data.get("success", "true"),
                "data": {}
            }
            
            # Add categories in sorted order
            for category_id, category_data, _ in categories_with_amounts:
                new_data["data"][category_id] = category_data
            
            # Copy any other fields from original response
            for key, value in data.items():
                if key not in ["success", "data"]:
                    new_data[key] = value

            # Filter to only required fields per category
            filtered = {
                "success": new_data.get("success", "true"),
                "data": {}
            }

            for category_id, category_data in new_data["data"].items():
                category_name = category_data.get("category_name")
                sites_message = category_data.get("sites_message", {})

                # Derive price: prefer average_nightly_tariff from first tariff; fallback to first quoted amount
                price = None
                tariffs_available = category_data.get("tariffs_available", [])
                if tariffs_available:
                    first_tariff = tariffs_available[0]
                    price = first_tariff.get("average_nightly_tariff")
                    if price is None:
                        tariffs_quoted = first_tariff.get("tariffs_quoted", {})
                        if isinstance(tariffs_quoted, dict) and tariffs_quoted:
                            first_date_key = next(iter(tariffs_quoted.keys()))
                            quote = tariffs_quoted.get(first_date_key) or {}
                            price = quote.get("amount")

                filtered["data"][category_id] = {
                    "category_name": category_name,
                    "price": price,
                    "sites_message": sites_message,
                }

            data = filtered
        print(f"📥 Response Data: {data}")
        return data

    except Exception as e:
        print("❌ Error:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
# 2. Confirm Booking [POST]
@app.post("/confirm-booking")
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
    amount: int = Query(..., description="Total booking amount"),
    _: str = Depends(authenticate_request)
):
    try:
        # Get tariff information from availability API
        tariff_info = get_tariff_information(
            period_from=period_from,
            period_to=period_to,
            adults=adults,
            children=children,
            category_id=category_id,
            daily_mode=daily_mode
        )
        
        if not tariff_info:
            raise HTTPException(status_code=400, detail="No tariff information found for the specified category and dates")
        
        # Create tariffs_quoted using the actual tariff ID from availability
        tariffs_quoted = create_tariffs_quoted(
            period_from=period_from,
            period_to=period_to,
            tariff_total=tariff_info["tariff_total"],
            tariff_id=tariff_info["tariff_id"]  # Use the actual tariff ID
        )
        
        # Build payload with tariff information
        payload = {
            "region": REGION,
            "api_key": API_KEY,
            "period_from": period_from,
            "period_to": period_to,
            "guest_firstname": guest_firstname,
            "guest_lastname": guest_lastname,
            "guest_email": guest_email,
            "guest_phone": guest_phone,
            "adults": adults,
            "children": children,
            "category_id": category_id,
            "daily_mode": daily_mode,
            "amount": amount,
            "tariff_label": tariff_info["tariff_label"],
            "tariff_total": tariff_info["tariff_total"],
            "special_deal": tariff_info["special_deal"],
            "tariffs_quoted": tariffs_quoted
        }

        print(f"[INFO] Sending payload to NewBook: {payload}")

        # --- API Call to NewBook ---
        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_create",
            headers=NB_HEADERS,
            json=payload,
            verify=False,
            timeout=15
        )

        print(f"[DEBUG] Response Status Code: {response.status_code}")
        print(f"[DEBUG] Response Text: {response.text}")

        response.raise_for_status()
        result = response.json()

        # Remove api_key from response (if present)
        result.pop("api_key", None)

        return result

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    
# 3. Check Booking [GET]
@app.get("/check-booking")
def confirm_booking(
    name: str = Query(..., description="Guest name"),
    email: str = Query(..., description="Guest email"),
    booking_date: str | None = Query(None, description="Optional booking date (YYYY-MM-DD)"),
    _: str = Depends(authenticate_request)
):
    try:
        name = name.strip()
        email = email.strip()
        booking_date = booking_date.strip() if booking_date else None

        if not name or not email:
            raise HTTPException(status_code=400, detail="Missing required fields: name, email")

        # 🗓 Determine date range (period_from / period_to)
        if booking_date:
            try:
                date_obj = datetime.strptime(booking_date, "%Y-%m-%d")
                period_from = date_obj.strftime("%Y-%m-%d 00:00:00")
                period_to = date_obj.strftime("%Y-%m-%d 23:59:59")
            except ValueError:
                # Invalid date → fallback to current week
                today = datetime.now()
                monday = today - datetime.timedelta(days=today.weekday())
                sunday = monday + datetime.timedelta(days=6)
                period_from = monday.strftime("%Y-%m-%d 00:00:00")
                period_to = sunday.strftime("%Y-%m-%d 23:59:59")
        else:
            # No date → current month
            today = datetime.now()
            first_day = today.replace(day=1)
            next_month = first_day + datetime.timedelta(days=32)
            last_day = next_month.replace(day=1) - datetime.timedelta(days=1)
            period_from = first_day.strftime("%Y-%m-%d 00:00:00")
            period_to = last_day.strftime("%Y-%m-%d 23:59:59")

        # 🧾 Build request payload
        payload = {
            "region": REGION,
            "api_key": API_KEY,
            "period_from": period_from,
            "period_to": period_to,
            "list_type": "all"
        }

        print("\n📤 Payload being sent to Newbook API:")
        print(payload)

        # 🔗 Send request to NewBook
        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_list",
            headers=NB_HEADERS,
            json=payload,
            verify=False,  # Disable SSL for local testing only
            timeout=15
        )

        print("📥 Response Code:", response.status_code)
        print("📥 Response Body:", response.text)

        response.raise_for_status()
        return response.json()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 4. Create GHL Sub-Account [POST]
@app.post("/ghl/create-subaccount")
def create_ghl_subaccount_endpoint(
    business_name: str = Query(..., description="Business name for the sub-account (required)"),
    address: str = Query(None, description="Street address"),
    city: str = Query(None, description="City name"),
    state: str = Query(None, description="State/Province code (e.g., 'CA', 'NY')"),
    postal_code: str = Query(None, description="ZIP/Postal code"),
    country: str = Query("US", description="Country code (default: 'US')"),
    website: str = Query(None, description="Business website URL"),
    timezone: str = Query("America/New_York", description="Timezone (default: 'America/New_York')"),
    first_name: str = Query(None, description="Primary contact first name"),
    last_name: str = Query(None, description="Primary contact last name"),
    email: str = Query(None, description="Primary contact email"),
    phone: str = Query(None, description="Primary contact phone (E.164 format recommended, e.g., '+1234567890')"),
    snapshot_id: str = Query(None, description="Optional snapshot ID to apply template"),
    # _: str = Depends(authenticate_request)
):
    """
    Creates a new sub-account (location) in GoHighLevel using Agency API Key.
    """
    try:
        result = create_ghl_subaccount(
            businessName=business_name,
            address=address,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            website=website,
            timezone=timezone,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            snapshot_id=snapshot_id
        )
        
        if result:
            return {
                "success": True,
                "message": "Sub-account created successfully",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to create sub-account")
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error creating GHL sub-account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 5. Create GHL Sub-Account (Simple) [POST]
@app.post("/ghl/create-subaccount-simple")
def create_ghl_subaccount_simple_endpoint(
    name: str = Query(..., description="Business name (required)"),
    email: str = Query(None, description="Primary contact email"),
    phone: str = Query(None, description="Primary contact phone"),
    city: str = Query(None, description="City name"),
    state: str = Query(None, description="State/Province code"),
    country: str = Query("US", description="Country code (default: 'US')"),
    _: str = Depends(authenticate_request)
):
    """
    Simplified endpoint to create a sub-account with minimal required fields.
    """
    try:
        result = create_ghl_subaccount_simple(
            name=name,
            email=email,
            phone=phone,
            city=city,
            state=state,
            country=country
        )
        
        if result:
            return {
                "success": True,
                "message": "Sub-account created successfully",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to create sub-account")
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error creating GHL sub-account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 6. Delete GHL Sub-Account [DELETE]
@app.delete("/ghl/delete-subaccount")
def delete_ghl_subaccount_endpoint(
    location_id: str = Query(..., description="The ID of the location to delete"),
    _: str = Depends(authenticate_request)
):
    """
    Deletes a sub-account (location) by its ID.
    """
    try:
        success = delete_ghl_subaccount(location_id)
        
        if success:
            return {
                "success": True,
                "message": f"Sub-account {location_id} deleted successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=f"Failed to delete sub-account {location_id}")
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error deleting GHL sub-account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 7. List GHL Locations [GET]
@app.get("/ghl/list-locations")
def list_ghl_locations_endpoint(
    # _: str = Depends(authenticate_request)
):
    """
    Lists all locations (sub-accounts) in the agency.
    """
    try:
        locations = list_ghl_locations()
        
        if locations is not None:
            return {
                "success": True,
                "count": len(locations),
                "locations": locations
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to list locations")
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error listing GHL locations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 8. Get GHL Location [GET]
@app.get("/ghl/get-location")
def get_ghl_location_endpoint(
    location_id: str = Query(..., description="The ID of the location to retrieve"),
    # _: str = Depends(authenticate_request)
):
    """
    Gets details of a specific location by ID.
    """
    try:
        location = get_ghl_location(location_id)
        
        if location:
            return {
                "success": True,
                "data": location
            }
        else:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting GHL location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Run the scheduler in a background thread
# start_scheduler_in_background() # Comment out for local testing


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )