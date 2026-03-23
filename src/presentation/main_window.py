from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, 
                             QLineEdit, QTableWidgetItem, QMessageBox, 
                             QDialog, QHeaderView, QHBoxLayout,
                             QApplication, QDialogButtonBox, QMenu) 
from PySide6.QtCore import Qt, QEvent
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtGui import QColor

import os
import re
import logging
from datetime import datetime, date

from utils.settings_manager import SettingsManager
from presentation.dialogs.statement import generate_learner_statement_html, generate_family_statement_html
from presentation.statement_pdf import (
    build_statement_pdf_bytes,
    render_statement_pdf_documents_to_printer,
    save_statement_pdf_bytes,
)
from data.repositories.learner_repository import LearnerRepository
from data.repositories.payment_repository import PaymentRepository
from data.repositories.family_repository import FamilyRepository
from data.repositories.parent_repository import ParentRepository
from business.services.learner_service import LearnerService
from domain.services.selection_service import SelectionService
from domain.services.dialog_service import DialogService
from domain.services.authentication_service import AuthenticationService
from domain.services.fee_service import FeeService
from domain.services.statement_service import StatementService
from presentation.styles import colors, styles
from presentation.components.buttons import ButtonFrame, ButtonFactory
from presentation.components.search_bar import SearchBar
from presentation.components.table import Table
from presentation.components.success_dialog import SuccessDialog
from presentation.components.menu_bar import MenuBar
from presentation.styles.colors import set_theme, TEXT_COLOR
from presentation.dialogs.system_settings_dialog import SystemSettingsDialog
from presentation.dialogs.class_list_dialog import ClassListDialog
from presentation.components.window_component import WindowComponent
from presentation.components.status_info_panel import StatusInfoPanel
from presentation.widgets.progress_tracker_panel import ProgressTrackerPanel

