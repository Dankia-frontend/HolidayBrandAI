# filepath: c:\Users\HP\Desktop\NewBookApi\config.py
import os
from dotenv import load_dotenv

load_dotenv()

NEWBOOK_API_BASE = os.getenv("NEWBOOK_API_BASE")
NEWBOOK_API_TOKEN = os.getenv("NEWBOOK_API_TOKEN")
API_KEY = os.getenv("API_KEY")
REGION = os.getenv("REGION")

USERNAME = os.getenv("NEWBOOK_USERNAME")
PASSWORD = os.getenv("NEWBOOK_PASSWORD")
GHL_CLIENT_ID = os.getenv("GHL_CLIENT_ID")
GHL_CLIENT_SECRET = os.getenv("GHL_CLIENT_SECRET")
GHL_API_KEY = os.getenv("GHL_API_KEY")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID") 
GHL_API_BASE = os.getenv("GHL_API_BASE")
GHL_PIPELINE_ID = os.getenv("GHL_PIPELINE_ID")
GHL_STAGE_ID = os.getenv("GHL_STAGE_ID")
GHL_AUTHORIZATION_CODE = os.getenv("GHL_AUTHORIZATION_CODE")
GHL_REDIRECT_URI = os.getenv("GHL_REDIRECT_URI")
GHL_CONTACT_ID = os.getenv("GHL_CONTACT_ID")
AI_AGENT_KEY = os.getenv("AI_AGENT_KEY")

DBUSERNAME = os.getenv("DBUSERNAME")
DBPASSWORD = os.getenv("DBPASSWORD")
DBHOST = os.getenv("DBHOST")
DATABASENAME = os.getenv("DATABASENAME")

