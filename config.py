# filepath: c:\Users\HP\Desktop\NewBookApi\config.py
import os
from dotenv import load_dotenv

load_dotenv()

NEWBOOK_API_BASE = os.getenv("NEWBOOK_API_BASE")
NEWBOOK_API_TOKEN = os.getenv("NEWBOOK_API_TOKEN")
API_KEY = os.getenv("API_KEY")
REGION = os.getenv("REGION")
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {"instances_5d5a3e706c853fed32092cdb0ad27b4c"}"
}