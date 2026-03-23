# database_operations/learner_operations.py
import logging
import sqlite3
from datetime import datetime, date  # Update import to be explicit
from utils.helpers import generate_acc_no, log_action

# --- Data Fetching Functions ---

def fetch_all_payment_options_data(db_manager):
    """Fetches all payment options grouped by grade and subjects."""
    options_cache = {}
    try:
        query = "SELECT grade, subjects_count, option_name FROM PaymentOptions ORDER BY grade, subjects_count, option_name"
        all_options = db_manager.execute_query(query, fetchall=True)
        if all_options:
            for grade, subjects, option in all_options:
                if grade not in options_cache: options_cache[grade] = {}
                if subjects not in options_cache[grade]: options_cache[grade][subjects] = []
                options_cache[grade][subjects].append(option)
        return options_cache
    except sqlite3.Error as e:
        # Let the caller handle the UI part (e.g., QMessageBox)
        logging.exception("Error fetching payment options:") # Log exception
        raise sqlite3.Error(f"Error fetching payment options: {e}")

def fetch_all_payment_terms_data(db_manager):
    """Fetches all payment terms (ID and Name)."""
    terms_cache = {}
    try:
        query = "SELECT term_id, term_name FROM PaymentTerms ORDER BY term_name"
        all_terms = db_manager.execute_query(query, fetchall=True)
        if all_terms:
            for term_id, term_name in all_terms:
                terms_cache[term_name] = {'id': term_id}  # Store as dictionary with 'id' key
        return terms_cache
    except sqlite3.Error as e:
        logging.exception("Error fetching payment terms:") # Log exception
        raise sqlite3.Error(f"Error fetching payment terms: {e}")

def fetch_all_families_data(db_manager):
    """Fetches all families (ID and Name)."""
    families_cache = {}
    try:
        query = "SELECT family_id, family_name FROM Families ORDER BY family_name"
        all_families = db_manager.execute_query(query, fetchall=True)
        if all_families:
            for family_id, family_name in all_families:
                # Use "(No Name)" in the UI if name is empty, but store ID correctly
                families_cache[family_name or "(No Name)"] = family_id
        return families_cache
    except sqlite3.Error as e:
        logging.exception("Error fetching families:") # Log exception
        raise sqlite3.Error(f"Error fetching families: {e}")

def fetch_learner_details(db_manager, acc_no):
    """Fetches detailed learner data including parent/guardian info."""
    try:
        query = """SELECT
                       s.name, s.surname, s.date_of_birth, s.gender, s.country_code, s.contact_number, s.email,
                       COALESCE(s.grade, 1) as grade, s.subjects_count, s.payment_option,
                       s.is_new_learner, s.apply_admission_fee,
                       -- po.term_id removed, will be fetched from LearnerPayments
                       f.family_id,
                       p1.title AS p1_title, p1.name AS p1_name, p1.surname AS p1_surname, p1.country_code AS p1_code, p1.contact_number AS p1_contact, p1.email AS p1_email,
                       p2.title AS p2_title, p2.name AS p2_name, p2.surname AS p2_surname, p2.country_code AS p2_code, p2.contact_number AS p2_contact, p2.email AS p2_email,
                       g.title AS g_title, g.name AS g_name, g.surname AS g_surname, g.country_code AS g_code, g.contact_number AS g_contact, g.email AS g_email
                   FROM Learners s
                   LEFT JOIN Parents p1 ON s.parent_id = p1.id
                   LEFT JOIN Parents p2 ON s.parent2_id = p2.id
                   LEFT JOIN Parents g ON s.guardian_id = g.id
                   LEFT JOIN PaymentOptions po ON s.payment_option = po.option_name AND s.subjects_count = po.subjects_count AND s.grade = po.grade -- Keep the join to retrieve adm_reg_fee and monthly_fee
                   LEFT JOIN Families f ON s.family_id = f.family_id
                   WHERE s.acc_no = ?"""
        data = db_manager.execute_query(query, (acc_no,), fetchone=True)
        if not data:
            raise ValueError(f"Learner {acc_no} not found.")  # Use ValueError for not found
        return data
    except sqlite3.Error as e:
        logging.exception(f"Error loading learner data for {acc_no}:") # Log exception
        raise sqlite3.Error(f"Error loading learner data: {e}")
    except Exception as e:
        logging.exception(f"Unexpected error loading learner data for {acc_no}:") # Log exception
        raise Exception(f"Unexpected error loading learner data: {e}")

