# RMS Instance Database Helpers
import mysql.connector
from cryptography.fernet import Fernet, InvalidToken
import os
from config.config import db_config
from .logger import get_logger

log = get_logger("RmsDB")

# Encryption key for client_pass - uses existing ENCRYPTION_KEY from .env
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")


def _get_cipher():
    """Get Fernet cipher for encryption/decryption"""
    if not ENCRYPTION_KEY:
        log.warning("ENCRYPTION_KEY not set in environment variables")
        return None
    try:
        return Fernet(ENCRYPTION_KEY.encode())
    except Exception as e:
        log.error(f"Error creating cipher: {e}")
        return None


def _decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt an encrypted password.
    If decryption fails (password is plain text), return as-is.
    """
    if not encrypted_password:
        return encrypted_password
    
    cipher = _get_cipher()
    if not cipher:
        # No encryption key, return password as-is
        return encrypted_password
    
    try:
        # Try to decrypt
        decrypted = cipher.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except InvalidToken:
        # Password is not encrypted (plain text), return as-is
        log.info("Password appears to be plain text (not encrypted)")
        return encrypted_password
    except Exception as e:
        # Other error, return as-is
        log.warning(f"Could not decrypt password, using as-is: {e}")
        return encrypted_password


def _encrypt_password(plain_password: str) -> str:
    """Encrypt a plain text password"""
    cipher = _get_cipher()
    if not cipher:
        log.warning("No encryption key available, storing password as plain text")
        return plain_password
    
    try:
        encrypted = cipher.encrypt(plain_password.encode())
        return encrypted.decode()
    except Exception as e:
        log.error(f"Error encrypting password: {e}")
        return plain_password


def get_rms_instance(location_id: str) -> dict | None:
    """
    Retrieve RMS API credentials for a specific location_id.
    Returns: dict with location_id, client_id, client_pass, agent_id or None if not found
    """
    conn = None
    try:
        log.info(f"Looking up RMS instance for location_id: {location_id}")
        print(f"🔍 Looking up RMS instance for location_id: {location_id}")
        print(f"   Database config: host={db_config.get('host')}, database={db_config.get('database')}")
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # First, check what columns exist
        cursor.execute("DESCRIBE rms_instances")
        columns = [row['Field'] for row in cursor.fetchall()]
        print(f"   Table columns: {columns}")
        
        # Build query based on available columns
        select_columns = ['location_id', 'client_id', 'client_pass']
        if 'agent_id' in columns:
            select_columns.append('agent_id')
        if 'park_name' in columns:
            select_columns.append('park_name')
        
        query = f"SELECT {', '.join(select_columns)} FROM rms_instances WHERE location_id = %s"
        print(f"   Query: {query}")
        print(f"   Parameter: {location_id}")
        
        cursor.execute(query, (location_id,))
        row = cursor.fetchone()
        
        if row:
            log.info(f"Found RMS instance: client_id={row.get('client_id')}, agent_id={row.get('agent_id')}")
            print(f"✅ Found RMS instance: client_id={row.get('client_id')}, agent_id={row.get('agent_id')}")
            
            # Handle password - try to decrypt, fall back to plain text
            if row.get('client_pass'):
                original_pass = row['client_pass']
                row['client_pass'] = _decrypt_password(original_pass)
                print(f"✅ Password processed successfully")
            
            # Ensure agent_id exists (default to 0 if not in table)
            if 'agent_id' not in row:
                row['agent_id'] = 0
                print(f"⚠️ agent_id column not found, defaulting to 0")
            
            return row
        else:
            log.warning(f"RMS instance not found for location_id: {location_id}")
            print(f"⚠️ RMS instance not found for location_id: {location_id}")
            
            # Debug: list all location_ids in table
            cursor.execute("SELECT location_id FROM rms_instances")
            all_ids = [r['location_id'] for r in cursor.fetchall()]
            print(f"   Available location_ids in table: {all_ids}")
            
            return None
            
    except mysql.connector.Error as e:
        log.exception(f"MySQL error getting RMS instance: {e}")
        print(f"❌ MySQL error: {e}")
        print(f"   Error code: {e.errno}")
        print(f"   SQL State: {e.sqlstate}")
        return None
    except Exception as e:
        log.exception(f"Error getting RMS instance: {e}")
        print(f"❌ Error getting RMS instance: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if conn:
            conn.close()


def get_all_rms_instances() -> list[dict]:
    """
    Retrieve all RMS instances.
    Returns: list of dicts with location_id, client_id, client_pass, agent_id
    """
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Check what columns exist
        cursor.execute("DESCRIBE rms_instances")
        columns = [row['Field'] for row in cursor.fetchall()]
        
        select_columns = ['location_id', 'client_id', 'client_pass']
        if 'agent_id' in columns:
            select_columns.append('agent_id')
        if 'park_name' in columns:
            select_columns.append('park_name')
        
        cursor.execute(f"SELECT {', '.join(select_columns)} FROM rms_instances")
        rows = cursor.fetchall()
        
        # Process passwords
        for row in rows:
            if row.get('client_pass'):
                row['client_pass'] = _decrypt_password(row['client_pass'])
            if 'agent_id' not in row:
                row['agent_id'] = 0
        
        return rows
    except Exception as e:
        log.exception(f"Error getting all RMS instances: {e}")
        return []
    finally:
        if conn:
            conn.close()


def create_rms_instance(location_id: str, client_id: int, client_pass: str, agent_id: int) -> bool:
    """
    Create a new RMS instance entry.
    The client_pass will be encrypted before storing (if ENCRYPTION_KEY is set).
    Returns: True if successful, False if location_id already exists or error
    """
    conn = None
    try:
        # Encrypt the password before storing
        encrypted_pass = _encrypt_password(client_pass)
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = """
            INSERT INTO rms_instances (location_id, client_id, client_pass, agent_id)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (location_id, client_id, encrypted_pass, agent_id))
        conn.commit()
        log.info(f"Created RMS instance for location_id: {location_id}")
        return True
    except mysql.connector.IntegrityError:
        log.warning(f"RMS instance already exists for location_id: {location_id}")
        return False
    except Exception as e:
        log.exception(f"Error creating RMS instance: {e}")
        return False
    finally:
        if conn:
            conn.close()


