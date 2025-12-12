# Newbook Instance Database Helpers
import mysql.connector
from config.config import db_config
from .logger import get_logger

log = get_logger("NewbookDB")

def get_newbook_instance(location_id):
    """
    Retrieve Newbook API credentials for a specific location_id.
    Returns: dict with location_id, api_key, park_name or None if not found
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT location_id, api_key, park_name FROM newbook_instances WHERE location_id = %s", (location_id,))
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

def create_newbook_instance(location_id, api_key, park_name):
    """
    Create a new Newbook instance entry.
    Returns: True if successful, False if location_id already exists
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = """
            INSERT INTO newbook_instances (location_id, api_key, park_name)
            VALUES (%s, %s, %s)
        """
        cursor.execute(query, (location_id, api_key, park_name))
        conn.commit()
        conn.close()
        return True
    except mysql.connector.IntegrityError:
        # location_id already exists
        return False
    except Exception as e:
        log.exception(f"Error creating newbook instance: {e}")
        return False

def update_newbook_instance(location_id, api_key=None, park_name=None):
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
    
    if park_name is not None:
        updates.append("park_name = %s")
        params.append(park_name)
    
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

def log_newbook_booking(
    location_id: str,
    park_name: str,
    guest_firstname: str,
    guest_lastname: str,
    guest_email: str,
    guest_phone: str,
    arrival_date: str,
    departure_date: str,
    adults: int = None,
    children: int = None,
    category_id: str = None,
    category_name: str = None,
    amount: float = None,
    booking_id: str = None,
    status: str = None
):
    """
    Log a booking created via Newbook API.
    Returns: True if successful, False otherwise
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = """
            INSERT INTO newbook_booking_logs 
            (location_id, park_name, guest_firstName, guest_lastName, guest_email, 
             guest_phone, arrival_date, departure_date, adults, children, 
             category_id, category_name, amount, booking_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            location_id,
            park_name,
            guest_firstname,
            guest_lastname,
            guest_email,
            guest_phone,
            arrival_date,
            departure_date,
            adults,
            children,
            category_id,
            category_name,
            amount,
            booking_id,
            status
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log.exception(f"Error logging newbook booking: {e}")
        return False

# CRUD operations for booking logs
def get_newbook_booking_log(log_id: int):
    """
    Retrieve a booking log by ID.
    Returns: dict with booking log data or None if not found
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, location_id, park_name, guest_firstName, guest_lastName, 
               guest_email, guest_phone, arrival_date, departure_date, 
               adults, children, category_id, category_name, 
               amount, booking_id, status, created_at, updated_at
        FROM newbook_booking_logs 
        WHERE id = %s
    """, (log_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_all_newbook_booking_logs(location_id: str = None, park_name: str = None, month: int = None, year: int = None):
    """
    Retrieve all booking logs, optionally filtered by location_id, park_name, or month/year.
    Returns: list of dicts with booking log data
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    conditions = []
    params = []
    
    if park_name:
        conditions.append("park_name = %s")
        params.append(park_name)
    
    if location_id:
        conditions.append("location_id = %s")
        params.append(location_id)
    
    if month is not None and year is not None:
        conditions.append("arrival_date IS NOT NULL AND YEAR(arrival_date) = %s AND MONTH(arrival_date) = %s")
        params.extend([year, month])
    
    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    query = f"""
        SELECT id, location_id, park_name, guest_firstName, guest_lastName, 
               guest_email, guest_phone, arrival_date, departure_date, 
               adults, children, category_id, category_name, 
               amount, booking_id, status, created_at, updated_at
        FROM newbook_booking_logs 
        {where_clause}
        ORDER BY created_at DESC
    """
    
    cursor.execute(query, tuple(params) if params else None)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_park_names():
    """
    Retrieve all unique park names from booking logs.
    Returns: list of unique park names (sorted)
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT park_name 
        FROM newbook_booking_logs 
        WHERE park_name IS NOT NULL AND park_name != ''
        ORDER BY park_name ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    # Extract park names from tuples
    return [row[0] for row in rows]

def create_newbook_booking_log(
    location_id: str,
    park_name: str,
    guest_firstname: str,
    guest_lastname: str,
    guest_email: str,
    guest_phone: str,
    arrival_date: str,
    departure_date: str,
    adults: int = None,
    children: int = None,
    category_id: str = None,
    category_name: str = None,
    amount: float = None,
    booking_id: str = None,
    status: str = None
):
    """
    Manually create a booking log entry.
    Returns: dict with the created log entry (including id) or None if failed
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        query = """
            INSERT INTO newbook_booking_logs 
            (location_id, park_name, guest_firstName, guest_lastName, guest_email, 
             guest_phone, arrival_date, departure_date, adults, children, 
             category_id, category_name, amount, booking_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            location_id,
            park_name,
            guest_firstname,
            guest_lastname,
            guest_email,
            guest_phone,
            arrival_date,
            departure_date,
            adults,
            children,
            category_id,
            category_name,
            amount,
            booking_id,
            status
        ))
        log_id = cursor.lastrowid
        conn.commit()
        
        # Fetch the created record
        cursor.execute("""
            SELECT id, location_id, park_name, guest_firstName, guest_lastName, 
                   guest_email, guest_phone, arrival_date, departure_date, 
                   adults, children, category_id, category_name, 
                   amount, booking_id, status, created_at, updated_at
            FROM newbook_booking_logs 
            WHERE id = %s
        """, (log_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        log.exception(f"Error creating newbook booking log: {e}")
        conn.close()
        return None

def update_newbook_booking_log(
    log_id: int,
    location_id: str = None,
    park_name: str = None,
    guest_firstname: str = None,
    guest_lastname: str = None,
    guest_email: str = None,
    guest_phone: str = None,
    arrival_date: str = None,
    departure_date: str = None,
    adults: int = None,
    children: int = None,
    category_id: str = None,
    category_name: str = None,
    amount: float = None,
    booking_id: str = None,
    status: str = None
):
    """
    Update an existing booking log entry.
    Only updates fields that are provided (not None).
    Returns: dict with updated log entry or None if not found
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if location_id is not None:
        updates.append("location_id = %s")
        params.append(location_id)
    if park_name is not None:
        updates.append("park_name = %s")
        params.append(park_name)
    if guest_firstname is not None:
        updates.append("guest_firstName = %s")
        params.append(guest_firstname)
    if guest_lastname is not None:
        updates.append("guest_lastName = %s")
        params.append(guest_lastname)
    if guest_email is not None:
        updates.append("guest_email = %s")
        params.append(guest_email)
    if guest_phone is not None:
        updates.append("guest_phone = %s")
        params.append(guest_phone)
    if arrival_date is not None:
        updates.append("arrival_date = %s")
        params.append(arrival_date)
    if departure_date is not None:
        updates.append("departure_date = %s")
        params.append(departure_date)
    if adults is not None:
        updates.append("adults = %s")
        params.append(adults)
    if children is not None:
        updates.append("children = %s")
        params.append(children)
    if category_id is not None:
        updates.append("category_id = %s")
        params.append(category_id)
    if category_name is not None:
        updates.append("category_name = %s")
        params.append(category_name)
    if amount is not None:
        updates.append("amount = %s")
        params.append(amount)
    if booking_id is not None:
        updates.append("booking_id = %s")
        params.append(booking_id)
    if status is not None:
        updates.append("status = %s")
        params.append(status)
    
    if not updates:
        conn.close()
        return None
    
    params.append(log_id)
    query = f"""
        UPDATE newbook_booking_logs
        SET {', '.join(updates)}
        WHERE id = %s
    """
    cursor.execute(query, params)
    affected = cursor.rowcount
    conn.commit()
    
    if affected > 0:
        # Fetch the updated record
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, location_id, park_name, guest_firstName, guest_lastName, 
                   guest_email, guest_phone, arrival_date, departure_date, 
                   adults, children, category_id, category_name, 
                   amount, booking_id, status, created_at, updated_at
            FROM newbook_booking_logs 
            WHERE id = %s
        """, (log_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    else:
        conn.close()
        return None

def delete_newbook_booking_log(log_id: int):
    """
    Delete a booking log entry.
    Returns: True if successful, False if log_id not found
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM newbook_booking_logs WHERE id = %s", (log_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0