def fetch_payment_options(db_manager):
    """Fetches all payment options."""
    query = "SELECT id, option_name, subjects_count, grade, adm_reg_fee, monthly_fee FROM PaymentOptions"
    try:
        return db_manager.execute_query(query, fetchall=True)
    except Exception as e:
        logging.exception("Error fetching payment options:") # Log exception
        raise # Re-raise

# --- Data Modification Functions ---

def _find_or_create_parent_record(cursor, parent_data):
    """
    Finds a parent by contact or creates a new one within a transaction.
    Returns parent ID or None if essential data is missing.
    Raises sqlite3.Error on database issues.
    """
    # Check if essential data for finding/creating is present
    if not parent_data or not parent_data.get('contact_number') or not parent_data.get('country_code') or not parent_data.get('name') or not parent_data.get('surname'):
        return None # Cannot find/create without essential info

    try:
        find_p = "SELECT id FROM Parents WHERE country_code = ? AND contact_number = ?"
        cursor.execute(find_p, (parent_data['country_code'], parent_data['contact_number']))
        parent = cursor.fetchone()
        p_id = None
        if parent:
            p_id = parent[0]
            # Update existing parent record only if necessary fields are provided
            update_fields = {k: v for k, v in parent_data.items() if k in ['title', 'name', 'surname', 'email'] and v is not None and v != ''}
            if update_fields:
                set_clause = ", ".join([f"{key} = ?" for key in update_fields.keys()])
                params = list(update_fields.values()) + [p_id]
                upd_p = f"UPDATE Parents SET {set_clause} WHERE id = ?"
                cursor.execute(upd_p, params)
        else:
            # Insert new parent record - ensure all required DB fields are present
            required_db_fields = ['name', 'surname', 'country_code', 'contact_number']
            if not all(parent_data.get(f) for f in required_db_fields):
                 # Log or handle this case? For now, return None as it indicates incomplete data for creation.
                 logging.warning(f"Skipping insert for parent due to missing required fields: {parent_data}") # Use logging
                 return None

            insert_data = {
                'title': parent_data.get('title') or None,
                'name': parent_data['name'],
                'surname': parent_data['surname'],
                'country_code': parent_data['country_code'],
                'contact_number': parent_data['contact_number'],
                'email': parent_data.get('email') or None
            }
            cols = ", ".join(insert_data.keys())
            vals = ", ".join(["?"] * len(insert_data))
            ins_p = f"INSERT INTO Parents ({cols}) VALUES ({vals})"
            cursor.execute(ins_p, tuple(insert_data.values()))
            p_id = cursor.lastrowid
        return p_id
    except sqlite3.Error as e:
        # Re-raise the error to be handled by the transaction management
        logging.exception("Database error during parent find/create:") # Log exception
        raise sqlite3.Error(f"Database error during parent find/create: {e}")


