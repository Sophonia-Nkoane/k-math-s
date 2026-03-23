# src/data/repositories/family_repository.py

import sqlite3
import logging
from datetime import date

from utils.payment_schedule import next_scheduled_date, normalize_scheduled_dates

class FamilyRepository:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_families(self):
        """Loads all family data from the database and returns them as a dictionary."""
        try:
            query = """
                SELECT family_id, family_name, payment_mode, COALESCE(discount_percentage, 0) as discount_percentage
                FROM Families
            """
            families_data = self.db_manager.execute_query(query, fetchall=True) or []
            # Convert list of tuples/rows to a dictionary
            # Assuming family_name is unique and can be used as key
            return {fam[1]: {'family_id': fam[0], 'payment_mode': fam[2], 'discount_percentage': fam[3]} for fam in families_data}
        except sqlite3.Error as e:
            self.logger.error(f"Error loading families: {e}")
            return {} # Return empty dictionary on error

    def get_family_and_learner_details_for_statement(self, family_id):
        """Retrieves family, parent, and learner details needed for the family statement."""
        if not family_id: return None
        family_details = {}
        try:
            fam_query = """
                SELECT family_account_no, payment_mode
                FROM Families
                WHERE family_id = ?
            """
            fam_result = self.db_manager.execute_query(fam_query, (family_id,), fetchone=True)
            if not fam_result:
                self.logger.error(f"Could not find family details for family_id {family_id}")
                return None
            family_details['account_no'] = fam_result[0] or f"FAM-{family_id}"
            family_details['payment_mode'] = fam_result[1]

            parent_query = """
                SELECT
                    p1.title AS p1_title, p1.name AS p1_name, p1.surname AS p1_surname,
                    p2.title AS p2_title, p2.name AS p2_name, p2.surname AS p2_surname,
                    g.title AS g_title, g.name AS g_name, g.surname AS g_surname
                FROM Learners s
                LEFT JOIN Parents p1 ON s.parent_id = p1.id
                LEFT JOIN Parents p2 ON s.parent2_id = p2.id
                LEFT JOIN Parents g ON s.guardian_id = g.id
                WHERE s.family_id = ?
                ORDER BY s.acc_no
                LIMIT 1
            """
            parent_result = self.db_manager.execute_query(parent_query, (family_id,), fetchone=True)
            if parent_result:
                family_details['p1_title'] = parent_result[0]
                family_details['p1_name'] = parent_result[1]
                family_details['p1_surname'] = parent_result[2]
                family_details['p2_title'] = parent_result[3]
                family_details['p2_name'] = parent_result[4]
                family_details['p2_surname'] = parent_result[5]
                family_details['g_title'] = parent_result[6]
                family_details['g_name'] = parent_result[7]
                family_details['g_surname'] = parent_result[8]
            else:
                family_details['p1_title'] = None; family_details['p1_name'] = "N/A"; family_details['p1_surname'] = ""
                family_details['p2_title'] = None; family_details['p2_name'] = None; family_details['p2_surname'] = None
                family_details['g_title'] = None; family_details['g_name'] = None; family_details['g_surname'] = None

            learners_query = """
                SELECT acc_no, name, surname, COALESCE(grade, 1) as grade
                FROM Learners
                WHERE family_id = ?
                ORDER BY grade, surname, name
            """
            learners_result = self.db_manager.execute_query(learners_query, (family_id,), fetchall=True)
            family_details['learners'] = [
                {'acc_no': s[0], 'name': s[1], 'surname': s[2], 'grade': s[3]}
                for s in learners_result
            ] if learners_result else []

            return family_details

        except sqlite3.Error as e:
            self.logger.error(f"Error fetching family/learner statement details for family_id {family_id}: {e}")
            return None
        except Exception as e:
            self.logger.exception(f"Unexpected error fetching family/learner details for family_id {family_id}: {e}")
            return None

    def get_payment_history_for_family(self, family_id):
        """Retrieves combined payment history for all learners in a family, ordered by date ASC."""
        history_data = []
        if not family_id: return history_data
        try:
            query = f"""
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

    def get_family_due_day(self, family_id):
        """Retrieves the most recent active due day across the family."""
        try:
            query = """
                SELECT lp.due_day_of_month, lp.scheduled_payment_dates
                FROM LearnerPayments lp
                JOIN Learners s ON s.acc_no = lp.learner_id
                WHERE s.family_id = ?
                  AND (lp.end_date IS NULL OR lp.end_date >= date('now'))
                  AND lp.start_date <= date('now')
                ORDER BY lp.start_date DESC, lp.learner_id ASC
                LIMIT 1
            """
            result = self.db_manager.execute_query(query, (family_id,), fetchone=True)
            if result:
                scheduled_date = next_scheduled_date(result[1], reference_date=date.today())
                if scheduled_date:
                    return scheduled_date.day
                if result[0] is not None:
                    return result[0]
            return 1
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching due day for family_id {family_id}: {e}")
            return 1

    def get_family_next_scheduled_payment_date(self, family_id, reference_date=None):
        """Retrieves the earliest upcoming exact payment date across a family."""
        try:
            query = """
                SELECT lp.scheduled_payment_dates
                FROM LearnerPayments lp
                JOIN Learners s ON s.acc_no = lp.learner_id
                WHERE s.family_id = ?
                  AND (lp.end_date IS NULL OR lp.end_date >= date('now'))
                  AND lp.start_date <= date('now')
            """
            rows = self.db_manager.execute_query(query, (family_id,), fetchall=True) or []
            combined_dates = []
            for row in rows:
                combined_dates.extend(normalize_scheduled_dates(row[0]))
            return next_scheduled_date(combined_dates, reference_date=reference_date)
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching scheduled payment dates for family_id {family_id}: {e}")
            return None

    def calculate_expected_charges_for_family(self, family_id, billing_year, current_month_num, payment_mode):
        """Calculates expected charges (admission, monthly) for a family up to the current date."""
        charges = {'admission': 0.0, 'monthly': {}}
        if not family_id: return charges

        try:
            family_discount_percent = 0.0
            try:
                fam_discount_query = "SELECT discount_percentage FROM Families WHERE family_id = ?"
                fam_discount_result = self.db_manager.execute_query(fam_discount_query, (family_id,), fetchone=True)
                if fam_discount_result and fam_discount_result[0] is not None:
                    family_discount_percent = float(fam_discount_result[0])
            except (sqlite3.Error, ValueError, TypeError) as e:
                self.logger.warning(f"Could not fetch or parse family discount for family {family_id}: {e}")
                family_discount_percent = 0.0

            family_discount_multiplier = (100.0 - family_discount_percent) / 100.0

            query = """
                SELECT s.acc_no, s.is_new_learner, s.apply_admission_fee,
                       po.adm_reg_fee, po.monthly_fee, sp.term_id, s.is_active
                FROM Learners s
                LEFT JOIN PaymentOptions po ON s.payment_option = po.option_name 
                    AND s.subjects_count = po.subjects_count AND s.grade = po.grade
                LEFT JOIN LearnerPayments sp ON s.acc_no = sp.learner_id
                WHERE s.family_id = ?
            """
            learners_fees = self.db_manager.execute_query(query, (family_id,), fetchall=True)

            if not learners_fees: return charges

            start_billing_date = (billing_year, 2, 1)

            active_learners = []
            paused_learners = []
            for learner in learners_fees:
                if learner[6]:
                    active_learners.append(learner)
                else:
                    paused_learners.append(learner)

            sorted_active_learners = sorted(active_learners, key=lambda x: x[4] if x[4] is not None else 0, reverse=True)

            for i, (acc_no, is_new, apply_adm, adm_fee_db, monthly_fee_db, term_id, _) in enumerate(sorted_active_learners):
                discount_percent = self.get_term_discount(term_id)
                discount_multiplier = (100.0 - discount_percent) / 100.0

                adm_fee = 0.0
                raw_adm_fee = 0.0
                if is_new and apply_adm and adm_fee_db is not None:
                    try:
                        raw_adm_fee = float(adm_fee_db)
                        if raw_adm_fee > 0:
                            if payment_mode == 'single_coverage':
                                if i == 0:
                                    adm_fee = raw_adm_fee
                            else:
                                adm_fee = raw_adm_fee * family_discount_multiplier
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"Could not convert admission fee '{adm_fee_db}' for learner {acc_no}: {e}")
                if adm_fee > 0:
                    charges['admission'] += adm_fee

                monthly_fee = 0.0
                raw_monthly_fee = 0.0
                if monthly_fee_db is not None:
                    try:
                        raw_monthly_fee = float(monthly_fee_db)
                        if raw_monthly_fee > 0:
                            if payment_mode == 'single_coverage':
                                if i == 0:
                                    monthly_fee = raw_monthly_fee
                            elif payment_mode == 'individual_discount':
                                monthly_fee = raw_monthly_fee * family_discount_multiplier
                            else:
                                monthly_fee = raw_monthly_fee
                                self.logger.warning(f"Unknown payment_mode '{payment_mode}' for family {family_id} monthly fee calc. Using raw fee.")
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"Could not convert monthly fee '{monthly_fee_db}' for learner {acc_no}: {e}")

                if monthly_fee > 0:
                    for month_num in range(2, current_month_num + 1):
                        fee_date = (billing_year, month_num, 1)
                        if fee_date >= start_billing_date:
                            charges['monthly'][fee_date] = charges['monthly'].get(fee_date, 0.0) + monthly_fee

            for paused_learner in paused_learners:
                acc_no = paused_learner[0]
                if acc_no not in self.individual_statements_queue:
                    self.individual_statements_queue.append(acc_no)

            return charges

        except sqlite3.Error as e:
            self.logger.error(f"Error calculating charges for family {family_id}: {e}")
            return {'admission': 0.0, 'monthly': {}}
