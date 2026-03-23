import logging
from typing import List, Dict, Any
from business.services.email_service import EmailService
from data.repositories.learner_repository import LearnerRepository
from data.repositories.parent_repository import ParentRepository

class PaymentNotificationService:
    """Service for handling payment notifications via email."""

    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.email_service = EmailService()
        self.learner_repository = LearnerRepository(db_manager)
        self.parent_repository = ParentRepository(db_manager)
        self.logger = logging.getLogger(__name__)

    def process_payment_notifications(self, ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process OCR results and send thank you emails to parents.

        Args:
            ocr_results: List of dictionaries containing OCR extracted payment data

        Returns:
            Dict with success/failure counts and details
        """
        results = {
            'total_processed': len(ocr_results),
            'emails_sent': 0,
            'emails_failed': 0,
            'errors': []
        }

        for payment_info in ocr_results:
            try:
                learner_name = payment_info.get('name', '').strip()
                amount = payment_info.get('amount')
                date = payment_info.get('date')

                if not learner_name or not amount:
                    results['errors'].append(f"Missing learner name or amount in payment info: {payment_info}")
                    continue

                # Find learner by name
                learner_data = self._find_learner_by_name(learner_name)
                if not learner_data:
                    results['errors'].append(f"Learner not found: {learner_name}")
                    continue

                # Get parent email addresses
                parent_emails = self._get_parent_emails_for_learner(learner_data['acc_no'])
                if not parent_emails:
                    results['errors'].append(f"No parent emails found for learner: {learner_name}")
                    continue

                # Send thank you emails to all parents
                emails_sent_for_learner = 0
                for email in parent_emails:
                    if self.email_service.send_payment_thank_you_email(
                        email, learner_name, amount, date or "recent"
                    ):
                        emails_sent_for_learner += 1
                        self.logger.info(f"Thank you email sent to {email} for {learner_name}'s payment")
                    else:
                        results['errors'].append(f"Failed to send email to {email} for {learner_name}")
                        results['emails_failed'] += 1

                if emails_sent_for_learner > 0:
                    results['emails_sent'] += emails_sent_for_learner

            except Exception as e:
                error_msg = f"Error processing payment notification for {payment_info.get('name', 'Unknown')}: {str(e)}"
                results['errors'].append(error_msg)
                self.logger.error(error_msg)

        return results

    def _find_learner_by_name(self, learner_name: str) -> Dict[str, Any]:
        """
        Find learner by name (supports both "First Last" and "Last, First" formats).

        Args:
            learner_name: Learner name to search for

        Returns:
            Dict with learner data or None if not found
        """
        try:
            # Try different name formats
            name_parts = learner_name.split()
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])

                # Query for learner
                query = """
                    SELECT acc_no, name, surname
                    FROM Learners
                    WHERE LOWER(name) = LOWER(?) AND LOWER(surname) = LOWER(?)
                    LIMIT 1
                """
                result = self.db_manager.execute_query(query, (first_name, last_name), fetchone=True)

                if result:
                    return {
                        'acc_no': result[0],
                        'name': result[1],
                        'surname': result[2]
                    }

            # If not found, try searching by surname, firstname format
            if ',' in learner_name:
                parts = learner_name.split(',')
                if len(parts) == 2:
                    last_name = parts[0].strip()
                    first_name = parts[1].strip()

                    query = """
                        SELECT acc_no, name, surname
                        FROM Learners
                        WHERE LOWER(name) = LOWER(?) AND LOWER(surname) = LOWER(?)
                        LIMIT 1
                    """
                    result = self.db_manager.execute_query(query, (first_name, last_name), fetchone=True)

                    if result:
                        return {
                            'acc_no': result[0],
                            'name': result[1],
                            'surname': result[2]
                        }

        except Exception as e:
            self.logger.error(f"Error finding learner by name '{learner_name}': {str(e)}")

        return None

    def _get_parent_emails_for_learner(self, learner_acc_no: str) -> List[str]:
        """
        Get all parent/guardian email addresses for a learner.

        Args:
            learner_acc_no: Learner account number

        Returns:
            List of email addresses
        """
        emails = []

        try:
            # Get learner data to find parent IDs
            learner_query = """
                SELECT parent_id, parent2_id, guardian_id
                FROM Learners
                WHERE acc_no = ?
            """
            learner_result = self.db_manager.execute_query(learner_query, (learner_acc_no,), fetchone=True)

            if learner_result:
                parent_ids = [pid for pid in learner_result if pid is not None]

                # Get emails for each parent
                for parent_id in parent_ids:
                    parent_query = """
                        SELECT email FROM Parents
                        WHERE parent_id = ? AND email IS NOT NULL AND email != ''
                    """
                    parent_result = self.db_manager.execute_query(parent_query, (parent_id,), fetchone=True)
                    if parent_result and parent_result[0]:
                        emails.append(parent_result[0])

        except Exception as e:
            self.logger.error(f"Error getting parent emails for learner {learner_acc_no}: {str(e)}")

        return emails

    def send_manual_payment_notification(self, learner_acc_no: str, amount: float, payment_date: str) -> bool:
        """
        Send payment notification for manually recorded payments.

        Args:
            learner_acc_no: Learner account number
            amount: Payment amount
            payment_date: Payment date

        Returns:
            bool: True if at least one email was sent successfully
        """
        try:
            # Get learner name
            learner_query = """
                SELECT name, surname FROM Learners WHERE acc_no = ?
            """
            learner_result = self.db_manager.execute_query(learner_query, (learner_acc_no,), fetchone=True)

            if not learner_result:
                self.logger.error(f"Learner not found: {learner_acc_no}")
                return False

            learner_name = f"{learner_result[0]} {learner_result[1]}"

            # Get parent emails
            parent_emails = self._get_parent_emails_for_learner(learner_acc_no)
            if not parent_emails:
                self.logger.warning(f"No parent emails found for learner: {learner_name}")
                return False

            # Send emails
            emails_sent = 0
            for email in parent_emails:
                if self.email_service.send_payment_thank_you_email(email, learner_name, amount, payment_date):
                    emails_sent += 1
                    self.logger.info(f"Manual payment notification sent to {email} for {learner_name}")
                else:
                    self.logger.error(f"Failed to send manual payment notification to {email}")

            return emails_sent > 0

        except Exception as e:
            self.logger.error(f"Error sending manual payment notification: {str(e)}")
            return False
