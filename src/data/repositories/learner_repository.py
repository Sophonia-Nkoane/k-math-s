import sqlite3
import uuid
import logging
from datetime import datetime
from data.connection_pool import get_connection_pool

from utils.helpers import log_action
from utils.payment_schedule import (
    normalize_due_days,
    normalize_scheduled_dates,
    primary_due_day,
    serialize_due_days,
    serialize_scheduled_dates,
)
from domain.models.learner_dto import LearnerDTO

class LearnerRepository:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def _generate_unique_acc_no(self, cursor):
        """Generates a unique account number (acc_no) as TEXT."""
        while True:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            unique_id = str(uuid.uuid4())[:8]
            acc_no = f"KM{timestamp}-{unique_id.upper()}"
            cursor.execute("SELECT 1 FROM Learners WHERE acc_no = ?", (acc_no,))
            if not cursor.fetchone():
                return acc_no

    def insert_parent_guardian(self, cursor, parent_data):
        """
        Finds a parent by contact or creates a new one within a transaction.
        Returns parent ID or None if essential data is missing.
        Raises sqlite3.Error on database issues.
        """
        if not parent_data:
            return None

        # Check required fields with more flexible validation
        required_fields = ['contact_number', 'country_code', 'name', 'surname']
        missing_fields = [field for field in required_fields if not parent_data.get(field)]

        if missing_fields:
            return None

        try:
            find_p = "SELECT id FROM Parents WHERE country_code = ? AND contact_number = ?"
            cursor.execute(find_p, (parent_data['country_code'], parent_data['contact_number']))
            parent = cursor.fetchone()
            p_id = None

            if parent:
                p_id = parent[0]
                update_fields = {k: v for k, v in parent_data.items() if k in ['title', 'name', 'surname', 'email'] and v is not None and v != ''}
                if update_fields:
                    set_clause = ", ".join([f"{key} = ?" for key in update_fields.keys()])
                    params = list(update_fields.values()) + [p_id]
                    upd_p = f"UPDATE Parents SET {set_clause} WHERE id = ?"
                    cursor.execute(upd_p, params)
            else:
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
            raise sqlite3.Error(f"Database error during parent find/create: {e}")

    def get_all_learners(self):
        """Loads all learner data from the database."""
        try:
            query = """SELECT s.acc_no, s.name, s.surname, s.date_of_birth, s.gender, s.country_code, s.contact_number,
                              COALESCE(s.grade, 1) as grade, s.subjects_count, s.payment_option,
                              s.is_new_learner, s.apply_admission_fee, s.is_active, s.family_id
                       FROM Learners s ORDER BY s.surname, s.name"""
            return self.db_manager.execute_query(query, fetchall=True) or []
        except sqlite3.Error as e:
            self.logger.error(f"Database error loading learners: {e}")
            return []

    def get_family_id_for_learner(self, acc_no):
        """Retrieves the family_id for a given learner acc_no."""
        if not acc_no: return None
        try:
            if isinstance(acc_no, dict):
                acc_no = acc_no.get('acc_no')

            query = "SELECT family_id FROM Learners WHERE acc_no = ?"
            result_row = self.db_manager.execute_query(query, (acc_no,), fetchone=True)
            return result_row[0] if result_row and result_row[0] is not None else None
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching family_id for learner {acc_no}: {e}")
            return None

    def is_learner_active(self, acc_no):
        """Checks if a learner is currently active."""
        if not acc_no:
            return False
        try:
            query = "SELECT is_active FROM Learners WHERE acc_no = ?"
            result = self.db_manager.execute_query(query, (acc_no,), fetchone=True)
            return result[0] == 1 if result else False
        except sqlite3.Error as e:
            self.logger.error(f"Database error checking learner status for {acc_no}: {e}")
            return False

    def get_learner_details_for_statement(self, acc_no):
        """Retrieves learner and parent/guardian details needed for the individual statement."""
        try:
            query = """
                SELECT s.acc_no, s.name, s.surname, COALESCE(s.grade, 1) as grade,
                       s.is_new_learner, s.apply_admission_fee, s.payment_option,
                       p1.title AS p1_title, p1.name AS p1_name, p1.surname AS p1_surname,
                       p2.title AS p2_title, p2.name AS p2_name, p2.surname AS p2_surname,
                       g.title AS g_title, g.name AS g_name, g.surname AS g_surname,
                       po.adm_reg_fee, s.skip_initial_fee, s.custom_admission_amount_enabled, s.custom_admission_amount
                FROM Learners s
                LEFT JOIN Parents p1 ON s.parent_id = p1.id
                LEFT JOIN Parents p2 ON s.parent2_id = p2.id
                LEFT JOIN Parents g ON s.guardian_id = g.id
                LEFT JOIN PaymentOptions po ON s.payment_option = po.option_name AND s.subjects_count = po.subjects_count AND s.grade = po.grade
                WHERE s.acc_no = ?
            """
            result_row = self.db_manager.execute_query(query, (acc_no,), fetchone=True)

            if result_row:
                return result_row
            else:
                self.logger.info(f"No learner details found in DB for acc_no: {acc_no}")
                return None

        except sqlite3.Error as e:
            self.logger.error(f"Database error fetching learner statement details for {acc_no}: {e}")
            return None
        except Exception as e:
            self.logger.exception(f"Unexpected error fetching learner statement details for {acc_no}: {e}")
            return None


    def get_learner_payment_history(self, acc_no):
        """Retrieves the entire payment option history for a learner."""
        try:
            query = """
                SELECT
                    sp.start_date,
                    sp.end_date,
                    po.option_name,
                    po.monthly_fee,
                    po.adm_reg_fee,
                    s.is_new_learner,
                    s.apply_admission_fee,
                    s.skip_initial_fee,
                    s.custom_admission_amount_enabled,
                    s.custom_admission_amount
                FROM LearnerPayments sp
                JOIN PaymentOptions po ON sp.payment_option_id = po.id
                JOIN Learners s ON sp.learner_id = s.acc_no
                WHERE sp.learner_id = ?
                ORDER BY sp.start_date
            """
            return self.db_manager.execute_query(query, (acc_no,), fetchall=True)
        except sqlite3.Error as e:
            self.logger.error(f"Database error fetching learner payment history for {acc_no}: {e}")
            return []

    def get_learner_for_update(self, acc_no):
        """Retrieves all details for a single learner for the update form."""
        try:
            learner_query = """
                SELECT s.acc_no, s.name, s.surname, s.date_of_birth, s.gender, s.country_code, s.contact_number,
                       s.email, s.grade, s.subjects_count, s.payment_option, s.is_new_learner,
                       s.apply_admission_fee, s.family_id, s.parent_id, s.parent2_id, s.guardian_id,
                       sp.term_id, sp.due_day_of_month, sp.due_days_of_month, sp.scheduled_payment_dates, sp.start_date, sp.payment_option_id,
                       s.skip_initial_fee, s.custom_admission_amount_enabled, s.custom_admission_amount,
                       s.progress_percentage,
                       po.monthly_fee as manual_amount
                FROM Learners s
                LEFT JOIN (
                    SELECT * FROM LearnerPayments
                    WHERE learner_id = ?
                    ORDER BY start_date DESC
                    LIMIT 1
                ) sp ON s.acc_no = sp.learner_id
                LEFT JOIN PaymentOptions po ON sp.payment_option_id = po.id
                WHERE s.acc_no = ?
            """
            learner_row = self.db_manager.execute_query(learner_query, (acc_no, acc_no), fetchone=True)

            if not learner_row:
                self.logger.info(f"No learner found for acc_no: {acc_no}")
                return None

            # Fetch parent/guardian contact details
            contacts = []
            parent_ids = [learner_row['parent_id'], learner_row['parent2_id'], learner_row['guardian_id']]
            parent_ids = [pid for pid in parent_ids if pid is not None]

            if parent_ids:
                placeholders = ','.join(['?'] * len(parent_ids))
                contacts_query = f"""
                    SELECT id, title, name, surname, country_code, contact_number, email,
                           CASE
                               WHEN id IN (SELECT parent_id FROM Learners WHERE parent_id = Parents.id) THEN 'Parent'
                               WHEN id IN (SELECT parent2_id FROM Learners WHERE parent2_id = Parents.id) THEN 'Parent'
                               WHEN id IN (SELECT guardian_id FROM Learners WHERE guardian_id = Parents.id) THEN 'Guardian'
                           END as relationship_type
                    FROM Parents
                    WHERE id IN ({placeholders})
                """
                contacts_rows = self.db_manager.execute_query(contacts_query, parent_ids, fetchall=True)
                if contacts_rows:
                    for contact_row in contacts_rows:
                        contact_data = {
                            'relationship_type': contact_row['relationship_type'] or 'Parent',
                            'title': contact_row['title'],
                            'name': contact_row['name'],
                            'surname': contact_row['surname'],
                            'country_code': contact_row['country_code'],
                            'contact_number': contact_row['contact_number'],
                            'email': contact_row['email']
                        }
                        contacts.append(contact_data)

            learner_dto = LearnerDTO(
                acc_no=learner_row['acc_no'],
                name=learner_row['name'],
                surname=learner_row['surname'],
                dob=learner_row['date_of_birth'],
                gender=learner_row['gender'],
                country_code=learner_row['country_code'],
                contact_number=learner_row['contact_number'],
                email=learner_row['email'],
                grade=learner_row['grade'],
                subjects_count=learner_row['subjects_count'],
                payment_option=learner_row['payment_option'],
                payment_option_id=learner_row['payment_option_id'],
                is_new_learner=bool(learner_row['is_new_learner']),
                apply_admission_fee=bool(learner_row['apply_admission_fee']),
                family_id=learner_row['family_id'],
                parent_id=learner_row['parent_id'],
                parent2_id=learner_row['parent2_id'],
                guardian_id=learner_row['guardian_id'],
                term_id=learner_row['term_id'],
                due_day_of_month=primary_due_day(learner_row['due_days_of_month'], learner_row['due_day_of_month']),
                billing_start_date=learner_row['start_date'],
                due_days_of_month=normalize_due_days(learner_row['due_days_of_month'], learner_row['due_day_of_month']),
                scheduled_payment_dates=normalize_scheduled_dates(learner_row['scheduled_payment_dates']),
                contacts=contacts,
                skip_initial_fee=bool(learner_row['skip_initial_fee']),
                custom_admission_amount_enabled=bool(learner_row['custom_admission_amount_enabled']),
                custom_admission_amount=learner_row['custom_admission_amount'],
                progress_percentage=learner_row['progress_percentage'],
                manual_amount=learner_row['manual_amount']
            )
            return learner_dto

        except sqlite3.Error as e:
            self.logger.error(f"Database error fetching learner for update {acc_no}: {e}")
            return None
        except Exception as e:
            self.logger.exception(f"Unexpected error fetching learner for update {acc_no}: {e}")
            return None

    def get_active_learners_in_family(self, family_id):
        """Retrieves all active learners in a given family."""
        try:
            query = """SELECT s.acc_no, s.name, s.surname, s.date_of_birth, s.gender, s.country_code, s.contact_number,
                              COALESCE(s.grade, 1) as grade, s.subjects_count, s.payment_option,
                              s.is_new_learner, s.apply_admission_fee, s.is_active, s.family_id
                       FROM Learners s WHERE s.family_id = ? AND s.is_active = 1"""
            return self.db_manager.execute_query(query, (family_id,), fetchall=True) or []
        except sqlite3.Error as e:
            self.logger.error(f"Database error loading active learners for family {family_id}: {e}")
            return []

    def update_learner_billing_status(self, acc_no, is_active, reason=None):
        """Updates the billing status (is_active) of a learner and optionally records a reason."""
        try:
            pool = get_connection_pool() # Get the global connection pool
            with pool.transaction() as conn: # Use the transaction context manager
                cursor = conn.cursor()
                
                query = "UPDATE Learners SET is_active = ? WHERE acc_no = ?"
                cursor.execute(query, (1 if is_active else 0, acc_no))
                
                if not is_active and reason:
                    archive_query = """
                        INSERT INTO Archive (learner_acc_no, archive_date, reason, reactivation_date)
                        VALUES (?, datetime('now'), ?, NULL)
                    """
                    cursor.execute(archive_query, (acc_no, reason))
                
                elif is_active:
                    reactivate_query = """
                        UPDATE Archive 
                        SET reactivation_date = datetime('now')
                        WHERE learner_acc_no = ? 
                        AND reactivation_date IS NULL 
                        ORDER BY archive_date DESC 
                        LIMIT 1
                    """
                    cursor.execute(reactivate_query, (acc_no,))
                
                # Commit is handled by the context manager
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Database error updating learner billing status for {acc_no}: {e}")
            return False
        except Exception as e:
            self.logger.exception(f"Unexpected error updating learner billing status for {acc_no}: {e}")
            return False

    def add_learner(self, cursor, learner_dto: LearnerDTO, user_id):
        """Adds a new learner to the database using the provided cursor."""
        acc_no = self._generate_unique_acc_no(cursor)
        due_days = normalize_due_days(learner_dto.due_days_of_month, learner_dto.due_day_of_month)
        scheduled_dates = normalize_scheduled_dates(learner_dto.scheduled_payment_dates)
        primary_schedule_day = int(scheduled_dates[0][-2:]) if scheduled_dates else primary_due_day(due_days)
        if scheduled_dates and not learner_dto.due_days_of_month:
            due_days = [primary_schedule_day]

        cursor.execute("""
            INSERT INTO Learners (
                acc_no, name, surname, date_of_birth, gender, country_code, contact_number, email,
                grade, subjects_count, payment_option, is_new_learner, apply_admission_fee,
                family_id, parent_id, parent2_id, guardian_id, skip_initial_fee,
                custom_admission_amount_enabled, custom_admission_amount, progress_percentage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            acc_no, learner_dto.name, learner_dto.surname, learner_dto.dob, learner_dto.gender,
            learner_dto.country_code, learner_dto.contact_number, learner_dto.email,
            learner_dto.grade, learner_dto.subjects_count, learner_dto.payment_option,
            learner_dto.is_new_learner, learner_dto.apply_admission_fee, learner_dto.family_id,
            learner_dto.parent_id, learner_dto.parent2_id, learner_dto.guardian_id,
            learner_dto.skip_initial_fee, learner_dto.custom_admission_amount_enabled,
            learner_dto.custom_admission_amount, learner_dto.progress_percentage
        ))

        cursor.execute("""
            INSERT INTO LearnerPayments (
                learner_id, term_id, payment_option_id, due_day_of_month, due_days_of_month, scheduled_payment_dates, start_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            acc_no,
            learner_dto.term_id,
            learner_dto.payment_option_id,
            primary_schedule_day,
            serialize_due_days(due_days),
            serialize_scheduled_dates(scheduled_dates),
            learner_dto.billing_start_date,
        ))

        log_action(self.db_manager, user_id, 'ADD_LEARNER', acc_no, f"Added learner {learner_dto.name} {learner_dto.surname}.")
        return acc_no

    def update_learner(self, cursor, learner_dto: LearnerDTO, user_id):
        """Updates an existing learner in the database using the provided cursor."""
        due_days = normalize_due_days(learner_dto.due_days_of_month, learner_dto.due_day_of_month)
        scheduled_dates = normalize_scheduled_dates(learner_dto.scheduled_payment_dates)
        primary_schedule_day = int(scheduled_dates[0][-2:]) if scheduled_dates else primary_due_day(due_days)
        if scheduled_dates and not learner_dto.due_days_of_month:
            due_days = [primary_schedule_day]
        cursor.execute("""
            UPDATE Learners
            SET name = ?, surname = ?, date_of_birth = ?, gender = ?, country_code = ?,
                contact_number = ?, email = ?, grade = ?, subjects_count = ?,
                payment_option = ?, is_new_learner = ?, apply_admission_fee = ?,
                family_id = ?, parent_id = ?, parent2_id = ?, guardian_id = ?,
                skip_initial_fee = ?, custom_admission_amount_enabled = ?, custom_admission_amount = ?,
                progress_percentage = ?
            WHERE acc_no = ?
        """, (
            learner_dto.name, learner_dto.surname, learner_dto.dob, learner_dto.gender,
            learner_dto.country_code, learner_dto.contact_number, learner_dto.email,
            learner_dto.grade, learner_dto.subjects_count, learner_dto.payment_option,
            learner_dto.is_new_learner, learner_dto.apply_admission_fee,
            learner_dto.family_id, learner_dto.parent_id, learner_dto.parent2_id, learner_dto.guardian_id,
            learner_dto.skip_initial_fee, learner_dto.custom_admission_amount_enabled,
            learner_dto.custom_admission_amount, learner_dto.progress_percentage, learner_dto.acc_no
        ))

        cursor.execute("""
            UPDATE LearnerPayments
            SET term_id = ?, due_day_of_month = ?, due_days_of_month = ?, scheduled_payment_dates = ?, start_date = ?
            WHERE learner_id = ?
        """, (
            learner_dto.term_id,
            primary_schedule_day,
            serialize_due_days(due_days),
            serialize_scheduled_dates(scheduled_dates),
            learner_dto.billing_start_date,
            learner_dto.acc_no,
        ))

        log_action(self.db_manager, user_id, 'UPDATE_LEARNER', learner_dto.acc_no, f"Updated learner {learner_dto.name} {learner_dto.surname}.")

    def delete_learner(self, cursor, acc_no, user_id, learner_name):
        """Deletes a learner and associated orphan parents using the provided cursor."""
        cursor.execute("PRAGMA foreign_keys = ON")

        cursor.execute("SELECT parent_id, parent2_id, guardian_id FROM Learners WHERE acc_no = ?", (acc_no,))
        fetch_result = cursor.fetchone()
        if not fetch_result:
            raise sqlite3.Error("Learner not found during delete transaction.")
        
        parent_ids_to_check = [pid for pid in fetch_result if pid is not None]

        # Delete related records in order to avoid foreign key constraint violations
        # 1. Delete from LearnerPayments (has FK to Learners)
        cursor.execute("DELETE FROM LearnerPayments WHERE learner_id = ?", (acc_no,))
        
        # 2. Delete from Payments (has FK to Learners with ON DELETE CASCADE, but delete explicitly to be safe)
        cursor.execute("DELETE FROM Payments WHERE learner_id = ?", (acc_no,))
        
        # 3. Now delete the learner
        cursor.execute("DELETE FROM Learners WHERE acc_no = ?", (acc_no,))
        deleted_count = cursor.rowcount
        if deleted_count == 0:
            raise sqlite3.Error("Learner not found during delete transaction.")

        # 4. Clean up orphan parents
        for p_id in parent_ids_to_check:
            cursor.execute("SELECT COUNT(*) FROM Learners WHERE parent_id = ? OR parent2_id = ? OR guardian_id = ?", (p_id, p_id, p_id))
            count_res = cursor.fetchone()
            if count_res and count_res[0] == 0:
                cursor.execute("DELETE FROM Parents WHERE id = ?", (p_id,))

        log_action(self.db_manager, user_id, 'DELETE_LEARNER', acc_no, f"Deleted learner: {learner_name}")
        return True, None
''
