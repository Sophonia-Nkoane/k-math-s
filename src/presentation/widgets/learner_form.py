import calendar
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QHBoxLayout, QSlider, QLabel, QPushButton
)
from PySide6.QtCore import QDate, Qt

from presentation.components.rounded_field import (
    RoundedPlainTextField,
    RoundedSpinner,
    RoundedCalendarDropdown,
    RoundedDropdown,
    RoundedCheckBox
)
from presentation.components.buttons import ButtonFactory
from presentation.styles import styles
from presentation.widgets.parent_guardian_widget import ParentGuardianWidget
from presentation.widgets.contact_info_widget import ContactInfoWidget
from utils.payment_schedule import format_scheduled_dates

class LearnerForm(QWidget):
    """
    A comprehensive form widget for capturing and editing learner details.

    This widget includes fields for learner personal information, contact details,
    parent/guardian information, academic details (grade, subjects), and detailed
    payment and billing settings.

    It is designed to be embedded within a dialog, such as 'AddUpdateLearnerDialog'.
    The form handles its own internal layout and provides methods to get and set
    learner data using a LearnerDTO object. It also manages dynamic UI updates,
    like populating dropdowns based on other selections.
    """
    def __init__(self, acc_no=None, parent=None):
        super().__init__(parent)
        self.acc_no = acc_no

        # Caches for dropdown data
        self.payment_options_cache = {}
        self.payment_terms_cache = {}
        self.families_cache = {}

        self._create_widgets()
        self.setup_layout()
        self._connect_signals()
        self._update_subject_dropdown(self.grade_spinbox.value())

    def _create_widgets(self):
        """Creates all the widgets for the dialog."""
        self.name_entry = RoundedPlainTextField()
        self.surname_entry = RoundedPlainTextField()
        self.dob_entry = RoundedCalendarDropdown()

        self.gender_combobox = RoundedDropdown()
        self.gender_combobox.addItem("-- Select Option --")
        self.gender_combobox.addItem("Male")
        self.gender_combobox.addItem("Female")
        self.gender_combobox.addItem("Other")

        # Use the reusable contact info widget for learner contact details
        self.learner_contact_info_widget = ContactInfoWidget(
            contact_placeholder="0XX-XXX-XXXX",
            email_placeholder="learner@example.com"
        )

        # Always show parent/guardian section for first parent
        self.parent_guardian_widget = ParentGuardianWidget(show_remove_button=False)
        self.parent_guardian_widget.setVisible(True)

        # Checkbox and widget for second parent
        self.add_second_parent_checkbox = RoundedCheckBox("Add Second Parent")
        self.add_second_parent_checkbox.setChecked(False)
        self.second_parent_guardian_widget = ParentGuardianWidget(show_remove_button=False, allow_guardian=False, hide_relationship=True)
        self.second_parent_guardian_widget.setVisible(False)

        self.grade_spinbox = RoundedSpinner()
        self.grade_spinbox.setRange(0, 13)
        self.grade_spinbox.setValue(0)

        self.subjects_count_combobox = RoundedDropdown()
        self.payment_option_combobox = RoundedDropdown()
        self.bypass_amount_checkbox = RoundedCheckBox("Bypass Amount Manually")
        self.bypass_amount_checkbox.setChecked(False)
        self.manual_amount_entry = RoundedPlainTextField()
        self.manual_amount_entry.setPlaceholderText("Enter special amount")
        self.manual_amount_entry.setEnabled(False)

        self.payment_term_combobox = RoundedDropdown()
        self.payment_term_combobox.addItem("-- Select Option --")

        self.payment_schedule_entry = RoundedPlainTextField()
        self.payment_schedule_entry.setPlaceholderText("e.g. 2026-02-15, 2026-03-20")

        self.billing_start_date_edit = RoundedCalendarDropdown()

        self.family_combobox = RoundedDropdown()
        self.family_checkbox = RoundedCheckBox("Link to Family")
        self.family_checkbox.setChecked(False)

        self.clear_family_button = ButtonFactory.create_clear_button("Clear Family")
        self.clear_family_button.setVisible(self.acc_no is not None)
        self.family_combobox.setEnabled(False)

        self.is_new_learner_check = RoundedCheckBox("New Learner Enrollment")
        self.is_new_learner_check.setChecked(False)
        self.apply_admission_fee_check = RoundedCheckBox("Apply Admission Fee (if applicable)")
        self.apply_admission_fee_check.setChecked(False)
        self.custom_admission_fee_checkbox = RoundedCheckBox("Custom Admission Fee")
        self.custom_admission_fee_checkbox.setChecked(False)
        self.custom_admission_entry = RoundedPlainTextField()
        self.custom_admission_entry.setPlaceholderText("Enter custom admission amount")
        self.custom_admission_entry.setEnabled(False)
        self.skip_initial_fee_check = RoundedCheckBox("Skip Initial Monthly Fee")
        self.skip_initial_fee_check.setChecked(False)

        # Progress tracking fields (for grades 1-7)
        # Old spinbox replaced by a slider + quick preset buttons for simplicity
        self.progress_percentage_spinbox = RoundedSpinner()
        self.progress_percentage_spinbox.setRange(0, 100)
        self.progress_percentage_spinbox.setValue(0)
        self.progress_percentage_spinbox.setSuffix("%")
        self.progress_percentage_spinbox.setEnabled(False)  # keep for backward compatibility/hiding

        self.progress_slider = QSlider()
        self.progress_slider.setOrientation(Qt.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(False)

        self.progress_label = QLabel("0%")

        # Quick preset buttons (0,25,50,75,100)
        self.progress_quick_buttons = []
        for pct in (0, 25, 50, 75, 100):
            btn = QPushButton(f"{pct}%")
            btn.setProperty('progress_value', pct)
            btn.setEnabled(False)
            self.progress_quick_buttons.append(btn)

        self.progress_group = QGroupBox("Progress Tracking (Grades 1-7)")
        self.progress_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        self.progress_group.setVisible(False)  # Initially hidden

    def _connect_signals(self):
        self.family_checkbox.toggled.connect(self._toggle_family_link)
        self.bypass_amount_checkbox.toggled.connect(self._toggle_manual_amount)
        self.custom_admission_fee_checkbox.toggled.connect(self._toggle_custom_admission_amount)
        self.add_second_parent_checkbox.toggled.connect(self._toggle_second_parent_widget)
        self.grade_spinbox.valueChanged.connect(self._update_subject_dropdown)
        self.grade_spinbox.valueChanged.connect(self._handle_grade_change)
        self.subjects_count_combobox.currentTextChanged.connect(self._handle_subject_change)
        # Progress controls signals
        self.progress_slider.valueChanged.connect(self._on_progress_slider_changed)
        for btn in getattr(self, 'progress_quick_buttons', []):
            btn.clicked.connect(self._on_quick_progress_clicked)

    def _on_progress_slider_changed(self, value):
        # Keep label and legacy spinbox in sync
        try:
            self.progress_label.setText(f"{int(value)}%")
        except Exception:
            self.progress_label.setText(str(value))
        # update legacy spinbox value
        if hasattr(self, 'progress_percentage_spinbox'):
            self.progress_percentage_spinbox.setValue(int(value))

    def _on_quick_progress_clicked(self):
        sender = self.sender()
        if not sender:
            return
        pct = sender.property('progress_value')
        try:
            pct = int(pct)
        except Exception:
            return
        self.progress_slider.setValue(pct)
        # slider signal will update label and spinbox

    def populate_initial_data(self, families, payment_terms, payment_options):
        """
        Populates the form's dropdowns with initial data from the database.
        This method should be called after the form is created.
        """
        self.set_families(families)
        self.set_payment_terms(payment_terms)
        self.set_payment_options(payment_options)

    def set_families(self, families):
        """Sets the available families and updates the UI."""
        self.families_cache = families if families else {}
        self._populate_families()

    def _populate_families(self):
        """Populates the family dropdown."""
        current_family = self.family_combobox.currentText()
        self.family_combobox.clear()
        self.family_combobox.addItem("-- Select Option --")
        if hasattr(self, 'families_cache'):
            for family_name in sorted(self.families_cache.keys()):
                self.family_combobox.addItem(family_name)
        self.family_combobox.setCurrentText(current_family)

    def set_payment_terms(self, payment_terms):
        """Sets the available payment terms and updates the UI."""
        self.payment_terms_cache = payment_terms if payment_terms else {}
        self._populate_payment_terms()

    def _populate_payment_terms(self):
        """Populates the payment term dropdown."""
        current_term = self.payment_term_combobox.currentText()
        self.payment_term_combobox.clear()
        self.payment_term_combobox.addItem("-- Select Option --")
        if hasattr(self, 'payment_terms_cache'):
            for term_name in sorted(self.payment_terms_cache.keys()):
                self.payment_term_combobox.addItem(term_name)
        self.payment_term_combobox.setCurrentText(current_term)

    def set_payment_options(self, payment_options):
        """Sets the available payment options and updates the UI."""
        self.payment_options_cache = payment_options if payment_options else {}
        self._update_payment_options()

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

    def _handle_grade_change(self, grade):
        if grade > 0:
            self.grade_spinbox.setMinimum(1)

        # Show/hide progress tracking for grades 1-7
        is_grade_1_7 = 1 <= grade <= 7
        self.progress_group.setVisible(is_grade_1_7)
        # enable/disable slider, spinbox and quick buttons
        self.progress_slider.setEnabled(is_grade_1_7)
        self.progress_percentage_spinbox.setEnabled(is_grade_1_7)
        for btn in getattr(self, 'progress_quick_buttons', []):
            btn.setEnabled(is_grade_1_7)
        if not is_grade_1_7:
            self.progress_slider.setValue(0)
            self.progress_percentage_spinbox.setValue(0)
            self.progress_label.setText("0%")

    def _handle_subject_change(self, subject_text):
        self._update_payment_option_status()

    def _update_subject_dropdown(self, grade):
        """Updates the subject count dropdown based on the selected grade."""
        self.subjects_count_combobox.clear()
        self.subjects_count_combobox.addItem("-- Select --")
        if grade == 0:
            self.subjects_count_combobox.setEnabled(False)
        else:
            self.subjects_count_combobox.setEnabled(True)
            if 1 <= grade <= 7:
                self.subjects_count_combobox.addItems(["1"])
            elif 8 <= grade <= 12:
                self.subjects_count_combobox.addItems(["1", "2"])
            else: # for grade 13
                self.subjects_count_combobox.addItems(["1"])

    def _update_payment_option_status(self):
        """
        Disables/enables the payment option dropdown based on bypass status and subject selection.
        If enabled, it validates the current selection and attempts to auto-select a default
        if no valid option is chosen.
        """
        is_bypassed = self.bypass_amount_checkbox.isChecked()
        subjects_text = self.subjects_count_combobox.currentText()

        # Disable and reset if bypassed or no subjects selected
        if is_bypassed or subjects_text == "-- Select --":
            self.payment_option_combobox.setEnabled(False)
            self.payment_option_combobox.setCurrentIndex(0)
            return

        # Enable if not bypassed and subjects are selected
        self.payment_option_combobox.setEnabled(True)
        
        grade = self.grade_spinbox.value()
        try:
            subjects = int(subjects_text)
        except (ValueError, TypeError):
            subjects = 0

        current_option_name = self.payment_option_combobox.currentText()
        
        # Check if the currently selected option is valid for the current grade/subjects
        is_current_option_valid = False
        if current_option_name != "-- Select Option --" and grade > 0 and subjects > 0:
            for option_key in self.payment_options_cache.keys():
                option_name, option_subjects, option_grade = option_key
                if (option_name == current_option_name and
                    option_grade == grade and 
                    option_subjects == subjects):
                    is_current_option_valid = True
                    break
        
        # If the current selection is valid, do nothing and keep it.
        if is_current_option_valid:
            return

        # If the current selection is NOT valid (or no option is selected),
        # reset and try to find a suitable default for the new grade/subject combo.
        self.payment_option_combobox.setCurrentIndex(0)
        if grade > 0 and subjects > 0:
            matching_option = None
            # Sort keys for deterministic behavior when picking a default
            for option_key in sorted(self.payment_options_cache.keys()):
                option_name, option_subjects, option_grade = option_key
                if option_grade == grade and option_subjects == subjects:
                    matching_option = option_name
                    break  # Found the first suitable option
            
            if matching_option:
                index = self.payment_option_combobox.findText(matching_option)
                if index != -1:
                    self.payment_option_combobox.setCurrentIndex(index)

    def _toggle_family_link(self, checked):
        self.family_combobox.setEnabled(checked)

    def _toggle_parent_widget(self, checked):
        self.parent_guardian_widget.setVisible(checked)

    def _toggle_second_parent_widget(self, checked):
        self.second_parent_guardian_widget.setVisible(checked)
        if checked:
            # Automatically set relationship to "Second Parent" when checkbox is checked
            second_parent_data = self.second_parent_guardian_widget.get_data()
            second_parent_data['relationship_type'] = 'Second Parent'
            # Create a minimal data dict to set the relationship
            self.second_parent_guardian_widget.set_data(second_parent_data)

    def _toggle_manual_amount(self, checked):
        self.manual_amount_entry.setEnabled(checked)
        self._update_payment_option_status()

    def _toggle_custom_admission_amount(self, checked):
        self.custom_admission_entry.setEnabled(checked)

    def _update_payment_options(self, learner_option=None): # learner_option might be int or str from signal
        """
        Populates the payment option dropdown and sets the current selection
        based on the selected grade and subject count.
        """
        # If called by a signal, learner_option might be an int or str (from spinbox/combobox).
        # We only care about it if it's explicitly passed as a string representing a selection.
        if not isinstance(learner_option, str):
            learner_option = None # Ignore if it's not a string for selection
            
        grade = self.grade_spinbox.value()
        subjects_text = self.subjects_count_combobox.currentText()
        subjects = int(subjects_text) if subjects_text.isdigit() else 0

        self.payment_option_combobox.blockSignals(True) # Block signals to prevent re-entry
        self.payment_option_combobox.clear()
        self.payment_option_combobox.addItem("-- Select Option --")

        # Filter payment options based on grade and subjects, excluding manual options
        # Ensure payment_options_cache is populated before filtering
        if hasattr(self, 'payment_options_cache') and self.payment_options_cache:
            filtered_options = sorted([
                option_name for (option_name, sub_count, opt_grade), data in self.payment_options_cache.items()
                if opt_grade == grade and sub_count == subjects and not option_name.startswith("MANUAL")
            ])
            self.payment_option_combobox.addItems(filtered_options)

        # If a standard learner_option is provided, try to set it
        if learner_option and not learner_option.startswith("MANUAL"):
            index = self.payment_option_combobox.findText(learner_option)
            if index != -1:
                self.payment_option_combobox.setCurrentIndex(index)

        self.payment_option_combobox.blockSignals(False) # Unblock signals
        self._update_payment_option_status() # Call the status updater after populating

    def _get_country_code_display(self, country_code):
        """Converts a country code (e.g., 'ZA') to its display format (e.g., 'ZA (+27)')."""
        for i in range(self.country_code_combobox.count()):
            item_text = self.country_code_combobox.itemText(i)
            if item_text.startswith(country_code):
                return item_text
        return country_code

    def _parse_float_safely(self, value):
        """Safely parse a string to float, returning None if invalid."""
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _parse_scheduled_dates_input(self):
        raw_text = self.payment_schedule_entry.text().strip()
        if not raw_text:
            return [], "At least one payment schedule date is required."

        valid_dates = []
        invalid_parts = []
        for part in [item.strip() for item in raw_text.split(",") if item.strip()]:
            try:
                year_text, month_text, day_text = part.split("-")
                year = int(year_text)
                month = int(month_text)
                day = int(day_text)
                last_day = calendar.monthrange(year, month)[1]
                if not 1 <= day <= last_day:
                    raise ValueError
                normalized = f"{year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                invalid_parts.append(part)
                continue
            if normalized not in valid_dates:
                valid_dates.append(normalized)

        if invalid_parts:
            return [], f"Payment schedule dates must use YYYY-MM-DD. Invalid: {', '.join(invalid_parts)}."

        if not valid_dates:
            return [], "At least one payment schedule date is required."

        valid_dates.sort()
        return valid_dates, ""

    def setup_layout(self):
        """Sets up the layout of the dialog, including scroll area and form layouts."""
        form_container_layout = QVBoxLayout(self)

        learner_group = QGroupBox("Learner Details")
        learner_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        learner_layout = QFormLayout(learner_group)
        learner_layout.addRow("Name:", self.name_entry)
        learner_layout.addRow("Surname:", self.surname_entry)
        learner_layout.addRow("DOB:", self.dob_entry)
        learner_layout.addRow("Gender:", self.gender_combobox)
        # Add the learner contact info widget
        learner_layout.addRow(self.learner_contact_info_widget)
        form_container_layout.addWidget(learner_group)

        form_container_layout.addWidget(self.parent_guardian_widget)

        # Add checkbox and second parent widget
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addWidget(self.add_second_parent_checkbox)
        checkbox_layout.addStretch()
        form_container_layout.addLayout(checkbox_layout)
        form_container_layout.addWidget(self.second_parent_guardian_widget)

        grade_subject_payment_group = QGroupBox("Academic & Payment")
        grade_subject_payment_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        grade_subject_payment_layout = QFormLayout(grade_subject_payment_group)
        grade_subject_payment_layout.addRow("Grade:", self.grade_spinbox)
        grade_subject_payment_layout.addRow("Subjects:", self.subjects_count_combobox)
        grade_subject_payment_layout.addRow("Payment Option:", self.payment_option_combobox)

        checkbox_layout = QHBoxLayout()
        checkbox_layout.addWidget(self.bypass_amount_checkbox)
        checkbox_layout.addWidget(self.custom_admission_fee_checkbox)
        grade_subject_payment_layout.addRow(checkbox_layout)

        amount_layout = QHBoxLayout()
        amount_layout.addWidget(self.manual_amount_entry)
        amount_layout.addWidget(self.custom_admission_entry)
        grade_subject_payment_layout.addRow("Manual Amount:", amount_layout)

        grade_subject_payment_layout.addRow("Payment Term:", self.payment_term_combobox)
        grade_subject_payment_layout.addRow("Billing Start Date:", self.billing_start_date_edit)
        grade_subject_payment_layout.addRow("Payment Schedule Dates:", self.payment_schedule_entry)

        family_layout = QHBoxLayout()
        family_layout.addWidget(self.family_checkbox, 1)
        family_layout.addWidget(self.family_combobox, 3)
        family_layout.addWidget(self.clear_family_button, 1)
        grade_subject_payment_layout.addRow("Family:", family_layout)

        grade_subject_payment_layout.addRow(self.is_new_learner_check)
        grade_subject_payment_layout.addRow(self.apply_admission_fee_check)
        grade_subject_payment_layout.addRow(self.skip_initial_fee_check)
        form_container_layout.addWidget(grade_subject_payment_group)

        # Add progress tracking group (slider + quick buttons + label)
        progress_layout = QFormLayout(self.progress_group)
        # Horizontal layout for slider + label
        slider_row = QHBoxLayout()
        slider_row.addWidget(self.progress_slider, 5)
        slider_row.addWidget(self.progress_label, 1)
        progress_layout.addRow("Progress Percentage:", slider_row)

        # Quick preset buttons
        quick_row = QHBoxLayout()
        for btn in self.progress_quick_buttons:
            quick_row.addWidget(btn)
        quick_row.addStretch()
        progress_layout.addRow(quick_row)
        form_container_layout.addWidget(self.progress_group)

    def validate_form(self):
        """Validates the form data."""
        if not self.name_entry.text().strip():
            return False, "Name is required."
        if not self.surname_entry.text().strip():
            return False, "Surname is required."
        if not self.dob_entry.date().isValid():
            return False, "Date of Birth is required."
        if self.gender_combobox.currentText() == "-- Select Option --":
            return False, "Gender is required."
        learner_contact_data = self.learner_contact_info_widget.get_data()
        if not learner_contact_data.get('contact_number'):
            return False, "Contact Number is required."
        if not self.bypass_amount_checkbox.isChecked() and self.payment_option_combobox.currentText() == "-- Select Option --":
            return False, "Payment Option is required."
        # Always require parent/guardian data since it's always visible
        parent_data = self.parent_guardian_widget.get_data()
        if not parent_data.get('name') or not parent_data.get('surname') or not parent_data.get('relationship_type') or parent_data.get('relationship_type') == '-- Select Option --':
            return False, "Parent/Guardian Name, Surname and Relationship are required."

        # Validate second parent data if checkbox is checked
        if self.add_second_parent_checkbox.isChecked():
            second_parent_data = self.second_parent_guardian_widget.get_data()
            if not second_parent_data.get('name') or not second_parent_data.get('surname'):
                return False, "Second Parent/Guardian Name and Surname are required when the checkbox is selected."

        # Validate custom admission amount if checkbox is checked
        if self.custom_admission_fee_checkbox.isChecked():
            custom_amount_text = self.custom_admission_entry.text().strip()
            if custom_amount_text:
                try:
                    float(custom_amount_text)
                except ValueError:
                    return False, "Custom Admission Fee must be a valid number."

        scheduled_dates, scheduled_dates_error = self._parse_scheduled_dates_input()
        if not scheduled_dates:
            return False, scheduled_dates_error

        return True, ""

    def get_data(self):
        """Collects all form data into a dictionary."""
        contacts_list = []

        # Always include parent/guardian data since it's always visible
        contact_data = self.parent_guardian_widget.get_data()
        if any(contact_data.values()) and contact_data.get('relationship_type') and contact_data.get('name') and contact_data.get('surname'):
            contacts_list.append(contact_data)

        # Include second parent data if checkbox is checked and data is provided
        if self.add_second_parent_checkbox.isChecked():
            second_contact_data = self.second_parent_guardian_widget.get_data()
            # Ensure relationship is set to "Second Parent" if not already set
            if not second_contact_data.get('relationship_type'):
                second_contact_data['relationship_type'] = 'Second Parent'
            if any(second_contact_data.values()) and second_contact_data.get('name') and second_contact_data.get('surname'):
                contacts_list.append(second_contact_data)

        # Get learner contact data from the reusable widget
        learner_contact_data = self.learner_contact_info_widget.get_data()

        # Get term_id with fallback to first available term or default value
        current_term_text = self.payment_term_combobox.currentText()
        term_id = None
        if current_term_text and current_term_text != "-- Select Option --":
            term_data = self.payment_terms_cache.get(current_term_text, {})
            term_id = term_data.get('term_id')

        # If no valid term selected, try to get the first available term
        if term_id is None and self.payment_terms_cache:
            first_term_name = next(iter(self.payment_terms_cache))
            first_term_data = self.payment_terms_cache[first_term_name]
            term_id = first_term_data.get('term_id')

        # Final fallback to term_id = 1 if no terms are available
        if term_id is None:
            term_id = 1

        scheduled_dates, _ = self._parse_scheduled_dates_input()
        primary_due_day = int(scheduled_dates[0][-2:]) if scheduled_dates else 1

        return {
            'contacts': contacts_list,
            'name': self.name_entry.text().strip(),
            'surname': self.surname_entry.text().strip(),
            'dob': self.dob_entry.date().toString("yyyy-MM-dd"),
            'gender': self.gender_combobox.currentText(),
            'country_code': learner_contact_data['country_code'],
            'contact_number': learner_contact_data['contact_number'],
            'email': learner_contact_data['email'],
            'grade': self.grade_spinbox.value(),
            'subjects_count': int(self.subjects_count_combobox.currentText()) if self.subjects_count_combobox.currentText() != "-- Select --" else 0,
            'payment_option': self.payment_option_combobox.currentText(),
            'is_new_learner': self.is_new_learner_check.isChecked(),
            'apply_admission_fee': self.apply_admission_fee_check.isChecked(),
            'family_id': self.families_cache.get(self.family_combobox.currentText()),
            'term_id': term_id,
            'due_day_of_month': primary_due_day,
            'due_days_of_month': [],
            'scheduled_payment_dates': scheduled_dates,
            'billing_start_date': self.billing_start_date_edit.date().toString("yyyy-MM-dd"),
            'manual_amount_enabled': self.bypass_amount_checkbox.isChecked(),
            'manual_amount': self._parse_float_safely(self.manual_amount_entry.text().strip()) if self.manual_amount_entry.text().strip() else None,
            'skip_initial_fee': self.skip_initial_fee_check.isChecked(),
            'custom_admission_amount_enabled': self.custom_admission_fee_checkbox.isChecked(),
            'custom_admission_amount': self._parse_float_safely(self.custom_admission_entry.text().strip()) if self.custom_admission_fee_checkbox.isChecked() and self.custom_admission_entry.text().strip() else None,
            'progress_percentage': self.progress_slider.value() if getattr(self, 'progress_slider', None) and self.progress_slider.isEnabled() else None

        }

    def to_learner_dto(self, acc_no=None):
        """Creates a LearnerDTO from the form data."""
        from domain.models.learner_dto import LearnerDTO # Import here to avoid circular dependency
        
        form_data = self.get_data()

        family_name = form_data.get('family_name')
        family_id = self.families_cache.get(family_name) if family_name else None

        # Get term_id with fallback to first available term or default value
        term_name = form_data.get('term_name')
        term_id = None
        if term_name and term_name != "-- Select Option --":
            term_data = self.payment_terms_cache.get(term_name)
            if term_data:
                term_id = term_data.get('term_id')

        # If no valid term selected, try to get the first available term
        if term_id is None and self.payment_terms_cache:
            first_term_name = next(iter(self.payment_terms_cache))
            first_term_data = self.payment_terms_cache[first_term_name]
            term_id = first_term_data.get('term_id')

        # Final fallback to term_id = 1 if no terms are available
        if term_id is None:
            term_id = 1

        payment_option = form_data['payment_option']
        manual_amount_enabled = form_data['manual_amount_enabled']
        manual_amount = form_data['manual_amount']

        grade = form_data['grade']
        subjects_count = form_data['subjects_count']

        payment_option_id = None
        if manual_amount_enabled and manual_amount is not None:
            payment_option = "MANUAL"
            # For manual options, payment_option_id will be set by the service after creation
        else:
            payment_option_name = form_data['payment_option']
            # Find the payment option in the cache
            key = (payment_option_name, subjects_count, grade)
            payment_option_data = self.payment_options_cache.get(key)
            if payment_option_data:
                payment_option_id = payment_option_data.get('id')

        return LearnerDTO(
            acc_no=acc_no, # Use the acc_no passed to this method
            name=form_data['name'],
            surname=form_data['surname'],
            dob=form_data['dob'],
            gender=form_data['gender'],
            country_code=form_data['country_code'],
            contact_number=form_data['contact_number'],
            email=form_data['email'],
            grade=form_data['grade'],
            subjects_count=form_data['subjects_count'],
            payment_option=payment_option,
            payment_option_id=payment_option_id,
            is_new_learner=form_data['is_new_learner'],
            apply_admission_fee=form_data['apply_admission_fee'],
            family_id=family_id,
            term_id=term_id,
            due_day_of_month=form_data['due_day_of_month'],
            billing_start_date=form_data['billing_start_date'],
            due_days_of_month=form_data['due_days_of_month'],
            scheduled_payment_dates=form_data['scheduled_payment_dates'],
            contacts=form_data['contacts'],
            manual_amount_enabled=manual_amount_enabled,
            manual_amount=manual_amount,
            skip_initial_fee=form_data['skip_initial_fee'],
            custom_admission_amount_enabled=form_data['custom_admission_amount_enabled'],
            custom_admission_amount=form_data['custom_admission_amount'],
            progress_percentage=form_data.get('progress_percentage')
        )

    def set_data(self, learner_dto):
        """Populates the form fields with data from a LearnerDTO."""
        self.name_entry.setText(learner_dto.name or "")
        self.surname_entry.setText(learner_dto.surname or "")
        if learner_dto.dob:
            self.dob_entry.setDate(QDate.fromString(learner_dto.dob, "yyyy-MM-dd"))
        self.gender_combobox.setCurrentText(learner_dto.gender or "")

        # Set learner contact info using the reusable widget
        learner_contact_data = {
            "country_code": learner_dto.country_code,
            "contact_number": learner_dto.contact_number,
            "email": learner_dto.email
        }
        self.learner_contact_info_widget.set_data(learner_contact_data)
        self.grade_spinbox.setValue(learner_dto.grade or 0)
        self.subjects_count_combobox.setCurrentText(str(learner_dto.subjects_count or "-- Select --"))

        # Always set parent/guardian data since it's always visible
        if hasattr(learner_dto, 'contacts') and learner_dto.contacts:
            if len(learner_dto.contacts) > 0:
                self.parent_guardian_widget.set_data(learner_dto.contacts[0])
                # If there's a second contact, set it and check the checkbox
                if len(learner_dto.contacts) > 1:
                    self.second_parent_guardian_widget.set_data(learner_dto.contacts[1])
                    self.add_second_parent_checkbox.setChecked(True)

        payment_option_name = learner_dto.payment_option

        # Handle MANUAL payment options - they should use the bypass checkbox instead of dropdown
        if payment_option_name and payment_option_name.startswith("MANUAL"):
            # For MANUAL options, enable bypass and set the manual amount
            self.bypass_amount_checkbox.setChecked(True)
            self.manual_amount_entry.setEnabled(True)
            # Extract the amount from the payment option name or use the manual_amount field
            if learner_dto.manual_amount is not None:
                self.manual_amount_entry.setText(str(learner_dto.manual_amount))
            # Don't try to set MANUAL in the dropdown
            self._update_payment_options(learner_option=None)
        else:
            # For standard options, update the dropdown normally
            self._update_payment_options(learner_option=payment_option_name)
            # Set bypass checkbox based on manual_amount_enabled flag
            self.bypass_amount_checkbox.setChecked(learner_dto.manual_amount_enabled)
            self.manual_amount_entry.setEnabled(learner_dto.manual_amount_enabled)
            # Set manual amount if bypass is enabled
            if learner_dto.manual_amount_enabled and learner_dto.manual_amount is not None:
                self.manual_amount_entry.setText(str(learner_dto.manual_amount))

        # Update payment option status after setting bypass checkbox
        self._update_payment_option_status()

        self.is_new_learner_check.setChecked(learner_dto.is_new_learner)
        self.apply_admission_fee_check.setChecked(learner_dto.apply_admission_fee)

        self.skip_initial_fee_check.setChecked(learner_dto.skip_initial_fee)
        self.custom_admission_fee_checkbox.setChecked(learner_dto.custom_admission_amount_enabled)
        if learner_dto.custom_admission_amount_enabled and learner_dto.custom_admission_amount is not None:
            self.custom_admission_entry.setText(str(learner_dto.custom_admission_amount))

        if learner_dto.family_id:
            for family_name, family_id in self.families_cache.items():
                if family_id == learner_dto.family_id:
                    self.family_combobox.setCurrentText(family_name)
                    self.family_checkbox.setChecked(True)
                    break

        if learner_dto.term_id:
            for term_name, term_data in self.payment_terms_cache.items():
                if term_data['term_id'] == learner_dto.term_id:
                    self.payment_term_combobox.setCurrentText(term_name)
                    break

        scheduled_dates = list(getattr(learner_dto, 'scheduled_payment_dates', []) or [])
        fallback_due_days = list(getattr(learner_dto, 'due_days_of_month', []) or [])
        if not fallback_due_days and learner_dto.due_day_of_month:
            fallback_due_days = [learner_dto.due_day_of_month]
        if not scheduled_dates and learner_dto.billing_start_date and fallback_due_days:
            try:
                year_text, month_text, _ = learner_dto.billing_start_date.split("-")
                year = int(year_text)
                month = int(month_text)
                last_day = calendar.monthrange(year, month)[1]
                scheduled_dates = []
                for due_day in sorted({int(day) for day in fallback_due_days if day is not None}):
                    day = min(max(due_day, 1), last_day)
                    scheduled_dates.append(f"{year:04d}-{month:02d}-{day:02d}")
            except (TypeError, ValueError):
                scheduled_dates = []
        self.payment_schedule_entry.setText(format_scheduled_dates(scheduled_dates))
        if learner_dto.billing_start_date:
            self.billing_start_date_edit.setDate(QDate.fromString(learner_dto.billing_start_date, "yyyy-MM-dd"))

        # Set progress data if available
        if hasattr(learner_dto, 'progress_percentage') and learner_dto.progress_percentage is not None:
            pct = int(learner_dto.progress_percentage)
            # set slider, legacy spinbox and label
            if hasattr(self, 'progress_slider'):
                self.progress_slider.setValue(pct)
            self.progress_percentage_spinbox.setValue(pct)
            self.progress_label.setText(f"{pct}%")