def update_rms_instance(location_id: str, client_id: int = None, client_pass: str = None, agent_id: int = None, park_name: str = None) -> bool:
    """
    Update an existing RMS instance.
    Only updates fields that are provided (not None).
    If client_pass is provided, it will be encrypted before storing.
    Returns: True if successful, False if location_id not found or error
    """
    conn = None
    try:
        updates = []
        params = []
        
        if client_id is not None:
            updates.append("client_id = %s")
            params.append(client_id)
        
        if client_pass is not None:
            updates.append("client_pass = %s")
            params.append(_encrypt_password(client_pass))
        
        if agent_id is not None:
            updates.append("agent_id = %s")
            params.append(agent_id)
        
        if park_name is not None:
            updates.append("park_name = %s")
            params.append(park_name)
        
        if not updates:
            return False
        
        params.append(location_id)
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = f"""
            UPDATE rms_instances
            SET {', '.join(updates)}
            WHERE location_id = %s
        """
        cursor.execute(query, params)
        affected = cursor.rowcount
        conn.commit()
        
        if affected > 0:
            log.info(f"Updated RMS instance for location_id: {location_id}")
        return affected > 0
    except Exception as e:
        log.exception(f"Error updating RMS instance: {e}")
        return False
    finally:
        if conn:
            conn.close()


def set_current_rms_instance(location_id: str) -> bool:
    """
    Set the current RMS instance by loading credentials from database
    and setting them as environment variables.
    Returns: True if successful, False if location_id not found
    """
    instance = get_rms_instance(location_id)
    if not instance:
        log.warning(f"Cannot set current RMS instance - location_id not found: {location_id}")
        return False
    
    # Set environment variables for RMS services to use
    os.environ['RMS_LOCATION_ID'] = instance['location_id']
    os.environ['RMS_CLIENT_ID'] = str(instance['client_id'])
    os.environ['RMS_CLIENT_PASS'] = instance['client_pass']
    os.environ['RMS_AGENT_ID'] = str(instance.get('agent_id', 0))
    
    log.info(f"Set current RMS instance to location_id: {location_id}")
    print(f"✅ Set current RMS instance to location_id: {location_id}")
    return True


def delete_rms_instance(location_id: str) -> bool:
    """
    Delete an RMS instance.
    Returns: True if successful, False if location_id not found or error
    """
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rms_instances WHERE location_id = %s", (location_id,))
        affected = cursor.rowcount
        conn.commit()
        
        if affected > 0:
            log.info(f"Deleted RMS instance for location_id: {location_id}")
        return affected > 0
    except Exception as e:
        log.exception(f"Error deleting RMS instance: {e}")
        return False
    finally:
        if conn:
            conn.close()



