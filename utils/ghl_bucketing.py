from datetime import datetime, timedelta
import os
import json


# --- Helper to write bucket bookings to file ---
def write_bucket_file(bucket, bookings):
    """
    Writes bookings for a specific bucket to its own file.
    If the file doesn't exist, it is created automatically.
    """
    filename = f"{bucket}_bookings.json"
    filepath = os.path.join(os.path.dirname(__file__), "..", filename)
    with open(filepath, "w") as f:
        json.dump(bookings, f, indent=2)
    print(f"[BUCKET FILE] {bucket}: {len(bookings)} bookings written to {filepath}")

# --- Bucket bookings ---
def bucket_bookings(bookings):
    """
    Classifies bookings into buckets based on arrival/departure/status.
    Logic preserved from the previous implementation in utils/ghl_api.py.
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    dayafter = today + timedelta(days=2)
    seven_days = today + timedelta(days=7)

    buckets = {
        "arriving_soon": [],
        "arriving_today": [],
        "staying_now": [],
        "checking_out": [],
        "checked_out": [],
        "cancelled": []
    }

    for b in bookings:
        st = (b.get("booking_status") or "").lower().strip()
        arr_str = b.get("booking_arrival")
        dep_str = b.get("booking_departure")
        arr = datetime.strptime(arr_str, "%Y-%m-%d %H:%M:%S") if arr_str else None
        dep = datetime.strptime(dep_str, "%Y-%m-%d %H:%M:%S") if dep_str else None

        if st in ["cancelled", "no_show", "no show"]:
            buckets["cancelled"].append(b)
        elif st == "departed":
            buckets["checked_out"].append(b)
        elif st == "arrived" and dep and dep >= tomorrow:
            buckets["staying_now"].append(b)
        elif st == "arrived" and dep and dep >= today and dep < dayafter:
            buckets["checking_out"].append(b)
        elif arr and arr >= today and arr < tomorrow:
            buckets["arriving_today"].append(b)
        elif arr and arr >= tomorrow and arr <= seven_days:
            buckets["arriving_soon"].append(b)
    return buckets


