import os
import time
import threading
import sys
from apscheduler.schedulers.background import BackgroundScheduler
from utils.ghl_api import daily_cleanup, create_opportunities_from_newbook
from utils.logger import get_logger

# Initialize logger for scheduler
log = get_logger("Scheduler")


def daily_cleanup_with_cache():
    """
    Deletes the local cache file then runs the GHL cleanup.
    Logic preserved from the previous implementation in main.py.
    """
    log.info("[DAILY CLEANUP] Running cache cleanup...")
    cache_path = os.path.join(os.path.dirname(__file__), "..", "bookings_cache.json")
    cache_path = os.path.abspath(cache_path)
    try:
        if os.path.exists(cache_path):
            os.remove(cache_path)
            log.info("[CACHE CLEANUP] Deleted bookings_cache.json successfully.")
        else:
            log.info("[CACHE CLEANUP] No bookings_cache.json file found.")
    except Exception as e:
        log.error(f"[ERROR] Could not delete cache file: {e}")

    try:
        daily_cleanup()
        log.info("[DAILY CLEANUP] Completed GHL pipeline cleanup successfully.")
    except Exception as e:
        log.error(f"[ERROR] Failed to run daily_cleanup(): {e}")


def start_scheduler():
    """
    Starts background scheduler for daily cleanup and opportunity creation.
    Logic preserved from the previous implementation in main.py.
    """
    log.info("[SCHEDULER] Initializing scheduler...")
    scheduler = BackgroundScheduler()
    scheduler.add_job(daily_cleanup_with_cache, "cron", hour=0, minute=0)
    scheduler.add_job(create_opportunities_from_newbook, "interval", minutes=10)
    scheduler.start()
    log.info("[SCHEDULER] Started successfully. Running background tasks...")
    log.info("[SCHEDULER] - Daily cleanup scheduled: 00:00 (midnight)")
    log.info("[SCHEDULER] - Opportunity creation scheduled: every 10 minutes")

    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("[SCHEDULER] Stopped gracefully.")


def start_scheduler_in_background():
    """Start scheduler in background thread with immediate confirmation"""
    log.info("[SCHEDULER] Starting scheduler in background thread...")
    thread = threading.Thread(target=start_scheduler, daemon=True)
    thread.start()
    # Give it a moment to start and log
    time.sleep(0.5)
    log.info("[SCHEDULER] Background thread started (daemon=True)")