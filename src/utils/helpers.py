# Assuming this is in utils/helpers.py

import uuid
import sys
import os
# Keep the import as datetime.datetime if that's how you prefer,
# but 'from datetime import datetime' then using datetime.now() is standard.
from datetime import datetime
import sqlite3
import logging
import random
import string
# Import DatabaseManager if log_action uses it directly and is not in the same file
# from database_operations.database_manager import DatabaseManager

def get_app_base_dir():
    if getattr(sys, 'frozen', False):
        # The application is frozen
        return os.path.dirname(sys.executable)
    else:
        # The application is running from a .py file
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate_acc_no():
    """Generates a unique account number (acc_no) as TEXT."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    unique_id = str(uuid.uuid4())[:8]
    return f"KM{timestamp}-{unique_id.upper()}"

# Map common action types to default object types (optional, but helpful)
# You might need to adjust this mapping based on your specific actions
ACTION_OBJECT_TYPE_MAP = {
    'ADD_LEARNER': 'Learner',
    'UPDATE_LEARNER': 'Learner',
    'DELETE_LEARNER': 'Learner', # Example if you add this
    'PAUSE_BILLING': 'Learner',
    'RESUME_BILLING': 'Learner',
    'ADD_PAYMENT': 'Payment',
    'UPDATE_PAYMENT': 'Payment',
    'DELETE_PAYMENT': 'Payment',
    'CANCEL_PAYMENT': 'Payment', # <<< FIX: Added this line for consistency
    'ADD_FAMILY': 'Family',
    'UPDATE_FAMILY': 'Family',
    'DELETE_FAMILY': 'Family',
    'LOGIN': 'User',
    'LOGOUT': 'User',
    # Add mappings for other action types as needed
}


def log_action(db_manager, user_id, action_type, object_id=None, details="", object_type=None):
    """
    Logs an action performed by a user into the AuditLog table.

    Args:
        db_manager: Instance of DatabaseManager.
        user_id: The ID of the user performing the action.
        action_type: A string describing the action (e.g., 'ADD_LEARNER', 'LOGIN').
        object_id: The ID of the object affected by the action (e.g., learner acc_no, family_id). Can be None.
        details: Optional string providing more context about the action.
        object_type: Optional string indicating the type of object (e.g., 'Learner', 'Family').
                     If None, attempts to infer from action_type using ACTION_OBJECT_TYPE_MAP.
    """
    conn = None  # Initialize conn to None
    try:
        # Get timestamp. Using the DB's default is another option by omitting timestamp from INSERT.
        # Using datetime.now().isoformat() is fine as it's stored as TEXT.
        # timestamp = datetime.now().isoformat(sep=' ', timespec='seconds') # Keep this format if you like spaces
        # Or a more standard ISO format:
        timestamp = datetime.now().isoformat(timespec='milliseconds')

        # Infer object_type if not provided
        inferred_object_type = object_type if object_type is not None else ACTION_OBJECT_TYPE_MAP.get(action_type, None)

        # Ensure object_id is stored as text or NULL
        object_id_str = str(object_id) if object_id is not None else None

        conn = db_manager.get_connection() # Use get_connection for consistency
        cursor = conn.cursor()

        # FIX: Changed ActionLog to AuditLog
        # FIX: Added object_type column to the insert
        cursor.execute("""
            INSERT INTO AuditLog (user_id, action_type, object_type, object_id, timestamp, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, action_type, inferred_object_type, object_id_str, timestamp, details))

        conn.commit()
        # logging.debug(f"Audit log successful: User {user_id}, Action: {action_type}, Object Type: {inferred_object_type}, Object ID: {object_id_str}") # Optional debug log

    except sqlite3.Error as e:
        # This is a critical error as logging itself failed
        logging.error(f"FATAL ERROR: Failed to write audit log entry: {e}", exc_info=True)
        logging.error(f"Log details: User: {user_id}, Action: {action_type}, Object ID: {object_id_str}, Details: {details}")
    except Exception as e:
        logging.error(f"FATAL ERROR: Unexpected error writing audit log entry: {e}", exc_info=True)
        logging.error(f"Log details: User: {user_id}, Action: {action_type}, Object ID: {object_id_str}, Details: {details}")
    finally:
        # Ensure pooled connection handle is released.
        if conn:
            try:
                conn.close()
            except Exception:
                pass
