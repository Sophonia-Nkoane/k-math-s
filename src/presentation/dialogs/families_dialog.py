from PySide6.QtWidgets import (QTableWidgetItem, QVBoxLayout, QMessageBox,
                            QHeaderView, QGroupBox, QFormLayout,
                            QHBoxLayout, QLabel)
from PySide6.QtCore import Qt
import uuid
from core.desktop_shared_services import get_desktop_shared_services
from presentation.components.rounded_field import RoundedPlainTextField, RoundedSpinner, RoundedDropdown
from presentation.components.buttons import ButtonFactory
from presentation.components.window_component import WindowComponent
from presentation.components.table import Table
from presentation.styles import styles
from presentation.styles.colors import TEXT_COLOR
from domain.services.authentication_service import AuthenticationService
from presentation.components.confirmation_dialog import ConfirmationDialog
from presentation.components.success_dialog import SuccessDialog

# Payment Modes (Database Values)
PAYMENT_MODE_INDIVIDUAL = 'individual_discount'
PAYMENT_MODE_SINGLE = 'single_coverage'

# Payment Modes (Display Values)
PAYMENT_MODE_DISPLAY_INDIVIDUAL = "Individual Discount"
PAYMENT_MODE_DISPLAY_SINGLE = "Single Coverage"

# Account Prefix
FAMILY_ACCOUNT_PREFIX = "FAM-"

# Table Column Indices
COL_FAMILY_NAME = 0
COL_ACCOUNT_NO = 1
COL_PAYMENT_MODE = 2
COL_DISCOUNT = 3

# Message Box Titles
ERROR_TITLE_DATABASE = "Database Error"
ERROR_TITLE_GENERAL = "Error"
INPUT_ERROR_TITLE = "Input Error"
SELECTION_ERROR_TITLE = "Selection Error"
SUCCESS_TITLE = "Success"

