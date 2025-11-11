"""
Database helper functions for park configurations.
This module provides CRUD operations for managing park-specific configurations
including Newbook API credentials and GHL pipeline/stage IDs.
"""
import mysql.connector
from typing import Optional, List, Dict, Any
from config.config import DBUSERNAME, DBPASSWORD, DBHOST, DATABASENAME
from utils.logger import get_logger

log = get_logger("ParkConfigDB")

db_config = {
    "host": DBHOST,
    "user": DBUSERNAME,
    "password": DBPASSWORD,
    "database": DATABASENAME,
    "port": 3306
}


def get_db_connection():
    """Establish and return a database connection."""
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as e:
        log.error(f"Database connection error: {e}")
        raise


def create_park_configurations_table():
    """
    Creates the park_configurations table if it doesn't exist.
    This table stores location-specific configuration for different parks.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        create_table_query = """
        CREATE TABLE IF NOT EXISTS park_configurations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            location_id VARCHAR(255) NOT NULL UNIQUE,
            park_name VARCHAR(255) NOT NULL,
            newbook_api_token VARCHAR(500) NOT NULL,
            newbook_api_key VARCHAR(500) NOT NULL,
            newbook_region VARCHAR(100) NOT NULL,
            ghl_pipeline_id VARCHAR(255) NOT NULL,
            
            -- GHL Stage IDs
            stage_arriving_soon VARCHAR(255),
            stage_arriving_today VARCHAR(255),
            stage_arrived VARCHAR(255),
            stage_departing_today VARCHAR(255),
            stage_departed VARCHAR(255),
            
            -- Metadata
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_location_id (location_id),
            INDEX idx_is_active (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        cursor.execute(create_table_query)
        conn.commit()
        log.info("park_configurations table created successfully or already exists")
        print("✅ park_configurations table created successfully")
        return True
        
    except mysql.connector.Error as e:
        log.error(f"Error creating park_configurations table: {e}")
        print(f"❌ Error creating table: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def add_park_configuration(
    location_id: str,
    park_name: str,
    newbook_api_token: str,
    newbook_api_key: str,
    newbook_region: str,
    ghl_pipeline_id: str,
    stage_arriving_soon: Optional[str] = None,
    stage_arriving_today: Optional[str] = None,
    stage_arrived: Optional[str] = None,
    stage_departing_today: Optional[str] = None,
    stage_departed: Optional[str] = None
) -> bool:
    """
    Add a new park configuration to the database.
    
    Args:
        location_id: GHL location ID
        park_name: Human-readable park name
        newbook_api_token: Newbook API token for this park
        newbook_api_key: Newbook API key for this park
        newbook_region: Newbook region code
        ghl_pipeline_id: GHL pipeline ID for this park
        stage_arriving_soon: Stage ID for "arriving soon" bookings
        stage_arriving_today: Stage ID for "arriving today" bookings
        stage_arrived: Stage ID for "arrived" bookings
        stage_departing_today: Stage ID for "departing today" bookings
        stage_departed: Stage ID for "departed" bookings
    
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        insert_query = """
        INSERT INTO park_configurations (
            location_id, park_name, newbook_api_token, newbook_api_key, 
            newbook_region, ghl_pipeline_id, stage_arriving_soon, 
            stage_arriving_today, stage_arrived, stage_departing_today, stage_departed
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            location_id, park_name, newbook_api_token, newbook_api_key,
            newbook_region, ghl_pipeline_id, stage_arriving_soon,
            stage_arriving_today, stage_arrived, stage_departing_today, stage_departed
        ))
        
        conn.commit()
        log.info(f"Park configuration added successfully for location_id: {location_id}")
        print(f"✅ Park configuration added for {park_name} (location_id: {location_id})")
        return True
        
    except mysql.connector.IntegrityError as e:
        log.error(f"Duplicate location_id: {location_id}")
        print(f"❌ Error: Location ID {location_id} already exists")
        return False
    except mysql.connector.Error as e:
        log.error(f"Error adding park configuration: {e}")
        print(f"❌ Error adding park configuration: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def update_park_configuration(
    location_id: str,
    park_name: Optional[str] = None,
    newbook_api_token: Optional[str] = None,
    newbook_api_key: Optional[str] = None,
    newbook_region: Optional[str] = None,
    ghl_pipeline_id: Optional[str] = None,
    stage_arriving_soon: Optional[str] = None,
    stage_arriving_today: Optional[str] = None,
    stage_arrived: Optional[str] = None,
    stage_departing_today: Optional[str] = None,
    stage_departed: Optional[str] = None,
    is_active: Optional[bool] = None
) -> bool:
    """
    Update an existing park configuration.
    Only provided fields will be updated.
    
    Args:
        location_id: GHL location ID (required to identify the record)
        Other args: Optional fields to update
    
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build dynamic update query based on provided fields
        update_fields = []
        values = []
        
        if park_name is not None:
            update_fields.append("park_name = %s")
            values.append(park_name)
        if newbook_api_token is not None:
            update_fields.append("newbook_api_token = %s")
            values.append(newbook_api_token)
        if newbook_api_key is not None:
            update_fields.append("newbook_api_key = %s")
            values.append(newbook_api_key)
        if newbook_region is not None:
            update_fields.append("newbook_region = %s")
            values.append(newbook_region)
        if ghl_pipeline_id is not None:
            update_fields.append("ghl_pipeline_id = %s")
            values.append(ghl_pipeline_id)
        if stage_arriving_soon is not None:
            update_fields.append("stage_arriving_soon = %s")
            values.append(stage_arriving_soon)
        if stage_arriving_today is not None:
            update_fields.append("stage_arriving_today = %s")
            values.append(stage_arriving_today)
        if stage_arrived is not None:
            update_fields.append("stage_arrived = %s")
            values.append(stage_arrived)
        if stage_departing_today is not None:
            update_fields.append("stage_departing_today = %s")
            values.append(stage_departing_today)
        if stage_departed is not None:
            update_fields.append("stage_departed = %s")
            values.append(stage_departed)
        if is_active is not None:
            update_fields.append("is_active = %s")
            values.append(is_active)
        
        if not update_fields:
            log.warning("No fields provided for update")
            return False
        
        values.append(location_id)
        update_query = f"""
        UPDATE park_configurations 
        SET {', '.join(update_fields)}
        WHERE location_id = %s
        """
        
        cursor.execute(update_query, values)
        conn.commit()
        
        if cursor.rowcount == 0:
            log.warning(f"No park configuration found for location_id: {location_id}")
            print(f"⚠️ No configuration found for location_id: {location_id}")
            return False
        
        log.info(f"Park configuration updated for location_id: {location_id}")
        print(f"✅ Park configuration updated for location_id: {location_id}")
        return True
        
    except mysql.connector.Error as e:
        log.error(f"Error updating park configuration: {e}")
        print(f"❌ Error updating park configuration: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_park_configuration(location_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve park configuration by location_id.
    
    Args:
        location_id: GHL location ID
    
    Returns:
        dict: Park configuration data or None if not found
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT * FROM park_configurations 
        WHERE location_id = %s AND is_active = TRUE
        """
        
        cursor.execute(query, (location_id,))
        result = cursor.fetchone()
        
        if result:
            log.info(f"Park configuration retrieved for location_id: {location_id}")
            return result
        else:
            log.warning(f"No active park configuration found for location_id: {location_id}")
            return None
        
    except mysql.connector.Error as e:
        log.error(f"Error retrieving park configuration: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_all_park_configurations(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Retrieve all park configurations.
    
    Args:
        include_inactive: If True, includes inactive configurations
    
    Returns:
        list: List of park configuration dictionaries
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if include_inactive:
            query = "SELECT * FROM park_configurations ORDER BY park_name"
        else:
            query = "SELECT * FROM park_configurations WHERE is_active = TRUE ORDER BY park_name"
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        log.info(f"Retrieved {len(results)} park configurations")
        return results
        
    except mysql.connector.Error as e:
        log.error(f"Error retrieving park configurations: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def delete_park_configuration(location_id: str, soft_delete: bool = True) -> bool:
    """
    Delete or deactivate a park configuration.
    
    Args:
        location_id: GHL location ID
        soft_delete: If True, sets is_active to False; if False, deletes the record
    
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if soft_delete:
            query = "UPDATE park_configurations SET is_active = FALSE WHERE location_id = %s"
            action = "deactivated"
        else:
            query = "DELETE FROM park_configurations WHERE location_id = %s"
            action = "deleted"
        
        cursor.execute(query, (location_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            log.warning(f"No park configuration found for location_id: {location_id}")
            print(f"⚠️ No configuration found for location_id: {location_id}")
            return False
        
        log.info(f"Park configuration {action} for location_id: {location_id}")
        print(f"✅ Park configuration {action} for location_id: {location_id}")
        return True
        
    except mysql.connector.Error as e:
        log.error(f"Error deleting park configuration: {e}")
        print(f"❌ Error: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# Initialize table on module import (optional - can be run separately)
if __name__ == "__main__":
    print("Creating park_configurations table...")
    create_park_configurations_table()

