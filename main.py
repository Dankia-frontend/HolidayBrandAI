from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from utils.logger import get_logger
from utils.scheduler import start_scheduler_in_background
from routes.rms_routes import router as rms_router
from routes.newbook_routes import router as newbook_router
from services.rms import rms_service, rms_cache, rms_auth
from utils.rms_db import set_current_rms_instance, get_rms_instance, create_rms_instance as create_rms_instance_db
from utils.newbook_db import create_newbook_instance, update_newbook_instance
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import signal
import sys
import os


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

@app.post("/newbook-instances")
def create_newbook_instance_endpoint(
    location_id: str = Query(...),
    api_key: str = Query(...),
    park_name: str = Query(...),
    # region: str = Query(None),
    # _: str = Depends(authenticate_request)
):
    success = create_newbook_instance(location_id, api_key, park_name)
    if success:
        return {"message": "Newbook instance created successfully"}
    else:
        raise HTTPException(status_code=400, detail="Location ID already exists")


@app.put("/newbook-instances/{location_id}")
def update_newbook_instance_endpoint(
    location_id: str,
    api_key: str = Query(None),
    park_name: str = Query(None),
    # _: str = Depends(authenticate_request)
):
    """Update an existing Newbook instance. Only provided fields will be updated."""
    if api_key is None and park_name is None:
        raise HTTPException(status_code=400, detail="At least one field (api_key or park_name) must be provided")
    
    success = update_newbook_instance(location_id, api_key=api_key, park_name=park_name)
    if success:
        return {"message": "Newbook instance updated successfully"}
    else:
        raise HTTPException(status_code=404, detail="Location ID not found")


# RMS Instance Management Endpoints
@app.post("/rms-instances")
def create_rms_instance_endpoint(
    location_id: str = Query(..., description="GHL Location ID"),
    client_id: int = Query(..., description="RMS Client ID"),
    client_pass: str = Query(..., description="RMS Client Password (will be encrypted)"),
    agent_id: int = Query(..., description="RMS Agent ID"),
    # _: str = Depends(authenticate_request)
):
    """Create a new RMS instance entry in the database"""
    success = create_rms_instance_db(location_id, client_id, client_pass, agent_id)
    if success:
        return {"message": "RMS instance created successfully"}
    else:
        raise HTTPException(status_code=400, detail="Location ID already exists or error occurred")


@app.get("/rms-instances/{location_id}")
def get_rms_instance_endpoint(
    location_id: str,
    # _: str = Depends(authenticate_request)
):
    """Get RMS instance by location_id (password will be masked)"""
    instance = get_rms_instance(location_id)
    if instance:
        # Mask the password for security
        instance['client_pass'] = '********'
        return instance
    else:
        raise HTTPException(status_code=404, detail="RMS instance not found")


@app.post("/rms-instances/{location_id}/activate")
async def activate_rms_instance(
    location_id: str,
    # _: str = Depends(authenticate_request)
):
    """
    Activate an RMS instance for use.
    This sets the current RMS credentials and reinitializes the RMS service.
    """
    # Set the current RMS instance from database
    success = set_current_rms_instance(location_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"RMS instance not found for location_id: {location_id}")
    
    # Reload credentials in auth and cache
    rms_auth.reload_credentials()
    rms_cache.reload_credentials()
    
    # Reinitialize RMS service
    try:
        await rms_service.initialize()
        stats = rms_cache.get_stats()
        return {
            "message": f"RMS instance activated for location {location_id}",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize RMS: {str(e)}")


# Include RMS routes
app.include_router(rms_router)

# Include Newbook routes
app.include_router(newbook_router)

# Initialize scheduler
scheduler = AsyncIOScheduler()

async def daily_rms_refresh():
    """Automatically refresh RMS cache daily at 3 AM"""
    print("🔄 Running daily RMS cache refresh...")
    try:
        # Just clear the cache file to force fresh fetch on next request
        import os
        if os.path.exists("rms_cache.json"):
            os.remove("rms_cache.json")
        print("✅ Daily RMS cache cleared - will refresh on next request")
    except Exception as e:
        print(f"❌ Daily RMS cache refresh failed: {e}")

async def rms_sync_job():
    """Sync RMS bookings (GHL sending disabled - only NewBook sends to GHL)."""
    log.info("[RMS SYNC] Starting RMS fetch_and_sync_bookings job...")
    print("⏰ Running RMS fetch_and_sync_bookings job...")
    try:
        result = await rms_service.fetch_and_sync_bookings()
        log.info(f"[RMS SYNC] Job completed: {result}")
        print("✅ Sync result:", result)
    except Exception as e:
        log.error(f"[RMS SYNC] Job failed: {e}")
        print(f"❌ RMS sync job failed: {e}")


async def initialize_rms_from_db():
    """
    Initialize RMS using credentials from database.
    Uses RMS_LOCATION_ID from environment to determine which instance to use.
    """
    # Get location_id from environment variable
    location_id = os.getenv("RMS_LOCATION_ID")
    
    if not location_id:
        log.warning("⚠️ RMS_LOCATION_ID not set in environment - RMS will not be initialized from DB")
        print("⚠️ RMS_LOCATION_ID not set - falling back to env vars for RMS credentials")
        return False
    
    print(f"🔧 Initializing RMS from database for location: {location_id}")
    
    # Set the current RMS instance from database
    success = set_current_rms_instance(location_id)
    if not success:
        log.error(f"❌ RMS instance not found in database for location_id: {location_id}")
        print(f"❌ RMS instance not found for location_id: {location_id}")
        return False
    
    print(f"✅ RMS credentials loaded from database for location: {location_id}")
    return True


@app.on_event("startup")
async def startup_event():
    # RMS initialization removed - now handled per-request with credentials from headers
    # Each request creates its own RMS instance with the correct park's credentials
    print("✅ Server started - RMS will initialize per-request based on X-Location-ID header")
    
    # Schedule daily RMS refresh at 3 AM
    try:
        scheduler.add_job(daily_rms_refresh, 'cron', hour=3, minute=0)
        # Note: RMS sync job disabled - was using global instance
        # Each location now has its own credentials loaded per-request
        scheduler.start()
        log.info("✅ RMS daily refresh scheduled (3 AM)")
        print("✅ RMS daily cache cleanup scheduled (3 AM)")
    except Exception as e:
        print(f"⚠️ Scheduler error: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            print("✅ Scheduler stopped")
    except Exception as e:
        print(f"⚠️ Shutdown error: {e}")

# Handle Ctrl+C gracefully
def signal_handler(sig, frame):
    print('\n🛑 Shutting down gracefully...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Run the scheduler in a background thread
start_scheduler_in_background() # Comment out for local testing


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )