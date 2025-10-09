import os
import sys
import time
import schedule
from datetime import datetime

# --- Fix import paths so it can find main.py and utils ---
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from main import get_availability, confirm_booking, check_booking
from utils.ghl_api import add_note_to_ghl  # you'll create this
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define your sync function
def sync_bookings():
    print(f"\n🕒 Running sync job at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Call your NewBook API via FastAPI functions
        data = {
            "period_from": datetime.now().strftime("%Y-%m-%d"),
            "period_to": datetime.now().strftime("%Y-%m-%d"),
            "adults": 2,
            "children": 0,
            "daily_mode": "yes"
        }

        # Example: get availability
        response = get_availability(data)
        print("✅ Availability fetched:", response)

        # You can also confirm a booking or check existing ones here
        # result = confirm_booking(...)
        # check = check_booking(...)

        # Example: send data to GHL (GoHighLevel)
        add_note_to_ghl(contact_id="12345", note_text="New availability synced")

    except Exception as e:
        print("❌ Error in sync job:", e)


# Schedule the job every 5 minutes
schedule.every(5).minutes.do(sync_bookings)

if __name__ == "__main__":
    print("🚀 Cron job started. Running every 5 minutes...")
    sync_bookings()  # Run immediately at startup
    while True:
        schedule.run_pending()
        time.sleep(60)
