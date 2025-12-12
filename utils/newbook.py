"""
DEPRECATED: This file is deprecated. All functions have been moved to services/newbook/newbook_service.py

This file is kept for backward compatibility but should not be used in new code.
Please use NewbookService from services.newbook instead.
"""

# Keep NB_HEADERS for any legacy code that might still reference it
import base64
from config.config import USERNAME, PASSWORD

_user_pass = f"{USERNAME}:{PASSWORD}"
_encoded_credentials = base64.b64encode(_user_pass.encode()).decode()

NB_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Basic {_encoded_credentials}",
}

# All other functions have been moved to services/newbook/newbook_service.py
# Use NewbookService.get_tariff_information() instead of get_tariff_information()
# Use NewbookService.create_tariffs_quoted() instead of create_tariffs_quoted()
# Use NewbookService._extract_max_occupancy() instead of extract_max_occupancy()
