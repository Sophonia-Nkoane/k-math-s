import re
from PySide6.QtWidgets import QWidget, QHBoxLayout, QFormLayout

from presentation.components.rounded_field import (
    RoundedPlainTextField,
    RoundedDropdown
)

class ContactInfoWidget(QWidget):
    """
    A reusable widget for capturing contact information including
    contact number with country code and email address.

    This widget combines contact number (with formatting) and email fields
    in a consistent layout that's used across the application.
    """

    def __init__(self, contact_placeholder="0XX-XXX-XXXX", email_placeholder="example@domain.com", parent=None):
        super().__init__(parent)

        self.contact_number_entry = RoundedPlainTextField()
        self.contact_number_entry.setPlaceholderText(contact_placeholder)
        self.contact_number_entry.textChanged.connect(self.format_contact_number_input)

        self.country_code_combobox = RoundedDropdown()
        self.country_code_combobox.addItems(["ZA (+27)", "UK (+44)", "US (+1)"])
        self.country_code_combobox.setCurrentText("ZA (+27)")

        self.email_entry = RoundedPlainTextField()
        self.email_entry.setPlaceholderText(email_placeholder)

        self.setup_layout()

    def setup_layout(self):
        """Sets up the layout for the contact information widget."""
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Contact row with number and country code
        contact_layout = QHBoxLayout()
        contact_layout.addWidget(self.contact_number_entry, 3)
        contact_layout.addWidget(self.country_code_combobox, 1)
        layout.addRow("Contact:", contact_layout)
        layout.addRow("Email:", self.email_entry)

    def format_contact_number_input(self):
        """Formats the contact number input dynamically."""
        sender = self.sender()
        current_text = sender.text()
        digits_only = re.sub(r'\D', '', current_text)

        if digits_only and digits_only[0] != '0' and len(digits_only) > 0:
             digits_only = '0' + digits_only[1:]

        formatted_text = ""
        if len(digits_only) > 0: formatted_text += digits_only[0]
        if len(digits_only) > 1: formatted_text += digits_only[1:3]
        if len(digits_only) > 3: formatted_text += "-" + digits_only[3:6]
        if len(digits_only) > 6: formatted_text += "-" + digits_only[6:10]
        formatted_text = formatted_text[:12]

        sender.blockSignals(True)
        sender.setText(formatted_text)
        sender.setCursorPosition(len(formatted_text))
        sender.blockSignals(False)

    def get_data(self):
        """Returns the contact data as a dictionary."""
        code_display = self.country_code_combobox.currentText()
        code = code_display.split(' ')[0] if code_display else None
        return {
            'country_code': code,
            'contact_number': self.contact_number_entry.text().strip(),
            'email': self.email_entry.text().strip() or None
        }

    def set_data(self, data):
        """Sets the contact data from a dictionary."""
        if not data:
            return

        self.contact_number_entry.setText(data.get('contact_number', ''))

        country_code = data.get('country_code')
        if country_code:
            display_text = self._get_country_code_display(country_code)
            if display_text:
                self.country_code_combobox.setCurrentText(display_text)

        self.email_entry.setText(data.get('email', ''))

    def _get_country_code_display(self, country_code):
        """Converts a country code (e.g., 'ZA') to its display format (e.g., 'ZA (+27)')."""
        code_map = {"ZA": "ZA (+27)", "UK": "UK (+44)", "US": "US (+1)"}
        return code_map.get(country_code.upper())

    def clear_data(self):
        """Clears all contact fields."""
        self.contact_number_entry.clear()
        self.country_code_combobox.setCurrentText("ZA (+27)")
        self.email_entry.clear()

    def set_contact_number_enabled(self, enabled):
        """Enables or disables the contact number field."""
        self.contact_number_entry.setEnabled(enabled)

    def set_email_enabled(self, enabled):
        """Enables or disables the email field."""
        self.email_entry.setEnabled(enabled)

    def set_country_code_enabled(self, enabled):
        """Enables or disables the country code dropdown."""
        self.country_code_combobox.setEnabled(enabled)
