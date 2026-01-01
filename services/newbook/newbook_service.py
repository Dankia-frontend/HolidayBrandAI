from typing import Dict, Optional, List
from datetime import datetime, timedelta
from .newbook_api_client import NewbookApiClient
from utils.logger import get_logger

log = get_logger("NewbookService")


class NewbookService:
    """
    Main service class for Newbook operations.
    Handles availability, bookings, and related business logic.
    """
    
    def __init__(self, credentials: dict = None):
        """
        Initialize NewbookService with optional credentials.
        
        Args:
            credentials: dict with location_id, api_key, region
                        If not provided, will try to load from environment variables.
        """
        self.credentials = credentials
        self._api_client = None
    
    def _get_api_client(self) -> NewbookApiClient:
        """Get or create API client with current credentials"""
        if self._api_client is None:
            self._api_client = NewbookApiClient(self.credentials)
        return self._api_client
    
    @property
    def location_id(self) -> Optional[str]:
        """Get location_id from credentials"""
        if self.credentials:
            return self.credentials.get('location_id')
        return None
    
    @property
    def api_key(self) -> Optional[str]:
        """Get API key from credentials"""
        if self.credentials:
            return self.credentials.get('api_key')
        return None
    
    @property
    def region(self) -> Optional[str]:
        """Get region from credentials"""
        return "AU"
    
    def get_availability(
        self,
        period_from: str,
        period_to: str,
        adults: int,
        children: int,
        daily_mode: str
    ) -> Dict:
        """
        Get availability and pricing for specified dates and guests.
        
        Returns filtered and sorted availability data.
        """
        client = self._get_api_client()
        
        payload = {
            "region": self.region,
            "api_key": self.api_key,
            "period_from": period_from,
            "period_to": period_to,
            "adults": adults,
            "children": children,
            "daily_mode": daily_mode,
        }
        
        try:
            data = client.get_availability(payload)
            
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
                        "category_type_id": category_data.get("category_type_id"),
                        "price": price,
                        "sites_message": sites_message,
                    }

                return filtered
            
            return data
            
        except Exception as e:
            log.error(f"Error getting availability: {str(e)}")
            raise
    
    def get_tariff_information(
        self,
        period_from: str,
        period_to: str,
        adults: int,
        children: int,
        category_id: int,
        daily_mode: str,
        tariff_label: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get tariff information from availability API for a specific category.
        Returns tariff details including tariff_id, tariff_total, etc.
        """
        try:
            client = self._get_api_client()
            
            payload = {
                "region": self.region,
                "api_key": self.api_key,
                "period_from": period_from,
                "period_to": period_to,
                "adults": adults,
                "children": children,
                "daily_mode": daily_mode
            }

            log.info(f"Getting tariff information for category {category_id}")
            
            availability_data = client.get_availability(payload)

            if "data" in availability_data and str(category_id) in availability_data["data"]:
                category_data = availability_data["data"][str(category_id)]
                tariffs_available = category_data.get("tariffs_available", [])

                log.info(f"Found {len(tariffs_available)} tariffs for category {category_id}")

                if tariff_label:
                    for tariff in tariffs_available:
                        if tariff.get("tariff_label") == tariff_label:
                            log.info(f"Found matching tariff: {tariff_label}")
                            tariff_id = None
                            tariffs_quoted = tariff.get("tariffs_quoted", {})
                            base_max_adults, base_max_children = self._extract_max_occupancy(tariffs_quoted)
                            if tariffs_quoted:
                                first_date = next(iter(tariffs_quoted.keys()))
                                tariff_applied_data = tariffs_quoted[first_date]
                                tariff_applied_id = tariff_applied_data.get("tariff_applied_id")
                                if tariff_applied_id:
                                    tariff_id = int(tariff_applied_id)

                            return {
                                "tariff_label": tariff["tariff_label"],
                                "tariff_total": tariff["tariff_total"],
                                "original_tariff_total": tariff["original_tariff_total"],
                                "special_deal": tariff["special_deal"],
                                "tariff_code": tariff.get("tariff_code", 0),
                                "tariff_id": tariff_id,
                                "base_max_adults": base_max_adults,
                                "base_max_children": base_max_children,
                                "tariffs_available": [tariff]
                            }
                    log.warning(f"Tariff '{tariff_label}' not found, using first available")

                if tariffs_available:
                    first_tariff = tariffs_available[0]
                    log.info(f"Using first available tariff: {first_tariff['tariff_label']}")

                    tariff_id = None
                    tariffs_quoted = first_tariff.get("tariffs_quoted", {})
                    base_max_adults, base_max_children = self._extract_max_occupancy(tariffs_quoted)
                    if tariffs_quoted:
                        first_date = next(iter(tariffs_quoted.keys()))
                        tariff_applied_data = tariffs_quoted[first_date]
                        tariff_applied_id = tariff_applied_data.get("tariff_applied_id")
                        if tariff_applied_id:
                            tariff_id = int(tariff_applied_id)

                    return {
                        "tariff_label": first_tariff["tariff_label"],
                        "tariff_total": first_tariff["tariff_total"],
                        "original_tariff_total": first_tariff["original_tariff_total"],
                        "special_deal": first_tariff["special_deal"],
                        "tariff_code": first_tariff.get("tariff_code", 0),
                        "tariff_id": tariff_id,
                        "base_max_adults": base_max_adults,
                        "base_max_children": base_max_children,
                        "tariffs_available": [first_tariff]
                    }

            log.warning(f"No tariffs found for category {category_id}")
            return None

        except Exception as e:
            log.error(f"Error getting tariff information: {str(e)}")
            return None
    
    def _extract_max_occupancy(self, tariffs_quoted: dict) -> tuple:
        """
        Helper to extract base_max_adults and base_max_children from tariffs_quoted.
        Returns tuple (base_max_adults, base_max_children) or (None, None) if not found.
        """
        if not isinstance(tariffs_quoted, dict) or not tariffs_quoted:
            return None, None
        
        try:
            first_date_key = next(iter(tariffs_quoted.keys()))
            quote_data = tariffs_quoted.get(first_date_key) or {}
            base_max_adults = quote_data.get("base_max_adults")
            base_max_children = quote_data.get("base_max_children")
            return base_max_adults, base_max_children
        except (StopIteration, AttributeError, TypeError):
            return None, None
    
    def create_tariffs_quoted(self, period_from: str, period_to: str, tariff_total: float, tariff_id: int) -> dict:
        """
        Create tariffs_quoted in the expected format for NewBook.
        """
        try:
            start_date = datetime.strptime(period_from.split()[0], "%Y-%m-%d")
            end_date = datetime.strptime(period_to.split()[0], "%Y-%m-%d")

            nights = (end_date - start_date).days
            if nights <= 0:
                nights = 1

            price_per_night = tariff_total // nights

            tariffs_quoted = {}
            current_date = start_date
            while current_date < end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                tariffs_quoted[date_str] = {
                    "tariff_applied_id": tariff_id,
                    "price": price_per_night
                }
                current_date += timedelta(days=1)

            log.info(f"Created tariffs_quoted for {nights} nights")
            return tariffs_quoted

        except Exception as e:
            log.error(f"Error creating tariffs_quoted: {str(e)}")
            return {}
    
    def create_booking(
        self,
        period_from: str,
        period_to: str,
        guest_firstname: str,
        guest_lastname: str,
        guest_email: str,
        guest_phone: str,
        adults: int,
        children: int,
        category_id: int,
        daily_mode: str,
        # amount: int
    ) -> Dict:
        """
        Create a new booking in Newbook.
        """
        client = self._get_api_client()
        
        # Get tariff information from availability API
        tariff_info = self.get_tariff_information(
            period_from=period_from,
            period_to=period_to,
            adults=adults,
            children=children,
            category_id=category_id,
            daily_mode=daily_mode
        )
        
        if not tariff_info:
            raise Exception("No tariff information found for the specified category and dates")
        
        # Create tariffs_quoted using the actual tariff ID from availability
        tariffs_quoted = self.create_tariffs_quoted(
            period_from=period_from,
            period_to=period_to,
            tariff_total=tariff_info["tariff_total"],
            tariff_id=tariff_info["tariff_id"]
        )
        
        # Build payload with tariff information
        payload = {
            "region": self.region,
            "api_key": self.api_key,
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
            # "amount": amount,
            "tariff_label": tariff_info["tariff_label"],
            "tariff_total": tariff_info["tariff_total"],
            "special_deal": tariff_info["special_deal"],
            "tariffs_quoted": tariffs_quoted
        }

        log.info(f"Creating booking for {guest_firstname} {guest_lastname}")

        try:
            result = client.create_booking(payload)
            
            # Remove api_key from response (if present)
            result.pop("api_key", None)
            
            return result
            
        except Exception as e:
            log.error(f"Error creating booking: {str(e)}")
            raise
    
    def check_booking(
        self,
        booking_id: str,
        period_from: Optional[str] = None,
        period_to: Optional[str] = None
    ) -> Dict:
        """
        Check if a booking exists for the given booking_id.
        Searches through the list of bookings returned by the API.
        
        Args:
            booking_id: The booking ID to search for
            period_from: Optional booking start date filter
            period_to: Optional booking end date filter
        
        Returns:
            Dictionary with "exists" key containing boolean indicating if booking_id was found
        """
        client = self._get_api_client()

        if not booking_id:
            raise ValueError("Missing required fields: booking_id")

        # Build request payload
        payload = {
            "region": self.region,
            "api_key": self.api_key,
            "period_from": period_from,
            "period_to": period_to,
            "list_type": "staying"
        }

        try:
            result = client.list_bookings(payload)

            # Check if the API call was successful
            if not result.get("success") or result.get("success") != "true":
                log.warning(f"API call returned unsuccessful result: {result.get('success')}")
                return {"exists": False}

            # Extract the data array from the result
            bookings_data = result.get("data", [])
            
            if not isinstance(bookings_data, list):
                log.warning(f"Expected data to be a list, got {type(bookings_data)}")
                return {"exists": False}

            # Convert booking_id to int for comparison (API returns booking_id as int)
            try:
                target_booking_id = int(booking_id)
            except (ValueError, TypeError):
                log.error(f"Invalid booking_id format: {booking_id}")
                return {"exists": False}

            # Search for the booking_id in the data array
            booking_exists = False
            for booking in bookings_data:
                booking_id_in_result = booking.get("booking_id")
                # Handle both int and string comparisons
                if booking_id_in_result is not None:
                    if isinstance(booking_id_in_result, int):
                        if booking_id_in_result == target_booking_id:
                            booking_exists = True
                            break
                    elif isinstance(booking_id_in_result, str):
                        try:
                            if int(booking_id_in_result) == target_booking_id:
                                booking_exists = True
                                break
                        except (ValueError, TypeError):
                            continue

            log.info(f"Booking ID {booking_id} {'exists' if booking_exists else 'does not exist'} in the results")
            return {"exists": booking_exists}
            
        except Exception as e:
            log.error(f"Error checking booking: {str(e)}")
            raise


