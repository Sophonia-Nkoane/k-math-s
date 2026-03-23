from presentation.components.window_component import WindowComponent
from presentation.components.buttons import ButtonFactory
from presentation.components.rounded_field import RoundedPlainTextField
from PySide6.QtWidgets import QFormLayout, QHBoxLayout

class PasswordConfirmationDialog(WindowComponent):
    """Dialog for confirming user password."""
    def __init__(self, parent=None):
        super().__init__(parent, title="Password Confirmation") 
        self.set_size(300, 150)
        self.setup_ui()

    def setup_ui(self):
        # Main form layout
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        
        self.password_input = RoundedPlainTextField(placeholder_text="Enter your password")
        self.password_input.setEchoMode(RoundedPlainTextField.EchoMode.Password)
        form_layout.addRow("Password:", self.password_input)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        confirm_button = ButtonFactory.create_ok_button("Confirm")
        confirm_button.clicked.connect(self.accept)
        
        cancel_button = ButtonFactory.create_cancel_button("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(confirm_button)
        button_layout.addWidget(cancel_button)

        # Add layouts to container
        self.add_layout(form_layout)
        self.add_layout(button_layout)

    def get_password(self):
        """Returns the entered password."""
        return self.password_input.text()

    @staticmethod
    def get_password_from_user(parent=None):
        """Static method to show dialog and get password."""
        dialog = PasswordConfirmationDialog(parent)
        result = dialog.exec()
        return dialog.get_password() if result == WindowComponent.DialogCode.Accepted else None