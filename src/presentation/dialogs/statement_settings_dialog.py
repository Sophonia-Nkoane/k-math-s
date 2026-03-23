import base64

from PySide6.QtWidgets import (QVBoxLayout, QLabel, 
                            QFileDialog, QMessageBox, QHBoxLayout)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
import os
from utils.settings_manager import SettingsManager, SettingsSaveError
from presentation.components.buttons import ButtonFactory
from presentation.components.rounded_field import RoundedPlainTextField, RoundedTextEdit
from presentation.components.success_dialog import SuccessDialog
from presentation.components.window_component import WindowComponent
from presentation.styles.colors import TEXT_COLOR, FIELD_BORDER_COLOR, FIELD_BACKGROUND

CONFIG_FILE = "statement_config.json"
# Ensure resources directory exists
RESOURCES_DIR = os.path.join("presentation", "resources")  # Updated path to reflect move

class StatementSettingsDialog(WindowComponent):
    def __init__(self, parent=None):
        super().__init__(parent, title="Statement Settings")
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.load_statement_settings()
        self.original_logo_path = self.settings.get("logo_path", "")
        self.new_logo_path_temp = None
        
        self.set_size(650, 700)  # Set initial size to better fit content
        self.setup_ui()
        
    def setup_ui(self):
        # Use the container layout from WindowComponent
        layout = self.container_layout
        
        # Logo Group Box
        logo_group_box = QVBoxLayout()
        logo_label = QLabel("Company Logo:")
        logo_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        logo_group_box.addWidget(logo_label)
        
        
        # Logo Preview
        logo_display_layout = QHBoxLayout()  # Changed to QHBoxLayout for horizontal arrangement
        
        # Logo Buttons - Now on the left
        logo_button_layout = QVBoxLayout()  # Changed to QVBoxLayout for vertical button arrangement
        browse_button = ButtonFactory.create_view_button("Browse Logo")
        browse_button.clicked.connect(self.browse_logo)
        clear_logo_button = ButtonFactory.create_clear_button("Clear Logo")
        clear_logo_button.clicked.connect(self.clear_logo)
        logo_button_layout.addWidget(browse_button)
        logo_button_layout.addWidget(clear_logo_button)
        logo_display_layout.addLayout(logo_button_layout)
        
        # Add spacing between buttons and logo
        logo_display_layout.addSpacing(20)
        
        # Logo Preview - Now on the right with smaller size
        self.logo_preview = QLabel()
        self.logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_preview.setFixedSize(200, 100)  # Set smaller fixed size for the logo
        self.logo_preview.setStyleSheet(
            f"border: 1px solid {FIELD_BORDER_COLOR()}; background-color: {FIELD_BACKGROUND()};"
        )
        logo_display_layout.addWidget(self.logo_preview)
        
        # Load existing logo if available
        if self.settings.get("logo_data"):
            self.update_logo_preview(logo_data=self.settings["logo_data"])
        elif self.settings.get("logo_path"):
            self.update_logo_preview(file_path=self.settings["logo_path"])
            
        logo_group_box.addLayout(logo_display_layout)
        layout.addLayout(logo_group_box)
        layout.addSpacing(10)
        
        # Company Address
        address_label = QLabel("Company Address:")
        address_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        layout.addWidget(address_label)
        self.address_edit = RoundedTextEdit(placeholder_text="Enter company address (street, city, code)")
        self.address_edit.setText(self.settings.get("address", ""))
        self.address_edit.setFixedHeight(60)
        layout.addWidget(self.address_edit)
        
        # Contact Information
        contact_layout = QHBoxLayout()
        
        # WhatsApp Number
        whatsapp_layout = QVBoxLayout()
        whatsapp_label = QLabel("WhatsApp Number:")
        whatsapp_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        whatsapp_layout.addWidget(whatsapp_label)
        self.whatsapp_edit = RoundedPlainTextField(placeholder_text="e.g., 0731234567")
        self.whatsapp_edit.setText(self.settings.get("whatsapp", ""))
        whatsapp_layout.addWidget(self.whatsapp_edit)
        contact_layout.addLayout(whatsapp_layout)
        
        # Phone Number
        phone_layout = QVBoxLayout()
        phone_label = QLabel("Phone Number (Optional):")
        phone_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        phone_layout.addWidget(phone_label)
        self.phone_edit = RoundedPlainTextField(placeholder_text="e.g., 0161234567")
        self.phone_edit.setText(self.settings.get("phone", ""))
        phone_layout.addWidget(self.phone_edit)
        contact_layout.addLayout(phone_layout)
        layout.addLayout(contact_layout)
        
        # Statement Message
        statement_label = QLabel("Statement Footer Message:")
        statement_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        layout.addWidget(statement_label)
        self.statement_edit = RoundedTextEdit(placeholder_text="e.g., Please contact us if you have any questions.")
        self.statement_edit.setText(self.settings.get("statement_message", ""))
        self.statement_edit.setFixedHeight(60)
        layout.addWidget(self.statement_edit)
        
        # Statement Footer Email
        email_label = QLabel("Statement Footer Email:")
        email_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        layout.addWidget(email_label)
        self.email_edit = RoundedPlainTextField(placeholder_text="e.g., example@domain.com")
        self.email_edit.setText(self.settings.get("email", ""))
        layout.addWidget(self.email_edit)
        
        # Thank You Message
        thank_you_label = QLabel("Bottom Statement Footer Message:")
        thank_you_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        layout.addWidget(thank_you_label)
        self.thank_you_edit = RoundedTextEdit(placeholder_text="e.g., Thank you for your prompt payment!")
        self.thank_you_edit.setText(self.settings.get("thank_you_message", ""))
        self.thank_you_edit.setFixedHeight(60)
        layout.addWidget(self.thank_you_edit)
        
        layout.addSpacing(10)
        
        # Bank Details Section
        bank_details_label = QLabel("Bank Details:")
        bank_details_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        layout.addWidget(bank_details_label)
        bank_details_layout = QVBoxLayout()
        bank_details_layout.setContentsMargins(10, 5, 10, 5)
        
        # Bank Name
        bank_name_layout = QHBoxLayout()
        bank_name_label = QLabel("Bank Name:")
        bank_name_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        bank_name_layout.addWidget(bank_name_label)
        self.bank_name_edit = RoundedPlainTextField(placeholder_text="e.g., FNB, Standard Bank")
        self.bank_name_edit.setText(self.settings.get("bank_name", ""))
        bank_name_layout.addWidget(self.bank_name_edit)
        bank_details_layout.addLayout(bank_name_layout)
        
        # Account Holder
        acc_holder_layout = QHBoxLayout()
        acc_holder_label = QLabel("Account Holder:")
        acc_holder_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        acc_holder_layout.addWidget(acc_holder_label)
        self.acc_holder_edit = RoundedPlainTextField(placeholder_text="e.g., Company Name Pty Ltd")
        self.acc_holder_edit.setText(self.settings.get("account_holder", ""))
        acc_holder_layout.addWidget(self.acc_holder_edit)
        bank_details_layout.addLayout(acc_holder_layout)
        
        # Account Number
        acc_num_layout = QHBoxLayout()
        acc_num_label = QLabel("Account Number:")
        acc_num_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        acc_num_layout.addWidget(acc_num_label)
        self.acc_num_edit = RoundedPlainTextField(placeholder_text="e.g., 1234567890")
        self.acc_num_edit.setText(self.settings.get("account_number", ""))
        acc_num_layout.addWidget(self.acc_num_edit)
        bank_details_layout.addLayout(acc_num_layout)
        
        layout.addLayout(bank_details_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        save_button = ButtonFactory.create_save_button("Save")
        save_button.clicked.connect(self.save_settings)
        cancel_button = ButtonFactory.create_cancel_button("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def update_logo_preview(self, file_path=None, logo_data=None):
        """Updates the logo preview label."""
        pixmap = QPixmap()
        if logo_data and str(logo_data).startswith("data:"):
            try:
                _, encoded = str(logo_data).split(",", 1)
                pixmap.loadFromData(base64.b64decode(encoded))
            except Exception:
                pixmap = QPixmap()
        elif file_path and os.path.exists(file_path):
            pixmap = QPixmap(file_path)

        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                self.logo_preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_preview.setPixmap(scaled_pixmap)
            return
        self.logo_preview.clear()
        self.logo_preview.setText("No Logo")


    def browse_logo(self):
        """Opens file dialog to select a logo."""
        # Keep this method in the UI class
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.new_logo_path_temp = file_path # Store the newly selected path temporarily
            self.update_logo_preview(file_path)

    def clear_logo(self):
        """Clears the selected logo."""
        # Keep this method in the UI class
        self.new_logo_path_temp = "" # Set temp path to empty string
        self.update_logo_preview(None) # Update preview to show "No Logo"

    def save_settings(self):
        """Gathers data from fields and calls the SettingsManager to save."""
        # Create a dictionary with the current UI values
        updated_settings = {
            "address": self.address_edit.toPlainText().strip(),
            "whatsapp": self.whatsapp_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "thank_you_message": self.thank_you_edit.toPlainText().strip(),
            "statement_message": self.statement_edit.toPlainText().strip(),
            "email": self.email_edit.text().strip(),
            "bank_name": self.bank_name_edit.text().strip(),
            "account_holder": self.acc_holder_edit.text().strip(),
            "account_number": self.acc_num_edit.text().strip(),
            # The actual logo_path currently stored in settings will be handled by the manager
            "logo_path": self.settings.get("logo_path", "") # Pass current path for comparison
        }

        try:
            # Call the manager's save method, passing the updated data
            # and the temporary path for the new logo (if any)
            self.settings_manager.save_statement_settings(updated_settings, self.new_logo_path_temp)
            # Update the internal settings dict and original logo path upon successful save
            self.settings = self.settings_manager.load_statement_settings() # Reload settings after save
            self.original_logo_path = self.settings.get("logo_path", "")
            self.new_logo_path_temp = self.original_logo_path # Reset temp path

            success_dialog = SuccessDialog("Statement settings have been updated successfully.", self)
            success_dialog.exec()
            self.accept() # Close dialog

        except SettingsSaveError as e: # Catch specific validation/save errors from manager
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e: # Catch other potential errors during save
            QMessageBox.critical(self, "Save Error", f"Failed to save statement settings: {e}")
