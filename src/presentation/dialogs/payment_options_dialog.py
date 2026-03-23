from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QMessageBox,
    QHeaderView,
    QAbstractItemView,
    QGroupBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QStyledItemDelegate,
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import Qt
import logging
from core.desktop_shared_services import get_desktop_shared_services
from presentation.styles import styles
from presentation.styles.colors import TEXT_COLOR
from domain.services.authentication_service import AuthenticationService
from presentation.components.rounded_field import RoundedSpinner, RoundedDropdown, RoundedPlainTextField
from presentation.components.confirmation_dialog import ConfirmationDialog
from presentation.components.buttons import ButtonFactory
from presentation.components.success_dialog import SuccessDialog
from presentation.components.window_component import WindowComponent
from presentation.components.table import Table
from presentation.components.collapsible_section import CollapsibleSection

if TYPE_CHECKING:
    from presentation.main_window import LearnerManagementApp


OPTION_PLACEHOLDER = "-- Select Option --"


@dataclass(frozen=True)
class SelectedOptionData:
    option_id: int
    option_name: str
    subjects: int
    grade: int
    admission_fee: float
    monthly_fee: float
    table: object
    row: int

class DisableFirstItemDelegate(QStyledItemDelegate):
    """Delegate to disable the first item in a combobox (used for placeholder)."""
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, RoundedDropdown):
            if editor.view().model().item(0):
                 editor.view().model().item(0).setEnabled(False)
        return editor

    def editorEvent(self, event, model, option, index):
        if index.row() == 0:
            if event.type() == event.Type.MouseButtonPress:
                 event.accept()
                 return False
            if event.type() == event.Type.KeyPress:
                 if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                     return False
        return super().editorEvent(event, model, option, index)


