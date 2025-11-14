# Newbook Instance Database Helpers
import mysql.connector
from config.config import db_config
from .logger import get_logger

log = get_logger("NewbookDB")

def get_newbook_instance(location_id):
    """
    Retrieve Newbook API credentials for a specific location_id.
    Returns: dict with location_id, api_key, region or None if not found
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT location_id, api_key FROM newbook_instances WHERE location_id = %s", (location_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_all_newbook_instances():
    """
    Retrieve all Newbook instances.
    Returns: list of dicts with location_id, api_key, region
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT location_id, api_key, region FROM newbook_instances")
    rows = cursor.fetchall()
    conn.close()
    return rows

def create_newbook_instance(location_id, api_key):
    """
    Create a new Newbook instance entry.
    Returns: True if successful, False if location_id already exists
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = """
            INSERT INTO newbook_instances (location_id, api_key)
            VALUES (%s, %s)
        """
        cursor.execute(query, (location_id, api_key))
        conn.commit()
        conn.close()
        return True
    except mysql.connector.IntegrityError:
        # location_id already exists
        return False
    except Exception as e:
        log.exception(f"Error creating newbook instance: {e}")
        return False

def update_newbook_instance(location_id, api_key=None):
    """
    Update an existing Newbook instance.
    Only updates fields that are provided (not None).
    Returns: True if successful, False if location_id not found
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if api_key is not None:
        updates.append("api_key = %s")
        params.append(api_key)
    
    if not updates:
        conn.close()
        return False
    
    params.append(location_id)
    query = f"""
        UPDATE newbook_instances
        SET {', '.join(updates)}
        WHERE location_id = %s
    """
    cursor.execute(query, params)
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def delete_newbook_instance(location_id):
    """
    Delete a Newbook instance.
    Returns: True if successful, False if location_id not found
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM newbook_instances WHERE location_id = %s", (location_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0