def insert_new_learner(db_manager, current_user_id, learner_data, parent1_data, parent2_data, guardian_data, term_id):
    """
    Inserts a new learner and associated parent/guardian records within a transaction.
    Handles finding/creating parents.
    Raises sqlite3.Error or Exception on failure.
    Returns the new account number on success.
    """
    conn = None
    try:
        conn = db_manager._connect()
        cursor = conn.cursor()
        cursor.execute("BEGIN")

        # Find or Create Parents/Guardian using the helper
        p1_id = _find_or_create_parent_record(cursor, parent1_data)
        g_id = _find_or_create_parent_record(cursor, guardian_data)

        # Ensure at least one of Parent 1 or Guardian was successfully created/found
        if not p1_id and not g_id:
             raise ValueError("Validation Error: Either Parent 1 or Guardian details are required and must be valid.")

        p2_id = _find_or_create_parent_record(cursor, parent2_data) # Optional

        # Prepare Learner Data
        acc = generate_acc_no()
        learner_data['acc_no'] = acc

        # Handle email field - ensure it's None if empty
        if 'email' in learner_data and not learner_data['email']:
            learner_data['email'] = None

        # --- Modified Logic ---
        # Prioritize Parent 2 if provided, otherwise use Parent 1, otherwise use Guardian
        if p2_id:
            learner_data['parent_id'] = p2_id  # Make second parent the primary one
            learner_data['parent2_id'] = p1_id  # First parent becomes secondary
            learner_data['guardian_id'] = None # If parent_id is set, guardian_id should be null
        elif p1_id:
            learner_data['parent_id'] = p1_id
            learner_data['parent2_id'] = None
            learner_data['guardian_id'] = None # If parent_id is set, guardian_id should be null
        elif g_id:
            learner_data['parent_id'] = g_id # Use Guardian ID for parent_id if no parents
            learner_data['parent2_id'] = None
            learner_data['guardian_id'] = None # Keep guardian_id NULL as primary link is via parent_id now
        else:
             # This case should be caught by the check above, but added for safety
             raise ValueError("Internal Error: No valid parent or guardian ID found.")

        # Override parent2_id if we have both parents
        if p1_id and p2_id:
            learner_data['parent2_id'] = p1_id

        # Insert Learner
        cols = ", ".join(learner_data.keys())
        vals = ", ".join(["?"] * len(learner_data))
        ins_s = f"INSERT INTO Learners ({cols}) VALUES ({vals})"
        cursor.execute(ins_s, tuple(learner_data.values()))

        conn.commit()

        return acc # Return the new account number

    except (sqlite3.Error, ValueError, Exception) as e:
        if conn: conn.rollback()
        logging.exception("Error inserting new learner:") # Log exception
        raise e
    finally:
        if conn: conn.close()

def update_existing_learner(db_manager, current_user_id, acc_no, learner_data, parent1_data, parent2_data, guardian_data, term_id):
    """
    Updates an existing learner and associated parent/guardian records within a transaction.
    Handles finding/creating parents.
    Raises sqlite3.Error or Exception on failure.
    """
    conn = None
    try:
        conn = db_manager._connect()
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("BEGIN")

        # Get current parent/guardian IDs for comparison/update
        cursor.execute("SELECT parent_id, parent2_id, guardian_id FROM Learners WHERE acc_no = ?", (acc_no,))
        res = cursor.fetchone()
        if not res: raise ValueError(f"Learner {acc_no} not found for update.")
        current_p1_id, current_p2_id, current_g_id = res

        # Handle email field - ensure it's None if empty
        if 'email' in learner_data and not learner_data['email']:
            learner_data['email'] = None

        # --- Update/Create Parent 1 ---
        # If parent1_data is provided (name not empty), try to find/create. Otherwise, it implies removing/clearing P1.
        p1_id = current_p1_id # Default to current ID
        if parent1_data and parent1_data.get('name'): # Check if P1 data is actually provided
             p1_id = _find_or_create_parent_record(cursor, parent1_data)
        elif parent1_data and not parent1_data.get('name'): # If data structure exists but name is empty, clear P1
             p1_id = None # Clear P1 link
             # NOTE: Existing parent record is intentionally unlinked; cleanup is handled separately.


        # --- Update/Create Guardian ---
        # Similar logic for Guardian
        g_id = current_g_id # Default to current ID
        if guardian_data and guardian_data.get('name'): # Check if Guardian data is actually provided
             g_id = _find_or_create_parent_record(cursor, guardian_data)
        elif guardian_data and not guardian_data.get('name'): # If data structure exists but name is empty, clear Guardian
             g_id = None # Clear Guardian link
             # NOTE: Existing guardian record is intentionally unlinked; cleanup is handled separately.


        # --- Ensure at least one is present (based on the *outcome* of find/create) ---
        # This validation check is crucial after potentially clearing parents/guardians
        if not p1_id and not g_id:
             raise ValueError("Cannot update: Either Parent 1 or Guardian details must be present and valid.")


        # --- Update/Create Parent 2 (Optional) ---
        # Parent 2 is optional, process only if data is provided.
        # If data structure exists but name is empty, clear P2.
        p2_id = current_p2_id # Default to current ID
        if parent2_data and parent2_data.get('name'):
            p2_id = _find_or_create_parent_record(cursor, parent2_data)
        elif parent2_data and not parent2_data.get('name'):
             p2_id = None # Clear P2 link
             # NOTE: Existing parent 2 record is intentionally unlinked; cleanup is handled separately.


        # --- Update Learner Record ---
        # Determine which link gets priority for parent_id column (prioritize Parent 2)
        if p2_id:
            learner_data['parent_id'] = p2_id  # Make second parent the primary one
            learner_data['parent2_id'] = p1_id  # First parent becomes secondary
            learner_data['guardian_id'] = None # If parent_id is set, guardian_id should be null
        elif p1_id:
            learner_data['parent_id'] = p1_id
            learner_data['parent2_id'] = None
            learner_data['guardian_id'] = None # If parent_id is set, guardian_id should be null
        elif g_id:
            learner_data['parent_id'] = g_id # Use Guardian ID for parent_id if no parents
            learner_data['parent2_id'] = None
            learner_data['guardian_id'] = None # Keep guardian_id NULL as primary link is via parent_id now
        else:
             # This case should be caught by the check above, but added for safety
             raise ValueError("Internal Error: No valid parent or guardian ID found after processing updates.")

        # Override parent2_id if we have both parents
        if p1_id and p2_id:
            learner_data['parent2_id'] = p1_id

        learner_update_parts = ", ".join([f"{key} = ?" for key in learner_data.keys()])
        learner_query = f"UPDATE Learners SET {learner_update_parts} WHERE acc_no = ?"
        learner_params = tuple(learner_data.values()) + (acc_no,)
        cursor.execute(learner_query, learner_params)

        conn.commit()

    except (sqlite3.Error, ValueError, Exception) as e:
        if conn: conn.rollback()
        logging.exception(f"Error updating learner {acc_no}:") # Log exception
        raise e
    finally:
        if conn: conn.close()

