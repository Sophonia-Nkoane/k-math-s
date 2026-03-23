from PySide6.QtWidgets import QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt

from presentation.components.window_component import WindowComponent
from presentation.components.rounded_field import RoundedPlainTextField
from presentation.components.buttons import ButtonFactory
from presentation.styles.colors import TEXT_COLOR

class PauseBillingDialog(WindowComponent):
    def __init__(self, db_manager, acc_no, learner_name, parent=None):
        super().__init__(parent, f"Pause Billing - {learner_name}")
        self.db_manager = db_manager
        self.acc_no = acc_no
        self.learner_name = learner_name
        self.set_size(400, 200)
        self.reason = None
        
        layout = self.container_layout
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Add reason label and input
        reason_label = QLabel("Enter reason for pausing billing:")
        reason_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        layout.addWidget(reason_label)
        self.reason_input = RoundedPlainTextField()
        layout.addWidget(self.reason_input)
        
        # Create button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_button = ButtonFactory.create_ok_button("OK")
        ok_button.clicked.connect(self.accept)
        cancel_button = ButtonFactory.create_cancel_button("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def accept(self):
        if not self.reason_input.text().strip():
            self.show_styled_message("Error", "Please enter a reason for pausing the billing.")
            return
        self.reason = self.reason_input.text().strip()
        super().accept()

    def get_reason(self):
        return self.reason
