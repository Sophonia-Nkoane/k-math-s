import logging
from PySide6.QtWidgets import QFormLayout, QMessageBox, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from presentation.styles.colors import FIELD_BACKGROUND, TEXT_COLOR
from domain.services.authentication_service import AuthenticationService
from presentation.components.buttons import ButtonFactory
from presentation.components.rounded_field import RoundedPlainTextField
from presentation.components.window_component import WindowComponent

class LoginDialog(WindowComponent):
    def __init__(self, parent=None):
        super().__init__(parent, title="Login")
        self.logger = logging.getLogger(self.__class__.__name__)
        self.user_id = None
        self.username = None
        self.role = None
        self.set_size(300, 180)

        self.content_area.setStyleSheet(f"""
            QFrame {{
                background-color: {FIELD_BACKGROUND()};
            }}
        """)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(12)

        self.form_layout = QFormLayout()
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self.form_layout.setHorizontalSpacing(10)
        self.form_layout.setVerticalSpacing(10)

        self.username_input = RoundedPlainTextField(placeholder_text="Enter username")
        self.password_input = RoundedPlainTextField(placeholder_text="Enter password")
        self.password_input.setEchoMode(RoundedPlainTextField.EchoMode.Password)

        username_label = QLabel("Username:")
        username_label.setStyleSheet(f"color: {TEXT_COLOR()};")

        password_label = QLabel("Password:")
        password_label.setStyleSheet(f"color: {TEXT_COLOR()};")

        self.form_layout.addRow(username_label, self.username_input)
        self.form_layout.addRow(password_label, self.password_input)
        self.main_layout.addLayout(self.form_layout)

        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(10)

        login_button = ButtonFactory.create_ok_button()
        login_button.setText("Login")
        login_button.setMinimumWidth(100)
        login_button.clicked.connect(self.attempt_login)

        cancel_button = ButtonFactory.create_cancel_button()
        cancel_button.setMinimumWidth(100)
        cancel_button.clicked.connect(self.reject)

        self.button_layout.addStretch()
        self.button_layout.addWidget(login_button)
        self.button_layout.addWidget(cancel_button)

        self.main_layout.addLayout(self.button_layout)
        self.add_layout(self.main_layout)

        # Set focus to username input and connect Enter key
        self.username_input.setFocus()
        self.username_input.returnPressed.connect(self.handle_return)
        self.password_input.returnPressed.connect(self.handle_return)

    def handle_return(self):
        if self.username_input.text() and self.password_input.text():
            self.attempt_login()
        elif not self.username_input.text():
            self.username_input.setFocus()
        else:
            self.password_input.setFocus()

    def attempt_login(self):
        try:
            username = self.username_input.text()
            password = self.password_input.text()

            if not username or not password:
                QMessageBox.warning(self, "Error", "Please enter both username and password.")
                return

            auth_service = AuthenticationService(self.parent().db_manager)
            result, error = auth_service.validate_login(username, password)

            if error:
                QMessageBox.warning(self, "Error", error)
                return

            if result and isinstance(result, dict):
                self.logger.info(f"Processing login result: {result}")
                self.user_id = result.get('user_id')
                self.username = result.get('username')
                self.role = result.get('role')

                if all(x is not None for x in [self.user_id, self.username, self.role]):
                    self.logger.info(f"Login successful - user_id: {self.user_id}, username: {self.username}, role: {self.role}")
                    self.accept()
                else:
                    self.logger.error(f"Login failed - incomplete user data: {result}")
                    QMessageBox.warning(self, "Error", "Invalid login response from server")
            else:
                self.logger.warning(f"Login failed - invalid result format: {result}")
                QMessageBox.warning(self, "Error", "Invalid username or password.")
        except Exception as e:
            self.logger.exception("Exception in attempt_login")
            QMessageBox.critical(self, "Error", f"Login failed: {str(e)}")

    def get_user_details(self):
        """Returns the authenticated user's details as (user_id, role, username)."""
        return self.user_id, self.role, self.username
