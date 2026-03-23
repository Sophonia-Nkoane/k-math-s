import logging
from PySide6.QtWidgets import QDialog, QMessageBox, QLineEdit, QVBoxLayout, QLabel, QDialogButtonBox, QComboBox, QApplication
from core.desktop_shared_services import get_desktop_shared_services
from presentation.components.buttons import ButtonFactory
from domain.services.authentication_service import AuthenticationService
from utils.settings_manager import SettingsManager
from presentation.dialogs.login_dialog import LoginDialog
from presentation.dialogs.add_user_dialog import AddUserDialog
from presentation.dialogs.audit_log_dialog import AuditLogDialog
from presentation.dialogs.payment_options_dialog import PaymentOptionsDialog
from presentation.dialogs.record_payment_dialog import RecordPaymentDialog
from presentation.dialogs.view_details_dialog import ViewDetailsDialog
from presentation.dialogs.add_update_learner_dialog import AddUpdateLearnerDialog
from presentation.dialogs.payment_view_dialog import PaymentViewDialog
from presentation.dialogs.payment_terms_dialog import PaymentTermsDialog
from presentation.dialogs.families_dialog import FamiliesDialog
from presentation.dialogs.statement_settings_dialog import StatementSettingsDialog
from presentation.dialogs.payment_statistics_dialog import PaymentStatisticsDialog
from presentation.dialogs.statement import generate_learner_statement_html, generate_family_statement_html
from presentation.dialogs.delete_user_dialog import DeleteUserDialog
from presentation.dialogs.update_user_dialog import UpdateUserDialog
from presentation.dialogs.pause_billing_dialog import PauseBillingDialog
from presentation.dialogs.email_settings_dialog import EmailSettingsDialog

