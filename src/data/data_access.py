from business.services.balance_service import BalanceService
from data.database_manager import DatabaseManager
from PySide6.QtWidgets import QProgressDialog
import logging
from typing import Optional
from datetime import date, datetime
import sqlite3


class DataAccess:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.balance_service = BalanceService()

    def _fetch_payment_data(self, query, params, description):
        """Fetches payment data based on the provided query and parameters."""
        history_data = []
        try:
            payments = self.db_manager.execute_query(
                query, params, fetchall=True)
            if payments:
                for date_str, amount in payments:
                    history_data.append(
                        [date_str, description, f"R {amount:.2f}", "History"])
        except sqlite3.Error as e:
            raise Exception(f"DB Error fetching payment data: {e}")
        except Exception as e:
            raise Exception(f"Unexpected error fetching payment data: {e}")
        return history_data

    def fetch_payment_history(self, learner_acc_no, family_id):
        """Fetches last 5 payments for individual or family."""
        limit = 5
        try:
            if family_id:
                query = """SELECT p.date, p.amount FROM Payments p JOIN Learners s ON p.learner_id = s.acc_no
                           WHERE s.family_id = ? ORDER BY p.date DESC LIMIT ?"""
                params = (family_id, limit)
                description = "Payment Received (Family)"
            else:
                query = "SELECT date, amount FROM Payments WHERE learner_id = ? ORDER BY date DESC LIMIT ?"
                params = (learner_acc_no, limit)
                description = "Payment Received"
            return self._fetch_payment_data(query, params, description)
        except Exception as e:
            raise Exception(f"Error fetching payment history: {e}")

    def fetch_upcoming_fee(self, learner_acc_no, family_id):
        """Fetches next expected monthly fee for individual or family."""
        try:
            if family_id:
                query = """SELECT SUM(COALESCE(po.monthly_fee, 0))
                           FROM Learners s
                           LEFT JOIN PaymentOptions po ON s.payment_option = po.option_name AND s.subjects_count = po.subjects_count AND s.grade = po.grade
                           WHERE s.family_id = ?"""
                params = (family_id,)
                res = self.db_manager.execute_query(
                    query, params, fetchone=True)
                fee = res[0] if res and res[0] is not None else 0.0
                base_label = "Next Family Fee"
            else:
                query = """SELECT po.monthly_fee FROM Learners s
                       JOIN PaymentOptions po ON s.payment_option = po.option_name AND s.subjects_count = po.subjects_count AND s.grade = po.grade
                       WHERE s.acc_no = ?"""
                params = (learner_acc_no,)
                res = self.db_manager.execute_query(
                    query, params, fetchone=True)
                fee = res[0] if res and res[0] is not None else 0.0
                base_label = "Next Monthly Fee"

            if fee > 0:
                return self.calculate_due_date(fee, base_label)
            return None
        except sqlite3.Error as e:
            raise Exception(f"Error fetching upcoming fee: {e}")
        except Exception as e:
            raise Exception(f"Unexpected error fetching upcoming fee: {e}")

    def calculate_due_date(self, fee, base_label):
        """Calculates the due date for the fee (always 1st of current month)."""
        today = date.today()
        # Always calculate the 1st of the current month as the due date
        current_month_first_day = today.replace(day=1)
        try:
            # Use simple, universal format strings to avoid locale issues
            date_str = current_month_first_day.strftime("%Y-%m-%d")
            label = f"{base_label} Due {current_month_first_day.strftime('%Y-%m-%d')}"
        except ValueError:
            # Fallback if strftime fails
            date_str = str(current_month_first_day)
            label = f"{base_label} Due {date_str}"

        # Return raw fee amount and formatted amount
        return [date_str, label, fee, f"R {fee:.2f}", "Upcoming"]

    def fetch_learner_details(self, db_manager: DatabaseManager, acc_no: str) -> tuple:
        """Fetches detailed learner data including parent/guardian info."""
        ...

    def execute_query_with_error_handling(self, db_manager: DatabaseManager, query: str, params: tuple = ()) -> list:
        """Executes a query with error handling."""
        try:
            return db_manager.execute_query(query, params, fetchall=True)
        except sqlite3.Error as e:
            logging.error(f"Error executing query: {query} with params: {params}. Error: {e}")
            raise



    def fetch_last_payment(self, learner_acc_no: Optional[str], family_id: Optional[int]) -> Optional[tuple]:
        """Fetches the most recent payment record for an individual or family."""
        query = ""
        params = ()
        description = ""

        try:
            if family_id:
                # Fetch the latest payment associated with any learner in the family OR directly to the family
                query = """
                    SELECT p.date, p.amount
                    FROM Payments p
                    LEFT JOIN Learners s ON p.learner_id = s.acc_no
                    WHERE s.family_id = ? OR p.family_id = ?
                    ORDER BY p.date DESC
                    LIMIT 1
                """
                params = (family_id, family_id)
                description = "Last Payment Received (Family)"
            elif learner_acc_no:
                # Fetch the latest payment for the specific learner
                query = """
                    SELECT date, amount
                    FROM Payments
                    WHERE learner_id = ?
                    ORDER BY date DESC
                    LIMIT 1
                """
                params = (learner_acc_no,)
                description = "Last Payment Received"
            else:
                # No identifier provided
                return None

            result = self.db_manager.execute_query(
                query, params, fetchone=True)

            if result:
                date_str, amount = result
                # Format the result for the summary table (Date, Description, Amount String)
                return (date_str, description, f"R {amount:,.2f}")
            else:
                return None  # No payment found

        except sqlite3.Error as e:
            # Optionally re-raise or return None/error indicator
            return None  # Return None on DB error
        except Exception as e:
            return None  # Return None on other errors

    def get_term_discount_percentage(self, term_id: Optional[int]) -> float:
        """Fetches the discount percentage for a given payment term."""
        if term_id is None:
            return 0.0
        try:
            query = "SELECT discount_percentage FROM PaymentTerms WHERE term_id = ?"
            result = self.db_manager.execute_query(query, (term_id,), fetchone=True)
            return float(result[0] or 0.0) if result and result[0] is not None else 0.0
        except (sqlite3.Error, ValueError) as e:
            logging.error(f"Error fetching term discount for term_id {term_id}: {e}")
            return 0.0

    def fetch_current_balance(self, learner_acc_no: Optional[str] = None, family_id: Optional[int] = None) -> float:
        today = date.today()
        try:
            if family_id:
                fam_info_query = "SELECT payment_mode, discount_percentage FROM Families WHERE family_id = ?"
                fam_info = self.db_manager.execute_query(
                    fam_info_query, (family_id,), fetchone=True)

                learners_query = """
                    SELECT s.acc_no, s.is_new_learner, s.apply_admission_fee,
                           po.adm_reg_fee, po.monthly_fee, sp.term_id, sp.start_date
                    FROM Learners s
                    LEFT JOIN PaymentOptions po ON s.payment_option = po.option_name
                        AND s.subjects_count = po.subjects_count AND s.grade = po.grade
                    LEFT JOIN LearnerPayments sp ON s.acc_no = sp.learner_id
                    WHERE s.family_id = ? AND s.is_active = 1
                """
                learners_data = self.db_manager.execute_query(
                    learners_query, (family_id,), fetchall=True)

                payments_query = """
                    SELECT SUM(p.amount)
                    FROM Payments p
                    LEFT JOIN Learners s ON p.learner_id = s.acc_no
                    WHERE s.family_id = ? OR p.family_id = ?
                """
                payments_result = self.db_manager.execute_query(
                    payments_query, (family_id, family_id), fetchone=True)
                total_payments = float(
                    payments_result[0] or 0.0) if payments_result and payments_result[0] is not None else 0.0

                # Convert rows to dicts
                family_info_dict = dict(fam_info) if fam_info else {}
                learners_data_dicts = [dict(row) for row in learners_data]

                return self.balance_service.calculate_family_balance(
                    family_info=family_info_dict,
                    learners_data=learners_data_dicts,
                    family_payments=total_payments,
                    today=today
                )

            elif learner_acc_no:
                learner_query = """
                    SELECT s.is_new_learner, s.apply_admission_fee,
                           po.adm_reg_fee, po.monthly_fee, sp.term_id, sp.start_date
                    FROM Learners s
                    LEFT JOIN PaymentOptions po ON s.payment_option = po.option_name
                        AND s.subjects_count = po.subjects_count AND s.grade = po.grade
                    LEFT JOIN LearnerPayments sp ON s.acc_no = sp.learner_id
                    WHERE s.acc_no = ? AND s.is_active = 1
                """
                learner_info = self.db_manager.execute_query(
                    learner_query, (learner_acc_no,), fetchone=True)

                if not learner_info:
                    return 0.0

                term_id = learner_info['term_id']
                term_discount = self.get_term_discount_percentage(term_id)

                payments_query = "SELECT SUM(amount) FROM Payments WHERE learner_id = ?"
                payments_result = self.db_manager.execute_query(
                    payments_query, (learner_acc_no,), fetchone=True)
                total_payments = float(
                    payments_result[0] or 0.0) if payments_result and payments_result[0] is not None else 0.0

                return self.balance_service.calculate_learner_balance(
                    learner_info=dict(learner_info),
                    learner_payments=total_payments,
                    term_discount_percentage=term_discount,
                    today=today
                )

            return 0.0

        except Exception as e:
            logging.error(f"Error calculating balance: {e}", exc_info=True)
            raise


    def fetch_learner_details_for_filename(self, acc_no):
        """Fetches learner's name, surname, and grade for PDF filename."""
        try:
            query = "SELECT name, surname, grade FROM Learners WHERE acc_no = ?"
            result = self.db_manager.execute_query(query, (acc_no,), fetchone=True)
            # Return tuple, handling None result
            return result if result else (None, None, None)
        except sqlite3.Error as e:
            return (None, None, None)

    def fetch_family_details_for_filename(self, family_id):
        """Fetches primary parent's name/surname and family account number for PDF filename."""
        try:
            # Get Family Acc No first
            fam_acc_query = "SELECT family_account_no FROM Families WHERE family_id = ?"
            fam_acc_res = self.db_manager.execute_query(fam_acc_query, (family_id,), fetchone=True)
            family_acc_no = fam_acc_res[0] if fam_acc_res else None

            # Get first parent details from the first learner in the family
            parent_query = """
                SELECT p1.name, p1.surname
                FROM Learners s
                JOIN Parents p1 ON s.parent_id = p1.id
                WHERE s.family_id = ?
                ORDER BY s.acc_no LIMIT 1
            """
            parent_res = self.db_manager.execute_query(parent_query, (family_id,), fetchone=True)
            if parent_res:
                return (parent_res[0], parent_res[1], family_acc_no)
            else:
                # Fallback if no parent found (e.g., family exists but no learners yet)
                return (None, None, family_acc_no)
        except sqlite3.Error as e:
            return (None, None, None)  # Return tuple indicating failure

def log_action(db_manager: DatabaseManager, user_id: int, action_type: str, object_id: str, details: str = None):
    """Logs an action to the AuditLog table using DatabaseManager."""
    ...
