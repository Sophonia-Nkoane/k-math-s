# src/data/repositories/payment_repository.py

import sqlite3
import logging
from datetime import date

from utils.payment_schedule import next_scheduled_date

class PaymentRepository:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_payment_options(self):
        """Loads all payment options from the database and returns them as a dictionary."""
        try:
            query = """
                SELECT id, option_name, subjects_count, grade, monthly_fee, adm_reg_fee
                FROM PaymentOptions
            """
            options_data = self.db_manager.execute_query(query, fetchall=True) or []
            result = {}
            # Convert list of tuples/rows to a dictionary with validation
            for opt in options_data:
                if len(opt) >= 6:  # Ensure we have all required fields
                    key = (opt[1], opt[2], opt[3])  # option_name, subjects_count, grade
                    result[key] = {
                        'id': opt[0],
                        'monthly_fee': opt[4] if opt[4] is not None else 0,
                        'adm_reg_fee': opt[5] if opt[5] is not None else 0
                    }
            return result
        except sqlite3.Error as e:
            self.logger.error(f"Error loading payment options: {e}")
            return {} # Return empty dictionary on error

    def get_payment_terms(self):
        """Loads all payment terms from the database and returns them as a dictionary."""
        try:
            query = """
                SELECT term_name, term_id, COALESCE(discount_percentage, 0) as discount_percentage
                FROM PaymentTerms
            """
            terms_data = self.db_manager.execute_query(query, fetchall=True) or []
            # Convert list of tuples/rows to a dictionary
            # Assuming term_name is unique and can be used as key
            return {term[0]: {'term_id': term[1], 'discount_percentage': term[2]} for term in terms_data}
        except sqlite3.Error as e:
            self.logger.error(f"Error loading payment terms: {e}")
            return {} # Return empty dictionary on error

    def get_payment_history_for_learner(self, acc_no):
        """Retrieves payment history for an individual learner, ordered by date ASC."""
        history_data = []
        try:
            query = "SELECT date, amount FROM Payments WHERE learner_id = ? ORDER BY date ASC"
            payments = self.db_manager.execute_query(query, (acc_no,), fetchall=True)
            if payments:
                 history_data = [{'date': p[0], 'amount': p[1]} for p in payments]
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching payment history for statement {acc_no}: {e}")
        return history_data

    def get_payment_history_for_family(self, family_id):
        """Retrieves combined family payment history, ordered by date ASC."""
        history_data = []
        if not family_id:
            return history_data
        try:
            query = """
                SELECT p.date, p.amount
                FROM Payments p
                JOIN Learners s ON p.learner_id = s.acc_no
                WHERE s.family_id = ?
                UNION ALL
                SELECT p.date, p.amount
                FROM Payments p
                WHERE p.family_id = ?
                ORDER BY date ASC
            """
            payments = self.db_manager.execute_query(query, (family_id, family_id), fetchall=True)
            if payments:
                history_data = [{'date': p[0], 'amount': p[1], 'type': 'payment'} for p in payments]
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching payment history for family_id {family_id}: {e}")
        return history_data

    def get_monthly_fee_for_statement(self, acc_no):
        """Retrieves the currently applicable monthly fee for an individual learner statement."""
        try:
            query = """
                SELECT COALESCE(po.monthly_fee, 0.0)
                FROM Learners s
                LEFT JOIN PaymentOptions po ON s.payment_option = po.option_name AND s.subjects_count = po.subjects_count AND s.grade = po.grade
                WHERE s.acc_no = ?
            """
            result = self.db_manager.execute_query(query, (acc_no,), fetchone=True)
            return result[0] if result and result[0] is not None else 0.0
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching monthly fee for {acc_no}: {e}")
            return 0.0


    def get_term_discount(self, term_id):
        """Fetches the discount percentage for a given payment term ID."""
        if term_id is None:
            return 0.0
        try:
            query = "SELECT discount_percentage FROM PaymentTerms WHERE term_id = ?"
            result = self.db_manager.execute_query(query, (term_id,), fetchone=True)
            if result and result[0] is not None:
                return float(result[0])
            else:
                return 0.0
        except (sqlite3.Error, ValueError, TypeError) as e:
            self.logger.error(f"Error fetching or converting discount for term_id {term_id}: {e}")
            return 0.0

    def get_active_term_for_learner(self, acc_no):
        """Retrieves the active payment term for a given learner."""
        try:
            query = """
                SELECT sp.term_id
                FROM LearnerPayments sp
                WHERE sp.learner_id = ?
                  AND (sp.end_date IS NULL OR sp.end_date >= date('now'))
                  AND sp.start_date <= date('now')
                ORDER BY sp.start_date DESC
                LIMIT 1
            """
            result = self.db_manager.execute_query(query, (acc_no,), fetchone=True)
            return result[0] if result and result[0] is not None else None
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching active term for learner {acc_no}: {e}")
            return None

    def get_term_name_by_id(self, term_id):
        """Fetches the term name for a given payment term ID."""
        if term_id is None:
            return None
        try:
            query = "SELECT term_name FROM PaymentTerms WHERE term_id = ?"
            result = self.db_manager.execute_query(query, (term_id,), fetchone=True)
            return result[0] if result and result[0] is not None else None
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching term name for term_id {term_id}: {e}")
            return None

    def get_due_day_for_learner(self, acc_no):
        """Retrieves the active due day for a learner."""
        try:
            query = """
                SELECT due_day_of_month, scheduled_payment_dates
                FROM LearnerPayments
                WHERE learner_id = ?
                  AND (end_date IS NULL OR end_date >= date('now'))
                  AND start_date <= date('now')
                ORDER BY start_date DESC
                LIMIT 1
            """
            result = self.db_manager.execute_query(query, (acc_no,), fetchone=True)
            if result:
                scheduled_date = next_scheduled_date(result[1], reference_date=date.today())
                if scheduled_date:
                    return scheduled_date.day
                if result[0] is not None:
                    return result[0]
            return 1
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching due day for learner {acc_no}: {e}")
            return 1

    def get_next_scheduled_payment_date_for_learner(self, acc_no, reference_date=None):
        """Retrieves the next configured exact payment date for a learner."""
        try:
            query = """
                SELECT scheduled_payment_dates
                FROM LearnerPayments
                WHERE learner_id = ?
                  AND (end_date IS NULL OR end_date >= date('now'))
                  AND start_date <= date('now')
                ORDER BY start_date DESC
                LIMIT 1
            """
            result = self.db_manager.execute_query(query, (acc_no,), fetchone=True)
            return next_scheduled_date(result[0] if result else None, reference_date=reference_date)
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching scheduled payment dates for learner {acc_no}: {e}")
            return None

    def create_or_update_payment_option(self, option_name, grade, subjects_count, amount):
        """Creates or updates a payment option, typically for manual amounts."""
        try:
            query = """
                INSERT OR REPLACE INTO PaymentOptions (option_name, grade, subjects_count, monthly_fee, adm_reg_fee)
                VALUES (?, ?, ?, ?, 0)  -- Assuming manual options don't have an admission fee
            """
            params = (option_name, grade, subjects_count, amount)
            self.db_manager.execute_query(query, params, commit=True)
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Database error creating/updating payment option {option_name}: {e}")
            return False