class LearnerManagementApp(QMainWindow):
    """Main application window."""
    def __init__(self, learner_service, logo_path, theme_manager):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.setWindowTitle("Learner Payment Management System")
        self.learner_service = learner_service
        self.logo_path = logo_path
        self.theme_manager = theme_manager
        self.current_user_id = None
        self.current_username = None
        self.current_user_role = None
        self.all_learners_data = []
        self.payment_options_cache = {}
        self.family_data_cache = {}
        self.payment_terms_cache = {}
        self.sync_scheduler = None

        self.learner_repository = self.learner_service.learner_repository
        self.payment_repository = self.learner_service.payment_repository
        self.family_repository = self.learner_service.family_repository
        self.parent_repository = self.learner_service.parent_repository
        self.db_manager = self.learner_repository.db_manager

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.individual_statements_queue = []
        self.selection_service = SelectionService(self.db_manager)
        self.dialog_service = DialogService(self, self.db_manager, self.learner_service)
        self.auth_service = AuthenticationService(self.db_manager)
        self.fee_service = FeeService(self.payment_repository, self.learner_repository, self.family_repository)
        self.statement_service = StatementService(self, self.learner_repository, self.family_repository, self.payment_repository, self.logo_path, self.db_manager)

        self.setMinimumSize(800, 600)

        screen = QApplication.primaryScreen().availableGeometry()
        square_size = min(screen.width() * 0.8, screen.height() * 0.8)
        self.default_square_size = (int(square_size), int(square_size))

        self.showMaximized()

        self.status_info = StatusInfoPanel(self.db_manager, self.theme_manager, self)
        self.statusBar().addPermanentWidget(self.status_info, 1)
        self.statusBar().setStyleSheet(styles.STATUS_BAR_STYLE)

        self.logger.info("Attempting login")
        if not self.login():
             self.logger.warning("Login failed. Quitting application")
             QApplication.instance().quit()
        else:
            self.logger.info("Login successful. Application starting")

        self.theme_manager.themeChanged.connect(self.reinit_ui)

    def reinit_ui(self, _is_dark=None):
        """Reinitializes the UI elements, typically after a theme change."""
        self.setup_main_ui()
        self.statusBar().setStyleSheet(styles.STATUS_BAR_STYLE)
        if hasattr(self, "status_info"):
            self.status_info.update_styles()
        self.load_learners()

    def changeEvent(self, event):
        """Handle window state changes."""
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() == Qt.WindowState.WindowNoState:
                width, height = self.default_square_size
                self.resize(width, height)
        super().changeEvent(event)

    def show_styled_message(self, title, text, icon_type=QMessageBox.Icon.Information):
        """Displays a styled message dialog. Uses SuccessDialog for success messages."""
        if title == "Success":
            SuccessDialog.show_success(self, text)
        else:
            self.dialog_service.show_styled_message(title, text, icon_type)

    def on_learner_select(self):
        """Handles learner selection in the table."""
        selected_items = self.learner_table.selectedItems()
        if selected_items:
            # Get the item from the first column (acc_no column)
            selected_row = selected_items[0].row()
            item = self.learner_table.item(selected_row, 0)
            self.selection_service.update_selection(item)
            
            # Show progress tracker panel only for grades 1-7
            grade_item = self.learner_table.item(selected_row, 4)  # Grade is in column 4
            if grade_item:
                try:
                    grade = int(grade_item.text())
                    if 1 <= grade <= 7:
                        # Load learner data into progress panel and show it
                        acc_no = item.text()
                        learner_dto = self.learner_service.get_learner_for_update(acc_no)
                        if learner_dto:
                            self.progress_tracker_panel.load_single_learner(learner_dto)
                            self.progress_tracker_panel.setVisible(True)
                        else:
                            self.progress_tracker_panel.setVisible(False)
                    else:
                        self.progress_tracker_panel.setVisible(False)
                except (ValueError, AttributeError):
                    self.progress_tracker_panel.setVisible(False)
            else:
                self.progress_tracker_panel.setVisible(False)
        else:
            self.selection_service.clear_selection()
            self.progress_tracker_panel.setVisible(False)
        self.set_button_states_after_selection()

    def login(self):
        """Handles the login process. Returns True on success, False on cancel/fail."""
        while True:
            self.logger.debug("Calling show_login_dialog")
            result, auth_result = self.dialog_service.show_login_dialog()
            self.logger.debug(f"show_login_dialog returned: result={result}, auth_result={auth_result}")
            if result == QDialog.DialogCode.Accepted and auth_result:
                self.current_user_id, self.current_user_role, self.current_username = auth_result
                SuccessDialog.show_success(self, f"Welcome, {self.current_username}!")
                self.setup_main_ui()
                self.load_learners()
                return True
            elif result != QDialog.DialogCode.Accepted:
                self.logger.info("Login dialog not accepted or authentication failed")
                return False

    def setup_main_ui(self):
        """Sets up the main UI elements after successful login."""
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()

        self.setStyleSheet(styles.MAIN_WINDOW_STYLE)

        self.setup_menu_bar()

        self.search_bar = SearchBar(self)
        self.main_layout.addLayout(self.search_bar.layout)

        main_columns = [
            {"name": "Acc", "width": 105, "resize_mode": None},
            {"name": "Name", "width": None, "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "Surname", "width": None, "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "Gender", "width": 70, "resize_mode": None},
            {"name": "Grade", "width": 55, "resize_mode": None},
            {"name": "Subjects", "width": 85, "resize_mode": None},
            {"name": "Option", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Fees", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Status", "width": 85, "resize_mode": None}
        ]
        
        self.table_component = Table(self, columns=main_columns)
        self.learner_table = self.table_component.get_table()
        try:
            self.learner_table.cellDoubleClicked.connect(self._on_table_double_click)
            self.learner_table.itemSelectionChanged.connect(self.on_learner_select)
        except Exception:
            try:
                self.learner_table.doubleClicked.connect(lambda idx: self._on_table_double_click(idx.row(), idx.column()))
            except Exception:
                pass
        self.learner_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.learner_table.customContextMenuRequested.connect(self.show_context_menu)
        self.main_layout.addWidget(self.learner_table, 1)  # Give table stretch factor of 1

        # Add progress tracker panel (initially hidden)
        self.progress_tracker_panel = ProgressTrackerPanel(self.learner_service, self)
        self.progress_tracker_panel.setVisible(False)  # Hidden by default
        self.main_layout.addWidget(self.progress_tracker_panel, 0)  # No stretch for panel

        self.button_frame = ButtonFrame(self)
        self.main_layout.addLayout(self.button_frame.layout)

        self.set_button_states_after_selection()

    def show_context_menu(self, pos):
        """Shows a context menu on right-click."""
        selected_items = self.learner_table.selectedItems()
        if not selected_items:
            return

        # Get the acc_no from the first column of the selected row
        acc_no = self.learner_table.item(self.learner_table.currentRow(), 0).text()
        if not acc_no:
            return

        menu = QMenu()
        view_action = menu.addAction("View Details")
        record_payment_action = menu.addAction("Record Payment")
        update_action = menu.addAction("Update Learner")
        menu.addSeparator()
        
        # Check learner status to show either "Pause" or "Resume"
        is_active = self.learner_repository.is_learner_active(acc_no)
        if is_active:
            pause_action = menu.addAction("Pause Billing")
        else:
            resume_action = menu.addAction("Resume Billing")
            
        menu.addSeparator()
        delete_action = menu.addAction("Delete Learner")

        # Execute the menu
        action = menu.exec(self.learner_table.mapToGlobal(pos))

        # Handle the selected action
        if action == view_action:
            self.dialog_service.show_view_details_dialog(acc_no)
        elif action == record_payment_action:
            self.open_record_payment_dialog()
        elif action == update_action:
            self.dialog_service.show_update_learner_dialog(self.current_user_id, acc_no)
        elif 'pause_action' in locals() and action == pause_action:
            self.pause_selected_learner_billing()
        elif 'resume_action' in locals() and action == resume_action:
            self.resume_selected_learner_billing()
        elif action == delete_action:
            self.delete_learner()

    def update_status_bar_learner_count(self, count):
        self.status_info.update_learner_count(count)

    def set_button_states_after_selection(self):
        """Updates the enabled state of buttons based on learner selection."""
        has_selection = bool(self._resolve_selected_acc_no(sync_selection=False))
        self.button_frame.update_button_states(has_selection)

    def _resolve_selected_acc_no(self, sync_selection=True):
        """Return the selected learner acc_no from the table, falling back to cached selection."""
        if not hasattr(self, "learner_table") or self.learner_table is None:
            return self.selection_service.get_selected_acc_no()

        selected_items = self.learner_table.selectedItems()
        selected_row = selected_items[0].row() if selected_items else self.learner_table.currentRow()
        if selected_row is not None and selected_row >= 0:
            item = self.learner_table.item(selected_row, 0)
            if item:
                if sync_selection:
                    self.selection_service.update_selection(item)
                stored_data = item.data(Qt.ItemDataRole.UserRole)
                return stored_data or item.text()

        if sync_selection:
            self.selection_service.clear_selection()
        return self.selection_service.get_selected_acc_no()

    def get_family_id_for_learner(self, acc_no):
        return self.learner_repository.get_family_id_for_learner(acc_no)

    def get_learner_details_for_statement(self, acc_no):
        """Fetches learner details required for generating a statement."""
        return self.learner_service.get_learner_details(acc_no)

    def get_monthly_fee_for_statement(self, acc_no):
        """Fetches the monthly fee for a learner, required for generating a statement."""
        return self.payment_repository.get_monthly_fee_for_statement(acc_no)

    def get_payment_history_for_statement(self, acc_no):
        """Fetches the payment history for a learner, required for generating a statement."""
        return self.payment_repository.get_payment_history_for_learner(acc_no)

    def setup_menu_bar(self):
        """Sets up the application menu bar using the MenuBar component."""
        self.menu_bar = MenuBar(self)

    def show_payment_statistics(self):
        """Shows the payment statistics dialog."""
        self.dialog_service.show_payment_statistics_dialog()

    def switch_user(self):
        """Handles the user switching process."""
        self.current_user_id = None
        self.current_username = None
        self.current_user_role = None
        self.all_learners_data = []
        self.learner_table.setRowCount(0)
        self.search_bar.search_entry.clear()
        if self.login():
            self.load_learners()

    def load_caches(self):
        """Loads payment options, payment terms, and families from the database."""
        payment_options_data, payment_terms_data, families_data = self.learner_service.get_initial_data()
        self.payment_options_cache = payment_options_data
        self.payment_terms_cache = payment_terms_data
        self.family_data_cache = families_data

    def load_learners(self):
        """Loads learner data from DB into memory cache."""
        self.load_caches()
        self.all_learners_data = self.learner_repository.get_all_learners()
        self.filter_displayed_learners()
        self.update_status_bar_learner_count(len(self.all_learners_data))

    def filter_displayed_learners(self):
        """Filters cached learner data based on status filter, grade, and search term, then groups by grade and sorts alphabetically within each grade."""
        search_term = self.search_bar.search_entry.text().lower().strip()
        status_filter = self.search_bar.status_filter_combo.currentText()
        grade_filter_active = self.search_bar.grade_filter_checkbox.isChecked()
        grade_filter = self.search_bar.grade_filter_combo.currentText()

        grade_filtered_data = []
        if not grade_filter_active or grade_filter == "All":
            grade_filtered_data = self.all_learners_data
        else:
            try:
                grade_value = int(grade_filter)
                grade_filtered_data = [s for s in self.all_learners_data if s[7] == grade_value]
            except ValueError:
                grade_filtered_data = self.all_learners_data

        status_filtered_data = []
        if status_filter == "All":
            status_filtered_data = grade_filtered_data
        elif status_filter == "Active":
            status_filtered_data = [s for s in grade_filtered_data if s[12] == 1 or s[12] is True]
        elif status_filter == "Paused":
            status_filtered_data = [s for s in grade_filtered_data if s[12] == 0 or s[12] is False]

        if not search_term:
            filtered = status_filtered_data
        else:
            filtered = [s for s in status_filtered_data if
                        search_term in (s[1] or "").lower() or
                        search_term in (s[2] or "").lower() or
                        search_term in (s[0].split('-')[0] or "").lower() or
                        search_term in (s[9] or "").lower()]

        # Group by grade, sort each group by surname then name, then flatten
        from collections import defaultdict
        grouped = defaultdict(list)
        for s in filtered:
            grouped[s[7]].append(s)  # s[7] is grade
        sorted_learners = []
        for grade in sorted(grouped.keys()):
            learners_in_grade = grouped[grade]
            learners_in_grade.sort(key=lambda s: ((s[2] or "").lower(), (s[1] or "").lower()))  # s[2]=surname, s[1]=name
            sorted_learners.extend(learners_in_grade)

        self.display_learners_in_table(sorted_learners)
        self.learner_table.clearSelection()
        self.learner_table.setCurrentItem(None)
        self.selection_service.clear_selection()
        self.set_button_states_after_selection()
        self.update_status_bar_learner_count(len(sorted_learners))

    def display_learners_in_table(self, learners):
        """Displays learner data in the table."""
        self.learner_table.setRowCount(len(learners))
        for row, learner_tuple in enumerate(learners):
            # Create table items for each column
            for col, value in enumerate(learner_tuple[:9]):  # Only show first 9 columns
                if col == 0:  # acc_no column
                    item = QTableWidgetItem(str(value))
                    item.setData(Qt.ItemDataRole.UserRole, value)
                    self.learner_table.setItem(row, col, item)
                else:
                    self.learner_table.setItem(row, col, QTableWidgetItem(str(value or "")))

    def _on_table_double_click(self, row, column):
        """Handles double-click on table row."""
        item = self.learner_table.item(row, 0)
        if item:
            acc_no = item.text()
            self.dialog_service.show_view_details_dialog(acc_no)

    def show_add_learner_dialog(self):
        """Shows the add learner dialog."""
        self.dialog_service.show_add_learner_dialog(self.current_user_id)

    def open_update_selected_learner_dialog(self):
        """Open the update dialog for the learner selected in the table."""
        acc_no = self._resolve_selected_acc_no()
        if not acc_no:
            QMessageBox.warning(self, "No Selection", "Please select a learner first.")
            return
        self.dialog_service.show_update_learner_dialog(self.current_user_id, acc_no)

    def show_record_payment(self):
        """Shows the record payment dialog."""
        self.dialog_service.show_record_payment_dialog(self.current_user_id)

    def show_families_dialog(self):
        """Shows the families management dialog."""
        self.dialog_service.show_families_dialog(self.current_user_id)

    def show_payment_options_dialog(self):
        """Shows the payment options dialog."""
        self.dialog_service.show_payment_options_dialog()

    def show_payment_terms_dialog(self):
        """Shows the payment terms dialog."""
        self.dialog_service.show_payment_terms_dialog()

    def show_system_settings_dialog(self):
        """Shows the system settings dialog."""
        dialog = SystemSettingsDialog(self.db_manager, self)
        dialog.exec()

    def show_class_list_dialog(self):
        """Shows the class list dialog."""
        dialog = ClassListDialog(self, self.db_manager)
        dialog.exec()

    # Payment-related methods
    def open_record_payment_dialog(self):
        """Opens the record payment dialog."""
        acc_no = self._resolve_selected_acc_no()
        if acc_no:
            self.dialog_service.show_record_payment_dialog(self.current_user_id, acc_no)
        else:
            QMessageBox.warning(self, "No Selection", "Please select a learner first.")

    def open_payment_dialog(self):
        """Opens the payment dialog (legacy method for compatibility)."""
        self.open_record_payment_dialog()

    def pause_selected_learner_billing(self):
        """Handles pausing billing for the selected learner."""
        acc_no = self._resolve_selected_acc_no()
        if not acc_no:
            self.show_styled_message("Select Learner", "Please select a learner to pause billing for.")
            return

        learner_name = f"{self.selection_service.get_selected_learner_name()} {self.selection_service.get_selected_learner_surname()}"

        # Show dialog to get reason for pausing
        dialog_result, reason = self.dialog_service.show_pause_billing_dialog(acc_no, learner_name)

        if dialog_result == QDialog.DialogCode.Accepted:
            success, message = self.learner_service.pause_billing(acc_no, reason, self.current_user_id)
            if success:
                self.show_styled_message("Success", f"Billing paused for {learner_name}.")
                self.load_learners()
            else:
                self.show_styled_message("Error", f"Failed to pause billing: {message}", QMessageBox.Icon.Critical)
        else:
            self.show_styled_message("Cancelled", "Pausing billing cancelled.")

    def resume_selected_learner_billing(self):
        """Handles resuming billing for the selected learner."""
        acc_no = self._resolve_selected_acc_no()
        if not acc_no:
            self.show_styled_message("Select Learner", "Please select a learner to resume billing for.")
            return

        learner_name = f"{self.selection_service.get_selected_learner_name()} {self.selection_service.get_selected_learner_surname()}"

        success, message = self.learner_service.resume_billing(acc_no, self.current_user_id)
        if success:
            self.show_styled_message("Success", f"Billing resumed for {learner_name}.")
            self.load_learners()
        else:
            self.show_styled_message("Error", f"Failed to resume billing: {message}", QMessageBox.Icon.Critical)

    # Management dialogs
    def open_payment_options_dialog(self):
        """Opens the payment options management dialog."""
        self.dialog_service.show_payment_options_dialog()

    def open_payment_terms_dialog(self):
        """Opens the payment terms management dialog."""
        self.dialog_service.show_payment_terms_dialog()

    def open_families_dialog(self):
        """Opens the families management dialog."""
        self.dialog_service.show_families_dialog(self.current_user_id)

    # Admin methods
    def open_add_user_dialog(self):
        """Opens the add user dialog."""
        self.dialog_service.show_add_user_dialog(self.current_user_id)

    def open_delete_user_dialog(self):
        """Opens the delete/manage users dialog."""
        self.dialog_service.show_delete_user_dialog(self.current_user_id)

    def open_audit_log_dialog(self):
        """Opens the audit log dialog."""
        self.dialog_service.show_audit_log_dialog()

    # Settings dialogs
    def open_system_settings_dialog(self):
        """Opens the system settings dialog."""
        self.show_system_settings_dialog()

    def open_statement_settings_dialog(self):
        """Opens the statement settings dialog."""
        self.dialog_service.show_statement_settings_dialog()

    def open_email_settings_dialog(self):
        """Opens the email settings dialog."""
        self.dialog_service.show_email_settings_dialog()

    # Reports
    def open_learner_class_list_dialog(self):
        """Opens the learner class list dialog."""
        self.show_class_list_dialog()

    def open_learner_attendance_dialog(self):
        """Open the learner attendance dialog using the integrated attendance system."""
        try:
            from presentation.dialogs.attendance_dialog import show_attendance_dialog
            from business.services.email_service import EmailService

            try:
                email_service = EmailService()
            except Exception:
                email_service = None

            dialog = show_attendance_dialog(
                db_manager=self.db_manager,
                parent=self,
                email_service=email_service,
                event_bus=None
            )

            dialog.exec()
            self.load_learners()

        except ImportError as e:
            self.logger.exception(f"Integrated attendance dialog import failed: {e}")
            QMessageBox.critical(
                self,
                "Attendance Unavailable",
                "Integrated attendance components are missing. Legacy attendance fallback has been retired."
            )
        except Exception as e:
            self.logger.exception(f"Failed to open attendance dialog: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to open attendance dialog: {str(e)}")
    
    def _on_attendance_payment_fed(self, payment_data: dict):
        """
        Handle payment data fed from the attendance system.
        
        This method is called when the attendance system detects and feeds
        payment information to the payment system.
        
        Args:
            payment_data: Dictionary containing payment feed information
        """
        try:
            # Refresh the learner data to reflect any new payments
            self.load_learners()
            
            # Show notification to user
            payments_fed = payment_data.get('payments_fed', 0)
            if payments_fed > 0:
                self.statusBar().showMessage(
                    f"Attendance system fed {payments_fed} payment(s) to the payment system",
                    5000
                )
        except Exception as e:
            self.logger.error(f"Error handling attendance payment feed: {e}")

    # Print and export methods
    def print_all_statements(self):
        """Prints all learner statements."""
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            print_dialog = QPrintDialog(printer, self)
            if print_dialog.exec() == QDialog.DialogCode.Accepted:
                pdf_documents = []
                for learner_tuple in self.all_learners_data:
                    acc_no = learner_tuple[0]
                    html = self._get_learner_statement_html(acc_no)
                    if html and "Error" not in html:
                        pdf_documents.append(build_statement_pdf_bytes(html))

                if not pdf_documents:
                    QMessageBox.warning(self, "Print Statements", "No statements were available to print.")
                    return

                render_statement_pdf_documents_to_printer(pdf_documents, printer)
                QMessageBox.information(self, "Success", "Statements printed successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Print Error", f"Failed to print statements: {str(e)}")

    def save_all_to_pdf(self):
        """Saves all learner statements to PDF files."""
        try:
            from PySide6.QtCore import QStandardPaths
            documents_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
            count = 0
            for learner_tuple in self.all_learners_data:
                acc_no = learner_tuple[0]
                try:
                    pdf_path = os.path.join(documents_dir, f"Statement_{acc_no}.pdf")
                    html = self._get_learner_statement_html(acc_no)
                    if not html or "Error" in html:
                        continue
                    save_statement_pdf_bytes(build_statement_pdf_bytes(html), pdf_path)
                    count += 1
                except Exception as e:
                    self.logger.error(f"Error saving PDF for {acc_no}: {str(e)}")
            QMessageBox.information(self, "Success", f"{count} statements saved to PDF in Documents folder.")
        except Exception as e:
            QMessageBox.critical(self, "PDF Export Error", f"Failed to save statements: {str(e)}")

    def _get_learner_statement_html(self, acc_no):
        """Generates HTML for a learner statement."""
        try:
            statement_settings = SettingsManager().load_statement_settings()
            family_id = self.get_family_id_for_learner(acc_no)
            
            if family_id:
                html = generate_family_statement_html(self, family_id, statement_settings)
            else:
                html = generate_learner_statement_html(self, acc_no, statement_settings)
            return html
        except Exception as e:
            self.logger.error(f"Error generating statement for {acc_no}: {str(e)}")
            return f"<p>Error generating statement for {acc_no}</p>"

    def delete_learner(self):
        """Deletes the selected learner."""
        acc_no = self._resolve_selected_acc_no()
        if not acc_no:
            QMessageBox.warning(self, "No Selection", "Please select a learner to delete.")
            return
        
        # Confirm deletion
        reply = QMessageBox.question(self, "Confirm Delete", 
                                    f"Are you sure you want to delete learner {acc_no}?\nThis action cannot be undone.",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.learner_repository.delete_learner(acc_no)
                self.load_learners()
                QMessageBox.information(self, "Success", f"Learner {acc_no} deleted successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete learner: {str(e)}")

    def trigger_manual_sync(self):
        """Manually triggers data synchronization."""
        if not self.sync_scheduler:
            QMessageBox.information(
                self,
                "Sync Disabled",
                "Synchronization is currently disabled. This happens when the application is running in local-only mode (no remote database configured)."
            )
            return

        if not self.sync_scheduler.enabled:
            QMessageBox.information(
                self,
                "Sync Disabled",
                "V2 Synchronization is disabled in environment settings."
            )
            return

        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm Sync",
            "Triggering a manual sync will upload local changes and download remote updates immediately.\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.sync_scheduler.force_run()
            self.statusBar().showMessage("Manual sync initiated...", 5000)
