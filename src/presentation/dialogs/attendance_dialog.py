"""
Attendance Management Dialog

A comprehensive dialog for managing learner attendance with full integration
to the payment system. Provides both individual and bulk attendance recording.
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QDateEdit, QSpinBox, QGroupBox,
    QTabWidget, QWidget, QHeaderView, QCheckBox,
    QMessageBox, QProgressBar, QFrame, QSplitter,
    QTextEdit, QButtonGroup, QRadioButton, QLineEdit,
    QAbstractItemView, QStyledItemDelegate
)
from PySide6.QtCore import Qt, QDate, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QIcon

from core.desktop_shared_services import get_desktop_shared_services
from data.repositories.attendance_repository import (
    AttendanceRepository, AttendanceRecord, AttendanceStatus, AttendanceSummary
)
from business.services.attendance_service import AttendanceService
from presentation.dialogs.attendance_ui_sections import (
    create_header,
    create_daily_attendance_tab,
    create_history_tab,
    create_summary_tab,
    create_reports_tab,
    create_button_box,
)
from presentation.dialogs.attendance_report_formatters import (
    format_daily_report,
    format_monthly_report,
    format_trends_report,
)
from presentation.styles.colors import (
    STATUS_BAR_BACKGROUND,
    STATUS_BAR_BORDER,
    STATUS_BAR_TEXT_COLOR,
)


class AttendanceStatusDelegate(QStyledItemDelegate):
    """Custom delegate for attendance status display with colors."""
    
    STATUS_COLORS = {
        'present': QColor(144, 238, 144),    # Light green
        'absent': QColor(255, 182, 193),     # Light red
        'late': QColor(255, 218, 185),       # Light orange
        'excused': QColor(173, 216, 230),    # Light blue
        'half_day': QColor(255, 255, 200),   # Light yellow
    }
    
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        
        # Get status from the model
        status = index.data(Qt.UserRole)
        if status and status in self.STATUS_COLORS:
            option.backgroundBrush = self.STATUS_COLORS[status]


class AttendanceDialog(QDialog):
    """
    Main attendance management dialog.
    
    Features:
    - Daily attendance recording by grade
    - Bulk attendance operations
    - Attendance history viewing
    - Summary and reporting
    - Payment integration
    """
    
    def __init__(
        self,
        attendance_service: AttendanceService,
        db_manager,
        shared_services=None,
        parent=None
    ):
        """
        Initialize the attendance dialog.
        
        Args:
            attendance_service: The attendance service instance
            db_manager: Database manager for direct queries
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.attendance_service = attendance_service
        self.db_manager = db_manager
        self.shared_services = shared_services
        self.shared_attendance = shared_services.attendance_facade if shared_services else None
        self.shared_learner_use_case = shared_services.learner_use_case if shared_services else None
        self.logger = logging.getLogger(__name__)
        
        # State
        self.current_date = date.today()
        self.current_grade = 1
        self.attendance_records = []
        self.modified_records = set()
        
        self._setup_ui()
        self._connect_signals()
        self._load_initial_data()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Attendance Management")
        self.setMinimumSize(900, 600)
        
        main_layout = QVBoxLayout(self)
        
        # Header
        header_layout = self._create_header()
        main_layout.addLayout(header_layout)
        
        # Tab widget for different views
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Daily Attendance Tab
        daily_tab = self._create_daily_attendance_tab()
        self.tab_widget.addTab(daily_tab, "Daily Attendance")
        
        # History Tab
        history_tab = self._create_history_tab()
        self.tab_widget.addTab(history_tab, "History")
        
        # Summary Tab
        summary_tab = self._create_summary_tab()
        self.tab_widget.addTab(summary_tab, "Summary")
        
        # Reports Tab
        reports_tab = self._create_reports_tab()
        self.tab_widget.addTab(reports_tab, "Reports")
        
        # Status bar
        self.status_bar = QLabel("Ready")
        self.status_bar.setStyleSheet(
            f"""
            padding: 5px;
            background-color: {STATUS_BAR_BACKGROUND()};
            border: 1px solid {STATUS_BAR_BORDER()};
            color: {STATUS_BAR_TEXT_COLOR()};
            border-radius: 4px;
            """
        )
        main_layout.addWidget(self.status_bar)
        
        # Button box
        button_layout = self._create_button_box()
        main_layout.addLayout(button_layout)
    
    def _create_header(self) -> QHBoxLayout:
        """Create the header section."""
        return create_header(self)
    
    def _create_daily_attendance_tab(self) -> QWidget:
        """Create the daily attendance tab."""
        return create_daily_attendance_tab(self, AttendanceStatusDelegate)
    
    def _create_history_tab(self) -> QWidget:
        """Create the attendance history tab."""
        return create_history_tab(self)
    
    def _create_summary_tab(self) -> QWidget:
        """Create the attendance summary tab."""
        return create_summary_tab(self)
    
    def _create_reports_tab(self) -> QWidget:
        """Create the reports tab."""
        return create_reports_tab(self)
    
    def _create_button_box(self) -> QHBoxLayout:
        """Create the bottom button box."""
        return create_button_box(self)
    
    def _connect_signals(self):
        """Connect UI signals to slots."""
        self.date_edit.dateChanged.connect(self._on_date_changed)
        self.grade_combo.currentTextChanged.connect(self._on_grade_changed)
        
        # Table cell changed
        self.attendance_table.cellChanged.connect(self._on_cell_changed)
    
    def _load_initial_data(self):
        """Load initial data when dialog opens."""
        self._load_learners_for_attendance()
    
    def _load_learners_for_attendance(self):
        """Load learners for the selected grade and date."""
        try:
            self.attendance_table.setRowCount(0)
            self.modified_records.clear()

            learners = []
            if self.shared_learner_use_case:
                learners = self.shared_learner_use_case.list_learners(
                    grade=self.current_grade,
                    is_active=True,
                )

            existing_attendance = {}
            records = self.shared_attendance.list_daily(self.current_date, grade=self.current_grade) if self.shared_attendance else []
            for record in records:
                acc_no = str(record.get("learner_acc_no") or "")
                if acc_no:
                    existing_attendance[acc_no] = record

            # Populate table
            self.attendance_table.setRowCount(len(learners) if learners else 0)
            
            present_count = 0
            absent_count = 0
            late_count = 0
            
            for row, learner in enumerate(learners or []):
                acc_no = str(learner.get("acc_no") or "")
                name = str(learner.get("name") or "")
                surname = str(learner.get("surname") or "")
                grade = int(learner.get("grade") or self.current_grade)

                existing = existing_attendance.get(acc_no)
                
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
                
                # Grade
                grade_item = QTableWidgetItem(str(grade))
                grade_item.setFlags(grade_item.flags() & ~Qt.ItemIsEditable)
                self.attendance_table.setItem(row, 3, grade_item)
                
                # Status
                status = str(existing.get("status") or "present") if existing else 'present'
                status_item = QTableWidgetItem(status.capitalize())
                status_item.setData(Qt.UserRole, status)
                
                # Create dropdown for status
                status_combo = QComboBox()
                status_combo.addItems(['Present', 'Absent', 'Late', 'Excused', 'Half Day'])
                status_combo.setCurrentText(status.capitalize())
                status_combo.currentTextChanged.connect(
                    lambda text, r=row: self._on_status_changed(r, text.lower())
                )
                self.attendance_table.setCellWidget(row, 4, status_combo)
                
                # Count
                if status == 'present':
                    present_count += 1
                elif status == 'absent':
                    absent_count += 1
                elif status == 'late':
                    late_count += 1
                
                # Notes
                notes = str(existing.get("notes") or "") if existing else ''
                notes_item = QTableWidgetItem(notes)
                self.attendance_table.setItem(row, 5, notes_item)
                
                # Actions
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(0, 0, 0, 0)
                
                view_btn = QPushButton("View")
                view_btn.clicked.connect(lambda checked, a=acc_no: self._view_learner_history(a))
                actions_layout.addWidget(view_btn)
                
                self.attendance_table.setCellWidget(row, 6, actions_widget)
            
            # Update statistics
            total = len(learners) if learners else 0
            self.stats_label.setText(
                f"Learners: {total} | Present: {present_count} | "
                f"Absent: {absent_count} | Late: {late_count}"
            )
            
            self.status_bar.setText(f"Loaded {total} learners for grade {self.current_grade}")
            
        except Exception as e:
            self.logger.error(f"Error loading learners: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load learners: {e}")
    
    def _on_date_changed(self, qdate: QDate):
        """Handle date change."""
        self.current_date = qdate.toPython()
        self._load_learners_for_attendance()
    
    def _on_grade_changed(self, grade_text: str):
        """Handle grade change."""
        self.current_grade = int(grade_text)
        self._load_learners_for_attendance()
    
    def _on_cell_changed(self, row: int, column: int):
        """Handle cell content change."""
        if column == 5:  # Notes column
            acc_no = self.attendance_table.item(row, 0).text()
            self.modified_records.add(acc_no)
    
    def _on_status_changed(self, row: int, status: str):
        """Handle status dropdown change."""
        acc_no = self.attendance_table.item(row, 0).text()
        self.modified_records.add(acc_no)
        
        # Update statistics
        self._update_statistics()
    
    def _update_statistics(self):
        """Update the statistics display."""
        present = 0
        absent = 0
        late = 0
        excused = 0
        
        for row in range(self.attendance_table.rowCount()):
            combo = self.attendance_table.cellWidget(row, 4)
            if combo:
                status = combo.currentText().lower()
                if status == 'present':
                    present += 1
                elif status == 'absent':
                    absent += 1
                elif status == 'late':
                    late += 1
                elif status == 'excused':
                    excused += 1
        
        total = self.attendance_table.rowCount()
        self.stats_label.setText(
            f"Learners: {total} | Present: {present} | "
            f"Absent: {absent} | Late: {late}"
        )
    
    def _mark_all_present(self):
        """Mark all learners as present."""
        for row in range(self.attendance_table.rowCount()):
            combo = self.attendance_table.cellWidget(row, 4)
            if combo:
                combo.setCurrentText('Present')
                acc_no = self.attendance_table.item(row, 0).text()
                self.modified_records.add(acc_no)
        
        self._update_statistics()
    
    def _mark_all_absent(self):
        """Mark all learners as absent."""
        for row in range(self.attendance_table.rowCount()):
            combo = self.attendance_table.cellWidget(row, 4)
            if combo:
                combo.setCurrentText('Absent')
                acc_no = self.attendance_table.item(row, 0).text()
                self.modified_records.add(acc_no)
        
        self._update_statistics()
    
    def _save_attendance(self):
        """Save attendance records."""
        try:
            records = []
            
            for row in range(self.attendance_table.rowCount()):
                acc_no = self.attendance_table.item(row, 0).text()
                
                combo = self.attendance_table.cellWidget(row, 4)
                status = AttendanceStatus(combo.currentText().lower()) if combo else AttendanceStatus.PRESENT
                
                notes_item = self.attendance_table.item(row, 5)
                notes = notes_item.text() if notes_item else ''
                
                records.append({
                    'learner_acc_no': acc_no,
                    'date': self.current_date,
                    'status': status.value,
                    'notes': notes,
                    'recorded_by': getattr(self.parent(), 'current_username', 'system') or 'system'
                })
            
            if records:
                success_count, failure_count = self.shared_attendance.record_bulk(
                    records,
                    user_id=getattr(self.parent(), 'current_user_id', None),
                ) if self.shared_attendance else (0, len(records))
                
                QMessageBox.information(
                    self,
                    "Attendance Saved",
                    f"Successfully saved {success_count} records.\n"
                    f"Failed: {failure_count}"
                )
                
                self.modified_records.clear()
                self._load_learners_for_attendance()
            else:
                QMessageBox.warning(self, "No Data", "No learners to save attendance for.")
                
        except Exception as e:
            self.logger.error(f"Error saving attendance: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save attendance: {e}")
    
    def _go_to_today(self):
        """Navigate to today's date."""
        self.date_edit.setDate(QDate.currentDate())
    
    def _refresh_data(self):
        """Refresh the current view."""
        self._load_learners_for_attendance()
    
    def _view_learner_history(self, acc_no: str):
        """View attendance history for a learner."""
        self.tab_widget.setCurrentIndex(1)  # Switch to history tab
        self.learner_search.setText(acc_no)
        self._load_history()
    
    def _filter_history(self):
        """Filter history based on search text."""
        # Debounce the search
        QTimer.singleShot(300, self._load_history)
    
    def _load_history(self):
        """Load attendance history."""
        try:
            search_text = self.learner_search.text().strip()
            start_date = self.history_from_date.date().toPython()
            end_date = self.history_to_date.date().toPython()
            
            records = self.shared_attendance.history(
                start_date=start_date,
                end_date=end_date,
                limit=5000,
            ) if self.shared_attendance else []
            
            # Filter by search text if provided
            if search_text:
                filtered = []
                for record in records:
                    acc_no = str(record.get("learner_acc_no") or "")
                    learner_name = str(record.get("learner_name") or "")
                    learner_surname = str(record.get("learner_surname") or "")
                    if (search_text.lower() in acc_no.lower() or
                        search_text.lower() in learner_name.lower() or
                        search_text.lower() in learner_surname.lower()):
                        filtered.append(record)
                records = filtered
            
            # Populate table
            self.history_table.setRowCount(len(records))
            
            for row, record in enumerate(records):
                self.history_table.setItem(row, 0, QTableWidgetItem(str(record.get("date") or "")))
                self.history_table.setItem(row, 1, QTableWidgetItem(str(record.get("learner_acc_no") or "")))
                self.history_table.setItem(
                    row,
                    2,
                    QTableWidgetItem(f"{record.get('learner_name', '')} {record.get('learner_surname', '')}".strip()),
                )
                self.history_table.setItem(row, 3, QTableWidgetItem(str(record.get("grade") or "")))
                
                status = str(record.get("status") or "")
                status_item = QTableWidgetItem(status.capitalize())
                status_item.setData(Qt.UserRole, status)
                self.history_table.setItem(row, 4, status_item)
                
                self.history_table.setItem(row, 5, QTableWidgetItem(str(record.get("notes") or '')))
            
            self.status_bar.setText(f"Loaded {len(records)} history records")
            
        except Exception as e:
            self.logger.error(f"Error loading history: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load history: {e}")
    
    def _generate_summary(self):
        """Generate attendance summary."""
        try:
            start_date = self.summary_from_date.date().toPython()
            end_date = self.summary_to_date.date().toPython()
            grade = self.current_grade
            
            report = self.shared_attendance.grade_report(
                grade, start_date, end_date
            ) if self.shared_attendance else {"learners": [], "overall_attendance_rate": 0.0}
            
            learners = report.get('learners', [])
            
            self.summary_table.setRowCount(len(learners))
            
            for row, learner in enumerate(learners):
                self.summary_table.setItem(row, 0, QTableWidgetItem(learner.get('learner_acc_no', '')))
                self.summary_table.setItem(row, 1, QTableWidgetItem(
                    f"{learner.get('learner_name', '')} {learner.get('learner_surname', '')}"
                ))
                self.summary_table.setItem(row, 2, QTableWidgetItem(str(learner.get('grade', ''))))
                self.summary_table.setItem(row, 3, QTableWidgetItem(str(learner.get('total_days', 0))))
                self.summary_table.setItem(row, 4, QTableWidgetItem(str(learner.get('present_days', 0))))
                self.summary_table.setItem(row, 5, QTableWidgetItem(str(learner.get('absent_days', 0))))
                self.summary_table.setItem(row, 6, QTableWidgetItem(str(learner.get('late_days', 0))))
                self.summary_table.setItem(row, 7, QTableWidgetItem(
                    f"{learner.get('attendance_rate', 0):.1f}%"
                ))
            
            self.status_bar.setText(
                f"Summary generated: {len(learners)} learners, "
                f"Overall rate: {report.get('overall_attendance_rate', 0):.1f}%"
            )
            
        except Exception as e:
            self.logger.error(f"Error generating summary: {e}")
            QMessageBox.critical(self, "Error", f"Failed to generate summary: {e}")
    
    def _export_summary(self):
        """Export summary to CSV."""
        try:
            import csv
            from PySide6.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Summary", "", "CSV Files (*.csv)"
            )
            
            if file_path:
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    
                    # Header
                    writer.writerow([
                        'Account No', 'Name', 'Grade', 'Total Days',
                        'Present', 'Absent', 'Late', 'Rate %'
                    ])
                    
                    # Data
                    for row in range(self.summary_table.rowCount()):
                        row_data = []
                        for col in range(self.summary_table.columnCount()):
                            item = self.summary_table.item(row, col)
                            row_data.append(item.text() if item else '')
                        writer.writerow(row_data)
                
                QMessageBox.information(self, "Export Complete", f"Summary exported to {file_path}")
                
        except Exception as e:
            self.logger.error(f"Error exporting summary: {e}")
            QMessageBox.critical(self, "Error", f"Failed to export: {e}")
    
    def _generate_report(self):
        """Generate the selected report type."""
        try:
            report_type = self.report_type_combo.currentText()
            
            if report_type == "Daily Report":
                report_data = self.shared_attendance.daily_report(self.current_date) if self.shared_attendance else {}
                self._format_daily_report(report_data)
            elif report_type == "Monthly Report":
                report_data = self.shared_attendance.monthly_report(
                    self.current_date.year,
                    self.current_date.month
                ) if self.shared_attendance else {}
                self._format_monthly_report(report_data)
            elif report_type == "Attendance Trends":
                report_data = self.shared_attendance.attendance_trends(days=30) if self.shared_attendance else {}
                self._format_trends_report(report_data)
            else:
                self.report_text.setText(f"Report type '{report_type}' not yet implemented.")
                
        except Exception as e:
            self.logger.error(f"Error generating report: {e}")
            self.report_text.setText(f"Error generating report: {e}")
    
    def _format_daily_report(self, data: Dict[str, Any]):
        """Format daily report for display."""
        self.report_text.setText(format_daily_report(data))
    
    def _format_monthly_report(self, data: Dict[str, Any]):
        """Format monthly report for display."""
        self.report_text.setText(format_monthly_report(data))
    
    def _format_trends_report(self, data: Dict[str, Any]):
        """Format trends report for display."""
        self.report_text.setText(format_trends_report(data))
    
    def _print_report(self):
        """Print the current report."""
        QMessageBox.information(self, "Print", "Print functionality will be implemented.")
    
    def _export_report_pdf(self):
        """Export report to PDF."""
        QMessageBox.information(self, "Export PDF", "PDF export functionality will be implemented.")
    
    def _process_pending_payments(self):
        """Process pending payment feeds."""
        try:
            stats = self.attendance_service.process_pending_payment_feeds()
            
            QMessageBox.information(
                self,
                "Payment Processing",
                f"Payment feeds processed:\n"
                f"Total pending: {stats['total_pending']}\n"
                f"Processed: {stats['processed']}\n"
                f"Failed: {stats['failed']}"
            )
            
        except Exception as e:
            self.logger.error(f"Error processing payments: {e}")
            QMessageBox.critical(self, "Error", f"Failed to process payments: {e}")


def show_attendance_dialog(
    db_manager,
    parent=None,
    email_service=None,
    event_bus=None
) -> AttendanceDialog:
    """
    Factory function to create and show the attendance dialog.
    
    Args:
        db_manager: Database manager instance
        parent: Parent widget
        email_service: Optional email service
        event_bus: Optional event bus
        
    Returns:
        AttendanceDialog instance
    """
    from data.repositories.attendance_repository import AttendanceRepository
    from data.repositories.learner_repository import LearnerRepository
    from data.repositories.payment_repository import PaymentRepository
    
    # Create repositories
    attendance_repo = AttendanceRepository(db_manager)
    learner_repo = LearnerRepository(db_manager)
    payment_repo = PaymentRepository(db_manager)
    
    # Create service
    attendance_service = AttendanceService(
        attendance_repository=attendance_repo,
        learner_repository=learner_repo,
        payment_repository=payment_repo,
        email_service=email_service,
        event_bus=event_bus
    )
    
    shared_services = get_desktop_shared_services(db_manager)

    # Create and return dialog
    dialog = AttendanceDialog(attendance_service, db_manager, shared_services=shared_services, parent=parent)
    return dialog
