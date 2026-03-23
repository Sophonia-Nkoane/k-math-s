from PySide6.QtWidgets import (QVBoxLayout, QTableWidgetItem, QHeaderView, QHBoxLayout, QMessageBox,
                             QGroupBox, QFormLayout, QLabel)
from PySide6.QtCore import Qt
from core.desktop_shared_services import get_desktop_shared_services
from presentation.components.buttons import ButtonFactory
from presentation.styles import styles
from presentation.components.window_component import WindowComponent
from presentation.components.table import Table
from presentation.components.rounded_field import RoundedPlainTextField, RoundedSpinner
from presentation.styles.colors import TEXT_COLOR

class PaymentTermsDialog(WindowComponent):
    def __init__(self, db_manager, parent=None, main_window=None):
        super().__init__(parent, title="Payment Terms")
        self.db_manager = db_manager
        self.shared_services = get_desktop_shared_services(db_manager)
        self.main_window = main_window if main_window else parent
        self.setup_ui()
        self.populate_terms_table()
        
    def notify_main_window_refresh(self):
        """Notifies the main window to refresh dependent data if possible."""
        if hasattr(self.main_window, 'refresh_dependent_data'):
            self.main_window.refresh_dependent_data()

    def closeEvent(self, event):
        """Handle the close event to notify the main window."""
        self.notify_main_window_refresh()
        super().closeEvent(event)

    def clear_form(self):
        """Reset the form to its initial state."""
        self.term_name_entry.clear()
        self.term_description_entry.clear()
        self.discount_spinbox.setValue(0)
        self.term_id = None
        self.set_button_states(selected=False)
        self.term_name_entry.setFocus()
        self.terms_table.clearSelection()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(12)

        # Form group
        input_group = QGroupBox("Add / Edit Term")
        input_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        form_layout = QFormLayout(input_group)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(10)

        # Term name input using RoundedPlainTextField
        term_name_label = QLabel("Term Name:")
        term_name_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.term_name_entry = RoundedPlainTextField(placeholder_text="e.g., Monthly, Termly, etc.")
        form_layout.addRow(term_name_label, self.term_name_entry)

        # Description field
        description_label = QLabel("Description:")
        description_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.term_description_entry = RoundedPlainTextField(placeholder_text="Optional description...")
        form_layout.addRow(description_label, self.term_description_entry)
        

        # Discount Percentage spinner
        self.discount_spinbox = RoundedSpinner()
        self.discount_spinbox.setRange(0, 100)
        self.discount_spinbox.setValue(0)
        self.discount_spinbox.setSuffix("%")
        term_discount_label = QLabel("Term Discount Percentage:")
        term_discount_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        form_layout.addRow(term_discount_label, self.discount_spinbox)

        main_layout.addWidget(input_group)

        # Terms table
        table_columns = [
            {"name": "ID", "width": 0, "resize_mode": QHeaderView.ResizeMode.Fixed},
            {"name": "Term Name", "width": None, "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "Discount %", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents}
        ]

        self.terms_table_component = Table(self, columns=table_columns)
        self.terms_table = self.terms_table_component.get_table()
        self.terms_table.setColumnHidden(0, True)
        self.terms_table.itemSelectionChanged.connect(self.on_term_selection_changed)
        main_layout.addWidget(self.terms_table)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        self.add_button = ButtonFactory.create_add_button("Add Term")
        self.update_button = ButtonFactory.create_update_button("Update Selected")
        self.delete_button = ButtonFactory.create_delete_button("Delete Selected")
        self.clear_button = ButtonFactory.create_clear_button("Clear Form")

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

        self.add_button.clicked.connect(self.add_term)
        self.update_button.clicked.connect(self.update_term)
        self.delete_button.clicked.connect(self.delete_term)
        self.clear_button.clicked.connect(self.clear_form)

        main_layout.addLayout(button_layout)
        self.add_layout(main_layout)

        self.set_button_states(selected=False)

    def show_styled_message(self, title, text, icon_type=QMessageBox.Icon.Information):
        if hasattr(self.main_window, 'dialog_service'):
            self.main_window.dialog_service.show_styled_message(title, text, icon_type)
        else:
            msg = QMessageBox(self)
            msg.setWindowTitle(title)
            msg.setText(text)
            msg.setIcon(icon_type)
            ButtonFactory.style_dialog_buttons(msg)
            msg.exec()

    def show_styled_confirmation(self, title, text):
        if hasattr(self.main_window, 'dialog_service') and hasattr(self.main_window.dialog_service, 'show_confirmation_dialog'):
             return self.main_window.dialog_service.show_confirmation_dialog(title, text)
        else:
            # Fallback to a basic QMessageBox for confirmation
            msg = QMessageBox(self)
            msg.setWindowTitle(title)
            msg.setText(text)
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            ButtonFactory.style_dialog_buttons(msg)
            return msg.exec()


    def populate_terms_table(self):
        try:
            self.terms_table.setRowCount(0)
            terms = self.shared_services.payment_catalog_use_case.list_payment_terms()

            if terms:
                self.terms_table.setRowCount(len(terms))
                for row_idx, term in enumerate(terms):
                    term_id = term.get("term_id")
                    term_name = term.get("term_name")
                    description = term.get("description")
                    discount = term.get("discount_percentage")

                    # Set ID in hidden column 0
                    id_item = QTableWidgetItem(str(term_id))
                    id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable) # Make ID non-editable
                    # --- Store description in the UserRole of the hidden ID item ---
                    id_item.setData(Qt.ItemDataRole.UserRole, description or "") # Store description (or empty string)
                    # --- End Store description ---
                    self.terms_table.setItem(row_idx, 0, id_item)


                    # Set Term Name in visible column 0 (internal column 1)
                    name_item = QTableWidgetItem(term_name or "")
                    name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.terms_table.setItem(row_idx, 1, name_item)

                    # Set Discount % in visible column 1 (internal column 2)
                    discount_item = QTableWidgetItem(f"{discount}%" if discount is not None else "0%")
                    discount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                    discount_item.setFlags(discount_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.terms_table.setItem(row_idx, 2, discount_item)

        except Exception as e:
            self.show_styled_message("Database Error", f"Error loading payment terms: {e}", QMessageBox.Icon.Critical)


    def add_term(self):
        """Adds a new payment term."""
        term_name = self.term_name_entry.text().strip()
        term_description = self.term_description_entry.text().strip()
        discount = self.discount_spinbox.value()

        if not term_name:
            self.show_styled_message(
                "Input Error",
                "Please enter a payment term name.",
                QMessageBox.Icon.Warning
            )
            return

        try:
            _, error = self.shared_services.payment_catalog_use_case.create_payment_term(
                {
                    "term_name": term_name,
                    "description": term_description if term_description else None,
                    "discount_percentage": discount,
                },
                user_id=getattr(self.main_window, "current_user_id", None),
            )
            if error:
                self.show_styled_message("Duplicate Entry" if "exists" in error.lower() else "Error", error, QMessageBox.Icon.Warning)
                return
            self.populate_terms_table()
            self.clear_form()
            self.show_styled_message("Success", "Payment term added successfully.")

        except Exception as e:
            self.show_styled_message("Database Error", f"Error adding payment term: {e}", QMessageBox.Icon.Critical)

    def update_term(self):
        """Updates the selected payment term."""
        if not self.term_id:
            self.show_styled_message( # Use local or parent method
                "Selection Error",
                "Please select a payment term to update.",
                QMessageBox.Icon.Warning
            )
            return

        term_name = self.term_name_entry.text().strip()
        term_description = self.term_description_entry.text().strip()
        discount = self.discount_spinbox.value()

        if not term_name:
            self.show_styled_message( # Use local or parent method
                "Input Error",
                "Please enter a payment term name.",
                QMessageBox.Icon.Warning
            )
            return

        try:
            ok, error = self.shared_services.payment_catalog_use_case.update_payment_term(
                self.term_id,
                {
                    "term_name": term_name,
                    "description": term_description if term_description else None,
                    "discount_percentage": discount,
                },
                user_id=getattr(self.main_window, "current_user_id", None),
            )
            if not ok:
                self.show_styled_message("Error", error or "Failed to update payment term.", QMessageBox.Icon.Warning)
                return
            self.populate_terms_table()
            self.clear_form()
            self.show_styled_message("Success", "Payment term updated successfully.")

        except Exception as e:
            self.show_styled_message("Database Error", f"Error updating payment term: {e}", QMessageBox.Icon.Critical)

    def delete_term(self):
        """Deletes the selected payment term after confirmation."""
        if not self.term_id:
            self.show_styled_message( # Use local or parent method
                "Selection Error",
                "Please select a payment term to delete.",
                QMessageBox.Icon.Warning
            )
            return

        try:
            confirm_result = self.show_styled_confirmation(
                "Confirm Delete",
                f"Are you sure you want to delete the payment term '{self.term_name_entry.text()}'?"
            )

            confirm = confirm_result == QMessageBox.StandardButton.Yes if isinstance(confirm_result, QMessageBox.StandardButton) else confirm_result # Added compatibility check

            if confirm:
                ok, error = self.shared_services.payment_catalog_use_case.delete_payment_term(
                    self.term_id,
                    user_id=getattr(self.main_window, "current_user_id", None),
                )
                if not ok:
                    self.show_styled_message("Cannot Delete", error or "Failed to delete payment term.", QMessageBox.Icon.Warning)
                    return

                self.populate_terms_table()
                self.clear_form()
                self.show_styled_message("Success", "Payment term deleted successfully.")

        except Exception as e:
            self.show_styled_message("Database Error", f"Error deleting payment term: {e}", QMessageBox.Icon.Critical)

    def on_term_selection_changed(self):
        selected_rows = self.terms_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            # Get the term_id from the hidden column 0
            id_item = self.terms_table.item(row, 0)
            if id_item:
                self.term_id = int(id_item.text())

                description = id_item.data(Qt.ItemDataRole.UserRole)
                self.term_description_entry.setText(description or "") # Set description field, use empty string if None
                
                # Get Term Name from visible column 0 (internal column 1)
                name_item = self.terms_table.item(row, 1)
                if name_item:
                    self.term_name_entry.setText(name_item.text())

                # Get Discount % from visible column 1 (internal column 2)
                discount_item = self.terms_table.item(row, 2)
                if discount_item:
                    discount_text = discount_item.text() # Get text from the Discount % column
                    try:
                        # Remove '%' and convert to integer
                        self.discount_spinbox.setValue(int(float(discount_text.rstrip('%'))))
                    except (ValueError, TypeError):
                        self.discount_spinbox.setValue(0) # Default to 0 if parsing fails
            else:
                 # Should not happen if rows exist, but good practice
                 self.clear_form()
                 return


            self.set_button_states(selected=True) # Enables Update / Delete buttons
        else:
            self.clear_form() # Clear form when selection is cleared


    def set_button_states(self, selected=False):
         self.update_button.setEnabled(selected)
         self.delete_button.setEnabled(selected)
         self.add_button.setEnabled(not selected) # Add button enabled when nothing selected
