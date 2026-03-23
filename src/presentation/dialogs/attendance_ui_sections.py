"""UI section builders for the attendance dialog.

These helpers keep AttendanceDialog focused on behavior/state while
encapsulating widget construction for each tab and chrome section.
"""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDateEdit,
    QComboBox,
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QTableWidget,
    QHeaderView,
    QLineEdit,
    QTextEdit,
)
from PySide6.QtCore import QDate
from PySide6.QtGui import QFont
from presentation.components.buttons import ButtonFactory
from presentation.components.table import apply_standard_table_metrics
from presentation.styles.colors import STATUS_ACTIVE_COLOR


def create_header(dialog) -> QHBoxLayout:
    """Create the header section."""
    layout = QHBoxLayout()
    layout.setContentsMargins(10, 5, 10, 5)
    layout.setSpacing(10)

    layout.addWidget(QLabel("Date:"))
    dialog.date_edit = QDateEdit()
    dialog.date_edit.setCalendarPopup(True)
    dialog.date_edit.setDate(QDate.currentDate())
    dialog.date_edit.setDisplayFormat("yyyy-MM-dd")
    dialog.date_edit.setMaximumWidth(120)
    layout.addWidget(dialog.date_edit)

    layout.addWidget(QLabel("Grade:"))
    dialog.grade_combo = QComboBox()
    dialog.grade_combo.addItems([str(i) for i in range(1, 13)])
    dialog.grade_combo.setCurrentText("1")
    dialog.grade_combo.setMaximumWidth(100)
    layout.addWidget(dialog.grade_combo)

    layout.addStretch()

    dialog.today_btn = QPushButton("Today")
    dialog.today_btn.clicked.connect(dialog._go_to_today)
    dialog.today_btn.setMaximumWidth(80)
    layout.addWidget(dialog.today_btn)

    dialog.refresh_btn = QPushButton("Refresh")
    dialog.refresh_btn.clicked.connect(dialog._refresh_data)
    dialog.refresh_btn.setMaximumWidth(80)
    layout.addWidget(dialog.refresh_btn)

    return layout