class FamiliesDialog(WindowComponent):
    """Dialog for managing family discounts."""

    def __init__(self, db_manager, current_user_id, parent=None):
        super().__init__(parent, "Families Management")
        self.db_manager = db_manager
        self.current_user_id = current_user_id
        self.shared_services = get_desktop_shared_services(db_manager)
        self.auth_service = AuthenticationService(db_manager)
        self.main_window = parent  # Store parent as main_window
        self.set_size(900, 600)
        
        self.setup_ui()
        self.populate_families_table()

    def notify_main_window_refresh(self):
        if hasattr(self.main_window, 'refresh_dependent_data'):
            self.main_window.refresh_dependent_data()

    def closeEvent(self, event):
        self.notify_main_window_refresh()
        super().closeEvent(event)

    def setup_ui(self):
        """Creates and arranges the UI widgets."""
        # Table Widget
        family_columns = [
            {"name": "Family Name", "width": None, "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "Account No", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Payment Mode", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Discount (%)", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
        ]
        self.table_component = Table(self, columns=family_columns)
        self.families_table = self.table_component.get_table()
        
        # Connect selection changed signal manually
        self.families_table.itemSelectionChanged.connect(self.on_family_selection_changed)

        # Input Fields Group
        input_group = QGroupBox("Add / Edit Family")
        input_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        input_layout = QFormLayout(input_group)
        input_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        input_layout.setHorizontalSpacing(10)
        input_layout.setVerticalSpacing(10)

        # Use RoundedPlainTextField for family name input
        family_name_label = QLabel("Family Name:")
        family_name_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.family_name_entry = RoundedPlainTextField(placeholder_text="Enter family name")
        input_layout.addRow(family_name_label, self.family_name_entry)

        # Use RoundedDropdown for payment mode selection
        payment_mode_label = QLabel("Payment Mode:")
        payment_mode_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.payment_mode_combobox = RoundedDropdown()
        self.payment_mode_combobox.addItems([PAYMENT_MODE_DISPLAY_INDIVIDUAL, PAYMENT_MODE_DISPLAY_SINGLE])
        input_layout.addRow(payment_mode_label, self.payment_mode_combobox)

        # Use RoundedSpinner for discount percentage
        discount_label = QLabel ("Discount (%):")
        discount_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.discount_spinbox = RoundedSpinner(minimum=0, maximum=100, step=1)
        self.discount_spinbox.setSuffix(" %")
        input_layout.addRow(discount_label, self.discount_spinbox)

        # Buttons Layout using ButtonFactory
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Create buttons using ButtonFactory
        self.add_button = ButtonFactory.create_add_button("Add Family")
        self.update_button = ButtonFactory.create_update_button("Update Selected")
        self.delete_button = ButtonFactory.create_delete_button("Delete Selected")
        self.clear_button = ButtonFactory.create_clear_button("Clear")

        # Set a consistent minimum width for all buttons
        self.add_button.setMinimumWidth(styles.BUTTON_MIN_WIDTH)
        self.update_button.setMinimumWidth(styles.BUTTON_MIN_WIDTH)
        self.delete_button.setMinimumWidth(styles.BUTTON_MIN_WIDTH)
        self.clear_button.setMinimumWidth(styles.BUTTON_MIN_WIDTH)
        
        button_layout.addStretch()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.clear_button)

        # Connect Button Signals
        self.add_button.clicked.connect(self.add_family)
        self.update_button.clicked.connect(self.update_family)
        self.delete_button.clicked.connect(self.delete_family)
        self.clear_button.clicked.connect(self.clear_input_fields)
        
        # Set initial button states
        self.update_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        
        # Connect family name changes
        self.family_name_entry.textChanged.connect(self.on_family_name_changed)

        # Main Layout
        main_content = QVBoxLayout()
        main_content.setContentsMargins(10, 10, 10, 10)
        main_content.setSpacing(12)
        existing_families_label = QLabel("Existing Families:")
        existing_families_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        main_content.addWidget(existing_families_label)
        main_content.addWidget(self.families_table)
        main_content.addWidget(input_group)
        main_content.addLayout(button_layout)

        # Add to WindowComponent's content area
        self.add_layout(main_content)

    def populate_families_table(self):
        """Fetches families from the database and populates the table."""
        self.families_table.setRowCount(0) # Clear existing rows
        families = self.shared_services.family_use_case.list_families()

        if families:
            self.families_table.setRowCount(len(families))
            for row_idx, family in enumerate(families):
                family_id = int(family.get("family_id") or 0)
                family_name = family.get("family_name")
                acc_no = family.get("family_account_no")
                mode_db = family.get("payment_mode")
                discount = family.get("discount_percentage")

                mode_display = PAYMENT_MODE_DISPLAY_SINGLE if mode_db == PAYMENT_MODE_SINGLE else PAYMENT_MODE_DISPLAY_INDIVIDUAL

                family_item = QTableWidgetItem(family_name or "")
                family_item.setData(Qt.ItemDataRole.UserRole, family_id)
                self.families_table.setItem(row_idx, COL_FAMILY_NAME, family_item)
                self.families_table.setItem(row_idx, COL_ACCOUNT_NO, QTableWidgetItem(acc_no or ""))
                self.families_table.setItem(row_idx, COL_PAYMENT_MODE, QTableWidgetItem(mode_display))
                self.families_table.setItem(row_idx, COL_DISCOUNT, QTableWidgetItem(f"{discount:.2f}" if discount is not None else "0.00"))

    def handle_family_input(self, family_name, payment_mode_display, discount):
        """Handles common logic for adding and updating family."""
        if not family_name:
            self.show_styled_message(INPUT_ERROR_TITLE, "Family Name is required.", QMessageBox.Icon.Critical)
            return None

        payment_mode_db = PAYMENT_MODE_SINGLE if payment_mode_display == PAYMENT_MODE_DISPLAY_SINGLE else PAYMENT_MODE_INDIVIDUAL

        family_acc_no = f"{FAMILY_ACCOUNT_PREFIX}{str(uuid.uuid4())[:8].upper()}"

        return family_name, family_acc_no, payment_mode_db, discount

    def show_success_dialog(self, title, text):
        """Show a success dialog using SuccessDialog."""
        # We'll combine title and text since SuccessDialog only supports a single message
        dialog = SuccessDialog(f"{text}", parent=self)
        dialog.exec()

    def add_family(self):
        """Adds a new family based on input fields."""
        family_name = self.family_name_entry.text().strip()
        payment_mode_display = self.payment_mode_combobox.currentText()
        discount = self.discount_spinbox.value()

        family_data = self.handle_family_input(family_name, payment_mode_display, discount)
        if family_data is None:
            return

        try:
            family_name, family_acc_no, payment_mode_db, family_discount = family_data
            _, error = self.shared_services.family_use_case.create_family(
                {
                    "family_name": family_name,
                    "family_account_no": family_acc_no,
                    "payment_mode": payment_mode_db,
                    "discount_percentage": family_discount,
                },
                user_id=self.current_user_id,
            )
            if error:
                self.show_styled_message(ERROR_TITLE_GENERAL, error, QMessageBox.Icon.Critical)
                return
            self.populate_families_table()
            self.clear_input_fields()
            self.show_success_dialog(SUCCESS_TITLE, "Family added successfully.")
        except Exception as e:
            self.show_styled_message(ERROR_TITLE_GENERAL, f"An unexpected error occurred while adding the family: {e}", QMessageBox.Icon.Critical)

    def update_family(self):
        """Updates the selected family based on input fields."""
        selected_rows = self.families_table.selectionModel().selectedRows()
        if not selected_rows:
            self.show_styled_message(SELECTION_ERROR_TITLE, "Please select a family to update.", QMessageBox.Icon.Warning)
            return

        try:
            row = selected_rows[0].row()
            family_item = self.families_table.item(row, COL_FAMILY_NAME)
            acc_no_item = self.families_table.item(row, COL_ACCOUNT_NO)
            if not family_item or not acc_no_item:
                self.show_styled_message(ERROR_TITLE_GENERAL, "Could not retrieve account number from selected row.", QMessageBox.Icon.Critical)
                return
            account_no = acc_no_item.text()

            family_id = int(family_item.data(Qt.ItemDataRole.UserRole) or 0)
            if family_id <= 0:
                self.show_styled_message(ERROR_TITLE_GENERAL, f"Could not find family ID for account number: {account_no}", QMessageBox.Icon.Critical)
                return

            family_name = self.family_name_entry.text().strip()
            payment_mode_display = self.payment_mode_combobox.currentText()
            discount = self.discount_spinbox.value()

            payment_mode_db = PAYMENT_MODE_SINGLE if payment_mode_display == PAYMENT_MODE_DISPLAY_SINGLE else PAYMENT_MODE_INDIVIDUAL

            ok, error = self.shared_services.family_use_case.update_family(
                family_id,
                {
                    "family_name": family_name,
                    "family_account_no": account_no,
                    "payment_mode": payment_mode_db,
                    "discount_percentage": discount,
                },
                user_id=self.current_user_id,
            )
            if not ok:
                self.show_styled_message(ERROR_TITLE_GENERAL, error or "Failed to update family.", QMessageBox.Icon.Critical)
                return

            self.populate_families_table()
            self.clear_input_fields()
            self.show_success_dialog(SUCCESS_TITLE, "Family updated successfully.")
        except Exception as e:
            self.show_styled_message(ERROR_TITLE_GENERAL, f"An unexpected error occurred while updating the family: {e}", QMessageBox.Icon.Critical)

    def delete_family(self):
        """Deletes the selected family after confirmation."""
        selected_rows = self.families_table.selectionModel().selectedRows()
        if not selected_rows:
            self.show_styled_message(SELECTION_ERROR_TITLE, "Please select a family to delete.", QMessageBox.Icon.Warning)
            return

        try:
            row = selected_rows[0].row()
            family_item = self.families_table.item(row, COL_FAMILY_NAME)
            acc_no_item = self.families_table.item(row, COL_ACCOUNT_NO)
            if not family_item or not acc_no_item:
                self.show_styled_message(ERROR_TITLE_GENERAL, "Could not retrieve account number from selected row.", QMessageBox.Icon.Critical)
                return
            account_no = acc_no_item.text()

            family_id = int(family_item.data(Qt.ItemDataRole.UserRole) or 0)
            if family_id <= 0:
                self.show_styled_message(ERROR_TITLE_GENERAL, f"Could not find family ID for account number: {account_no}", QMessageBox.Icon.Critical)
                return

            family_name_item = self.families_table.item(row, COL_FAMILY_NAME)
            family_name_display = family_name_item.text() if family_name_item else "Selected Family"

            confirmed = ConfirmationDialog.show_dialog(
                self,
                title="Confirm Delete",
                message=f"Are you sure you want to delete the family '{family_name_display}' (Account: {account_no})?",
                accept_button_text="Delete",
                reject_button_text="Cancel",
            )

            if confirmed:
                from presentation.components.password_confirmation_dialog import PasswordConfirmationDialog
                
                # Get password using the PasswordConfirmationDialog
                password = PasswordConfirmationDialog.get_password_from_user(self)
                
                if password:
                    verification_result = self.auth_service.verify_user_password(self.db_manager, self.current_user_id, password)
                    
                    if verification_result:
                        success, error_msg = self.shared_services.family_use_case.delete_family(
                            family_id,
                            user_id=self.current_user_id,
                        )
                        if success:
                            self.populate_families_table()
                            self.clear_input_fields()
                            self.show_success_dialog(SUCCESS_TITLE, "Family deleted successfully.")
                        else:
                            self.show_styled_message(ERROR_TITLE_DATABASE, 
                                error_msg or "Failed to delete family. Please try again.", 
                                QMessageBox.Icon.Critical)
                    else:
                        self.show_styled_message("Authentication Failed",
                                             "Password verification failed. Please check your password.",
                                             QMessageBox.Icon.Warning)
                else:
                    self.show_styled_message("Deletion Cancelled", 
                                         "No password entered. Deletion cancelled.", 
                                         QMessageBox.Icon.Information)
        except Exception as e:
            self.show_styled_message(ERROR_TITLE_GENERAL, f"An unexpected error occurred: {str(e)}", QMessageBox.Icon.Critical)

    def on_family_selection_changed(self):
        """Populates input fields when a family is selected in the table."""
        selected_rows = self.families_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            name_item = self.families_table.item(row, COL_FAMILY_NAME)
            mode_item = self.families_table.item(row, COL_PAYMENT_MODE)
            discount_item = self.families_table.item(row, COL_DISCOUNT)

            self.family_name_entry.setText(name_item.text() if name_item else "")

            mode_display = mode_item.text() if mode_item else PAYMENT_MODE_DISPLAY_INDIVIDUAL
            self.payment_mode_combobox.setCurrentText(mode_display)

            try:
                # Extract numeric value from the discount text and ensure it's an integer
                discount_text = discount_item.text() if discount_item else "0"
                # Remove % sign, convert to float first to handle decimals, then to int
                discount_val = int(float(discount_text.strip().replace('%', '')))
                self.discount_spinbox.setValue(discount_val)
            except (ValueError, TypeError, AttributeError):
                self.discount_spinbox.setValue(0)

            self.set_button_states(selected=True)
        else:
            self.set_button_states(selected=False)

    def clear_input_fields(self):
        """Clears all input fields and the table selection."""
        self.family_name_entry.clear()
        self.payment_mode_combobox.setCurrentIndex(0)
        self.discount_spinbox.setValue(0)  # Changed from 0.0 to 0
        self.families_table.clearSelection()
        self.set_button_states(selected=False)
        self.add_button.setEnabled(True)

    def on_family_name_changed(self):
        """Handle family name input changes"""
        selected = bool(self.families_table.selectionModel().selectedRows())
        self.set_button_states(selected)

    def show_styled_message(self, title, text, icon=QMessageBox.Icon.Information):
        msg = QMessageBox(self)
        msg.setIcon(icon)
        msg.setText(text)
        msg.setWindowTitle(title)
        msg.exec_()
