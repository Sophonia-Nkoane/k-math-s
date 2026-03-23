from PySide6.QtWidgets import (QVBoxLayout, QLabel, QMessageBox, 
                           QHBoxLayout, QTableWidgetItem, QHeaderView)
import logging
from core.desktop_shared_services import get_desktop_shared_services
from presentation.components.window_component import WindowComponent
from presentation.components.table import Table
from presentation.components.rounded_field import RoundedPlainTextField
from presentation.components.buttons import ButtonFactory
from presentation.styles.colors import TEXT_COLOR
from presentation.components.confirmation_dialog import ConfirmationDialog

class DeleteUserDialog(WindowComponent):
    """Dialog for deleting users with modern UI components."""
    def __init__(self, db_manager, current_user_id, parent=None):
        super().__init__(parent, title="User Management")
        self.db_manager = db_manager
        self.current_user_id = current_user_id
        self.shared_services = get_desktop_shared_services(db_manager)
        self.user_to_delete = None
        self.setup_dialog_ui()
        self.load_users()
        self.setFixedSize(600, 400)  # Set an appropriate size for the dialog
        
    def setup_dialog_ui(self):
        """Sets up the dialog's UI components using modern styling."""
        content_layout = QVBoxLayout()
        
        # User Table - removed ID column
        table_columns = [
            {"name": "Username", "width": None, "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "Role", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents}
        ]
        
        self.table_component = Table(self, columns=table_columns)
        self.user_table = self.table_component.get_table()
        content_layout.addWidget(self.user_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        update_button = ButtonFactory.create_update_button("Update User")
        update_button.clicked.connect(self.update_user)
        
        delete_button = ButtonFactory.create_delete_button("Delete User")
        delete_button.clicked.connect(self.delete_user)
        
        close_button = ButtonFactory.create_close_button("Close")
        close_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(update_button)
        button_layout.addWidget(delete_button)
        button_layout.addWidget(close_button)
        
        content_layout.addLayout(button_layout)
        
        # Add the content layout to the window component
        self.add_layout(content_layout)

    def load_users(self):
        """Loads users into table."""
        try:
            current_username = getattr(self.parent(), "current_username", None)
            current_role = getattr(self.parent(), "current_user_role", None)
            if not current_role and self.current_user_id:
                current_user = self.shared_services.user_repo.get_user_by_id(self.current_user_id)
                current_role = current_user.get("role") if current_user else None

            if not current_role:
                self.parent().dialog_service.show_styled_message(
                    "Error",
                    "Could not retrieve current user role.",
                    QMessageBox.Icon.Critical
                )
                self.reject()
                return
            
            # Non-admins should not see this dialog at all
            if str(current_role).lower() != 'admin':
                self.parent().dialog_service.show_styled_message(
                    "Permission Denied",
                    "Only administrators can manage users.",
                    QMessageBox.Icon.Warning
                )
                self.reject()
                return
                
            users = self.shared_services.admin_use_case.list_users(exclude_username=current_username)
            self.user_table.setRowCount(0)
            for user in users:
                row = self.user_table.rowCount()
                self.user_table.insertRow(row)
                self.user_table.setItem(row, 0, QTableWidgetItem(str(user.get("username") or "")))
                self.user_table.setItem(row, 1, QTableWidgetItem(str(user.get("role") or "")))
        except Exception as e:
            logging.error(f"Error while loading users: {e}")
            self.parent().dialog_service.show_styled_message(
                "Error",
                "Failed to load user list. Please try again.",
                QMessageBox.Icon.Critical
            )

    def delete_user(self):
        """Handles user deletion."""
        selected_rows = self.user_table.selectedItems()
        if not selected_rows:
            self.parent().dialog_service.show_styled_message(
                "Selection Required",
                "Please select a user to delete.",
                QMessageBox.Icon.Warning
            )
            return
        
        row = selected_rows[0].row()
        username = self.user_table.item(row, 0).text()  # Username is now at index 0
        user_role = self.user_table.item(row, 1).text() # Role is now at index 1
        
        # Use ConfirmationDialog instead of custom dialog
        if ConfirmationDialog.show_dialog(
            self,
            title="Confirm Delete",
            message=f"Are you sure you want to delete the user '{username}'?",
            accept_button_text="Delete",
            reject_button_text="Cancel",
            size=(400, 150)
        ):
            # If confirmed, show password confirmation dialog
            from presentation.components.password_confirmation_dialog import PasswordConfirmationDialog
            password = PasswordConfirmationDialog.get_password_from_user(self)
            
            if password is not None:  # Only proceed if password was entered
                try:
                    if not self.shared_services.auth_use_case.verify_user_password(self.current_user_id, password):
                        self.parent().dialog_service.show_styled_message(
                            "Authentication Failed",
                            "Incorrect password.",
                            QMessageBox.Icon.Warning
                        )
                        return

                    ok, error = self.shared_services.admin_use_case.delete_user(
                        username=username,
                        actor_username=getattr(self.parent(), "current_username", None),
                        actor_user_id=self.current_user_id,
                        actor_role=getattr(self.parent(), "current_user_role", None),
                    )
                    if not ok:
                        self.parent().dialog_service.show_styled_message(
                            "Error",
                            error or "Failed to delete user.",
                            QMessageBox.Icon.Warning
                        )
                        return
                    
                    # Refresh the user list
                    self.load_users()
                    
                    self.parent().dialog_service.show_styled_message(
                        "Success",
                        f"User '{username}' has been deleted successfully.",
                        QMessageBox.Icon.Information
                    )
                    
                except Exception as e:
                    logging.error(f"Error while deleting user: {e}")
                    self.parent().dialog_service.show_styled_message(
                        "Error",
                        f"Error deleting user: {e}",
                        QMessageBox.Icon.Critical
                    )

    def update_user(self):
        """Handles updating the selected user's password (admin only)."""
        selected_items = self.user_table.selectedItems()
        if not selected_items:
            self.parent().dialog_service.show_styled_message(
                "Selection Required",
                "Please select a user to update.",
                QMessageBox.Icon.Warning
            )
            return
            
        row = selected_items[0].row()
        username = self.user_table.item(row, 0).text()  # Username is now at index 0
        result = self.parent().dialog_service.show_update_user_dialog(username, self.current_user_id)
        if result == WindowComponent.DialogCode.Accepted:
            self.load_users()
