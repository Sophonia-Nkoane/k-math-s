from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout,
                             QGroupBox, QFormLayout, QMessageBox, QLabel, QCheckBox,
                             QScrollArea, QWidget)
from core.desktop_shared_services import get_desktop_shared_services
from presentation.styles import styles
from presentation.styles.colors import TEXT_COLOR
from presentation.components.rounded_field import RoundedPlainTextField, RoundedSpinner, RoundedTextEdit
from presentation.components.buttons import ButtonFactory
from presentation.components.window_component import WindowComponent

class EmailSettingsDialog(WindowComponent):
    def __init__(self, db_manager, auth_service, parent=None):
        super().__init__(parent, title="Email Settings")
        self.db_manager = db_manager
        self.auth_service = auth_service
        self.shared_services = get_desktop_shared_services(db_manager)
        self.setup_ui()
        self.set_size(700, 700)  # Set appropriate size for the dialog with templates
        # Load settings AFTER UI is fully set up and sized
        self.load_settings()

    @staticmethod
    def _as_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def setup_ui(self):
        layout = QVBoxLayout()

        # Email Integration Group
        email_integration_group = QGroupBox("Email Integration")
        email_integration_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        email_integration_layout = QFormLayout()

        # Enable email integration
        self.email_enabled = QCheckBox("Enable Email Integration")
        self.email_enabled.setStyleSheet(f"color: {TEXT_COLOR()};")
        email_integration_layout.addRow(self.email_enabled)

        email_integration_group.setLayout(email_integration_layout)
        layout.addWidget(email_integration_group)

        # SMTP Settings Group (for sending emails)
        smtp_group = QGroupBox("SMTP Settings (For Sending Emails)")
        smtp_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        smtp_layout = QFormLayout()

        self.smtp_user = RoundedPlainTextField()
        self.smtp_user.setPlaceholderText("Enter email address")
        smtp_user_label = QLabel("SMTP Email Address:")
        smtp_user_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        smtp_layout.addRow(smtp_user_label, self.smtp_user)

        self.smtp_password = RoundedPlainTextField()
        self.smtp_password.setEchoMode(RoundedPlainTextField.EchoMode.Password)
        self.smtp_password.setPlaceholderText("Enter email password/App Password")
        smtp_password_label = QLabel("SMTP Password:")
        smtp_password_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        smtp_layout.addRow(smtp_password_label, self.smtp_password)

        self.smtp_host = RoundedPlainTextField()
        self.smtp_host.setPlaceholderText("smtp.gmail.com")
        smtp_host_label = QLabel("SMTP Host:")
        smtp_host_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        smtp_layout.addRow(smtp_host_label, self.smtp_host)

        self.smtp_port = RoundedSpinner()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(587)
        smtp_port_label = QLabel("SMTP Port:")
        smtp_port_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        smtp_layout.addRow(smtp_port_label, self.smtp_port)

        self.smtp_tls = QCheckBox("Use TLS/SSL")
        self.smtp_tls.setChecked(True)
        self.smtp_tls.setStyleSheet(f"color: {TEXT_COLOR()};")
        smtp_layout.addRow(self.smtp_tls)

        smtp_group.setLayout(smtp_layout)
        layout.addWidget(smtp_group)

        # IMAP Settings Group (for monitoring emails)
        imap_group = QGroupBox("IMAP Settings (For Monitoring Bank Emails)")
        imap_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        imap_layout = QFormLayout()

        self.imap_user = RoundedPlainTextField()
        self.imap_user.setPlaceholderText("Enter email address")
        imap_user_label = QLabel("IMAP Email Address:")
        imap_user_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        imap_layout.addRow(imap_user_label, self.imap_user)

        self.imap_password = RoundedPlainTextField()
        self.imap_password.setEchoMode(RoundedPlainTextField.EchoMode.Password)
        self.imap_password.setPlaceholderText("Enter email password/App Password")
        imap_password_label = QLabel("IMAP Password:")
        imap_password_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        imap_layout.addRow(imap_password_label, self.imap_password)

        self.imap_host = RoundedPlainTextField()
        self.imap_host.setPlaceholderText("imap.gmail.com")
        imap_host_label = QLabel("IMAP Host:")
        imap_host_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        imap_layout.addRow(imap_host_label, self.imap_host)

        self.imap_port = RoundedSpinner()
        self.imap_port.setRange(1, 65535)
        self.imap_port.setValue(993)
        imap_port_label = QLabel("IMAP Port:")
        imap_port_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        imap_layout.addRow(imap_port_label, self.imap_port)

        self.imap_tls = QCheckBox("Use TLS/SSL")
        self.imap_tls.setChecked(True)
        self.imap_tls.setStyleSheet(f"color: {TEXT_COLOR()};")
        imap_layout.addRow(self.imap_tls)

        self.bank_email_sender = RoundedPlainTextField()
        self.bank_email_sender.setPlaceholderText("noreply@yourbank.com")
        bank_email_label = QLabel("Bank Email Sender:")
        bank_email_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        imap_layout.addRow(bank_email_label, self.bank_email_sender)

        imap_group.setLayout(imap_layout)
        layout.addWidget(imap_group)

        # Email Message Templates Group
        templates_group = QGroupBox("Email Message Templates")
        templates_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        templates_layout = QFormLayout()

        # Payment Thank You Email Subject
        self.payment_subject = RoundedPlainTextField()
        self.payment_subject.setPlaceholderText("Payment Received - Thank You for {learner_name}'s Payment")
        payment_subject_label = QLabel("Payment Thank You Subject:")
        payment_subject_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        templates_layout.addRow(payment_subject_label, self.payment_subject)

        # Payment Thank You Email Body
        self.payment_body = RoundedTextEdit()
        self.payment_body.setPlaceholderText("Dear Parent/Guardian,\n\nWe are pleased to confirm that we have received your payment for {learner_name}.\n\nPayment Details:\nLearner: {learner_name}\nAmount: R{amount:.2f}\nDate: {payment_date}\n\nThank you for your continued support.\n\nBest regards,\nPro K-Maths Administration")
        self.payment_body.setMinimumHeight(100)
        payment_body_label = QLabel("Payment Thank You Body:")
        payment_body_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        templates_layout.addRow(payment_body_label, self.payment_body)

        # OCR Failure Email Subject
        self.ocr_subject = RoundedPlainTextField()
        self.ocr_subject.setPlaceholderText("OCR Processing Failed - {document_type} Document")
        ocr_subject_label = QLabel("OCR Failure Subject:")
        ocr_subject_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        templates_layout.addRow(ocr_subject_label, self.ocr_subject)

        # OCR Failure Email Body
        self.ocr_body = RoundedTextEdit()
        self.ocr_body.setPlaceholderText("Dear Administrator,\n\nThe system was unable to automatically process a {document_type} document using OCR.\n\nDocument Details:\nDocument Type: {document_type}\nFile Name: {filename}\n\nPlease review and enter the information manually.\n\nBest regards,\nPro K-Maths System")
        self.ocr_body.setMinimumHeight(100)
        ocr_body_label = QLabel("OCR Failure Body:")
        ocr_body_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        templates_layout.addRow(ocr_body_label, self.ocr_body)

        templates_group.setLayout(templates_layout)
        layout.addWidget(templates_group)

        # Admin Notification Settings Group
        admin_group = QGroupBox("Admin Notifications")
        admin_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        admin_layout = QFormLayout()

        self.admin_email = RoundedPlainTextField()
        self.admin_email.setPlaceholderText("admin@yourdomain.com")
        admin_email_label = QLabel("Admin Email (for OCR failures):")
        admin_email_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        admin_layout.addRow(admin_email_label, self.admin_email)

        admin_group.setLayout(admin_layout)
        layout.addWidget(admin_group)

        # Admin Password Verification Group
        admin_group = QGroupBox("Admin Verification")
        admin_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        admin_layout = QFormLayout()

        self.admin_password = RoundedPlainTextField()
        self.admin_password.setEchoMode(RoundedPlainTextField.EchoMode.Password)
        self.admin_password.setPlaceholderText("Enter admin password to save")
        admin_password_label = QLabel("Admin Password:")
        admin_password_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        admin_layout.addRow(admin_password_label, self.admin_password)

        admin_group.setLayout(admin_layout)
        layout.addWidget(admin_group)

        # Buttons
        button_layout = QHBoxLayout()
        test_btn = ButtonFactory.create_update_button("Test Connection")
        test_btn.clicked.connect(self.test_email_connection)
        save_btn = ButtonFactory.create_save_button("Save")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = ButtonFactory.create_cancel_button("Cancel")
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(test_btn)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        # Wrap the main layout in a widget so we can put it inside a scroll area
        container_widget = QWidget()
        container_widget.setLayout(layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container_widget)
        scroll.setStyleSheet("background: transparent; border: none;")

        # Add the scroll area to the window so long content gets scrollbars when needed
        self.add_widget(scroll)

    def load_settings(self):
        try:
            settings = self.shared_services.settings_use_case.get_email_settings()
            self.email_enabled.setChecked(self._as_bool(settings.get("email_enabled", False)))
            self.smtp_user.setText(str(settings.get("smtp_user", "") or ""))
            self.smtp_password.setText(str(settings.get("smtp_password", "") or ""))
            self.smtp_host.setText(str(settings.get("smtp_host", "smtp.gmail.com") or "smtp.gmail.com"))
            self.smtp_port.setValue(int(settings.get("smtp_port", 587) or 587))
            self.smtp_tls.setChecked(self._as_bool(settings.get("smtp_tls", True)))
            self.imap_user.setText(str(settings.get("imap_user", "") or ""))
            self.imap_password.setText(str(settings.get("imap_password", "") or ""))
            self.imap_host.setText(str(settings.get("imap_host", "imap.gmail.com") or "imap.gmail.com"))
            self.imap_port.setValue(int(settings.get("imap_port", 993) or 993))
            self.imap_tls.setChecked(self._as_bool(settings.get("imap_tls", True)))
            self.bank_email_sender.setText(str(settings.get("bank_email_sender", "") or ""))
            self.admin_email.setText(str(settings.get("admin_email", "") or ""))

            # Load email templates
            self.payment_subject.setText(str(settings.get("payment_subject", "Payment Received - Thank You for {learner_name}'s Payment") or ""))
            self.payment_body.setPlainText(str(settings.get("payment_body", "Dear Parent/Guardian,\n\nWe are pleased to confirm that we have received your payment for {learner_name}.\n\nPayment Details:\nLearner: {learner_name}\nAmount: R{amount:.2f}\nDate: {payment_date}\n\nThank you for your continued support.\n\nBest regards,\nPro K-Maths Administration") or ""))
            self.ocr_subject.setText(str(settings.get("ocr_subject", "OCR Processing Failed - {document_type} Document") or ""))
            self.ocr_body.setPlainText(str(settings.get("ocr_body", "Dear Administrator,\n\nThe system was unable to automatically process a {document_type} document using OCR.\n\nDocument Details:\nDocument Type: {document_type}\nFile Name: {filename}\n\nPlease review and enter the information manually.\n\nBest regards,\nPro K-Maths System") or ""))
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Error loading settings: {str(e)}")

    def save_settings(self):
        try:
            # Collect all settings data
            settings_data = {
                "email_enabled": self.email_enabled.isChecked(),
                "smtp_user": self.smtp_user.text(),
                "smtp_password": self.smtp_password.text(),
                "smtp_host": self.smtp_host.text(),
                "smtp_port": self.smtp_port.value(),
                "smtp_tls": self.smtp_tls.isChecked(),
                "imap_user": self.imap_user.text(),
                "imap_password": self.imap_password.text(),
                "imap_host": self.imap_host.text(),
                "imap_port": self.imap_port.value(),
                "imap_tls": self.imap_tls.isChecked(),
                "bank_email_sender": self.bank_email_sender.text(),
                "admin_email": self.admin_email.text(),
                "payment_subject": self.payment_subject.text(),
                "payment_body": self.payment_body.toPlainText(),
                "ocr_subject": self.ocr_subject.text(),
                "ocr_body": self.ocr_body.toPlainText()
            }

            # Save with admin password verification
            admin_password = self.admin_password.text()
            ok, error = self.shared_services.settings_use_case.save_email_settings(
                settings_data,
                admin_password=admin_password,
                actor_user_id=getattr(self.parent(), "current_user_id", None),
                actor_role=getattr(self.parent(), "current_user_role", None),
            )
            if not ok:
                QMessageBox.critical(self, "Error", error or "Failed to save email settings.")
                return

            QMessageBox.information(self, "Success", "Email settings saved successfully")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")

    def test_email_connection(self):
        """Test SMTP email connection."""
        try:
            from business.services.email_service import EmailService
            email_service = EmailService()

            if email_service.test_email_connection():
                QMessageBox.information(self, "Success", "SMTP connection test successful!")
            else:
                QMessageBox.warning(self, "Connection Failed", "SMTP connection test failed. Please check your settings.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection test error: {str(e)}")
