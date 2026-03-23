from __future__ import annotations

from PySide6.QtWidgets import (QFormLayout, QCompleter, QMessageBox, QGroupBox,
                           QVBoxLayout, QHBoxLayout, QLabel, QHeaderView, QApplication,
                           QTableWidgetItem, QScrollArea, QWidget, QFileDialog, QProgressDialog)
from PySide6.QtCore import Qt, QStringListModel, QDate
from core.desktop_shared_services import get_desktop_shared_services
from presentation.components.window_component import WindowComponent
from presentation.components.rounded_field import RoundedPlainTextField, RoundedCalendarDropdown
from presentation.components.password_confirmation_dialog import PasswordConfirmationDialog
from presentation.components.buttons import ButtonFactory
from presentation.components.confirmation_dialog import ConfirmationDialog
from presentation.components.success_dialog import SuccessDialog
from datetime import datetime
import fitz # PyMuPDF for getting page count
import traceback
import logging
from presentation.styles import styles
from presentation.styles.colors import (SCROLLBAR_BACKGROUND, SCROLLBAR_HANDLE,
                              SCROLLBAR_HANDLE_HOVER, STATUS_ACTIVE_COLOR,
                              STATUS_PAUSED_COLOR, NEGATIVE_VALUE_COLOR)
from utils.settings_manager import SettingsManager
from domain.services.authentication_service import AuthenticationService
from domain.services.progress_service import ProgressService
from presentation.styles.colors import TEXT_COLOR
from presentation.components.table import Table

# OCR functionality is optional. We defer importing heavy OCR packages until needed
# to avoid import-time stalls or errors (torch/easyocr can be slow or raise non-ImportError exceptions).
OCR_AVAILABLE = False

