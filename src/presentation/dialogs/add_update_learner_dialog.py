from PySide6.QtWidgets import (
    QMessageBox, QScrollArea, QWidget, QVBoxLayout, QHBoxLayout
)
from presentation.components.message_box import MessageBox
from presentation.components.window_component import WindowComponent
from business.services.learner_service import LearnerService
from presentation.widgets.learner_form import LearnerForm
from presentation.components.success_dialog import SuccessDialog

from presentation.components.buttons import ButtonFactory 

class AddUpdateLearnerDialog(WindowComponent):
    """Dialog for adding or updating a learner, using ParentGuardianWidget."""
    def __init__(self, learner_service: LearnerService, current_user_id, acc_no=None, parent=None):
        super().__init__(parent, title="Add Learner" if not acc_no else "Update Learner")
        self.learner_service = learner_service
        self.current_user_id = current_user_id
        self.acc_no = acc_no
        
        # Create a scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # Create a container for the form
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Add the learner form to the container
        self.learner_form = LearnerForm(acc_no)
        scroll_layout.addWidget(self.learner_form)
        
        # Set the container as the widget for the scroll area
        scroll_area.setWidget(scroll_content)
        
        # Add the scroll area to the main layout
        self.add_widget(scroll_area)

        self.ok_button = ButtonFactory.create_ok_button("Add Learner" if not self.acc_no else "Update Learner")
        self.cancel_button = ButtonFactory.create_cancel_button()

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        self.add_layout(button_layout)

        self._connect_signals()
        self._load_initial_data_into_form() # Renamed and refactored
        if acc_no:
            self.populate_learner_form()
        
        self.set_size(800, 600)

    def _connect_signals(self):
        """Connects widget signals to slots."""
        self.ok_button.clicked.connect(self.add_or_update_learner)
        self.cancel_button.clicked.connect(self.reject)
        # Connect directly to LearnerForm's update_payment_options
        self.learner_form.grade_spinbox.valueChanged.connect(self.learner_form._update_payment_options)
        self.learner_form.subjects_count_combobox.currentTextChanged.connect(self.learner_form._update_payment_options)

    def _load_initial_data_into_form(self):
        """Loads initial data from the service and populates the LearnerForm's combo boxes."""
        payment_options, payment_terms, families = self.learner_service.get_initial_data()
        self.learner_form.populate_initial_data(families, payment_terms, payment_options)

    def populate_learner_form(self):
        learner_dto = self.learner_service.get_learner_for_update(self.acc_no)
        if not learner_dto:
            self.show_styled_message("Not Found", f"Learner {self.acc_no} not found.", QMessageBox.Icon.Warning)
            self.reject()
            return

        self.learner_form.set_data(learner_dto)

    def add_or_update_learner(self):
        """Handles the logic for adding a new learner or updating an existing one."""
        is_valid, message = self.learner_form.validate_form()
        if not is_valid:
            self.show_styled_message("Validation Error", message, QMessageBox.Icon.Warning)
            return

        learner_dto = self.learner_form.to_learner_dto(self.acc_no) # Get DTO from LearnerForm
        
        if self.acc_no: # Update
            success, message = self.learner_service.add_or_update_learner(learner_dto, self.current_user_id)
        else: # Add
            success, message = self.learner_service.add_or_update_learner(learner_dto, self.current_user_id)

        if success:
            SuccessDialog.show_success(self, message)
            parent_window = self.parent()
            if parent_window and hasattr(parent_window, 'load_learners'):
                parent_window.load_learners()
            self.accept()
        else:
            self.show_styled_message("Operation Failed", message, QMessageBox.Icon.Critical)
        
    def show_styled_message(self, title, message, icon=QMessageBox.Icon.Information):
        """Displays a styled message box."""
        MessageBox.show_styled_message(self, title, message, icon)
        
    def set_size(self, width, height):
        self.setMinimumSize(width, height)
        self.resize(width, height)
        