def log_rms_booking(
    location_id: str,
    park_name: str,
    guest_firstName: str,
    guest_lastName: str,
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
    Log a booking created via RMS API.
    Returns: True if successful, False otherwise
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = """
            INSERT INTO rms_booking_logs 
            (location_id, park_name, guest_firstName, guest_lastName, guest_email, 
             guest_phone, arrival_date, departure_date, adults, children, 
             category_id, category_name, amount, booking_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            location_id,
            park_name,
            guest_firstName,
            guest_lastName,
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
        log.info(f"Logged RMS booking: {booking_id} - adults={adults}, children={children}, category={category_name}, amount=${amount}")
        return True
    except Exception as e:
        log.exception(f"Error logging RMS booking: {e}")
        return False


def get_rms_booking_log(log_id: int):
    """
    Retrieve a booking log by ID.
    Returns: dict with booking log data or None if not found
    """
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, location_id, park_name, guest_firstName, guest_lastName, 
                   guest_email, guest_phone, arrival_date, departure_date, 
                   adults, children, category_id, category_name, amount,
                   booking_id, status, created_at, updated_at
            FROM rms_booking_logs 
            WHERE id = %s
        """, (log_id,))
        row = cursor.fetchone()
        return row
    except Exception as e:
        log.exception(f"Error getting RMS booking log: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_all_rms_booking_logs(location_id: str = None, park_name: str = None, month: int = None, year: int = None):
    """
    Retrieve all booking logs, optionally filtered by location_id, park_name, or month/year.
    Returns: list of dicts with booking log data
    """
    conn = None
    try:
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
                   adults, children, category_id, category_name, amount,
                   booking_id, status, created_at, updated_at
            FROM rms_booking_logs 
            {where_clause}
            ORDER BY created_at DESC
        """
        
        cursor.execute(query, tuple(params) if params else None)
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        log.exception(f"Error getting all RMS booking logs: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_all_rms_park_names():
    """
    Retrieve all unique park names from booking logs.
    Returns: list of unique park names (sorted)
    """
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT park_name 
            FROM rms_booking_logs 
            WHERE park_name IS NOT NULL AND park_name != ''
            ORDER BY park_name ASC
        """)
        rows = cursor.fetchall()
        return [row[0] for row in rows]
    except Exception as e:
        log.exception(f"Error getting RMS park names: {e}")
        return []
    finally:
        if conn:
            conn.close()


def create_rms_booking_log(
    location_id: str,
    park_name: str,
    guest_firstName: str,
    guest_lastName: str,
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
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        query = """
            INSERT INTO rms_booking_logs 
            (location_id, park_name, guest_firstName, guest_lastName, guest_email, 
             guest_phone, arrival_date, departure_date, adults, children, 
             category_id, category_name, amount, booking_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            location_id,
            park_name,
            guest_firstName,
            guest_lastName,
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
                   adults, children, category_id, category_name, amount,
                   booking_id, status, created_at, updated_at
            FROM rms_booking_logs 
            WHERE id = %s
        """, (log_id,))
        result = cursor.fetchone()
        return result
    except Exception as e:
        log.exception(f"Error creating RMS booking log: {e}")
        return None
    finally:
        if conn:
            conn.close()


def update_rms_booking_log(
    log_id: int,
    location_id: str = None,
    park_name: str = None,
    guest_firstName: str = None,
    guest_lastName: str = None,
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
    conn = None
    try:
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
        if guest_firstName is not None:
            updates.append("guest_firstName = %s")
            params.append(guest_firstName)
        if guest_lastName is not None:
            updates.append("guest_lastName = %s")
            params.append(guest_lastName)
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
            return None
        
        params.append(log_id)
        query = f"""
            UPDATE rms_booking_logs
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
                       adults, children, category_id, category_name, amount,
                       booking_id, status, created_at, updated_at
                FROM rms_booking_logs 
                WHERE id = %s
            """, (log_id,))
            result = cursor.fetchone()
            return result
        else:
            return None
    except Exception as e:
        log.exception(f"Error updating RMS booking log: {e}")
        return None
    finally:
        if conn:
            conn.close()


def delete_rms_booking_log(log_id: int):
    """
    Delete a booking log entry.
    Returns: True if successful, False if log_id not found
    """
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rms_booking_logs WHERE id = %s", (log_id,))
        affected = cursor.rowcount
        conn.commit()
        return affected > 0
    except Exception as e:
        log.exception(f"Error deleting RMS booking log: {e}")
        return False
    finally:
        if conn:
            conn.close()