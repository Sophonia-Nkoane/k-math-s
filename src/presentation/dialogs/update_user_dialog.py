from PySide6.QtWidgets import (QVBoxLayout, QLabel, 
                            QMessageBox, QHBoxLayout, QComboBox, QFormLayout, QLineEdit)
import logging
from core.desktop_shared_services import get_desktop_shared_services
from presentation.components.rounded_field import RoundedPlainTextField
from presentation.components.buttons import ButtonFactory
from presentation.styles.colors import TEXT_COLOR
from presentation.components.window_component import WindowComponent

class UpdateUserDialog(WindowComponent):
    """Dialog for updating user information."""
    def __init__(self, db_manager, username_to_update, current_user_id, parent=None):
        super().__init__(parent, "Update User")
        self.db_manager = db_manager
        self.shared_services = get_desktop_shared_services(db_manager)
        self.username_to_update = username_to_update
        self.current_user_id = current_user_id
        self.current_user_role = getattr(parent, "current_user_role", None)
        self.set_size(400, 300)  # Made dialog taller
        self.setup_ui()
        if username_to_update:
            self.load_user_data()

    def is_admin_user(self):
        """Check if current user has admin role"""
        try:
            if self.current_user_role:
                return str(self.current_user_role).lower() == 'admin'
            current_user = self.shared_services.user_repo.get_user_by_id(self.current_user_id)
            self.current_user_role = current_user.get("role") if current_user else None
            return str(self.current_user_role or "").lower() == 'admin'
        except Exception as e:
            logging.error(f"Error checking admin status: {e}")
            return False

    def setup_ui(self):
        layout = self.get_container_layout()
        
        # Add search section
        search_layout = QHBoxLayout()
        self.search_input = RoundedPlainTextField()
        self.search_input.setPlaceholderText("Enter username to search")
        
        search_button = ButtonFactory.create_view_button("Search")
        search_button.clicked.connect(self.search_user)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)
        
        # Add separator
        line = QLabel()
        line.setStyleSheet(f"color: {TEXT_COLOR()};")
        line.setFrameStyle(QLabel.Shape.Box | QLabel.Shadow.Sunken)
        line.setFixedHeight(2)
        layout.addWidget(line)
        
        form_layout = QFormLayout()

        # Username display (read-only)
        self.username_label = QLabel()
        self.username_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        form_layout.addRow("Username:", self.username_label)
        
        # Role selection
        self.role_combo = QComboBox()
        self.role_combo.addItems(["user", "admin"])
        form_layout.addRow("Role:", self.role_combo)
        
        # New password (optional)
        self.new_password = RoundedPlainTextField()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password.setPlaceholderText("Enter new password for user")
        form_layout.addRow("New Password:", self.new_password)
        
        # Current user's password for verification (hidden for admins)
        self.current_password = RoundedPlainTextField()
        self.current_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.current_password.setPlaceholderText("Admin access required")
        self.current_password.hide()
        if self.is_admin_user():
            form_layout.addRow("", QLabel("Admin override - no verification needed"))
        else:
            form_layout.addRow("", QLabel("Admin access required to update users"))
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_button = ButtonFactory.create_save_button("Save Changes")
        save_button.clicked.connect(self.save_changes)
        
        cancel_button = ButtonFactory.create_cancel_button("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        layout.addStretch()
        layout.addLayout(button_layout)

    def load_user_data(self):
        try:
            result = self.shared_services.user_repo.get_user_by_username(self.username_to_update)
            if result:
                username = str(result.get("username") or "")
                role = str(result.get("role") or "user")
                self.username_label.setText(username)
                self.role_combo.setCurrentText(role)
            else:
                self.parent().dialog_service.show_styled_message(
                    "Error",
                    "User not found.",
                    QMessageBox.Icon.Critical
                )
                self.reject()
        except Exception as e:
            logging.error(f"Error while loading user data: {e}")
            self.parent().dialog_service.show_styled_message(
                "Error",
                "Failed to load user data.",
                QMessageBox.Icon.Critical
            )
            self.reject()

    def search_user(self):
        search_term = self.search_input.text().strip()
        if not search_term:
            self.parent().dialog_service.show_styled_message(
                "Search Error",
                "Please enter a username to search.",
                QMessageBox.Icon.Warning
            )
            return
            
        try:
            users = self.shared_services.admin_use_case.list_users()
            result = next(
                (user for user in users if search_term.lower() in str(user.get("username") or "").lower()),
                None,
            )

            if result:
                self.username_to_update = str(result.get("username") or "")
                self.load_user_data()
                self.search_input.setText(self.username_to_update)
            else:
                self.parent().dialog_service.show_styled_message(
                    "Not Found",
                    f"No user found matching '{search_term}'",
                    QMessageBox.Icon.Information
                )
                
        except Exception as e:
            logging.error(f"Error while searching user: {e}")
            self.parent().dialog_service.show_styled_message(
                "Error",
                "Failed to search for user.",
                QMessageBox.Icon.Critical
            )

    def save_changes(self):
        if not self.is_admin_user():
            self.parent().dialog_service.show_styled_message(
                "Permission Denied",
                "Only administrators can update users.",
                QMessageBox.Icon.Warning
            )
            return

        try:
            ok, error = self.shared_services.admin_use_case.update_user(
                username=self.username_to_update,
                role=self.role_combo.currentText(),
                new_password=self.new_password.text().strip() or None,
                actor_user_id=self.current_user_id,
                actor_role=self.current_user_role,
            )
            if not ok:
                self.parent().dialog_service.show_styled_message(
                    "Error",
                    error or "Failed to update user.",
                    QMessageBox.Icon.Warning
                )
                return

            self.parent().dialog_service.show_styled_message(
                "Success",
                "User information updated successfully."
            )
            self.accept()

        except Exception as e:
            logging.error(f"Error while updating user: {e}")
            self.parent().dialog_service.show_styled_message(
                "Error",
                f"Failed to update user: {e}",
                QMessageBox.Icon.Critical
            )