def add_learner_payment(db_manager, learner_id, term_id, payment_option_id, due_day_of_month=None, billing_start_date=None):
    """Adds a new payment record for a learner, including the due date and billing start date."""
    logging.info(f"Attempting to add LearnerPayment: learner_id={learner_id}, term_id={term_id}, payment_option_id={payment_option_id}, due_day={due_day_of_month}, billing_start={billing_start_date}")
    
    # Validate and fix due_day_of_month
    try:
        due_day = int(due_day_of_month) if due_day_of_month is not None else 1
        due_day = max(1, min(31, due_day))  # Ensure value is between 1 and 31
    except (ValueError, TypeError):
        due_day = 1
        logging.warning(f"Invalid due_day_of_month value: {due_day_of_month}. Defaulting to 1")

    # Updated date handling to ensure January registrations start in February
    try:
        if billing_start_date:
            start_date = datetime.strptime(billing_start_date, '%Y-%m-%d').date()
        else:
            start_date = date.today()

        # If registering in January, set billing start to February 1st
        if start_date.month == 1:
            final_start_date = date(start_date.year, 2, 1).strftime('%Y-%m-%d')
        else:
            final_start_date = start_date.strftime('%Y-%m-%d')

    except Exception as e:
        logging.error(f"Error formatting date: {e}")
        # Fallback to February 1st if in January, otherwise today's date
        today = date.today()
        if today.month == 1:
            final_start_date = f"{today.year}-02-01"
        else:
            final_start_date = f"{today.year}-{today.month:02d}-{today.day:02d}"

    query = """INSERT INTO LearnerPayments (learner_id, term_id, payment_option_id, due_day_of_month, start_date)
               VALUES (?, ?, ?, ?, ?)"""
    
    params = (learner_id, term_id, payment_option_id, due_day, final_start_date)
    try:
        result = db_manager.execute_query(query, params, commit=True)
        logging.info(f"Successfully added LearnerPayment for learner_id={learner_id}")
        return result
    except Exception as e:
        logging.exception(f"Failed to add LearnerPayment for learner_id={learner_id}:") # Log exception
        raise

