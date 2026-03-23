from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

class ProgressService:
    """Service for managing learner progress tracking and payment eligibility for grades 1-7."""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    def get_grade_payment_rules(self, grade: int) -> Optional[Dict[str, Any]]:
        """Get payment rules for a specific grade."""
        if grade < 1 or grade > 7:
            return None

        query = """
            SELECT min_progress_percentage, change_interval_months, progress_validity_months, is_active
            FROM GradePaymentRules
            WHERE grade = ? AND is_active = 1
        """
        result = self.db_manager.execute_query(query, (grade,), fetchone=True)
        if result:
            return {
                'min_progress_percentage': result[0],
                'change_interval_months': result[1],
                'progress_validity_months': result[2],
                'is_active': bool(result[3])
            }
        return None

    def update_learner_progress(self, acc_no: str, progress_percentage: float, user_id: int) -> bool:
        """Update a learner's progress percentage and eligibility dates."""
        try:
            # Validate progress percentage
            if not (0 <= progress_percentage <= 100):
                logging.error(f"Invalid progress percentage: {progress_percentage}")
                return False

            # Get learner grade
            grade_query = "SELECT grade FROM Learners WHERE acc_no = ?"
            grade_result = self.db_manager.execute_query(grade_query, (acc_no,), fetchone=True)
            if not grade_result:
                logging.error(f"Learner {acc_no} not found")
                return False

            grade = grade_result[0]

            # Check if grade has payment rules (1-7)
            rules = self.get_grade_payment_rules(grade)
            if not rules:
                # For grades outside 1-7, just update progress without restrictions
                update_query = """
                    UPDATE Learners
                    SET progress_percentage = ?, progress_updated_date = ?
                    WHERE acc_no = ?
                """
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.db_manager.execute_query(update_query, (progress_percentage, now, acc_no), commit=True)
                return True

            # Calculate eligibility date based on progress validity
            now = datetime.now()
            validity_months = rules['progress_validity_months']
            eligible_until = (now + timedelta(days=30 * validity_months)).strftime('%Y-%m-%d %H:%M:%S')

            # Update learner progress
            update_query = """
                UPDATE Learners
                SET progress_percentage = ?,
                    progress_updated_date = ?,
                    progress_eligible_until = ?
                WHERE acc_no = ?
            """
            update_data = (progress_percentage, now.strftime('%Y-%m-%d %H:%M:%S'), eligible_until, acc_no)
            self.db_manager.execute_query(update_query, update_data, commit=True)

            # Log the progress update
            from utils.helpers import log_action
            log_action(self.db_manager, user_id, 'UPDATE_PROGRESS',
                      acc_no, f"Progress updated to {progress_percentage}% for grade {grade}")

            return True

        except Exception as e:
            logging.exception(f"Error updating progress for learner {acc_no}: {e}")
            return False

    def is_payment_change_allowed(self, acc_no: str) -> Dict[str, Any]:
        """
        Check if a payment change is allowed for a learner.
        Returns dict with 'allowed': bool and 'reason': str if not allowed.
        """
        try:
            # Get learner data
            query = """
                SELECT grade, progress_percentage, last_payment_change_date, progress_eligible_until
                FROM Learners WHERE acc_no = ?
            """
            result = self.db_manager.execute_query(query, (acc_no,), fetchone=True)
            if not result:
                return {'allowed': False, 'reason': 'Learner not found'}

            grade, progress_pct, last_change_date, eligible_until = result

            # Check if grade has payment rules (1-7)
            rules = self.get_grade_payment_rules(grade)
            if not rules:
                return {'allowed': True, 'reason': 'No restrictions for this grade'}

            # Check progress eligibility
            if progress_pct < rules['min_progress_percentage']:
                return {
                    'allowed': False,
                    'reason': f'Progress {progress_pct:.1f}% below minimum {rules["min_progress_percentage"]}%'
                }

            # Check if progress is still valid
            if eligible_until:
                eligible_date = datetime.strptime(eligible_until, '%Y-%m-%d %H:%M:%S')
                if datetime.now() > eligible_date:
                    return {'allowed': False, 'reason': 'Progress eligibility has expired'}

            # Check time interval since last payment change
            if last_change_date:
                last_change = datetime.strptime(last_change_date, '%Y-%m-%d %H:%M:%S')
                months_since_change = (datetime.now() - last_change).days / 30

                if months_since_change < rules['change_interval_months']:
                    remaining_months = rules['change_interval_months'] - months_since_change
                    return {
                        'allowed': False,
                        'reason': f'Payment change not allowed for {remaining_months:.1f} more months'
                    }

            return {'allowed': True, 'reason': 'Payment change allowed'}

        except Exception as e:
            logging.exception(f"Error checking payment change eligibility for {acc_no}: {e}")
            return {'allowed': False, 'reason': 'System error checking eligibility'}

    def record_payment_change(self, acc_no: str, user_id: int, change_description: str = "") -> bool:
        """Record that a payment change has occurred for a learner."""
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            update_query = """
                UPDATE Learners
                SET last_payment_change_date = ?
                WHERE acc_no = ?
            """
            self.db_manager.execute_query(update_query, (now, acc_no), commit=True)

            # Log the payment change
            from utils.helpers import log_action
            log_action(self.db_manager, user_id, 'PAYMENT_CHANGE',
                      acc_no, f"Payment change recorded: {change_description}")

            return True

        except Exception as e:
            logging.exception(f"Error recording payment change for {acc_no}: {e}")
            return False

    def get_learner_progress_status(self, acc_no: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive progress status for a learner."""
        try:
            query = """
                SELECT s.grade, s.progress_percentage, s.last_payment_change_date,
                       s.progress_eligible_until, s.progress_updated_date,
                       g.min_progress_percentage, g.change_interval_months, g.progress_validity_months
                FROM Learners s
                LEFT JOIN GradePaymentRules g ON s.grade = g.grade AND g.is_active = 1
                WHERE s.acc_no = ?
            """
            result = self.db_manager.execute_query(query, (acc_no,), fetchone=True)
            if not result:
                return None

            grade, progress_pct, last_change, eligible_until, updated_date, min_progress, interval_months, validity_months = result

            status = {
                'grade': grade,
                'progress_percentage': progress_pct or 0,
                'last_payment_change_date': last_change,
                'progress_eligible_until': eligible_until,
                'progress_updated_date': updated_date,
                'has_restrictions': grade >= 1 and grade <= 7 and min_progress is not None
            }

            if status['has_restrictions']:
                status.update({
                    'min_progress_required': min_progress,
                    'change_interval_months': interval_months,
                    'progress_validity_months': validity_months,
                    'progress_eligible': (progress_pct or 0) >= min_progress if progress_pct else False
                })

                # Check if progress is still valid
                if eligible_until:
                    eligible_date = datetime.strptime(eligible_until, '%Y-%m-%d %H:%M:%S')
                    status['progress_still_valid'] = datetime.now() <= eligible_date
                else:
                    status['progress_still_valid'] = False

                # Calculate time until next payment change allowed
                if last_change:
                    last_change_date = datetime.strptime(last_change, '%Y-%m-%d %H:%M:%S')
                    months_since_change = (datetime.now() - last_change_date).days / 30
                    status['months_until_next_change'] = max(0, interval_months - months_since_change)
                else:
                    status['months_until_next_change'] = 0

            return status

        except Exception as e:
            logging.exception(f"Error getting progress status for {acc_no}: {e}")
            return None
