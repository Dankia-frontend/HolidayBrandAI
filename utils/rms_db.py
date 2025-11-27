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


def update_rms_instance(location_id: str, client_id: int = None, client_pass: str = None, agent_id: int = None) -> bool:
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