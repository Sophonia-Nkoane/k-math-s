from utils.helpers import log_action
from domain.models.learner_dto import LearnerDTO
from domain.services.progress_service import ProgressService

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
        conn = None
        try:
            conn = self.learner_repository.db_manager._connect()
            cursor = conn.cursor()

            # Handle manual payment option
            if learner_dto.manual_amount_enabled and learner_dto.manual_amount is not None:
                option_name = "MANUAL"
                self.payment_repository.create_or_update_payment_option(
                    option_name,
                    learner_dto.grade,
                    learner_dto.subjects_count,
                    learner_dto.manual_amount
                )
                learner_dto.payment_option = option_name
                # Get the payment_option_id for the newly created manual option
                manual_key = (option_name, learner_dto.subjects_count, learner_dto.grade)
                manual_options = self.payment_repository.get_payment_options()
                if manual_key in manual_options:
                    learner_dto.payment_option_id = manual_options[manual_key]['id']

            validation_error = self._validate_learner_data(learner_dto)
            if validation_error:
                return False, validation_error

            # Process contacts
            parent_ids = []
            guardian_ids = []
            if learner_dto.contacts:
                for contact in learner_dto.contacts:
                    if contact.get('relationship_type') == 'Parent':
                        parent_id = self.learner_repository.insert_parent_guardian(cursor, contact)
                        if parent_id:
                            parent_ids.append(parent_id)
                    elif contact.get('relationship_type') == 'Guardian':
                        guardian_id = self.learner_repository.insert_parent_guardian(cursor, contact)
                        if guardian_id:
                            guardian_ids.append(guardian_id)

            # Ensure we have at least one parent if we have contacts
            if learner_dto.contacts and not parent_ids and not guardian_ids:
                return False, "Failed to process parent/guardian contacts. Please ensure contact information is valid."

            learner_dto.parent_id = parent_ids[0] if len(parent_ids) > 0 else None
            learner_dto.parent2_id = parent_ids[1] if len(parent_ids) > 1 else None
            learner_dto.guardian_id = guardian_ids[0] if len(guardian_ids) > 0 else None

            # Ensure parent_id is set: use first parent, or guardian if no parents
            if not learner_dto.parent_id:
                if learner_dto.guardian_id:
                    learner_dto.parent_id = learner_dto.guardian_id
                    learner_dto.guardian_id = None  # Clear guardian since it's now the primary parent
                elif learner_dto.parent2_id:
                    learner_dto.parent_id = learner_dto.parent2_id
                    learner_dto.parent2_id = None  # Clear parent2 since it's now the primary parent

            # Validation: Ensure at least one parent is assigned (parent_id is required by DB)
            if not learner_dto.parent_id:
                return False, "A learner must have at least one parent or guardian."



            if learner_dto.acc_no:
                self._update_learner(cursor, learner_dto, user_id)
                # Update progress if provided
                if hasattr(learner_dto, 'progress_percentage') and learner_dto.progress_percentage is not None:
                    progress_service = ProgressService(self.learner_repository.db_manager)
                    progress_service.update_learner_progress(learner_dto.acc_no, learner_dto.progress_percentage, user_id)
                message = f"Learner {learner_dto.name} {learner_dto.surname} updated successfully."
            else:
                new_acc_no = self._add_learner(cursor, learner_dto, user_id)
                # Set initial progress for new learners if provided
                if hasattr(learner_dto, 'progress_percentage') and learner_dto.progress_percentage is not None and learner_dto.progress_percentage > 0:
                    progress_service = ProgressService(self.learner_repository.db_manager)
                    progress_service.update_learner_progress(new_acc_no, learner_dto.progress_percentage, user_id)
                message = f"Learner {learner_dto.name} {learner_dto.surname} added (Acc: {new_acc_no.split('-')[0]})."

            conn.commit()
            return True, message
        except Exception as e:
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def _validate_learner_data(self, learner_dto: LearnerDTO):
        """Validates the learner data."""
        if not all([learner_dto.name, learner_dto.surname, learner_dto.dob, learner_dto.gender, learner_dto.contact_number]):
            return "Name, Surname, DOB, Gender, and Contact Number are required."

        if not learner_dto.manual_amount_enabled and (learner_dto.payment_option == "-- Select Option --" or learner_dto.payment_option == "MANUAL_0"):
            return "Payment Option is required."

        if learner_dto.manual_amount_enabled and learner_dto.manual_amount is None:
            return "Manual Amount cannot be empty when Bypass is enabled."

        if not learner_dto.contacts:
            return "At least one parent/guardian contact is required."
        return None

    def _add_learner(self, cursor, learner_dto: LearnerDTO, user_id):
        """Adds a new learner to the database."""
        return self.learner_repository.add_learner(cursor, learner_dto, user_id)

    def _update_learner(self, cursor, learner_dto: LearnerDTO, user_id):
        """Updates an existing learner in the database."""
        return self.learner_repository.update_learner(cursor, learner_dto, user_id)

    def delete_learner(self, acc_no, user_id, learner_name):
        """Handles the business logic for deleting a learner."""
        conn = None
        try:
            conn = self.learner_repository.db_manager._connect()
            cursor = conn.cursor()
            result = self.learner_repository.delete_learner(cursor, acc_no, user_id, learner_name)
            conn.commit()
            return result
        except Exception as e:
            if conn:
                conn.rollback()
            return False, f"Error deleting learner: {str(e)}"
        finally:
            if conn:
                conn.close()

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

    def update_learner_progress(self, acc_no: str, progress_percentage: float, user_id: int):
        """Updates a learner's progress percentage."""
        try:
            progress_service = ProgressService(self.learner_repository.db_manager)
            success = progress_service.update_learner_progress(acc_no, progress_percentage, user_id)
            if success:
                return True, f"Progress updated to {progress_percentage}% for learner {acc_no}"
            else:
                return False, "Failed to update learner progress"
        except Exception as e:
            return False, f"Error updating progress: {str(e)}"
