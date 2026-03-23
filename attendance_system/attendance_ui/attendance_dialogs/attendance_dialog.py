"""
Attendance Dialog

Main dialog for the decoupled attendance system UI.
"""

import sys
import os
from datetime import date, datetime

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QComboBox, QLabel, QPushButton, QMessageBox, QFileDialog,
    QHeaderView, QDateEdit, QCheckBox, QGroupBox, QProgressBar
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QColor

# Import attendance system components
from attendance_main import AttendanceSystem, create_attendance_system
from attendance_models.attendance_models import AttendanceStatus


class AttendanceDialog(QDialog):
    """
    Main dialog for attendance management.
    
    This dialog provides:
    - Grade selection and learner loading
    - Attendance recording (present/absent/late/excused)
    - OCR document processing
    - Payment data integration
    """
    
    # Signal emitted when payment data is fed to payment system
    payment_data_fed = Signal(dict)
    
    def __init__(
        self, 
        payment_db_manager=None,
        notification_service=None,
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Learner Attendance System")
        self.setMinimumSize(900, 600)
        
        # Initialize attendance system
        self.attendance_system = create_attendance_system(
            payment_db_manager=payment_db_manager,
            notification_service=notification_service
        )
        self.payment_db_manager = payment_db_manager
        
        # Store current state
        self.current_grade = None
        self.current_date = date.today()
        self.uploaded_file_path = None
        
        # Setup UI
        self._setup_ui()
        self._load_grades()
    
    def _setup_ui(self):
        """Setup the dialog UI components."""
        layout = QVBoxLayout(self)
        
        # === Top Controls ===
        controls_group = QGroupBox("Attendance Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        # Grade selection
        controls_layout.addWidget(QLabel("Grade:"))
        self.grade_combo = QComboBox()
        self.grade_combo.currentIndexChanged.connect(self._on_grade_changed)
        controls_layout.addWidget(self.grade_combo)
        
        # Date selection
        controls_layout.addWidget(QLabel("Date:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_date_changed)
        controls_layout.addWidget(self.date_edit)
        
        # Load learners button
        self.load_btn = QPushButton("Load Learners")
        self.load_btn.clicked.connect(self._load_learners)
        controls_layout.addWidget(self.load_btn)
        
        controls_layout.addStretch()
        layout.addWidget(controls_group)
        
        # === Attendance Table ===
        table_group = QGroupBox("Attendance Register")
        table_layout = QVBoxLayout(table_group)
        
        self.attendance_table = QTableWidget()
        self.attendance_table.setColumnCount(6)
        self.attendance_table.setHorizontalHeaderLabels([
            "Acc No", "Name", "Surname", "Status", "Notes", "Present"
        ])
        self.attendance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.attendance_table.setAlternatingRowColors(True)
        table_layout.addWidget(self.attendance_table)
        
        layout.addWidget(table_group)
        
        # === OCR Processing ===
        ocr_group = QGroupBox("OCR Document Processing")
        ocr_layout = QHBoxLayout(ocr_group)
        
        self.upload_btn = QPushButton("Upload Document")
        self.upload_btn.clicked.connect(self._upload_document)
        ocr_layout.addWidget(self.upload_btn)
        
        self.file_label = QLabel("No file selected")
        ocr_layout.addWidget(self.file_label)
        
        self.process_btn = QPushButton("Process Document")
        self.process_btn.clicked.connect(self._process_document)
        self.process_btn.setEnabled(False)
        ocr_layout.addWidget(self.process_btn)
        
        self.extract_payments_cb = QCheckBox("Extract Payments")
        self.extract_payments_cb.setChecked(True)
        ocr_layout.addWidget(self.extract_payments_cb)
        
        ocr_layout.addStretch()
        layout.addWidget(ocr_group)
        
        # === Progress Bar ===
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # === Bottom Buttons ===
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("Save Attendance")
        self.save_btn.clicked.connect(self._save_attendance)
        button_layout.addWidget(self.save_btn)
        
        self.report_btn = QPushButton("View Report")
        self.report_btn.clicked.connect(self._show_report)
        button_layout.addWidget(self.report_btn)
        
        self.sync_btn = QPushButton("Sync with Payment System")
        self.sync_btn.clicked.connect(self._sync_with_payment_system)
        button_layout.addWidget(self.sync_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _load_grades(self):
        """Load grades from the payment system database."""
        self.grade_combo.clear()
        
        if not self.payment_db_manager:
            # Add default grades if no payment DB
            for i in range(1, 13):
                self.grade_combo.addItem(str(i))
            return
        
        try:
            query = "SELECT DISTINCT grade FROM Learners WHERE is_active = 1 ORDER BY grade"
            grades = self.payment_db_manager.execute_query(query, fetchall=True)
            
            if grades:
                for grade in grades:
                    self.grade_combo.addItem(str(grade[0]))
            else:
                # Add default grades
                for i in range(1, 13):
                    self.grade_combo.addItem(str(i))
                    
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load grades: {e}")
            for i in range(1, 13):
                self.grade_combo.addItem(str(i))
    
    def _on_grade_changed(self, index):
        """Handle grade selection change."""
        grade_text = self.grade_combo.currentText()
        if grade_text:
            self.current_grade = int(grade_text)
    
    def _on_date_changed(self, qdate):
        """Handle date selection change."""
        self.current_date = qdate.toPython()
    
    def _load_learners(self):
        """Load learners for the selected grade."""
        if not self.current_grade:
            QMessageBox.warning(self, "Warning", "Please select a grade first.")
            return
        
        if not self.payment_db_manager:
            QMessageBox.warning(self, "Warning", "Payment database not connected.")
            return
        
        try:
            query = """
                SELECT acc_no, name, surname 
                FROM Learners 
                WHERE grade = ? AND is_active = 1 
                ORDER BY surname, name
            """
            learners = self.payment_db_manager.execute_query(
                query, (self.current_grade,), fetchall=True
            )
            
            if not learners:
                QMessageBox.information(self, "Info", "No learners found for this grade.")
                return
            
            self.attendance_table.setRowCount(len(learners))
            
            for row, learner in enumerate(learners):
                acc_no, name, surname = learner
                
                # Account number
                acc_item = QTableWidgetItem(acc_no)
                acc_item.setFlags(acc_item.flags() & ~Qt.ItemIsEditable)
                self.attendance_table.setItem(row, 0, acc_item)
                
                # Name
                name_item = QTableWidgetItem(name)
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                self.attendance_table.setItem(row, 1, name_item)
                
                # Surname
                surname_item = QTableWidgetItem(surname)
                surname_item.setFlags(surname_item.flags() & ~Qt.ItemIsEditable)
                self.attendance_table.setItem(row, 2, surname_item)
                
                # Status dropdown
                status_combo = QComboBox()
                status_combo.addItems(["present", "absent", "late", "excused"])
                self.attendance_table.setCellWidget(row, 3, status_combo)
                
                # Notes
                notes_item = QTableWidgetItem("")
                self.attendance_table.setItem(row, 4, notes_item)
                
                # Present checkbox
                present_item = QTableWidgetItem()
                present_item.setCheckState(Qt.Checked)
                self.attendance_table.setItem(row, 5, present_item)
            
            # Check for existing attendance records
            self._load_existing_attendance()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load learners: {e}")
    
    def _load_existing_attendance(self):
        """Load existing attendance records for the selected date and grade."""
        records = self.attendance_system.get_attendance_for_date(
            self.current_date, self.current_grade
        )
        
        if not records:
            return
        
        # Create a lookup by acc_no
        record_map = {r.learner_acc_no: r for r in records}
        
        for row in range(self.attendance_table.rowCount()):
            acc_no = self.attendance_table.item(row, 0).text()
            
            if acc_no in record_map:
                record = record_map[acc_no]
                
                # Update status combo
                status_combo = self.attendance_table.cellWidget(row, 3)
                if status_combo:
                    index = status_combo.findText(record.status.value)
                    if index >= 0:
                        status_combo.setCurrentIndex(index)
                
                # Update notes
                if record.notes:
                    self.attendance_table.item(row, 4).setText(record.notes)
                
                # Update checkbox
                present_state = Qt.Checked if record.status == AttendanceStatus.PRESENT else Qt.Unchecked
                self.attendance_table.item(row, 5).setCheckState(present_state)
    
    def _upload_document(self):
        """Upload a document for OCR processing."""
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("Documents (*.pdf *.png *.jpg *.jpeg)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.uploaded_file_path = selected_files[0]
                self.file_label.setText(os.path.basename(self.uploaded_file_path))
                self.process_btn.setEnabled(True)
    
    def _process_document(self):
        """Process the uploaded document using OCR."""
        if not self.uploaded_file_path:
            QMessageBox.warning(self, "Warning", "Please upload a document first.")
            return
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.setEnabled(False)
        
        try:
            # Refresh learner list from payment DB
            self.attendance_system.refresh_learner_list_from_payment_db()
            
            self.progress_bar.setValue(30)
            
            # Process the document
            extract_payments = self.extract_payments_cb.isChecked()
            result = self.attendance_system.process_attendance_document(
                self.uploaded_file_path,
                extract_payments=extract_payments,
                auto_record=True
            )
            
            self.progress_bar.setValue(80)
            
            # Show results
            if result['success']:
                message = f"Document processed successfully!\n\n"
                message += f"Attendance records: {result['attendance_recorded']}\n"
                message += f"Payments detected: {result['payments_detected']}\n"
                message += f"Payments fed to system: {result['payments_fed']}"
                
                if result['errors']:
                    message += f"\n\nErrors:\n" + "\n".join(result['errors'])
                
                QMessageBox.information(self, "Success", message)
                
                # Emit signal for payment data
                if result['payments_fed'] > 0:
                    self.payment_data_fed.emit(result)
                
                # Reload the table
                self._load_learners()
            else:
                QMessageBox.warning(
                    self, "Processing Failed",
                    f"Failed to process document:\n" + "\n".join(result['errors'])
                )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error processing document: {e}")
        
        finally:
            self.progress_bar.setValue(100)
            self.progress_bar.setVisible(False)
            self.setEnabled(True)
    
    def _save_attendance(self):
        """Save the attendance records."""
        records = []
        
        for row in range(self.attendance_table.rowCount()):
            acc_no = self.attendance_table.item(row, 0).text()
            name = self.attendance_table.item(row, 1).text()
            surname = self.attendance_table.item(row, 2).text()
            
            status_combo = self.attendance_table.cellWidget(row, 3)
            status = AttendanceStatus(status_combo.currentText())
            
            notes = self.attendance_table.item(row, 4).text()
            
            records.append({
                'learner_acc_no': acc_no,
                'learner_name': name,
                'learner_surname': surname,
                'grade': self.current_grade,
                'date': self.current_date,
                'status': status.value,
                'notes': notes if notes else None
            })
        
        if not records:
            QMessageBox.warning(self, "Warning", "No attendance records to save.")
            return
        
        try:
            success_count, failure_count = self.attendance_system.record_bulk_attendance(records)
            
            message = f"Attendance saved successfully!\n\n"
            message += f"Records saved: {success_count}\n"
            if failure_count > 0:
                message += f"Failed: {failure_count}"
            
            QMessageBox.information(self, "Save Complete", message)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save attendance: {e}")
    
    def _show_report(self):
        """Show attendance report for the current grade."""
        if not self.current_grade:
            QMessageBox.warning(self, "Warning", "Please select a grade first.")
            return
        
        # Get date range (current month)
        today = date.today()
        start_of_month = date(today.year, today.month, 1)
        
        report = self.attendance_system.get_grade_attendance_report(
            self.current_grade,
            start_of_month,
            today
        )
        
        # Show report dialog
        report_dialog = AttendanceReportDialog(report, self)
        report_dialog.exec()
    
    def _sync_with_payment_system(self):
        """Synchronize with the payment system."""
        result = self.attendance_system.sync_with_payment_system()
        
        message = "Synchronization Complete!\n\n"
        message += f"Learners refreshed: {result['learners_refreshed']}\n"
        
        if result['payment_feeds_processed']:
            feeds = result['payment_feeds_processed']
            message += f"Payment feeds processed: {feeds.get('processed', 0)}\n"
            message += f"Payment feeds failed: {feeds.get('failed', 0)}"
        
        QMessageBox.information(self, "Sync Complete", message)


class AttendanceReportDialog(QDialog):
    """Dialog for displaying attendance reports."""
    
    def __init__(self, report_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Attendance Report - Grade {report_data.get('grade', 'N/A')}")
        self.setMinimumSize(700, 500)
        
        self.report_data = report_data
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the report dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(f"<b>Grade:</b> {self.report_data.get('grade', 'N/A')}"))
        header_layout.addWidget(QLabel(f"<b>Period:</b> {self.report_data.get('period_start', '')} to {self.report_data.get('period_end', '')}"))
        header_layout.addWidget(QLabel(f"<b>Total Records:</b> {self.report_data.get('total_records', 0)}"))
        layout.addLayout(header_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Learner", "Total Days", "Present", "Absent", "Late", "Excused", "Rate %"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        learners = self.report_data.get('learners', [])
        self.table.setRowCount(len(learners))
        
        for row, learner in enumerate(learners):
            name = f"{learner.get('learner_name', '')} {learner.get('learner_surname', '')}"
            
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(str(learner.get('total_days', 0))))
            self.table.setItem(row, 2, QTableWidgetItem(str(learner.get('present_days', 0))))
            self.table.setItem(row, 3, QTableWidgetItem(str(learner.get('absent_days', 0))))
            self.table.setItem(row, 4, QTableWidgetItem(str(learner.get('late_days', 0))))
            self.table.setItem(row, 5, QTableWidgetItem(str(learner.get('excused_days', 0))))
            
            rate = learner.get('attendance_rate', 0)
            rate_item = QTableWidgetItem(f"{rate:.1f}%")
            
            # Color code based on attendance rate
            if rate >= 90:
                rate_item.setBackground(QColor(200, 255, 200))  # Green
            elif rate >= 75:
                rate_item.setBackground(QColor(255, 255, 200))  # Yellow
            else:
                rate_item.setBackground(QColor(255, 200, 200))  # Red
            
            self.table.setItem(row, 6, rate_item)
        
        layout.addWidget(self.table)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)


# Standalone function to launch the dialog
def show_attendance_dialog(payment_db_manager=None, notification_service=None, parent=None):
    """
    Show the attendance dialog.
    
    Args:
        payment_db_manager: Optional payment system database manager
        notification_service: Optional notification service
        parent: Optional parent widget
        
    Returns:
        The dialog instance
    """
    dialog = AttendanceDialog(
        payment_db_manager=payment_db_manager,
        notification_service=notification_service,
        parent=parent
    )
    return dialog


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Create standalone dialog (no payment DB connection)
    dialog = AttendanceDialog()
    dialog.show()
    
    sys.exit(app.exec())