def create_daily_attendance_tab(dialog, status_delegate_cls) -> QWidget:
    """Create the daily attendance tab."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(10, 5, 10, 5)
    layout.setSpacing(8)

    control_group = QGroupBox("Quick Actions")
    control_layout = QHBoxLayout(control_group)
    control_layout.setContentsMargins(8, 5, 8, 5)
    control_layout.setSpacing(8)

    dialog.mark_all_present_btn = QPushButton("Mark All Present")
    dialog.mark_all_present_btn.clicked.connect(dialog._mark_all_present)
    dialog.mark_all_present_btn.setMaximumWidth(130)
    control_layout.addWidget(dialog.mark_all_present_btn)

    dialog.mark_all_absent_btn = QPushButton("Mark All Absent")
    dialog.mark_all_absent_btn.clicked.connect(dialog._mark_all_absent)
    dialog.mark_all_absent_btn.setMaximumWidth(130)
    control_layout.addWidget(dialog.mark_all_absent_btn)

    control_layout.addStretch()

    dialog.stats_label = QLabel("Learners: 0 | Present: 0 | Absent: 0 | Late: 0")
    dialog.stats_label.setStyleSheet("font-size: 11px;")
    control_layout.addWidget(dialog.stats_label)

    layout.addWidget(control_group)

    dialog.attendance_table = QTableWidget()
    dialog.attendance_table.setColumnCount(7)
    dialog.attendance_table.setHorizontalHeaderLabels(
        ["Acc No", "Name", "Surname", "Grade", "Status", "Notes", "Actions"]
    )

    header = dialog.attendance_table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.Stretch)
    header.setSectionResizeMode(2, QHeaderView.Stretch)
    header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(5, QHeaderView.Stretch)
    header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

    dialog.attendance_table.setSortingEnabled(True)
    dialog.attendance_table.setAlternatingRowColors(True)
    dialog.attendance_table.setItemDelegateForColumn(4, status_delegate_cls())
    apply_standard_table_metrics(dialog.attendance_table)

    layout.addWidget(dialog.attendance_table)

    save_layout = QHBoxLayout()
    save_layout.addStretch()

    dialog.save_btn = ButtonFactory.create_save_button("Save Attendance")
    dialog.save_btn.setMinimumWidth(180)
    dialog.save_btn.clicked.connect(dialog._save_attendance)
    save_layout.addWidget(dialog.save_btn)

    layout.addLayout(save_layout)
    return widget


def create_history_tab(dialog) -> QWidget:
    """Create the attendance history tab."""
    widget = QWidget()
    layout = QVBoxLayout(widget)

    filter_layout = QHBoxLayout()
    filter_layout.addWidget(QLabel("Learner:"))

    dialog.learner_search = QLineEdit()
    dialog.learner_search.setPlaceholderText("Enter account number or name...")
    dialog.learner_search.textChanged.connect(dialog._filter_history)
    filter_layout.addWidget(dialog.learner_search)

    filter_layout.addWidget(QLabel("From:"))
    dialog.history_from_date = QDateEdit()
    dialog.history_from_date.setCalendarPopup(True)
    dialog.history_from_date.setDate(QDate.currentDate().addMonths(-1))
    filter_layout.addWidget(dialog.history_from_date)

    filter_layout.addWidget(QLabel("To:"))
    dialog.history_to_date = QDateEdit()
    dialog.history_to_date.setCalendarPopup(True)
    dialog.history_to_date.setDate(QDate.currentDate())
    filter_layout.addWidget(dialog.history_to_date)

    dialog.search_history_btn = QPushButton("Search")
    dialog.search_history_btn.clicked.connect(dialog._load_history)
    filter_layout.addWidget(dialog.search_history_btn)
    layout.addLayout(filter_layout)

    dialog.history_table = QTableWidget()
    dialog.history_table.setColumnCount(6)
    dialog.history_table.setHorizontalHeaderLabels(
        ["Date", "Acc No", "Name", "Grade", "Status", "Notes"]
    )

    header = dialog.history_table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.Stretch)
    header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(5, QHeaderView.Stretch)

    dialog.history_table.setSortingEnabled(True)
    dialog.history_table.setAlternatingRowColors(True)
    apply_standard_table_metrics(dialog.history_table)
    layout.addWidget(dialog.history_table)

    return widget


def create_summary_tab(dialog) -> QWidget:
    """Create the attendance summary tab."""
    widget = QWidget()
    layout = QVBoxLayout(widget)

    period_layout = QHBoxLayout()
    period_layout.addWidget(QLabel("Period:"))

    dialog.summary_from_date = QDateEdit()
    dialog.summary_from_date.setCalendarPopup(True)
    dialog.summary_from_date.setDate(QDate.currentDate().addMonths(-1))
    period_layout.addWidget(dialog.summary_from_date)

    period_layout.addWidget(QLabel("to"))

    dialog.summary_to_date = QDateEdit()
    dialog.summary_to_date.setCalendarPopup(True)
    dialog.summary_to_date.setDate(QDate.currentDate())
    period_layout.addWidget(dialog.summary_to_date)

    dialog.generate_summary_btn = QPushButton("Generate Summary")
    dialog.generate_summary_btn.clicked.connect(dialog._generate_summary)
    period_layout.addWidget(dialog.generate_summary_btn)
    layout.addLayout(period_layout)

    dialog.summary_table = QTableWidget()
    dialog.summary_table.setColumnCount(8)
    dialog.summary_table.setHorizontalHeaderLabels(
        ["Acc No", "Name", "Grade", "Total Days", "Present", "Absent", "Late", "Rate %"]
    )

    header = dialog.summary_table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.Stretch)
    header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(7, QHeaderView.ResizeToContents)

    dialog.summary_table.setSortingEnabled(True)
    dialog.summary_table.setAlternatingRowColors(True)
    apply_standard_table_metrics(dialog.summary_table)
    layout.addWidget(dialog.summary_table)

    export_layout = QHBoxLayout()
    export_layout.addStretch()

    dialog.export_summary_btn = QPushButton("Export to CSV")
    dialog.export_summary_btn.clicked.connect(dialog._export_summary)
    export_layout.addWidget(dialog.export_summary_btn)
    layout.addLayout(export_layout)

    return widget


def create_reports_tab(dialog) -> QWidget:
    """Create the reports tab."""
    widget = QWidget()
    layout = QVBoxLayout(widget)

    type_layout = QHBoxLayout()
    type_layout.addWidget(QLabel("Report Type:"))

    dialog.report_type_combo = QComboBox()
    dialog.report_type_combo.addItems(
        [
            "Daily Report",
            "Weekly Report",
            "Monthly Report",
            "Grade Comparison",
            "Attendance Trends",
        ]
    )
    type_layout.addWidget(dialog.report_type_combo)

    dialog.generate_report_btn = QPushButton("Generate Report")
    dialog.generate_report_btn.clicked.connect(dialog._generate_report)
    type_layout.addWidget(dialog.generate_report_btn)
    layout.addLayout(type_layout)

    dialog.report_text = QTextEdit()
    dialog.report_text.setReadOnly(True)
    dialog.report_text.setFont(QFont("Courier", 10))
    layout.addWidget(dialog.report_text)

    report_btn_layout = QHBoxLayout()
    report_btn_layout.addStretch()

    dialog.print_report_btn = QPushButton("Print")
    dialog.print_report_btn.clicked.connect(dialog._print_report)
    report_btn_layout.addWidget(dialog.print_report_btn)

    dialog.export_report_btn = QPushButton("Export PDF")
    dialog.export_report_btn.clicked.connect(dialog._export_report_pdf)
    report_btn_layout.addWidget(dialog.export_report_btn)
    layout.addLayout(report_btn_layout)

    return widget


def create_button_box(dialog) -> QHBoxLayout:
    """Create the bottom button box."""
    layout = QHBoxLayout()
    layout.setContentsMargins(10, 5, 10, 5)
    layout.setSpacing(8)

    dialog.payment_status_label = QLabel("✓ Payment Integration")
    dialog.payment_status_label.setStyleSheet(
        f"color: {STATUS_ACTIVE_COLOR()}; font-size: 10px;"
    )
    layout.addWidget(dialog.payment_status_label)

    layout.addStretch()

    dialog.process_payments_btn = QPushButton("Process Payments")
    dialog.process_payments_btn.clicked.connect(dialog._process_pending_payments)
    dialog.process_payments_btn.setMaximumWidth(130)
    layout.addWidget(dialog.process_payments_btn)

    dialog.close_btn = QPushButton("Close")
    dialog.close_btn.clicked.connect(dialog.close)
    dialog.close_btn.setMaximumWidth(80)
    layout.addWidget(dialog.close_btn)

    return layout
