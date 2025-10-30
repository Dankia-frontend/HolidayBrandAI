import os
import time
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from utils.ghl_api import daily_cleanup, create_opportunities_from_newbook


def daily_cleanup_with_cache():
    """
    Deletes the local cache file then runs the GHL cleanup.
    Logic preserved from the previous implementation in main.py.
    """
    print("[DAILY CLEANUP] Running cache cleanup...")
    cache_path = os.path.join(os.path.dirname(__file__), "..", "bookings_cache.json")
    cache_path = os.path.abspath(cache_path)
    try:
        if os.path.exists(cache_path):
            os.remove(cache_path)
            print("[CACHE CLEANUP] Deleted bookings_cache.json successfully.")
        else:
            print("[CACHE CLEANUP] No bookings_cache.json file found.")
    except Exception as e:
        print(f"[ERROR] Could not delete cache file: {e}")

    try:
        daily_cleanup()
        print("[DAILY CLEANUP] Completed GHL pipeline cleanup successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to run daily_cleanup(): {e}")


def start_scheduler():
    """
    Starts background scheduler for daily cleanup and opportunity creation.
    Logic preserved from the previous implementation in main.py.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(daily_cleanup_with_cache, "cron", hour=0, minute=0)
    scheduler.add_job(create_opportunities_from_newbook, "interval", minutes=10)
    scheduler.start()
    print("[SCHEDULER] Started successfully. Running background tasks...")

    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("[SCHEDULER] Stopped gracefully.")


def start_scheduler_in_background():
    threading.Thread(target=start_scheduler, daemon=True).start()


