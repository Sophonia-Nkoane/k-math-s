import logging
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QMessageBox, QTableWidgetItem,
                          QHeaderView, QHBoxLayout, QFileDialog, QDialog)
from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtGui import QColor
import re
from datetime import date
from data.data_access import DataAccess
from presentation.dialogs.statement import generate_learner_statement_html, generate_family_statement_html
from presentation.dialogs.statement_pdf_preview_dialog import StatementPdfPreviewDialog
from presentation.statement_pdf import (
    build_statement_pdf_bytes,
    render_statement_pdf_bytes_to_printer,
    save_statement_pdf_bytes,
)
from presentation.styles.colors import TEXT_COLOR
from presentation.styles.styles import SECTION_TITLE_STYLE, TOTAL_AMOUNT_STYLE
from utils.settings_manager import SettingsManager
from presentation.components.buttons import ButtonFactory
from presentation.components.window_component import WindowComponent
from presentation.components.table import Table
from presentation.components.success_dialog import SuccessDialog  # Add this import

class PaymentViewDialog(WindowComponent):
    """Dialog for viewing summary, full statement preview, and printing statements for individuals or families."""

    def __init__(self, db_manager, learner_acc_no, family_id=None, parent=None):
        title = f"{('Family' if family_id else 'Individual')} Payment View & Statement"
        super().__init__(parent=parent, title=title)
        
        self.setFixedSize(850, 650)
        self.db_manager = db_manager
        self.data_access = DataAccess(db_manager)
        self.learner_acc_no = learner_acc_no 
        self.family_id = family_id
        self.main_window = parent
        self.dialog_service = getattr(parent, 'dialog_service', None)
        self.statement_html = None
        self.statement_pdf_bytes = None
        self.statement_type = "Family" if self.family_id else "Individual"
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize UI
        self.init_ui()

    def init_ui(self):
        # Create main layout
        main_content = QVBoxLayout()
        button_layout = QHBoxLayout()

        # Initialize Table component
        table_columns = [
            {"name": "Date", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Description", "width": None, "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "Amount (R)", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents}
        ]
        
        self.combined_table = Table(self, table_columns).get_table()
        self.combined_table.setMaximumHeight(100)
        self.combined_table.setAlternatingRowColors(True)

        # Total Due Label with theme-aware text color
        self.total_amount_label = QLabel("Full Statement Total Due: Calculating...")
        self.total_amount_label.setStyleSheet(f"{TOTAL_AMOUNT_STYLE}; color: {TEXT_COLOR()};")
        self.total_amount_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Buttons
        self.preview_statement_button = ButtonFactory.create_view_button("Preview Statement")
        self.print_statement_button = ButtonFactory.create_print_button("Print Statement")
        self.save_pdf_button = ButtonFactory.create_save_button("Save to PDF")

        self.preview_statement_button.clicked.connect(self.show_full_statement_preview)
        self.print_statement_button.clicked.connect(self.print_statement)
        self.save_pdf_button.clicked.connect(self.save_to_pdf)

        button_layout.addStretch()
        button_layout.addWidget(self.preview_statement_button)
        button_layout.addWidget(self.print_statement_button)
        button_layout.addWidget(self.save_pdf_button)

        # Title with theme-aware text color
        title_text = f"Summary & Statement for {'Family ID: ' + str(self.family_id) if self.family_id else 'Acc: ' + self.learner_acc_no.split('-')[0]}"
        title_label = QLabel(title_text)
        title_label.setStyleSheet(f"{SECTION_TITLE_STYLE}; color: {TEXT_COLOR()};")

        # Add widgets to layout
        main_content.addWidget(title_label)
        main_content.addSpacing(10)
        main_content.addWidget(self.combined_table)
        main_content.addWidget(self.total_amount_label)
        main_content.addSpacing(15)
        main_content.addLayout(button_layout)

        # Add the main content layout to the window component's content area
        self.add_layout(main_content)
        
        self.populate_combined_view()

    def show_styled_message(self, title, text, icon_type=QMessageBox.Icon.Information):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon_type)
        ok_button = ButtonFactory.create_ok_button("OK")
        msg.addButton(ok_button, QMessageBox.ButtonRole.AcceptRole)
        msg.exec()

    def populate_combined_view(self):
        """Populates the summary table and generates the full statement HTML."""
        if not self.learner_acc_no and not self.family_id:
            self.total_amount_label.setText("Total Amount Due: N/A")
            return

        # Fetch data for the modified summary view
        summary_data_for_table = []
        current_balance = None # Initialize current_balance
        try:
            last_payment = self.data_access.fetch_last_payment(self.learner_acc_no, self.family_id)
            if last_payment:
                summary_data_for_table.append(last_payment)

            # Fetch current balance *once*
            current_balance = self.data_access.fetch_current_balance(self.learner_acc_no, self.family_id)

            summary_data_for_table.append(self._build_balance_row(current_balance))

            self.display_combined_data_in_table(summary_data_for_table)

        except AttributeError as ae:
            if 'fetch_last_payment' in str(ae) or 'fetch_current_balance' in str(ae):
                self.show_styled_message("Development Notice", 
                    f"Required data method not yet implemented: {ae}",
                    QMessageBox.Icon.Warning)
                self.combined_table.setRowCount(0)
            else:
                self.show_styled_message("Error", 
                    f"An unexpected attribute error occurred: {ae}",
                    QMessageBox.Icon.Warning)
        except Exception as e:
            self.show_styled_message("Error Fetching Summary", str(e), QMessageBox.Icon.Warning)
            self.combined_table.setRowCount(0)

        total_due_str = "Error"; self.statement_html = None; self.statement_pdf_bytes = None
        self.logger.debug(f"Generating {self.statement_type} statement")
        try:
            if self.main_window:
                # SettingsManager is a singleton and doesn't need parameters
                settings_manager = SettingsManager()
                statement_settings = settings_manager.load_statement_settings()

                if self.family_id:
                    self.statement_html = generate_family_statement_html(self.main_window, self.family_id, statement_settings)
                    self.logger.debug(f"Family HTML generated (length: {len(self.statement_html) if self.statement_html else 0})")
                else:
                    self.statement_html = generate_learner_statement_html(self.main_window, self.learner_acc_no, statement_settings)
                    self.logger.debug(f"Individual HTML generated (length: {len(self.statement_html) if self.statement_html else 0})")

                if self.statement_html:
                    total_due_str = self._extract_total_due_label(self.statement_html)
                else:
                    total_due_str = "Error (No HTML)"
                    self.logger.warning("No HTML was generated")
            else:
                total_due_str = "Error (No Window)"
                self.logger.warning("Main window not available")
        except Exception as e:
            total_due_str = "Error (Generation)"
            self.logger.exception(f"Error generating {self.statement_type} statement: {e}")

        self.total_amount_label.setText(total_due_str)

    def display_combined_data_in_table(self, data):
        """Displays the specific summary data (last payment, adjusted upcoming) in the table."""
        self.combined_table.setRowCount(0)
        self.combined_table.setRowCount(len(data))

        # Create QColor object once
        text_color = QColor(TEXT_COLOR())

        for r, row_data in enumerate(data):
            if len(row_data) == 3:
                date_str, desc_str, amount_str = row_data
                
                # Create items with theme-aware text color
                date_item = QTableWidgetItem(str(date_str))
                desc_item = QTableWidgetItem(str(desc_str))
                amount_item = QTableWidgetItem(str(amount_str))
                
                # Use QColor object for setForeground
                date_item.setForeground(text_color)
                desc_item.setForeground(text_color)
                amount_item.setForeground(text_color)
                
                amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                self.combined_table.setItem(r, 0, date_item)
                self.combined_table.setItem(r, 1, desc_item)
                self.combined_table.setItem(r, 2, amount_item)
            else:
                error_item = QTableWidgetItem("Error")
                invalid_item = QTableWidgetItem("Invalid data format")
                empty_item = QTableWidgetItem("")
                
                # Use same QColor object for error items
                error_item.setForeground(text_color)
                invalid_item.setForeground(text_color)
                empty_item.setForeground(text_color)
                
                self.combined_table.setItem(r, 0, error_item)
                self.combined_table.setItem(r, 1, invalid_item)
                self.combined_table.setItem(r, 2, empty_item)

    def show_full_statement_preview(self):
        """Shows the generated statement in a high-clarity PDF preview dialog."""
        if not self.statement_html:
            self.show_styled_message("Statement Not Available", 
                "Statement HTML could not be generated or is empty.",
                QMessageBox.Icon.Warning)
            return
        try:
            preview = StatementPdfPreviewDialog(
                self._get_statement_pdf_bytes(),
                parent=self,
                title=f"{self.statement_type} Statement Preview",
            )
            preview.exec()
        except Exception as e:
            self.show_styled_message("Preview Error", 
                f"Could not show statement preview:\n{e}",
                QMessageBox.Icon.Critical)
            self.logger.exception(f"Preview error details: {e}")

    def print_statement(self):
        """Prints the generated shared-PDF statement."""
        if not self.statement_html:
            self.show_styled_message("Error", "Statement HTML not generated.", QMessageBox.Icon.Critical)
            return

        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dialog = QPrintDialog(printer, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                render_statement_pdf_bytes_to_printer(self._get_statement_pdf_bytes(), printer)
                SuccessDialog(f"{self.statement_type} statement sent to printer.", self).exec()
        except Exception as e:
            self.show_styled_message("Error", f"Failed to print statement:\n{str(e)}", QMessageBox.Icon.Critical)

    def save_to_pdf(self):
        """Saves the generated shared-PDF statement to a PDF file."""
        if not self.statement_html:
            self.show_styled_message("Error", "Statement HTML not generated.", QMessageBox.Icon.Critical)
            return

        default_filename = self.generate_default_filename()
        default_filename = re.sub(r'[\/*?:\"<>|]', '_', default_filename)
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            f"Save {self.statement_type} Statement as PDF", 
            default_filename, 
            "PDF Files (*.pdf)"
        )
        
        if not file_path:
            return  # User cancelled
            
        try:
            save_statement_pdf_bytes(self._get_statement_pdf_bytes(), file_path)
            SuccessDialog(f"{self.statement_type} statement saved successfully to:\n{file_path}", self).exec()

        except Exception as e:
            self.show_styled_message("Error", f"Failed to save PDF:\n{str(e)}", QMessageBox.Icon.Critical)

    def generate_default_filename(self):
        """Generates a default filename for the PDF based on statement type and date."""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self.family_id:
            return f"Family_Statement_ID{self.family_id}_{timestamp}.pdf"
        else:
            # Get learner name from the main window's learner data if available
            learner_name = "Learner"
            if self.main_window and hasattr(self.main_window, 'all_learners_data') and self.learner_acc_no:
                try:
                    # Find learner details in the cached data
                    learner_details = next((s for s in self.main_window.all_learners_data if s[0] == self.learner_acc_no), None)
                    if learner_details:
                        name = learner_details[1] or 'Learner'
                        surname = learner_details[2] or ''
                        grade = learner_details[7] or ''
                        learner_name = f"{name}_{surname}_Grade{grade}".replace(' ', '_')
                except Exception as e:
                    self.logger.warning(f"Could not get learner details for filename: {e}")
            
            acc_prefix = self.learner_acc_no.split('-')[0] if self.learner_acc_no and '-' in self.learner_acc_no else self.learner_acc_no
            return f"Individual_Statement_{learner_name}_{acc_prefix}_{timestamp}.pdf"

    def _get_statement_pdf_bytes(self):
        if not self.statement_html:
            raise RuntimeError("Statement HTML not generated.")
        if self.statement_pdf_bytes is None:
            self.statement_pdf_bytes = build_statement_pdf_bytes(self.statement_html)
        return self.statement_pdf_bytes

    def _build_balance_row(self, current_balance):
        """Build a summary table row for current balance."""
        balance_date_str = date.today().strftime("%Y-%m-%d")
        if current_balance is None:
            return (balance_date_str, "Balance Unavailable", "Error")
        if current_balance < 0:
            return (balance_date_str, "Current Credit Balance", f"R {abs(current_balance):,.2f}")
        if current_balance > 0:
            return (balance_date_str, "Current Amount Due", f"R {current_balance:,.2f}")
        return (balance_date_str, "Current Balance", "R 0.00")

    def _extract_total_due_label(self, statement_html):
        """Extract and format total due/credit label from statement HTML."""
        patterns = [
            r'<div[^>]*class="[^"]*status-value[^"]*"[^>]*>\s*R\s*(-?[\d,]+\.\d{2})\s*</div>',
            r'<td[^>]*class="amount"[^>]*>\s*R\s*(-?[\d,]+\.\d{2})\s*</td>',
            r':\s*R\s*<span[^>]*>\s*(-?[\d,]+\.\d{2})\s*</span>',
        ]
        match = None
        for pattern in patterns:
            match = re.search(pattern, statement_html, re.IGNORECASE)
            if match:
                break

        if not match:
            self.logger.warning("No total found in HTML using regex patterns")
            return "Error (Parsing Total)"

        total_due_val_str = match.group(1)
        self.logger.debug(f"Found total amount string: '{total_due_val_str}'")
        try:
            total_due_val = float(total_due_val_str.replace(',', ''))
        except ValueError:
            self.logger.warning(f"Could not parse float from '{total_due_val_str}'")
            return "Error (Parsing Value)"

        if total_due_val > 0:
            return f"Total Amount Due: R {total_due_val:,.2f}"
        if total_due_val < 0:
            return f"Credit Balance: R {abs(total_due_val):,.2f}"
        return "Account Up-to-Date: R 0.00"
