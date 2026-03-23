from utils.helpers import log_action
import sqlite3
from domain.models.learner_dto import LearnerDTO

class LearnerService:
    def __init__(self, learner_repository, parent_repository, payment_repository, family_repository):
        self.learner_repository = learner_repository
        self.parent_repository = parent_repository
        self.payment_repository = payment_repository
        self.family_repository = family_repository

    def get_initial_data(self):
        """Gets the initial data required for the add/update learner dialog."""
        payment_options = self.payment_repository.get_payment_options()
        payment_terms = self.payment_repository.get_payment_terms()
        families = self.family_repository.get_families()
        return payment_options, payment_terms, families

    def get_learner_details(self, acc_no):
        """Gets the details for a given learner."""
        return self.learner_repository.get_learner_for_update(acc_no)

    def get_learner_for_update(self, acc_no):
        """Gets all details for a given learner for the update form."""
        return self.learner_repository.get_learner_for_update(acc_no)

    def add_or_update_learner(self, learner_dto: LearnerDTO, user_id):
        """Handles the business logic for adding or updating a learner."""
        try:
            validation_error = self._validate_learner_data(learner_dto)
            if validation_error:
                return False, validation_error

            if learner_dto.acc_no:
                self._update_learner(learner_dto, user_id)
                message = f"Learner {learner_dto.name} {learner_dto.surname} updated successfully."
            else:
                new_acc_no = self._add_learner(learner_dto, user_id)
                message = f"Learner {learner_dto.name} {learner_dto.surname} added (Acc: {new_acc_no.split('-')[0]})."

            return True, message
        except Exception as e:
            return False, str(e)

    def _validate_learner_data(self, learner_dto: LearnerDTO):
        """Validates the learner data."""
        # This is a placeholder for the validation logic.
        # In a real application, this would contain the validation logic from the dialog.
        return None

    def _add_learner(self, learner_dto: LearnerDTO, user_id):
        """Adds a new learner to the database."""
        # This is a placeholder for the logic to add a new learner.
        pass

    def _update_learner(self, learner_dto: LearnerDTO, user_id):
        """Updates an existing learner in the database."""
        # This is a placeholder for the logic to update an existing learner.
        pass

    def delete_learner(self, acc_no, user_id, learner_name):
        """Handles the business logic for deleting a learner."""
        conn = None
        try:
            conn = self.db_manager._connect()
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("BEGIN")
            
            # Get Parent ID
            cursor.execute("SELECT parent_id FROM Learners WHERE acc_no = ?", (acc_no,))
            p_id_res = cursor.fetchone()
            p_id = p_id_res[0] if p_id_res else None
            
            # Delete learner (Payments deleted by CASCADE FK)
            cursor.execute("DELETE FROM Learners WHERE acc_no = ?", (acc_no,))
            deleted_count = cursor.rowcount
            if deleted_count == 0:
                raise sqlite3.Error("Learner not found during delete transaction.")
            
            # Check and delete orphan parent
            if p_id:
                cursor.execute("SELECT COUNT(*) FROM Learners WHERE parent_id = ?", (p_id,))
                count_res = cursor.fetchone()
                if count_res and count_res[0] == 0:
                    cursor.execute("DELETE FROM Parents WHERE id = ?", (p_id,))
            
            conn.commit()
            log_action(self.db_manager, user_id, 'DELETE_LEARNER', acc_no, f"Deleted learner: {learner_name}")
            return True, None
            
        except sqlite3.Error as e:
            if conn: conn.rollback()
            return False, f"Database Error: {str(e)}"
        except Exception as e:
            if conn: conn.rollback()
            return False, f"An unexpected error occurred: {str(e)}"

    def pause_billing(self, acc_no, reason, user_id):
        """Pauses billing for a learner and records the reason."""
        try:
            self.learner_repository.update_learner_billing_status(acc_no, False, reason)
            # Assuming db_manager is accessible via learner_repository for logging
            log_action(self.learner_repository.db_manager, user_id, 'PAUSE_BILLING', acc_no, f"Paused billing for {acc_no}. Reason: {reason}")
            return True, "Billing paused successfully."
        except Exception as e:
            return False, f"Error pausing billing: {str(e)}"

    def resume_billing(self, acc_no, user_id):
        """Resumes billing for a learner."""
        try:
            self.learner_repository.update_learner_billing_status(acc_no, True, None) # Clear reason on resume
            # Assuming db_manager is accessible via learner_repository for logging
            log_action(self.learner_repository.db_manager, user_id, 'RESUME_BILLING', acc_no, f"Resumed billing for {acc_no}.")
            return True, "Billing resumed successfully."
        except Exception as e:
            return False, f"Error resuming billing: {str(e)}"
