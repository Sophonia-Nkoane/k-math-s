from PySide6.QtCore import Qt
import logging

class SelectionService:
    def __init__(self, db_manager):
        self._selected_acc_no = None
        self._selected_is_active = None
        self._db_manager = db_manager
        self._selected_learner_details = None

    def update_selection(self, selected_item):
        """Updates selection state based on table item."""
        if not selected_item:
            self.clear_selection()
            return
            
        stored_data = selected_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(stored_data, dict):
            self._selected_acc_no = stored_data.get('acc_no')
            self._selected_is_active = stored_data.get('is_active')
        else:
            # Fallback for older data format
            self._selected_acc_no = stored_data
            self._selected_is_active = None
            
        # Fetch learner details
        try:
            if self._selected_acc_no:
                query = "SELECT name, surname FROM Learners WHERE acc_no = ?"
                self._selected_learner_details = self._db_manager.execute_query(query, (self._selected_acc_no,), fetchone=True)
        except Exception as e:
            logging.error(f"Failed to fetch learner details: {e}")
            self._selected_learner_details = None

    def clear_selection(self):
        """Clears current selection."""
        self._selected_acc_no = None
        self._selected_is_active = None
        self._selected_learner_details = None

    def has_selection(self):
        """Returns if there is a current selection."""
        return bool(self._selected_acc_no)

    def is_selected_active(self):
        """Returns if selected learner is active."""
        return bool(self._selected_is_active == 1 or self._selected_is_active is True)

    def get_selected_acc_no(self):
        """Returns the currently selected account number."""
        return self._selected_acc_no

    def get_selected_is_active(self):
        """Returns the raw active status of selected learner."""
        return self._selected_is_active

    def get_selected_learner_name(self):
        """Returns the name of the currently selected learner."""
        if self._selected_learner_details:
            return self._selected_learner_details[0]
        return ""

    def get_selected_learner_surname(self):
        """Returns the surname of the currently selected learner."""
        if self._selected_learner_details:
            return self._selected_learner_details[1]
        return ""
