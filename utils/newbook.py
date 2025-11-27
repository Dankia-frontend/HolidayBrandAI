import base64
from datetime import datetime, timedelta
import requests
from config.config import REGION, API_KEY, NEWBOOK_API_BASE, USERNAME, PASSWORD

_user_pass = f"{USERNAME}:{PASSWORD}"
_encoded_credentials = base64.b64encode(_user_pass.encode()).decode()

NB_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Basic {_encoded_credentials}",
}

def extract_max_occupancy(tariffs_quoted):
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


def get_tariff_information(period_from, period_to, adults, children, category_id, daily_mode, api_key=None, region=None, tariff_label=None):
    """
    Helper to get tariff information from NewBook availability API.
    Logic preserved from the previous implementation in main.py.
    """
    try:
        # Use provided api_key and region, or fallback to config values
        api_key = api_key or API_KEY
        region = region or REGION
        
        payload = {
            "region": region,
            "api_key": api_key,
            "period_from": period_from,
            "period_to": period_to,
            "adults": adults,
            "children": children,
            "daily_mode": daily_mode
        }

        print(f"[TARIFF_HELPER] Getting availability for category {category_id}")
        print(f"[TARIFF_HELPER] Payload: {payload}")

        response = requests.post(
            f"{NEWBOOK_API_BASE}/bookings_availability_pricing",
            headers=NB_HEADERS,
            json=payload,
            verify=False,
            timeout=15
        )

        response.raise_for_status()
        availability_data = response.json()

        print(f"[TARIFF_HELPER] Availability response received")

        if "data" in availability_data and str(category_id) in availability_data["data"]:
            category_data = availability_data["data"][str(category_id)]
            tariffs_available = category_data.get("tariffs_available", [])

            print(f"[TARIFF_HELPER] Found {len(tariffs_available)} tariffs for category {category_id}")

            if tariff_label:
                for tariff in tariffs_available:
                    if tariff.get("tariff_label") == tariff_label:
                        print(f"[TARIFF_HELPER] Found matching tariff: {tariff_label}")
                        tariff_id = None
                        tariffs_quoted = tariff.get("tariffs_quoted", {})
                        base_max_adults, base_max_children = extract_max_occupancy(tariffs_quoted)
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
                print(f"[TARIFF_HELPER] Warning: Tariff '{tariff_label}' not found, using first available")

            if tariffs_available:
                first_tariff = tariffs_available[0]
                print(f"[TARIFF_HELPER] Using first available tariff: {first_tariff['tariff_label']}")

                tariff_id = None
                tariffs_quoted = first_tariff.get("tariffs_quoted", {})
                base_max_adults, base_max_children = extract_max_occupancy(tariffs_quoted)
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

        print(f"[TARIFF_HELPER] No tariffs found for category {category_id}")
        return None

    except Exception as e:
        print(f"[TARIFF_HELPER] Error getting tariff information: {str(e)}")
        return None


def create_tariffs_quoted(period_from, period_to, tariff_total, tariff_id):
    """
    Helper to create tariffs_quoted in the expected format for NewBook.
    Logic preserved from the previous implementation in main.py.
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

        print(f"[TARIFF_HELPER] Created tariffs_quoted: {tariffs_quoted}")
        return tariffs_quoted

    except Exception as e:
        print(f"[TARIFF_HELPER] Error creating tariffs_quoted: {str(e)}")
        return {}