class PaymentOptionsDialog(WindowComponent):
    """Dialog for managing payment options with modern, rounded styling."""
    def __init__(self, db_manager, parent=None):
        super().__init__(parent, title="Payment Options")
        self.db_manager = db_manager
        self.shared_services = get_desktop_shared_services(db_manager)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.auth_service = AuthenticationService(db_manager)
        self.main_window: 'LearnerManagementApp' = parent

        try:
            self.current_user_id = self.main_window.current_user_id
            self.dialog_service = self.main_window.dialog_service
        except AttributeError as e:
            self.current_user_id = None
            self.dialog_service = None
            self.logger.warning(f"Could not access dialog_service or current_user_id from parent: {e}")

        self.set_size(950, 650)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setContentsMargins(0, 0, 0, 0)
        self.scroll_area.setStyleSheet(styles.SCROLL_AREA_STYLE)

        self.scroll_content_widget = QWidget()
        self.grade_options_layout = QVBoxLayout(self.scroll_content_widget)
        self.grade_options_layout.setContentsMargins(0, 0, 0, 0)
        self.grade_options_layout.setSpacing(12)
        self.scroll_area.setWidget(self.scroll_content_widget)

        # Create main content layout
        content_layout = QVBoxLayout()
        content_layout.setSpacing(16)
        content_layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel("Existing Payment Options")
        title_label.setStyleSheet(styles.PAYMENT_OPTIONS_TITLE_LABEL_STYLE)
        content_layout.addWidget(title_label)

        content_layout.addWidget(self.scroll_area)
        
        input_group = QGroupBox("Add / Edit Option")
        input_group.setStyleSheet(styles.GROUP_BOX_STYLE)

        form_layout = QFormLayout(input_group)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(16, 20, 16, 16)

        # --- START: Combine Grade and Subjects into one form row ---
        # Create a QHBoxLayout to hold Grade and Subjects inputs side-by-side
        grade_subjects_layout = QHBoxLayout()
        grade_subjects_layout.setSpacing(12) # Spacing between the two pairs
        grade_subjects_layout.setContentsMargins(0, 0, 0, 0) # No extra margins for this internal layout

        # Grade Input Pair (Label + Spinner)
        grade_label = QLabel("Grade:")
        grade_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.grade_spinbox = RoundedSpinner(minimum=0, maximum=13)
        self.grade_spinbox.setValue(0)
        self.grade_spinbox.lineEdit().setReadOnly(True)
        self.grade_spinbox.valueChanged.connect(self.on_grade_changed)
        self.grade_spinbox.setProperty("had_non_zero", False)

        grade_subjects_layout.addWidget(grade_label)
        grade_subjects_layout.addWidget(self.grade_spinbox)

        # Add a visual separator or spacing between the two pairs
        separator_label = QLabel("/") # Or use addSpacing(value) or addStretch()
        separator_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center the slash
        separator_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        grade_subjects_layout.addWidget(separator_label)
        subjects_label = QLabel("Subjects:")
        subjects_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.subjects_spinbox = RoundedSpinner(minimum=0, maximum=2)
        self.subjects_spinbox.setValue(0)
        self.subjects_spinbox.lineEdit().setReadOnly(True)
        self.subjects_spinbox.valueChanged.connect(self.on_subjects_changed)
        self.subjects_spinbox.setProperty("had_non_zero", False)

        grade_subjects_layout.addWidget(subjects_label)
        grade_subjects_layout.addWidget(self.subjects_spinbox)

        # Add a stretch to push the elements to the left within the QHBoxLayout
        grade_subjects_layout.addStretch()

        # Add the combined QHBoxLayout to the QFormLayout as a single row
        grade_subjects_label = QLabel("Grade / Subjects:")
        grade_subjects_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        form_layout.addRow(grade_subjects_label, grade_subjects_layout)
        # --- END: Combine Grade and Subjects into one form row ---


        self.option_combobox = RoundedDropdown()
        self.option_combobox.addItem(OPTION_PLACEHOLDER)
        self.option_combobox.addItem("A")
        self.option_combobox.addItem("B")
        self.option_combobox.setEditable(False)

        delegate = DisableFirstItemDelegate(self.option_combobox)
        self.option_combobox.setItemDelegate(delegate)
        self.option_combobox.model().item(0).setEnabled(False)

        option_code_label = QLabel("Payment Option Code:")
        option_code_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        form_layout.addRow(option_code_label, self.option_combobox)

        self.adm_fee_entry = RoundedPlainTextField(placeholder_text="e.g., 500.00")
        adm_fee_label = QLabel("Admission Fee (R):")
        adm_fee_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        form_layout.addRow(adm_fee_label, self.adm_fee_entry)

        self.monthly_fee_entry = RoundedPlainTextField(placeholder_text="e.g., 1200.00")
        monthly_fee_label = QLabel("Monthly Fee (R):")
        monthly_fee_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        form_layout.addRow(monthly_fee_label, self.monthly_fee_entry)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.add_button = ButtonFactory.create_add_button("Add Option")
        self.update_button = ButtonFactory.create_update_button("Update Selected")
        self.delete_button = ButtonFactory.create_delete_button("Delete Selected")
        self.clear_button = ButtonFactory.create_clear_button("Clear Form")

        self.add_button.setMinimumWidth(styles.BUTTON_MIN_WIDTH)
        self.update_button.setMinimumWidth(styles.BUTTON_MIN_WIDTH)
        self.delete_button.setMinimumWidth(styles.BUTTON_MIN_WIDTH)
        self.clear_button.setMinimumWidth(styles.BUTTON_MIN_WIDTH)

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()

        # Connect buttons to their slots
        self.add_button.clicked.connect(self.add_payment_option)
        self.update_button.clicked.connect(self.update_payment_option)
        self.delete_button.clicked.connect(self.delete_payment_option)
        self.clear_button.clicked.connect(self.clear_form)


        content_layout.addWidget(input_group)
        content_layout.addLayout(button_layout)

        self.add_layout(content_layout)

        self._grade_tables = {}
        self._collapsible_sections = {}  # Add this line to store references to collapsible sections

        self.populate_payment_table()
        self.clear_form()

        # Ensure option and subjects spinners are disabled initially when grade is 0
        self.option_combobox.setEnabled(False)
        self.subjects_spinbox.setEnabled(False)

        if self.dialog_service:
            self.dialog_service.center_dialog(self)


    def show_styled_message(self, title, text, icon_type=QMessageBox.Icon.Information):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon_type)
        msg.addButton(QMessageBox.StandardButton.Ok)
        msg.exec()

    def show_styled_confirmation(self, title, text):
        return ConfirmationDialog.show_dialog(
            parent=self,
            title=title,
            message=text,
            icon=QMessageBox.Icon.Question,
            default_button="reject"
        )

    @staticmethod
    def _is_primary_grade(grade):
        return 1 <= grade <= 7

    def _set_form_controls_enabled(self, enabled):
        self.option_combobox.setEnabled(enabled)
        self.subjects_spinbox.setEnabled(enabled)

    def _clear_table_selections(self):
        for table in self._grade_tables.values():
            table.clearSelection()

    @staticmethod
    def _build_option_subject_text(option_name, subjects_count):
        return f"Option {option_name} / Subjects {subjects_count}"

    @staticmethod
    def _create_readonly_item(text, alignment, user_data=None):
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(alignment)
        if user_data is not None:
            item.setData(Qt.ItemDataRole.UserRole, user_data)
        return item

    @staticmethod
    def _format_fee_text(value):
        try:
            amount = float(value) if value is not None else 0.0
            return f"{amount:.2f}"
        except (TypeError, ValueError):
            return "Invalid Amount"

    def _find_grade_for_table(self, selected_table):
        for grade, table in self._grade_tables.items():
            if table is selected_table:
                return grade
        return None

    def _parse_option_tuple(self, first_column_item, selected_table):
        user_data = first_column_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(user_data, dict):
            try:
                return (
                    int(user_data.get("id") or 0),
                    str(user_data.get("option_name") or ""),
                    int(user_data.get("subjects_count") or 0),
                    int(user_data.get("grade") or 0),
                )
            except (TypeError, ValueError):
                pass
        if isinstance(user_data, tuple) and len(user_data) == 4:
            return user_data
        if isinstance(user_data, tuple) and len(user_data) == 3:
            option_name, subjects, grade = user_data
            return 0, option_name, subjects, grade

        try:
            option_part, subjects_part = first_column_item.text().split("/", maxsplit=1)
            option_name = option_part.replace("Option", "", 1).strip()
            subjects = int(subjects_part.replace("Subjects", "", 1).strip())
            grade = self._find_grade_for_table(selected_table)
            if grade is None:
                raise ValueError("Could not determine grade from table key.")
            self.logger.warning(
                "Parsed option/subjects from fallback text: Option %s, Subjects %s, Grade %s",
                option_name,
                subjects,
                grade,
            )
            return 0, option_name, subjects, grade
        except (AttributeError, TypeError, ValueError) as parse_error:
            self.logger.error("Error parsing option/subject/grade fallback: %s", parse_error)
            return None

    @staticmethod
    def _parse_fee_from_table(table_widget, row, col):
        item = table_widget.item(row, col)
        if not item:
            raise ValueError(f"Missing fee item in row {row}, column {col}.")
        fee_text = item.text().replace("R", "").strip()
        return float(fee_text) if fee_text else 0.0

    def _show_option_exists_message(self, option_name, grade, subjects):
        self.show_styled_message(
            "Option Already Exists",
            f"Payment Option '{option_name}' for Grade {grade} with {subjects} subject(s) already exists.\n\n"
            "To modify the fees for this existing option, please find and select it in the table above and use the "
            "'Update Selected' button.",
            QMessageBox.Icon.Information
        )

    def _refresh_after_mutation(self, clear_form=True):
        self.populate_payment_table()
        if clear_form:
            self.clear_form()
        self.notify_main_window_refresh()

    def _parse_fee_inputs(
        self,
        *,
        empty_message,
        invalid_message,
        negative_adm_message,
        negative_monthly_message,
    ):
        adm_fee_str = self.adm_fee_entry.text().strip()
        monthly_fee_str = self.monthly_fee_entry.text().strip()

        if not adm_fee_str or not monthly_fee_str:
            self.show_styled_message("Input Error", empty_message, QMessageBox.Icon.Warning)
            if not adm_fee_str:
                self.adm_fee_entry.setFocus()
            else:
                self.monthly_fee_entry.setFocus()
            return None

        try:
            adm_fee = float(adm_fee_str)
            monthly_fee = float(monthly_fee_str)
        except ValueError:
            self.show_styled_message("Input Error", invalid_message, QMessageBox.Icon.Warning)
            if not self.adm_fee_entry.text().strip():
                self.adm_fee_entry.setFocus()
            elif not self.monthly_fee_entry.text().strip():
                self.monthly_fee_entry.setFocus()
            else:
                self.adm_fee_entry.setFocus()
            return None

        if adm_fee < 0:
            self.show_styled_message("Input Error", negative_adm_message, QMessageBox.Icon.Warning)
            self.adm_fee_entry.setFocus()
            return None

        if monthly_fee < 0:
            self.show_styled_message("Input Error", negative_monthly_message, QMessageBox.Icon.Warning)
            self.monthly_fee_entry.setFocus()
            return None

        return adm_fee, monthly_fee

    def clear_form(self):
        """Reset the form to its initial state and clear table selections."""
        self.grade_spinbox.blockSignals(True)
        self.subjects_spinbox.blockSignals(True)
        self.option_combobox.blockSignals(True)

        self.grade_spinbox.setValue(0)
        self.grade_spinbox.setProperty("had_non_zero", False)
        self.subjects_spinbox.setValue(0)
        self.subjects_spinbox.setProperty("had_non_zero", False)
        self.option_combobox.setCurrentIndex(0)
        self.adm_fee_entry.clear()
        self.monthly_fee_entry.clear()

        self.grade_spinbox.blockSignals(False)
        self.subjects_spinbox.blockSignals(False)
        self.option_combobox.blockSignals(False)

        self._clear_table_selections()

        self.set_button_states(selected=False)
        self._set_form_controls_enabled(False)

    def on_grade_changed(self, new_value):
        """Handle grade changes and keep dependent controls in a valid state."""
        is_grade_selected = new_value > 0
        self._set_form_controls_enabled(is_grade_selected)

        had_non_zero = self.grade_spinbox.property("had_non_zero") or False

        if new_value == 0 and had_non_zero:
            self.grade_spinbox.blockSignals(True)
            self.grade_spinbox.setValue(1)
            self.grade_spinbox.blockSignals(False)
            return

        if new_value > 0:
            self.grade_spinbox.setProperty("had_non_zero", True)

        if is_grade_selected and self._is_primary_grade(new_value) and self.subjects_spinbox.value() > 1:
            self.subjects_spinbox.blockSignals(True)
            self.subjects_spinbox.setValue(1)
            self.subjects_spinbox.blockSignals(False)


    def on_subjects_changed(self, new_value):
        """Handle subject count changes and enforce grade-specific constraints."""
        grade = self.grade_spinbox.value()

        if self._is_primary_grade(grade) and new_value > 1:
            self.subjects_spinbox.blockSignals(True)
            self.subjects_spinbox.setValue(1)
            self.subjects_spinbox.blockSignals(False)
            return

        had_non_zero = self.subjects_spinbox.property("had_non_zero") or False

        if new_value == 0 and had_non_zero:
            self.subjects_spinbox.blockSignals(True)
            self.subjects_spinbox.setValue(1)
            self.subjects_spinbox.blockSignals(False)
            return

        if new_value > 0:
            self.subjects_spinbox.setProperty("had_non_zero", True)


    def populate_payment_table(self):
        try:
            # Clear existing widgets from the layout and safely delete them
            while self.grade_options_layout.count():
                child = self.grade_options_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            self._grade_tables.clear()
            self._collapsible_sections.clear()

            options_data = self.shared_services.payment_catalog_use_case.list_payment_options()

            if not options_data:
                no_options_label = QLabel("No payment options found.")
                no_options_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                no_options_label.setStyleSheet(styles.NO_PAYMENT_OPTIONS_LABEL_STYLE)
                self.grade_options_layout.addWidget(no_options_label)
                self.grade_options_layout.addStretch()
                return

            options_by_grade = {}
            for option in options_data:
                grade = int(option.get("grade") or 0)
                options_by_grade.setdefault(grade, []).append(option)

            first_group_created = False
            for grade in sorted(options_by_grade.keys()):
                collapsible_section = CollapsibleSection(f"Grade {grade} Options")
                self._collapsible_sections[grade] = collapsible_section

                if not first_group_created:
                    collapsible_section.toggle_button.setChecked(True)
                    first_group_created = True
                else:
                    collapsible_section.toggle_button.setChecked(False)

                columns = [
                    {"name": "Option / Subjects", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
                    {"name": "Admission Fee (R)", "width": None, "resize_mode": QHeaderView.ResizeMode.Stretch},
                    {"name": "Monthly Fee (R)", "width": None, "resize_mode": QHeaderView.ResizeMode.Stretch}
                ]
                grade_table_component = Table(self, columns)
                grade_table = grade_table_component.get_table()
                self._grade_tables[grade] = grade_table

                grade_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                grade_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                grade_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                grade_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                grade_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
                grade_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
                grade_table.setAlternatingRowColors(True)
                grade_table.itemSelectionChanged.connect(self.on_any_grade_table_selection_changed)

                grade_options = options_by_grade[grade]
                grade_table.setRowCount(len(grade_options))
                for row_idx, row_data in enumerate(grade_options):
                    option_id = int(row_data.get("id") or 0)
                    option_name = str(row_data.get("option_name") or "")
                    subjects_count = int(row_data.get("subjects_count") or 0)
                    current_grade = int(row_data.get("grade") or 0)
                    adm_reg_fee = row_data.get("adm_reg_fee")
                    monthly_fee = row_data.get("monthly_fee")
                    grade_table.setItem(
                        row_idx,
                        0,
                        self._create_readonly_item(
                            self._build_option_subject_text(option_name, subjects_count),
                            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                            {
                                "id": option_id,
                                "option_name": option_name,
                                "subjects_count": subjects_count,
                                "grade": current_grade,
                            },
                        ),
                    )
                    grade_table.setItem(
                        row_idx,
                        1,
                        self._create_readonly_item(
                            self._format_fee_text(adm_reg_fee),
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        ),
                    )
                    grade_table.setItem(
                        row_idx,
                        2,
                        self._create_readonly_item(
                            self._format_fee_text(monthly_fee),
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        ),
                    )

                row_height = grade_table.verticalHeader().defaultSectionSize()
                if grade_table.rowCount() > 0:
                    try:
                        row_height = grade_table.rowHeight(0)
                    except Exception:
                        pass

                header_height = grade_table.horizontalHeader().height()
                table_height = header_height + (row_height * grade_table.rowCount())
                table_height += 4
                grade_table.setFixedHeight(table_height)

                collapsible_section.add_widget(grade_table)
                self.grade_options_layout.addWidget(collapsible_section)

            self.grade_options_layout.addStretch()

        except Exception as e:
            self.show_styled_message("Error", f"An unexpected error occurred populating options: {e}", QMessageBox.Icon.Critical)


    def on_any_grade_table_selection_changed(self):
        selected_data = self._get_selected_option_data(clear_others=True)

        if not selected_data:
            self.clear_form()
            return

        self.grade_spinbox.blockSignals(True)
        self.subjects_spinbox.blockSignals(True)
        self.option_combobox.blockSignals(True)

        self.grade_spinbox.setValue(selected_data.grade)
        self.grade_spinbox.setProperty("had_non_zero", True)

        self._set_form_controls_enabled(True)
        index = self.option_combobox.findText(
            selected_data.option_name,
            Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchCaseSensitive,
        )
        if index != -1:
            self.option_combobox.setCurrentIndex(index)
        else:
            self.logger.warning(
                "Could not find option '%s' in combobox upon selection. Resetting combobox.",
                selected_data.option_name,
            )
            self.option_combobox.setCurrentIndex(0)

        self.subjects_spinbox.setValue(selected_data.subjects)
        self.subjects_spinbox.setProperty("had_non_zero", True)

        self.adm_fee_entry.setText(f"{selected_data.admission_fee:.2f}")
        self.monthly_fee_entry.setText(f"{selected_data.monthly_fee:.2f}")

        self.grade_spinbox.blockSignals(False)
        self.subjects_spinbox.blockSignals(False)
        self.option_combobox.blockSignals(False)

        self.set_button_states(selected=True)


    def _get_selected_option_data(self, clear_others=True):
        selected_table = None
        selected_row = None

        for table_widget in self._grade_tables.values():
            selected_items = table_widget.selectedItems()
            if selected_items:
                selected_table = table_widget
                selected_row = selected_items[0].row()
                break

        if not selected_table:
            return None

        if clear_others:
            for other_table in self._grade_tables.values():
                if other_table is not selected_table:
                    other_table.clearSelection()

        try:
            first_column_item = selected_table.item(selected_row, 0)
            if not first_column_item:
                raise ValueError(f"First column item not found in selected row {selected_row}.")

            parsed_option_data = self._parse_option_tuple(first_column_item, selected_table)
            if not parsed_option_data:
                self.show_styled_message(
                    "Data Error",
                    "Could not retrieve valid Option/Subject/Grade data from the selected row.",
                    QMessageBox.Icon.Warning,
                )
                return None

            option_id, option_name, subjects, grade = parsed_option_data
            admission_fee = self._parse_fee_from_table(selected_table, selected_row, 1)
            monthly_fee = self._parse_fee_from_table(selected_table, selected_row, 2)
            return SelectedOptionData(
                option_id=option_id,
                option_name=option_name,
                subjects=subjects,
                grade=grade,
                admission_fee=admission_fee,
                monthly_fee=monthly_fee,
                table=selected_table,
                row=selected_row,
            )
        except (TypeError, ValueError) as error:
            self.logger.error("Error parsing selected row data in _get_selected_option_data: %s", error)
            self.show_styled_message("Data Error", "Could not read data from the selected row.", QMessageBox.Icon.Warning)
            return None

    def validate_add_inputs(self):
        """Validate add flow inputs and return parsed fee values."""
        grade = self.grade_spinbox.value()
        subjects = self.subjects_spinbox.value()
        option_name = self.option_combobox.currentText().strip().upper()

        if grade == 0:
            self.show_styled_message("Input Error", "Grade cannot be 0. Please select a valid grade (1-13).", QMessageBox.Icon.Warning)
            self.grade_spinbox.setFocus()
            return None

        if subjects == 0:
            self.show_styled_message("Input Error", "Subject count cannot be 0. Please select 1 or 2 subjects.", QMessageBox.Icon.Warning)
            self.subjects_spinbox.setFocus()
            return None

        if self._is_primary_grade(grade) and subjects > 1:
            self.show_styled_message("Input Error", "Grades 1-7 can only have 1 subject.", QMessageBox.Icon.Warning)
            self.subjects_spinbox.setFocus()
            return None

        if not option_name or option_name == OPTION_PLACEHOLDER.upper():
            self.show_styled_message("Input Error", "Payment Option Code: Please select a valid option (A or B).", QMessageBox.Icon.Warning)
            self.option_combobox.setFocus()
            return None

        return self._parse_fee_inputs(
            empty_message="Admission Fee and Monthly Fee are required.",
            invalid_message="Invalid fee amount. Please enter valid numbers (e.g., 500.00).",
            negative_adm_message="Admission Fee cannot be negative.",
            negative_monthly_message="Monthly Fee cannot be negative.",
        )


    def add_payment_option(self):
        """Adds a new payment option to the database after validation and uniqueness check."""
        if self._get_selected_option_data(clear_others=False):
            self.show_styled_message(
                "Operation Not Allowed",
                "A payment option is currently selected in the table. Please clear the form (using the 'Clear Form' button) or unselect the row before adding a new option.",
                QMessageBox.Icon.Warning
            )
            return

        parsed_fees = self.validate_add_inputs()
        if not parsed_fees:
            return

        grade = self.grade_spinbox.value()
        option_name = self.option_combobox.currentText().strip().upper()
        subjects = self.subjects_spinbox.value()
        adm_fee, monthly_fee = parsed_fees

        try:
            option_id, error = self.shared_services.payment_catalog_use_case.create_payment_option(
                {
                    "option_name": option_name,
                    "subjects_count": subjects,
                    "grade": grade,
                    "adm_reg_fee": adm_fee,
                    "monthly_fee": monthly_fee,
                },
                user_id=self.current_user_id,
            )
            if not option_id:
                if error and "already exists" in error.lower():
                    self._show_option_exists_message(option_name, grade, subjects)
                else:
                    self.show_styled_message("Database Error", error or "Failed to add payment option.", QMessageBox.Icon.Critical)
                self.populate_payment_table()
                return

            self._refresh_after_mutation(clear_form=True)
            SuccessDialog.show_success(parent=self, message="Payment option added successfully!")

        except Exception as e:
            error_msg = str(e).lower()
            if "already exists" in error_msg:
                self._show_option_exists_message(option_name, grade, subjects)
            else:
                self.show_styled_message("Error", f"An unexpected error occurred while adding option: {e}", QMessageBox.Icon.Critical)
            self.populate_payment_table()

    def _get_or_create_manual_payment_option(self, amount_str, grade, subjects_count):
        """Gets the ID of a manual payment option, creating it if it doesn't exist."""
        try:
            option_name = f"Manual_{amount_str}"
            existing_options = self.shared_services.payment_catalog_use_case.list_payment_options()
            for option in existing_options:
                if (
                    str(option.get("option_name") or "") == option_name
                    and int(option.get("grade") or 0) == grade
                    and int(option.get("subjects_count") or 0) == subjects_count
                ):
                    return int(option.get("id") or 0) or None

            amount = float(amount_str)
            option_id, error = self.shared_services.payment_catalog_use_case.create_payment_option(
                {
                    "option_name": option_name,
                    "grade": grade,
                    "subjects_count": subjects_count,
                    "monthly_fee": amount,
                    "adm_reg_fee": 0.0,
                },
                user_id=self.current_user_id,
            )
            if error:
                self.logger.error("Error creating manual payment option: %s", error)
                return None
            return option_id

        except (TypeError, ValueError) as e:
            self.logger.error("Error getting or creating manual payment option: %s", e)
            return None


    def update_payment_option(self):
        """Updates the fees for the selected payment option combination after validation and confirmation."""
        selected_data = self._get_selected_option_data(clear_others=False)

        if not selected_data:
            self.show_styled_message("Selection Error", "Please select a payment option from the table to update.", QMessageBox.Icon.Warning)
            return

        parsed_fees = self._parse_fee_inputs(
            empty_message="Admission Fee and Monthly Fee cannot be empty for update.",
            invalid_message="Invalid new fee amount. Please enter valid numbers (e.g., 500.00).",
            negative_adm_message="New Admission Fee cannot be negative.",
            negative_monthly_message="New Monthly Fee cannot be negative.",
        )
        if not parsed_fees:
            return

        new_adm_fee, new_monthly_fee = parsed_fees

        if (
            abs(new_adm_fee - selected_data.admission_fee) < 0.001
            and abs(new_monthly_fee - selected_data.monthly_fee) < 0.001
        ):
            self.show_styled_message(
                "No Change Detected",
                "The entered fees are the same as the currently selected option's fees.\nNo update is necessary.",
                QMessageBox.Icon.Information
            )
            return

        confirmed = self.show_styled_confirmation(
            "Confirm Update",
            f"Are you sure you want to update the fees for the following option?\n\n"
            f"<b>Option:</b> {selected_data.option_name}\n"
            f"<b>Subjects:</b> {selected_data.subjects}\n"
            f"<b>Grade:</b> {selected_data.grade}\n\n"
            f"<b>Old Admission Fee:</b> R{selected_data.admission_fee:.2f}\n"
            f"<b>Old Monthly Fee:</b> R{selected_data.monthly_fee:.2f}\n\n"
            f"<b>New Admission Fee:</b> R{new_adm_fee:.2f}\n"
            f"<b>New Monthly Fee:</b> R{new_monthly_fee:.2f}"
        )

        if confirmed:
            try:
                ok, error = self.shared_services.payment_catalog_use_case.update_payment_option(
                    selected_data.option_id,
                    {
                        "option_name": selected_data.option_name,
                        "subjects_count": selected_data.subjects,
                        "grade": selected_data.grade,
                        "adm_reg_fee": new_adm_fee,
                        "monthly_fee": new_monthly_fee,
                    },
                    user_id=self.current_user_id,
                )

                if ok:
                    SuccessDialog.show_success(parent=self, message="Payment option updated successfully!")
                    self._refresh_after_mutation(clear_form=True)
                else:
                    self.show_styled_message(
                        "Update Failed",
                        error or "The selected payment option could not be updated.",
                        QMessageBox.Icon.Warning
                    )
                    self.populate_payment_table()

            except Exception as e:
                self.show_styled_message("Error", f"An unexpected error occurred during update: {e}", QMessageBox.Icon.Critical)
                self.populate_payment_table()


    def delete_payment_option(self):
        """Deletes the selected payment option after checking for references, confirmation, and password verification."""
        selected_data = self._get_selected_option_data(clear_others=False)

        if not selected_data:
            self.show_styled_message("Selection Error", "No payment option selected to delete.", QMessageBox.Icon.Warning)
            return

        confirmed = self.show_styled_confirmation(
            "Confirm Deletion",
            f"Are you sure you want to permanently delete payment option '{selected_data.option_name}' for Grade {selected_data.grade} with {selected_data.subjects} subject(s)?\n\n"
            "This action cannot be undone."
        )

        if not confirmed:
            return

        if not self.dialog_service or not self.current_user_id:
            self.show_styled_message("Error", "User or Dialog service not available. Cannot verify password.", QMessageBox.Icon.Critical)
            return

        password = self.dialog_service.show_password_dialog(
            title="Password Required",
            message="Please enter your password to confirm deletion:",
            parent=self
        )

        if password is None:
            self.show_styled_message("Operation Cancelled", "Deletion operation was cancelled.", QMessageBox.Icon.Information)
            return

        if not self.auth_service.verify_user_password(self.db_manager, self.current_user_id, password):
            self.show_styled_message("Authentication Failed", "Incorrect password. Deletion cancelled.", QMessageBox.Icon.Warning)
            return

        try:
            ok, error = self.shared_services.payment_catalog_use_case.delete_payment_option(
                selected_data.option_id,
                user_id=self.current_user_id,
            )
            if ok:
                SuccessDialog.show_success(parent=self, message="Payment option deleted successfully!")
                self._refresh_after_mutation(clear_form=True)
                return

            self.show_styled_message(
                "Cannot Delete",
                error or "The selected payment option could not be deleted.",
                QMessageBox.Icon.Warning
            )
            self.populate_payment_table()

        except Exception as e:
            self.show_styled_message("Error", f"An unexpected error occurred while checking references: {e}", QMessageBox.Icon.Critical)


    def set_button_states(self, selected=False):
        """
        Sets the enabled state of the Add, Update, and Delete buttons
        based on whether a table row is currently selected (`selected=True`)
        or if no row is selected (`selected=False`).
        """
        self.add_button.setEnabled(not selected)
        self.update_button.setEnabled(selected)
        self.delete_button.setEnabled(selected)

    def notify_main_window_refresh(self):
        """Notifies the main window to refresh dependent data if the method exists."""
        if hasattr(self.main_window, 'refresh_dependent_data'):
            self.main_window.refresh_dependent_data()
        else:
            self.logger.warning("Main window does not have 'refresh_dependent_data' method.")


    def closeEvent(self, event):
        """Handle the close event to notify the main window before the dialog closes."""
        self.notify_main_window_refresh()
        super().closeEvent(event)
