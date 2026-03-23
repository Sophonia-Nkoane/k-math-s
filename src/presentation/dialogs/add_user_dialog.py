from PySide6.QtWidgets import (QFormLayout, QMessageBox, QVBoxLayout, QHBoxLayout, QLabel)
from core.desktop_shared_services import get_desktop_shared_services
from presentation.styles.colors import TEXT_COLOR
from presentation.components.rounded_field import RoundedPlainTextField, RoundedDropdown
from presentation.components.buttons import ButtonFactory
from presentation.components.window_component import WindowComponent

class AddUserDialog(WindowComponent):
    """Dialog for adding new users."""
    def __init__(self, db_manager, current_user_id, parent=None):
        super().__init__(parent, title="Add New User")
        self.db_manager = db_manager
        self.current_user_id = current_user_id
        self.shared_services = get_desktop_shared_services(db_manager)
        self.set_size(400, 300)
        self.setup_ui()

    def setup_ui(self):
        """Sets up the dialog's UI components."""
        # Create form layout
        form_layout = QFormLayout()
        
        # Username field
        username_label = QLabel("Username:")
        username_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.username_entry = RoundedPlainTextField(placeholder_text="Enter username")
        form_layout.addRow(username_label, self.username_entry)
        
        # Password fields
        password_label = QLabel("Password")
        password_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.password_entry = RoundedPlainTextField(placeholder_text="Enter password")
        self.password_entry.setEchoMode(RoundedPlainTextField.EchoMode.Password)
        form_layout.addRow(password_label, self.password_entry)
        
        # User role selection
        user_role_label = QLabel("User Role")
        user_role_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.role_combo = RoundedDropdown()
        self.role_combo.addItems(["user", "admin"])
        form_layout.addRow(user_role_label, self.role_combo)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        
        save_button = ButtonFactory.create_save_button("Save")
        save_button.clicked.connect(self.save_user)
        
        cancel_button = ButtonFactory.create_cancel_button("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)

        # Add layouts to window component
        self.add_layout(form_layout)
        self.add_layout(button_layout)

    def validate_input(self):
        """Validates the user input."""
        username = self.username_entry.text().strip()
        password = self.password_entry.text()
        
        if not username:
            self.parent().dialog_service.show_styled_message(
                "Input Error",
                "Please enter a username.",
                QMessageBox.Icon.Warning
            )
            return False
            
        if not password:
            self.parent().dialog_service.show_styled_message(
                "Input Error",
                "Please enter a password.",
                QMessageBox.Icon.Warning
            )
            return False
            
        if self.shared_services.user_repo.get_user_by_username(username):
            self.parent().dialog_service.show_styled_message(
                "Input Error",
                "This username already exists.",
                QMessageBox.Icon.Warning
            )
            return False
            
        return True

    def save_user(self):
        """Saves the new user to the database."""
        if not self.validate_input():
            return
            
        username = self.username_entry.text().strip()
        password = self.password_entry.text()
        role = self.role_combo.currentText().lower()
        actor_role = getattr(self.parent(), "current_user_role", None)
        if not actor_role and self.current_user_id:
            current_user = self.shared_services.user_repo.get_user_by_id(self.current_user_id)
            actor_role = current_user.get("role") if current_user else None
        
        try:
            ok, error = self.shared_services.admin_use_case.create_user(
                username=username,
                password=password,
                role=role,
                actor_user_id=self.current_user_id,
                actor_role=actor_role,
            )
            if not ok:
                self.parent().dialog_service.show_styled_message(
                    "Error",
                    error or "Failed to create user.",
                    QMessageBox.Icon.Warning
                )
                return
            
            self.parent().dialog_service.show_styled_message(
                "Success",
                "User added successfully."
            )
            
            self.accept()
            
        except Exception as e:
            self.parent().dialog_service.show_styled_message(
                "Error",
                f"Error creating user: {e}",
                QMessageBox.Icon.Critical
            )