class DialogService:
    def __init__(self, parent, db_manager, learner_service):
        self.parent = parent
        self.db_manager = db_manager
        self.learner_service = learner_service
        self.shared_services = get_desktop_shared_services(db_manager)
        self.auth_service = AuthenticationService(db_manager)
        self.logger = logging.getLogger(self.__class__.__name__)

    def show_login_dialog(self):
        self.logger.debug("show_login_dialog called")
        dialog = LoginDialog(self.parent)
        result = dialog.exec()
        self.logger.debug(f"LoginDialog.exec() returned {result}")
        if result == QDialog.DialogCode.Accepted:
            try:
                user_details = dialog.get_user_details()
                if all(x is not None for x in user_details):
                    self.logger.info("Login accepted from dialog")
                    return result, user_details
                else:
                    self.logger.warning("Login dialog accepted but user details were incomplete")
                    return QDialog.DialogCode.Rejected, None
            except Exception as e:
                self.logger.exception(f"Error reading login dialog user details: {e}")
                return QDialog.DialogCode.Rejected, None
        self.logger.info("Login dialog not accepted")
        return result, None

    def show_add_learner_dialog(self, user_id):
        dialog = AddUpdateLearnerDialog(self.learner_service, user_id, None, self.parent)
        return dialog.exec()

    def show_update_learner_dialog(self, user_id, acc_no):
        dialog = AddUpdateLearnerDialog(self.learner_service, user_id, acc_no, self.parent)
        return dialog.exec()

    def show_view_details_dialog(self, acc_no):
        dialog = ViewDetailsDialog(self.db_manager, acc_no, self.parent)
        return dialog.exec()

    def show_payment_view_dialog(self, acc_no, family_id=None):
        dialog = PaymentViewDialog(
            db_manager=self.db_manager,
            learner_acc_no=acc_no,  # This now matches the constructor parameter
            family_id=family_id,
            parent=self.parent
        )
        dialog.exec()

    def show_payment_terms_dialog(self):
        dialog = PaymentTermsDialog(self.db_manager, self.parent)
        return dialog.exec()

    def show_families_dialog(self, user_id):
        dialog = FamiliesDialog(self.db_manager, user_id, self.parent)
        return dialog.exec()

    def show_payment_options_dialog(self):
        dialog = PaymentOptionsDialog(self.db_manager, self.parent)
        return dialog.exec()

    def show_record_payment_dialog(self, user_id, acc_no=None):
        dialog = RecordPaymentDialog(self.db_manager, user_id, acc_no, None, self.parent)
        return dialog.exec()

    def show_add_user_dialog(self, user_id):
        dialog = AddUserDialog(self.db_manager, user_id, self.parent)
        return dialog.exec()

    def show_audit_log_dialog(self):
        dialog = AuditLogDialog(self.db_manager, self.parent)
        return dialog.exec()

    def show_statement_settings_dialog(self):
        dialog = StatementSettingsDialog(self.parent)
        return dialog.exec()

    def show_email_settings_dialog(self):
        """Shows the email settings dialog."""
        dialog = EmailSettingsDialog(self.db_manager, self.auth_service, self.parent)
        return dialog.exec()

    def show_payment_statistics_dialog(self):
        current_user_id = getattr(self.parent, 'current_user_id', None)
        dialog = PaymentStatisticsDialog(self.db_manager, current_user_id, self.parent)
        return dialog.exec()

    def show_delete_user_dialog(self, current_user_id):
        """Shows the delete user dialog with table view."""
        dialog = DeleteUserDialog(self.db_manager, current_user_id, self.parent)
        return dialog.exec()

    def show_update_user_dialog(self, username_to_update, current_user_id):
        """Shows the dialog for updating user information."""
        dialog = UpdateUserDialog(self.db_manager, username_to_update, current_user_id, self.parent)
        return dialog.exec()

    def show_pause_billing_dialog(self, acc_no, learner_name):
        """Shows the dialog for pausing learner billing."""
        dialog = PauseBillingDialog(self.db_manager, acc_no, learner_name, self.parent)
        result = dialog.exec()
        return (result, dialog.get_reason() if result else "")

    def confirm_delete_user(self, selected_username, dialog):
        # Create custom password confirmation dialog
        password_dialog = QDialog(self.parent)
        password_dialog.setWindowTitle("Confirm Deletion")
        layout = QVBoxLayout()
        
        # Add password label and input
        layout.addWidget(QLabel("Enter your password:"))
        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(password_input)
        
        # Create button box with styled buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ButtonFactory.style_dialog_buttons(button_box)
        layout.addWidget(button_box)
        
        password_dialog.setLayout(layout)
        button_box.accepted.connect(password_dialog.accept)
        button_box.rejected.connect(password_dialog.reject)
        
        if password_dialog.exec() == QDialog.DialogCode.Accepted:
            password = password_input.text()
            if password:
                # Verify password
                if self.auth_service.verify_user_password(self.db_manager, self.parent.current_user_id, password):
                    from presentation.dialogs.delete_user_dialog import DeleteUserDialog
                    delete_dialog = DeleteUserDialog(self.parent, self.db_manager, selected_username)
                    delete_dialog.exec()
                    dialog.accept()
                else:
                    self.show_styled_message("Incorrect Password", "Incorrect password. Deletion cancelled.")
            else:
                self.show_styled_message("Deletion Cancelled", "Password required for deletion.")

    def show_styled_message(self, title, text, icon_type=QMessageBox.Icon.Information):
        """Show styled message using centralized dialog utilities."""
        from presentation.components.dialog_utils import DialogUtils
        DialogUtils.show_message(self.parent, title, text, icon_type)

    def generate_learner_statement(self, acc_no):
        """Generates statement HTML for a learner using SettingsManager."""
        settings_manager = SettingsManager()
        statement_settings = settings_manager.load_statement_settings()
        return generate_learner_statement_html(self.parent, acc_no, statement_settings)

    def generate_family_statement(self, family_id):
        """Generates statement HTML for a family using SettingsManager."""
        settings_manager = SettingsManager()
        statement_settings = settings_manager.load_statement_settings()
        return generate_family_statement_html(self.parent, family_id, statement_settings)

    def get_statement_settings(self):
        """Gets the current statement settings."""
        settings_manager = SettingsManager()
        return settings_manager.load_statement_settings()

    def save_statement_settings(self, settings_data, new_logo_path_temp=None):
        """Saves statement settings using SettingsManager."""
        settings_manager = SettingsManager()
        return settings_manager.save_statement_settings(settings_data, new_logo_path_temp)

    def center_dialog(self, dialog):
        """Centers a dialog on the screen - no longer needed as WindowComponent handles this."""
        pass  # WindowComponent handles centering automatically

    def show_confirmation_dialog(self, title, text, parent=None):
        """Shows a confirmation dialog with styled Yes/No buttons."""
        from presentation.components.confirmation_dialog import ConfirmationDialog
        return ConfirmationDialog.show_dialog(
            parent=parent or self.parent,
            title=title,
            message=text,
            icon=QMessageBox.Icon.Question,
            size=(400, 150)
        )

    def show_confirm_deletion_dialog(self, name, acc_prefix, parent=None):
        """Show a confirmation dialog specifically for deleting a learner.

        Returns True if the user confirms the deletion (Yes), False otherwise.
        """
        title = "Confirm Deletion"
        message = f"Are you sure you want to delete {name} (Account {acc_prefix})?"
        result = self.show_confirmation_dialog(title, message, parent=parent or self.parent)
        return result == QMessageBox.StandardButton.Yes or result == QDialog.DialogCode.Accepted

    def show_confirm_password_dialog(self, user_id, parent=None):
        """Prompt for password and verify it for the given user_id.

        Returns True if the password is provided and verified, False otherwise.
        """
        # Reuse the password dialog; it returns the entered password or None
        password = self.show_password_dialog(parent=parent or self.parent)
        if not password:
            return False

        try:
            verified = self.auth_service.verify_user_password(self.db_manager, user_id, password)
            if not verified:
                self.show_styled_message("Authentication Failed", "Incorrect password. Action cancelled.", QMessageBox.Icon.Warning)
            return verified
        except Exception as e:
            self.logger.exception(f"Error verifying password for user {user_id}: {e}")
            self.show_styled_message("Error", "An error occurred while verifying the password.", QMessageBox.Icon.Critical)
            return False

    def show_password_dialog(self, title="Confirm Action", message="Enter your password:", parent=None):
        """Shows a password confirmation dialog."""
        dialog = QDialog(parent or self.parent)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel(message))
        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(password_input)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ButtonFactory.style_dialog_buttons(button_box)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return password_input.text()
        return None

    def verify_password_and_proceed(self, user_id, action_description, callback):
        """Verifies password and executes callback if verified."""
        password = self.show_password_dialog(
            title="Password Verification",
            message=f"Enter your password to {action_description}:"
        )
        if password:
            if self.auth_service.verify_user_password(self.db_manager, user_id, password):
                callback()
            else:
                self.show_styled_message(
                    "Authentication Failed",
                    "Incorrect password. Action cancelled.",
                    QMessageBox.Icon.Warning
                )
        else:
            self.show_styled_message(
                "Cancelled",
                "Action cancelled by user.",
                QMessageBox.Icon.Information
            )