class RecordPaymentDialog(WindowComponent):
    """Dialog for recording learner payments."""
    def __init__(self, db_manager, current_user_id, selected_acc_no=None, family_id=None, parent=None):
        super().__init__(parent, title="Record Payment")
        self.db_manager = db_manager
        self.current_user_id = current_user_id
        self.shared_services = get_desktop_shared_services(db_manager)
        self.selected_acc_no = selected_acc_no
        self.family_id = family_id
        self.auth_service = AuthenticationService(db_manager)
        self.settings_manager = SettingsManager()
        self.logger = logging.getLogger(__name__)
        self.setup_ui()
        self.load_names_and_setup_completer()
        self._prefill_selected_learner()
        self.set_size(820, 620)

    def setup_ui(self):
        self.current_learner_acc_no = None
        self.current_family_id = None
        self.current_family_payment_mode = None
        self.current_family_discount = 0.0
        self.selected_payment_id = None

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameStyle(0)
        scroll_area.setStyleSheet(styles.SCROLL_AREA_STYLE)
        
        container_widget = QWidget()
        main_layout = QVBoxLayout(container_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(12)
        
        learner_select_group = QGroupBox("Select Learner")
        learner_select_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        learner_select_layout = QFormLayout(learner_select_group)
        learner_select_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        learner_select_layout.setHorizontalSpacing(10)
        learner_select_layout.setVerticalSpacing(10)
        
        self.learner_name_entry = RoundedPlainTextField(placeholder_text="Type learner name (Name Surname)...")
        learner_name_label = QLabel("Learner Name:")
        learner_name_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        learner_select_layout.addRow(learner_name_label, self.learner_name_entry)
        
        self.selected_learner_label = QLabel(
            f"Selected Learner: <font color='{NEGATIVE_VALUE_COLOR()}'>None</font>"
        )
        self.selected_learner_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.selected_learner_label.setWordWrap(True)
        learner_select_layout.addRow(QLabel(""), self.selected_learner_label)

        payment_details_group = QGroupBox("Payment Details")
        payment_details_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        payment_details_layout = QFormLayout(payment_details_group)
        payment_details_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        payment_details_layout.setHorizontalSpacing(10)
        payment_details_layout.setVerticalSpacing(10)

        amount_label = QLabel("Amount (R):")
        amount_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        date_label = QLabel("Date:")
        date_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.amount_entry = RoundedPlainTextField(placeholder_text="e.g., 1500.00")
        payment_details_layout.addRow(amount_label, self.amount_entry)
        self.date_entry = RoundedCalendarDropdown()
        date_layout = QHBoxLayout()
        date_layout.addWidget(self.date_entry)
        payment_details_layout.addRow(date_label, date_layout)

        action_button_layout = QHBoxLayout()
        action_button_layout.setSpacing(10)
        self.record_button = ButtonFactory.create_record_payment_button()
        self.record_button.clicked.connect(self.record_payment)
        self.record_button.setEnabled(False)
        self.upload_button = ButtonFactory.create_update_button("Upload Slip")
        self.upload_button.clicked.connect(self.upload_and_process_slip)
        self.upload_button.setMinimumWidth(140)
        self.record_button.setMinimumWidth(140)
        action_button_layout.addStretch()
        action_button_layout.addWidget(self.upload_button)
        action_button_layout.addWidget(self.record_button)

        history_group = QGroupBox("Payment History")
        history_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        history_layout = QVBoxLayout(history_group)
        history_layout.setContentsMargins(10, 10, 10, 10)
        history_layout.setSpacing(8)

        payment_history_columns = [
            {"name": "Date", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Amount", "width": None, "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "Actions", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "ID", "width": None, "resize_mode": None}
        ]
        self.payment_history_table_component = Table(self, columns=payment_history_columns)
        self.payment_history_table_widget = self.payment_history_table_component.get_table()
        self.payment_history_table_widget.setColumnHidden(3, True)
        history_layout.addWidget(self.payment_history_table_widget)

        main_layout.addWidget(learner_select_group)
        main_layout.addWidget(payment_details_group)
        main_layout.addLayout(action_button_layout)
        main_layout.addWidget(history_group)

        scroll_area.setWidget(container_widget)
        self.add_widget(scroll_area)

    def upload_and_process_slip(self):
        """Opens a file dialog, processes slip with OCR showing progress, and populates form."""
        # Try to import OCR functionality lazily when user requests it. This avoids heavy imports at module load time.
        global OCR_AVAILABLE
        try:
            if not OCR_AVAILABLE:
                from business.ocr.ocr_processor import analyze_document  # type: ignore
                OCR_AVAILABLE = True
        except Exception as e:
            OCR_AVAILABLE = False
            logging.warning(f"OCR import failed or unavailable: {e}")

        if not OCR_AVAILABLE:
            self.show_styled_message("OCR Not Available", "OCR functionality is not installed or failed to initialize. Please install easyocr and torch to enable document processing. For now, please enter payment details manually.", QMessageBox.Icon.Warning)
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Payment Slip",
            "",
            "Documents (*.pdf *.png *.jpg *.jpeg);;All Files (*)"
        )
        if not file_path:
            return

        num_pages = 1
        if file_path.lower().endswith('.pdf'):
            try:
                with fitz.open(file_path) as doc:
                    num_pages = len(doc)
            except Exception as e:
                self.show_styled_message("File Error", f"Could not read PDF: {e}", QMessageBox.Icon.Critical)
                return

        progress_dialog = QProgressDialog("Processing document...", "Cancel", 0, num_pages + 1, self)
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setWindowTitle("Processing Document")

        if not hasattr(self, '_ocr_initialized'):
            progress_dialog.setLabelText("First-time setup: Downloading OCR models...")
            progress_dialog.show()
            QApplication.processEvents()

        progress_dialog.setLabelText("Starting OCR process...")
        progress_dialog.show()
        QApplication.processEvents()

        def progress_callback(current_step, total_steps) -> bool:
            if progress_dialog.wasCanceled():
                return False
            if current_step == -1:
                progress_dialog.cancel()
                return False
            progress_dialog.setValue(current_step)
            if current_step < total_steps:
                progress_dialog.setLabelText(f"Processing page {current_step + 1} of {total_steps}...")
            else:
                progress_dialog.setLabelText("Processing complete.")
            QApplication.processEvents()
            return True

        extracted_data = None
        try:
            # --- CHANGE 2: Get learner names BEFORE the OCR call ---
            # The new function needs the list of names to search for.
            learner_names = list(self.learner_names_map.keys())

            # --- CHANGE 3: Call the new unified function ---
            # It takes the learner list and progress callback, and returns the final structured data.
            extracted_data = analyze_document(file_path, learner_names, progress_callback)

        finally:
            progress_dialog.close()

        # --- CHANGE 4: The rest of the logic is now much simpler ---
        # We no longer need the second `extract_structured_data` call.

        if not extracted_data:
            if not progress_dialog.wasCanceled():
                self.show_styled_message("OCR Result", "Could not automatically find payment details in the document. Please enter them manually.", QMessageBox.Icon.Information)

                # Send OCR failure notification email
                try:
                    from business.services.email_service import EmailService
                    email_service = EmailService()
                    admin_email = self.settings_manager.get_email_setting("admin_email", "")
                    if admin_email:
                        email_sent = email_service.send_ocr_failure_notification(
                            admin_email, "payment slip", file_path
                        )
                        if email_sent:
                            self.logger.info(f"OCR failure notification sent for payment slip: {file_path}")
                        else:
                            self.logger.warning(f"Failed to send OCR failure notification for payment slip: {file_path}")
                except Exception as e:
                    self.logger.error(f"Error sending OCR failure notification: {e}")

            return

        # Process payment notifications for all extracted payments
        try:
            from business.services.payment_notification_service import PaymentNotificationService
            notification_service = PaymentNotificationService(self.db_manager)
            notification_results = notification_service.process_payment_notifications(extracted_data)

            # Show notification results
            if notification_results['emails_sent'] > 0:
                self.show_styled_message("Success",
                    f"Payment details extracted and {notification_results['emails_sent']} thank you email(s) sent successfully. Please verify and record the payment.")
            else:
                self.show_styled_message("OCR Success",
                    "Payment details extracted successfully, but no emails were sent (check learner/parent data). Please verify and record the payment.")

            # Log any errors
            if notification_results['errors']:
                for error in notification_results['errors'][:3]:  # Show first 3 errors
                    self.logger.error(f"Email notification error: {error}")

        except Exception as e:
            self.logger.error(f"Error processing payment notifications: {e}")
            self.show_styled_message("Notification Error", f"OCR successful but email notifications failed: {e}", QMessageBox.Icon.Warning)

        # If we got results, populate the form with the first one found.
        try:
            payment_info = extracted_data[0]
            self.populate_form_from_ocr(payment_info)
        except Exception as e:
            self.show_styled_message("Data Population Error", f"An error occurred while populating the form: {e}", QMessageBox.Icon.Critical)
            self.logger.exception(f"Error populating form from OCR data: {e}")

    def show_styled_message(self, title, text, icon_type=QMessageBox.Icon.Information):
        """Shows a styled message dialog."""
        if icon_type == QMessageBox.Icon.Information and title == "Success":
            SuccessDialog.show_success(self, text)
        else:
            msg = QMessageBox(self)
            msg.setWindowTitle(title)
            msg.setText(text)
            msg.setIcon(icon_type)
            msg.addButton(QMessageBox.StandardButton.Ok)
            msg.exec()

    def load_names_and_setup_completer(self):
        """Load learner names and setup autocomplete."""
        try:
            self.learner_names_map = self.fetch_learner_names_map()
            completer_model = QStringListModel(list(self.learner_names_map.keys()))
            completer = QCompleter()
            completer.setModel(completer_model)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.learner_name_entry.setCompleter(completer)
            self.learner_name_entry.editingFinished.connect(self.validate_learner_selection)
        except Exception as e:
            self.show_styled_message("Error", f"Error loading learner names: {e}", QMessageBox.Icon.Critical)

    def fetch_learner_names_map(self):
        """Fetches learner names and their acc_no into a dictionary."""
        name_map = {}
        try:
            learners = self.shared_services.learner_use_case.list_learners()
            if learners:
                for learner in learners:
                    name = str(learner.get("name") or "")
                    surname = str(learner.get("surname") or "")
                    acc_no = str(learner.get("acc_no") or "")
                    if not acc_no:
                        continue
                    full_name = f"{name} {surname}"
                    display_name = full_name
                    count = 1
                    while display_name in name_map:
                        count += 1
                        display_name = f"{full_name} ({acc_no.split('-')[0][-4:]})"
                        if count > 10: break
                    name_map[display_name] = acc_no
        except Exception as e:
            self.show_styled_message("Error", f"Error loading learner names: {e}", QMessageBox.Icon.Critical)
        return name_map

    def _prefill_selected_learner(self):
        """Populate the learner field when the dialog is opened from a selected row."""
        if not self.selected_acc_no:
            return

        display_name = next(
            (name for name, acc_no in self.learner_names_map.items() if acc_no == self.selected_acc_no),
            None,
        )

        if display_name is None:
            try:
                learner = self.shared_services.learner_use_case.get_learner(self.selected_acc_no)
            except Exception as e:
                self.logger.warning("Failed to prefill selected learner %s: %s", self.selected_acc_no, e)
                learner = None

            if learner:
                name = str(learner.get("name") or "").strip()
                surname = str(learner.get("surname") or "").strip()
                full_name = f"{name} {surname}".strip()
                if full_name:
                    display_name = next(
                        (entry for entry, acc_no in self.learner_names_map.items() if acc_no == self.selected_acc_no),
                        full_name,
                    )

        if not display_name:
            self.current_learner_acc_no = self.selected_acc_no
            self.selected_learner_label.setText(
                f"Selected Learner: <font color='{STATUS_ACTIVE_COLOR()}'>"
                f"{self.selected_acc_no.split('-')[0]}</font>"
            )
            self.record_button.setEnabled(True)
            self.check_family_status()
            self.load_payment_history()
            return

        self.learner_name_entry.setText(display_name)
        self.validate_learner_selection()

    def validate_learner_selection(self):
        """Validates the entered learner name against the map and updates state."""
        entered_name = self.learner_name_entry.text().strip()
        self.current_learner_acc_no = None
        self.current_family_id = None
        self.current_family_payment_mode = None
        self.current_family_discount = 0.0
        self.record_button.setEnabled(False)
        self.payment_history_table_widget.setRowCount(0)

        if not entered_name:
            self.selected_learner_label.setText(
                f"Selected Learner: <font color='{NEGATIVE_VALUE_COLOR()}'>None</font>"
            )
            return

        if entered_name in self.learner_names_map:
            self.current_learner_acc_no = self.learner_names_map[entered_name]
            self.selected_learner_label.setText(
                f"Selected Learner: <font color='{STATUS_ACTIVE_COLOR()}'>{entered_name}</font> "
                f"(Acc: {self.current_learner_acc_no.split('-')[0]})"
            )
            self.record_button.setEnabled(True)
            self.check_family_status()
            self.load_payment_history()
        else:
            self.selected_learner_label.setText(
                f"Selected Learner: <font color='{STATUS_PAUSED_COLOR()}'>"
                f"'{entered_name}' - Not found/validated. Select from list.</font>"
            )

    def populate_form_from_ocr(self, payment_info: dict):
        """Populates the dialog's fields from the dictionary of extracted OCR data."""
        learner_name = payment_info.get('name')
        if learner_name and learner_name in self.learner_names_map:
            self.learner_name_entry.setText(learner_name)
            self.validate_learner_selection()

        amount = payment_info.get('amount')
        if amount is not None:
            self.amount_entry.setText(f"{amount:.2f}")

        date_str = payment_info.get('date')
        if date_str:
            q_date = self._parse_flexible_date(date_str)
            if q_date:
                self.date_entry.setDate(q_date)

    def _parse_flexible_date(self, date_str: str) -> QDate | None:
        """Parses a date string with various possible formats into a QDate."""
        if not date_str: return None
        date_str = date_str.replace('/', '-').replace('.', '-')
        formats_to_try = ['%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y', '%y-%m-%d', '%d-%m-%y', '%m-%d-%y']
        for fmt in formats_to_try:
            try:
                dt_obj = datetime.strptime(date_str, fmt)
                return QDate(dt_obj.year, dt_obj.month, dt_obj.day)
            except ValueError:
                continue
        return None

    def check_family_status(self):
        """Checks family status, mode, and discount for the selected learner."""
        self.current_family_id = None
        self.current_family_payment_mode = None
        self.current_family_discount = 0.0
        if not self.current_learner_acc_no: return

        try:
            learner = self.shared_services.learner_use_case.get_learner(self.current_learner_acc_no)
            family_id = int(learner.get("family_id") or 0) if learner else 0
            if family_id > 0:
                family = self.shared_services.family_use_case.get_family(family_id)
                if family:
                    self.current_family_id = family_id
                    self.current_family_payment_mode = family.get("payment_mode")
                    self.current_family_discount = float(family.get("discount_percentage") or 0.0)
        except Exception as e:
            self.logger.error(f"Error checking family status: {e}")

    def load_payment_history(self):
        """Loads and displays payment history for the selected learner."""
        self.payment_history_table_widget.setRowCount(0)
        self.selected_payment_id = None
        if not self.current_learner_acc_no: return

        try:
            payments = list(self.shared_services.payment_use_case.list_payments(learner_acc_no=self.current_learner_acc_no, limit=500))
            if self.current_family_id:
                payments.extend(self.shared_services.payment_use_case.list_payments(family_id=self.current_family_id, limit=500))

            unique_payments = {}
            for payment in payments:
                payment_id = int(payment.get("payment_id") or 0)
                if payment_id:
                    unique_payments[payment_id] = payment
            ordered_payments = sorted(
                unique_payments.values(),
                key=lambda item: (str(item.get("date") or ""), int(item.get("payment_id") or 0)),
                reverse=True,
            )

            self.payment_history_table_widget.setRowCount(len(ordered_payments))
            for row, payment in enumerate(ordered_payments):
                payment_id = int(payment.get("payment_id") or 0)
                date = str(payment.get("date") or "")
                amount = float(payment.get("amount") or 0.0)
                self.payment_history_table_widget.setItem(row, 0, QTableWidgetItem(date))
                
                amount_item = QTableWidgetItem(f"R {amount:.2f}")
                amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.payment_history_table_widget.setItem(row, 1, amount_item)

                # --- ADJUSTED DELETE BUTTON LOGIC ---
                # 1. Create the new icon-based button from your factory
                delete_button = ButtonFactory.create_delete_icon_button()
                delete_button.clicked.connect(lambda checked, r=row: self.delete_payment_row(r))

                # 2. Create a container widget and a layout to center the button
                cell_widget = QWidget()
                layout = QHBoxLayout(cell_widget)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center the content
                layout.addWidget(delete_button) # No stretches needed

                # 3. Add the container to the cell
                self.payment_history_table_widget.setCellWidget(row, 2, cell_widget)
                # --- END OF ADJUSTMENT ---

                self.payment_history_table_widget.setItem(row, 3, QTableWidgetItem(str(payment_id)))
        except Exception as e:
            self.show_styled_message("Error", f"Error loading payment history: {e}", QMessageBox.Icon.Critical)
                        
    def delete_payment_row(self, row):
        """Deletes a payment after confirmation and password validation."""
        try:
            payment_id = self.payment_history_table_widget.item(row, 3).text()
            amount = float(self.payment_history_table_widget.item(row, 1).text().replace('R ', ''))
            learner_name = self.learner_name_entry.text().strip()

            if not ConfirmationDialog.show_dialog(self, title="Confirm Delete", message=f"Are you sure you want to delete this payment of R {amount:,.2f}?"):
                return

            password = PasswordConfirmationDialog.get_password_from_user(self)
            if not password or not self.auth_service.verify_user_password(self.db_manager, self.current_user_id, password):
                self.show_styled_message("Authentication Failed", "Incorrect password. Payment deletion aborted.", QMessageBox.Icon.Warning)
                return

            ok, error = self.shared_services.payment_use_case.delete_payment(
                int(payment_id),
                user_id=self.current_user_id,
            )
            if not ok:
                self.show_styled_message("Error", error or "Payment deletion failed.", QMessageBox.Icon.Warning)
                return

            self.load_payment_history()
            SuccessDialog.show_success(self, f"Payment deleted successfully for {learner_name}.")
        except (Exception, ValueError) as e:
            self.show_styled_message("Error", f"Error cancelling payment: {e}", QMessageBox.Icon.Critical)

    def record_payment(self):
        """Records a new payment after validation and confirmation."""
        learner_name = self.learner_name_entry.text().strip()
        amount_str = self.amount_entry.text().strip()
        date_str = self.date_entry.text()

        if not self.validate_payment_input(amount_str, date_str):
            return

        # Check progress eligibility for grades 1-7
        progress_service = ProgressService(self.db_manager)
        eligibility_check = progress_service.is_payment_change_allowed(self.current_learner_acc_no)

        if not eligibility_check['allowed']:
            self.show_styled_message("Payment Not Allowed",
                                   f"Cannot record payment for this learner.\n\nReason: {eligibility_check['reason']}\n\n"
                                   "Please update the learner's progress or wait for the restriction period to expire.",
                                   QMessageBox.Icon.Warning)
            return

        try:
            final_amount, _ = self.calculate_final_amount(amount_str, date_str)

            confirm_msg = f"Record payment of R {final_amount:.2f} for {learner_name}?"
            if not ConfirmationDialog.show_dialog(self, title="Confirm Record Payment", message=confirm_msg):
                return
 
            month_year = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m")
            payload = {
                "amount": final_amount,
                "date": date_str,
                "month_year": month_year,
                "recorded_by_user_id": self.current_user_id,
            }
            if self.current_family_id and self.current_family_payment_mode == 'single_coverage':
                payload["family_id"] = self.current_family_id
            else:
                payload["learner_id"] = self.current_learner_acc_no

            payment_id, error = self.shared_services.payment_use_case.create_payment(
                payload,
                user_id=self.current_user_id,
            )
            if not payment_id:
                self.show_styled_message("Error", error or "Error recording payment.", QMessageBox.Icon.Critical)
                return

            try:
                progress_service.record_payment_change(
                    self.current_learner_acc_no,
                    self.current_user_id,
                    f"Payment recorded: R {final_amount:.2f}",
                )
            except Exception as progress_error:
                self.logger.warning("Failed to record payment change for progress tracking: %s", progress_error)
                
            # Send email notification for manual payment
            try:
                from business.services.payment_notification_service import PaymentNotificationService
                notification_service = PaymentNotificationService(self.db_manager)
                email_sent = notification_service.send_manual_payment_notification(
                    self.current_learner_acc_no, final_amount, date_str
                )
                if email_sent:
                    self.show_styled_message("Success", f"Payment recorded successfully for {learner_name} and thank you email sent.")
                else:
                    self.show_styled_message("Success", f"Payment recorded successfully for {learner_name}. (Email notification failed)")
            except Exception as e:
                self.logger.error(f"Error sending manual payment notification: {e}")
                self.show_styled_message("Success", f"Payment recorded successfully for {learner_name}. (Email notification error)")

            # We still clear the fields and update the history to show the new payment
            self.clear_payment_fields()
            self.load_payment_history()
            
            
        except (Exception, ValueError) as e:
            self.show_styled_message("Error", f"Error recording payment: {e}", QMessageBox.Icon.Critical)
    def validate_payment_input(self, amount_str, date_str):
        """Validates the payment input fields."""
        if not self.current_learner_acc_no:
            self.show_styled_message("Error", "No valid learner selected.", QMessageBox.Icon.Warning)
            return False
        if not amount_str or not date_str:
            self.show_styled_message("Input Error", "Amount and Date are required.", QMessageBox.Icon.Warning)
            return False
        try:
            amount = float(amount_str)
            if amount <= 0:
                self.show_styled_message("Input Error", "Amount must be greater than zero.", QMessageBox.Icon.Warning)
                return False
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            self.show_styled_message("Input Error", "Invalid amount or date format.", QMessageBox.Icon.Warning)
            return False

    def calculate_final_amount(self, amount_str, date_str):
        amount = float(amount_str)
        final_amount, log_details = amount, ""
        return final_amount, log_details

    def clear_payment_fields(self):
        self.amount_entry.clear()
        self.date_entry.setDate(QDate.currentDate())
