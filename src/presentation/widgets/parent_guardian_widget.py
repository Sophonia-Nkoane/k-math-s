import re
from PySide6.QtWidgets import QWidget, QGroupBox, QFormLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt
from presentation.components.rounded_field import RoundedPlainTextField, RoundedDropdown, ThemedWidgetMixin
from presentation.components.buttons import ButtonFactory
from presentation.widgets.contact_info_widget import ContactInfoWidget
from presentation.styles import styles

class ParentGuardianWidget(ThemedWidgetMixin, QWidget):
    """A reusable widget for capturing Parent or Guardian details."""
    remove_requested = Signal() # Define the signal

    def __init__(self, show_remove_button=True, allow_guardian=True, hide_relationship=False, parent=None):
        super().__init__(parent)

        self.hide_relationship = hide_relationship

        self.group_box = QGroupBox("Parent / Guardian Details")
        self.group_box.setStyleSheet(styles.GROUP_BOX_STYLE)
        layout = QFormLayout(self.group_box)

        # Only create and add relationship dropdown if not hidden
        if not hide_relationship:
            self.relationship_combobox = RoundedDropdown()
            self.relationship_combobox.addItem("-- Select Option --")

            # Add relationship options based on what's allowed
            if allow_guardian:
                self.relationship_combobox.addItems(["Parent", "Guardian"])
            else:
                self.relationship_combobox.addItem("Parent")

            layout.addRow("Relationship:", self.relationship_combobox)
        else:
            self.relationship_combobox = None

        self.title_combobox = RoundedDropdown()
        self.title_combobox.addItem("-- Select Option --")
        self.title_combobox.addItems(["Mr", "Mrs", "Ms", "Miss", "Dr", "Prof"])
        self.name_entry = RoundedPlainTextField()
        self.surname_entry = RoundedPlainTextField()

        # Use the reusable contact info widget
        self.contact_info_widget = ContactInfoWidget(
            contact_placeholder="0XX-XXX-XXXX",
            email_placeholder="example@domain.com"
        )

        layout.addRow("Title:", self.title_combobox)
        layout.addRow("Name:", self.name_entry)
        layout.addRow("Surname:", self.surname_entry)
        layout.addRow(self.contact_info_widget)

        # Add remove button
        self.remove_button = ButtonFactory.create_delete_icon_button()
        self.remove_button.clicked.connect(self.clear_data)
        self.remove_button.setVisible(show_remove_button)

        # Main layout for the widget itself to hold the group box and remove button
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self.group_box)
        main_layout.addWidget(self.remove_button, alignment=Qt.AlignTop | Qt.AlignRight)
        main_layout.setContentsMargins(0, 0, 0, 0)

    def set_remove_button_visible(self, visible):
        self.remove_button.setVisible(visible)

    def format_contact_number_input(self):
        sender = self.sender()
        current_text = sender.text()
        digits_only = re.sub(r'\\D', '', current_text)

        if digits_only and digits_only[0] != '0' and len(digits_only) > 0:
             # This logic might need adjustment for international numbers if ZA isn't default
             # For simplicity, keeping the original logic for now.
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
        contact_data = self.contact_info_widget.get_data()
        return {
            "relationship_type": self.relationship_combobox.currentText() if self.relationship_combobox and self.relationship_combobox.currentText() != "-- Select Option --" else None,
            "title": self.title_combobox.currentText() if self.title_combobox.currentText() != "-- Select Option --" else None,
            "name": self.name_entry.text().strip(),
            "surname": self.surname_entry.text().strip(),
            "country_code": contact_data["country_code"],
            "contact_number": contact_data["contact_number"],
            "email": contact_data["email"],
        }

    def set_data(self, data):
        if self.relationship_combobox:
            self.relationship_combobox.setCurrentText(data.get("relationship_type", "") or "-- Select Option --")
        self.title_combobox.setCurrentText(data.get("title", "") or "-- Select Option --")
        self.name_entry.setText(data.get("name", "") or "")
        self.surname_entry.setText(data.get("surname", "") or "")

        # Set contact info using the reusable widget
        contact_data = {
            "country_code": data.get("country_code"),
            "contact_number": data.get("contact_number", ""),
            "email": data.get("email")
        }
        self.contact_info_widget.set_data(contact_data)

    def _get_country_code_display(self, code):
        if not code: return None
        code_map = {"ZA": "ZA (+27)", "UK": "UK (+44)", "US": "US (+1)"}
        return code_map.get(code.upper())

    def clear_data(self):
        if self.relationship_combobox:
            self.relationship_combobox.setCurrentIndex(0)
        self.title_combobox.setCurrentIndex(0)
        self.name_entry.clear()
        self.surname_entry.clear()
        self.contact_info_widget.clear_data()
