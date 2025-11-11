"""
Multi-Location OAuth Token Manager

This module allows you to store and manage OAuth tokens for multiple locations,
enabling Voice AI agent copying across different GoHighLevel sub-accounts.
"""

import mysql.connector
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import requests
from config.config import DBHOST, DBUSERNAME, DBPASSWORD, DATABASENAME, GHL_CLIENT_ID, GHL_CLIENT_SECRET
from utils.logger import get_logger

log = get_logger("MultiLocationTokens")

db_config = {
    "host": DBHOST,
    "user": DBUSERNAME,
    "password": DBPASSWORD,
    "database": DATABASENAME,
    "port": 3306
}


def create_multi_token_table():
    """
    Creates the location_tokens table if it doesn't exist.
    
    Run this once to set up the database structure.
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    query = """
    CREATE TABLE IF NOT EXISTS location_tokens (
        id INT AUTO_INCREMENT PRIMARY KEY,
        location_id VARCHAR(255) UNIQUE NOT NULL,
        location_name VARCHAR(255),
        access_token TEXT NOT NULL,
        refresh_token TEXT NOT NULL,
        expire_in INT NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_location_id (location_id)
    )
    """
    
    cursor.execute(query)
    conn.commit()
    conn.close()
    
    print("✅ location_tokens table created successfully")
    log.info("location_tokens table created")


def store_location_token(location_id: str, tokens: dict, location_name: str = None):
    """
    Store or update OAuth token for a specific location.
    
    Args:
        location_id: The GHL location ID
        tokens: Token dict with access_token, refresh_token, expires_in
        location_name: Optional friendly name for the location
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    query = """
    INSERT INTO location_tokens (location_id, location_name, access_token, refresh_token, expire_in, created_at)
    VALUES (%s, %s, %s, %s, %s, NOW())
    ON DUPLICATE KEY UPDATE
        access_token = VALUES(access_token),
        refresh_token = VALUES(refresh_token),
        expire_in = VALUES(expire_in),
        location_name = VALUES(location_name),
        created_at = NOW()
    """
    
    cursor.execute(query, (
        location_id,
        location_name,
        tokens.get("access_token"),
        tokens.get("refresh_token"),
        tokens.get("expires_in")
    ))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Token stored for location: {location_id} ({location_name or 'N/A'})")
    log.info(f"Token stored for location {location_id}")


def get_location_token(location_id: str) -> Optional[Dict]:
    """
    Get the OAuth token for a specific location.
    
    Args:
        location_id: The GHL location ID
    
    Returns:
        dict with token data, or None if not found
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    query = "SELECT * FROM location_tokens WHERE location_id = %s"
    cursor.execute(query, (location_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    return row


def get_valid_location_token(location_id: str) -> Optional[str]:
    """
    Get a valid access token for a specific location.
    Refreshes if expired.
    
    Args:
        location_id: The GHL location ID
    
    Returns:
        Valid access token, or None if not found
    """
    token_data = get_location_token(location_id)
    
    if not token_data:
        print(f"⚠️  No token found for location: {location_id}")
        log.warning(f"No token found for location {location_id}")
        return None
    
    created_at = token_data["created_at"]
    expire_in = token_data["expire_in"]
    expiry_time = created_at + timedelta(seconds=expire_in)
    
    # Check if token is still valid
    if datetime.now() < expiry_time:
        print(f"✅ Token valid for location: {location_id}")
        return token_data["access_token"]
    else:
        # Token expired, refresh it
        print(f"⏰ Token expired for location: {location_id}, refreshing...")
        return refresh_location_token(location_id)


def refresh_location_token(location_id: str) -> Optional[str]:
    """
    Refresh the OAuth token for a specific location.
    
    Args:
        location_id: The GHL location ID
    
    Returns:
        New access token, or None on error
    """
    token_data = get_location_token(location_id)
    
    if not token_data:
        print(f"❌ Cannot refresh: no token found for location {location_id}")
        return None
    
    token_url = "https://services.leadconnectorhq.com/oauth/token"
    data = {
        "client_id": GHL_CLIENT_ID,
        "client_secret": GHL_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": token_data["refresh_token"]
    }
    
    response = requests.post(token_url, data=data)
    
    if response.status_code != 200:
        print(f"❌ Error refreshing token for {location_id}: {response.text}")
        log.error(f"Failed to refresh token for location {location_id}: {response.text}")
        return None
    
    new_tokens = response.json()
    
    # Store the refreshed token
    store_location_token(location_id, new_tokens, token_data.get("location_name"))
    
    print(f"✅ Token refreshed for location: {location_id}")
    log.info(f"Token refreshed for location {location_id}")
    
    return new_tokens.get("access_token")


def list_all_location_tokens() -> List[Dict]:
    """
    List all stored location tokens.
    
    Returns:
        List of location token records
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    query = "SELECT location_id, location_name, created_at, expire_in FROM location_tokens ORDER BY updated_at DESC"
    cursor.execute(query)
    
    rows = cursor.fetchall()
    conn.close()
    
    # Convert datetime to string for JSON serialization
    for row in rows:
        if row.get('created_at'):
            row['created_at'] = row['created_at'].isoformat()
    
    return rows


def delete_location_token(location_id: str):
    """
    Delete the OAuth token for a specific location.
    
    Args:
        location_id: The GHL location ID
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    query = "DELETE FROM location_tokens WHERE location_id = %s"
    cursor.execute(query, (location_id,))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Token deleted for location: {location_id}")
    log.info(f"Token deleted for location {location_id}")


if __name__ == "__main__":
    # Example: Create the table
    print("\n" + "="*60)
    print("Multi-Location Token Manager - Setup")
    print("="*60)
    
    create_multi_token_table()
    
    print("\n✅ Setup complete!")
    print("\nNext steps:")
    print("1. Run: python authorize_location.py LOCATION_ID")
    print("2. Repeat for each location you want to manage")
    print("\n" + "="*60)