def update_learner_payment(db_manager, learner_id, term_id=None, payment_option_id=None, due_day_of_month=None):
    """Updates payment details for an existing learner payment record. Finds the most recent one."""
    logging.info(f"Attempting to update LearnerPayment for learner_id={learner_id}: term_id={term_id}, payment_option_id={payment_option_id}, due_day={due_day_of_month}")

    # We expect due_day_of_month to be an integer (1-31) from the UI spinbox
    # Handle potential None or bad values just in case
    try:
        day = int(due_day_of_month) if due_day_of_month is not None else 1 # Default to 1 if None
        if not (1 <= day <= 31):
            logging.warning(f"Invalid due_day_of_month value received for update: {due_day_of_month}. Defaulting to 1.")
            day = 1
    except (ValueError, TypeError):
        logging.warning(f"Non-integer due_day_of_month value received for update: {due_day_of_month}. Defaulting to 1.")
        day = 1

    # Find the most recent payment record for this learner
    # Assuming the latest record (highest id) is the one to update
    find_query = "SELECT id FROM LearnerPayments WHERE learner_id = ? ORDER BY id DESC LIMIT 1"
    existing_record = db_manager.execute_query(find_query, (learner_id,), fetchone=True)

    if not existing_record:
        logging.error(f"Attempted to update payment for learner {learner_id}, but NO existing payment record was found.")
        # This indicates a data inconsistency if an update is called for a learner with no payment record.
        # Raise an error to highlight this issue.
        raise ValueError(f"Cannot update payment record for learner {learner_id}: No existing record found.")

    payment_record_id = existing_record[0]
    logging.info(f"Found LearnerPayment record ID {payment_record_id} for learner {learner_id} to update.")

    try:
        set_clause = []
        params = []

        if term_id is not None: # Only update if term_id is explicitly provided
            set_clause.append("term_id = ?")
            params.append(term_id)

        # For manual amounts, payment_option_id will be None. We should set the DB value to NULL.
        set_clause.append("payment_option_id = ?")
        params.append(payment_option_id)

        # Always include due_day_of_month in the update as it's directly from the spinbox value
        set_clause.append("due_day_of_month = ?")
        params.append(day)

        # Ensure we have something to update
        if not set_clause:
             logging.warning(f"No fields provided to update for LearnerPayment record {payment_record_id}.")
             return # Nothing to update

        params.append(payment_record_id) # For the WHERE clause
        update_query = f"UPDATE LearnerPayments SET {', '.join(set_clause)} WHERE id = ?"
        logging.debug(f"Executing update query: {update_query} with params: {params}")
        db_manager.execute_query(update_query, tuple(params), commit=True) # Ensure params is a tuple
        logging.info(f"Successfully updated LearnerPayment record {payment_record_id} for learner_id={learner_id}")

    except Exception as e:
        logging.exception(f"Failed to update LearnerPayment record {payment_record_id} for learner_id={learner_id}:") # Log exception
        raise # Re-raise the exception

def fetch_learner_payments(db_manager, learner_id):
    """Fetches all payment records for a specific learner, including due date."""
    # Explicitly list columns to ensure order and include the new one
    query = "SELECT id, learner_id, term_id, payment_option_id, start_date, end_date, due_day_of_month FROM LearnerPayments WHERE learner_id = ?"
    try:
        return db_manager.execute_query(query, (learner_id,), fetchall=True)
    except Exception as e:
        logging.exception(f"Error fetching learner payments for learner {learner_id}:") # Log exception
        raise # Re-raise

def fetch_all_learner_payments(db_manager):
    """Fetches all learner payment records, including due date."""
    # Explicitly list columns
    query = "SELECT id, learner_id, term_id, payment_option_id, start_date, end_date, due_day_of_month FROM LearnerPayments"
    try:
        return db_manager.execute_query(query, fetchall=True)
    except Exception as e:
        logging.exception("Error fetching all learner payments:") # Log exception
        raise # Re-raise

def get_current_user_id(db_manager, username):
    """Fetches the user_id for a given username."""
    query = "SELECT user_id FROM Users WHERE username = ?"
    try:
        user_id = db_manager.execute_query(query, (username,), fetchone=True)
        return user_id[0] if user_id else None
    except Exception as e:
        logging.exception(f"Error fetching user ID for username {username}:") # Log exception
        raise # Re-raise

def pause_learner_billing(db_manager, learner_acc_no, reason, archived_by_user_id, expected_return_date=None, notes=None):
    """Pauses billing for a learner.

    Updates the Learners table to set is_active = 0 and inserts a record into the Archive table.
    """
    conn = None
    try:
        conn = db_manager._connect()
        cursor = conn.cursor()
        cursor.execute("BEGIN")

        # 1. Update Learners table to set is_active = 0
        cursor.execute("UPDATE Learners SET is_active = 0 WHERE acc_no = ?", (learner_acc_no,))
        if cursor.rowcount == 0:
            raise ValueError(f"Learner with account number {learner_acc_no} not found.")

        # 2. Insert a record into the Archive table
        # Using STRFTIME is generally fine for timestamps in SQLite
        archive_query = """
            INSERT INTO Archive (learner_acc_no, archive_date, reason, expected_return_date, archived_by_user_id, notes)
            VALUES (?, STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW'), ?, ?, ?, ?)
        """
        archive_params = (learner_acc_no, reason, expected_return_date, archived_by_user_id, notes)
        cursor.execute(archive_query, archive_params)

        conn.commit()

    except (sqlite3.Error, ValueError) as e:
        if conn:
            conn.rollback()
        logging.exception(f"Error pausing billing for learner {learner_acc_no}:") # Log exception
        raise RuntimeError(f"Error pausing billing for learner {learner_acc_no}: {e}") from e
    finally:
        if conn:
            conn.close()

def resume_learner_billing(db_manager, learner_acc_no, reactivated_by_user_id):
    """Resumes billing for a learner.

    Updates the Learners table to set is_active = 1 and updates the Archive table.
    """
    conn = None
    try:
        conn = db_manager._connect()
        cursor = conn.cursor()
        cursor.execute("BEGIN")

        # 1. Check if learner exists and is currently inactive
        check_query = "SELECT is_active FROM Learners WHERE acc_no = ?"
        cursor.execute(check_query, (learner_acc_no,))
        result = cursor.fetchone()
        if not result:
            raise ValueError(f"Learner with account number {learner_acc_no} not found.")
        if result[0] == 1:
            raise ValueError(f"Learner {learner_acc_no} is already active.")

        # 2. Update Learners table to set is_active = 1
        cursor.execute("UPDATE Learners SET is_active = 1 WHERE acc_no = ?", (learner_acc_no,))
        
        # 3. Update the Archive table to set reactivation_date
        archive_update_query = """
            UPDATE Archive 
            SET reactivation_date = STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW'), 
                reactivated_by_user_id = ?
            WHERE learner_acc_no = ? 
            AND reactivation_date IS NULL
            AND archive_id = (
                SELECT MAX(archive_id) 
                FROM Archive 
                WHERE learner_acc_no = ? 
                AND reactivation_date IS NULL
            )
        """
        cursor.execute(archive_update_query, (reactivated_by_user_id, learner_acc_no, learner_acc_no))
        
        # Verify archive update
        if cursor.rowcount == 0:
            logging.warning(f"No active pause record found for learner {learner_acc_no} to update reactivation date.")
            # Continue anyway since we've already set is_active = 1

        # Commit all changes
        conn.commit()
        return True

    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.exception(f"Database error resuming billing for learner {learner_acc_no}:") # Log exception
        raise RuntimeError(f"Database error resuming billing for learner {learner_acc_no}: {e}") from e
    except ValueError as e:
        if conn:
            conn.rollback()
        logging.error(f"Validation error resuming billing for learner {learner_acc_no}: {e}")
        raise  # Re-raise ValueError as is
    except Exception as e:
        logging.exception(f"Unexpected error resuming billing for learner {learner_acc_no}:")
        raise RuntimeError(f"Unexpected error resuming billing for learner {learner_acc_no}: {e}") from e
    finally:
        if conn:
            conn.close()

def get_total_learners_count(db_manager):
    """Fetches the total number of learners."""
    try:
        query = "SELECT COUNT(*) FROM Learners"
        count = db_manager.execute_query(query, fetchone=True)
        return count[0] if count else 0
    except sqlite3.Error as e:
        logging.exception("Error fetching total learners count:")
        raise sqlite3.Error(f"Error fetching total learners count: {e}")
