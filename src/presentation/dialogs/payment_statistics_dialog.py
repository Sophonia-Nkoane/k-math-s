from PySide6.QtWidgets import (QVBoxLayout, QLabel, QGridLayout,
                          QFrame, QMessageBox, QHBoxLayout,
                          QTabWidget, QWidget, QTableWidgetItem,
                          QHeaderView, QLineEdit, QPushButton, QCheckBox)
from presentation.components.table import Table
from PySide6.QtCore import Qt
from datetime import datetime
import calendar
import logging
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import QTextDocument, QColor
from presentation.styles.colors import (POSITIVE_VALUE_COLOR, NEGATIVE_VALUE_COLOR, 
                              NEUTRAL_VALUE_COLOR, SCROLLBAR_BACKGROUND, 
                              SCROLLBAR_HANDLE, SCROLLBAR_HANDLE_HOVER, STATS_TEXT_SECONDARY)
from presentation.styles.styles import MODERN_SCROLLBAR_STYLE, get_statistics_dialog_styles

from presentation.components.buttons import ButtonFactory
from presentation.components.rounded_field import RoundedDropdown
from presentation.components.collapsible_section import CollapsibleSection
from presentation.components.window_component import WindowComponent
from presentation.dialogs.payment_statistics_utils import (
    ACTIVE_LEARNERS_COUNT_QUERY,
    ACTIVE_LEARNERS_FOR_MONTH_QUERY,
    LAST_PAYMENT_BY_LEARNER_QUERY,
    MONTHLY_COLLECTED_TOTAL_QUERY,
    PAYMENTS_BY_FAMILY_QUERY,
    PAYMENTS_BY_LEARNER_QUERY,
    PROJECTED_TOTAL_QUERY,
    format_last_payment_date,
    iter_recent_months,
    month_bounds,
    parse_min_due_amount,
    previous_month,
)


class PaymentStatisticsDialog(WindowComponent):
    """Dialog for displaying payment statistics including monthly totals and projections."""
    
    def __init__(self, db_manager, current_user_id=None, parent=None):
        super().__init__(parent, title="Payment Statistics")
        self.db_manager = db_manager
        self.current_user_id = current_user_id
        self.logger = logging.getLogger(self.__class__.__name__)
        self.setup_ui()
        self.loadStatistics()
        self.setFixedSize(800, 600)
        if parent:
            self.center_on_parent()
        else:
            self.center_on_screen()

    def setup_ui(self):
        """Set up the user interface with theme-aware styles."""
        styles = get_statistics_dialog_styles()
        
        # Apply dialog style
        self.setStyleSheet(styles["dialog"])
        
        # Use the central, theme-aware scrollbar style
        scrollbar_style = MODERN_SCROLLBAR_STYLE.format(
            SCROLLBAR_BACKGROUND=SCROLLBAR_BACKGROUND(),
            SCROLLBAR_HANDLE=SCROLLBAR_HANDLE(),
            SCROLLBAR_HANDLE_HOVER=SCROLLBAR_HANDLE_HOVER()
        )

        # Tab Widget Style
        tab_widget_style = f"""
            QTabWidget::pane {{
                border: 1px solid {styles["border"]};
                background-color: {styles["tab_background"]};
                border-radius: 8px;
                border-top-left-radius: 0px;  /* Added this line to make top-left corner square */
                padding: 15px;
            }}
            QTabBar::tab {{
                background-color: {styles["tab_button_background"]};
                color: {styles["tab_button_color"]};
                border: 1px solid {styles["border"]};
                border-bottom: none;
                padding: 8px 24px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected, QTabBar::tab:hover {{
                background-color: {styles["tab_hover_background"]};
                color: {styles["tab_hover_color"]};
            }}
        """

        # Frame and Label Style
        frame_style = f"""
            QFrame {{
                background-color: {styles["frame_background"]};
                border: 1px solid {styles["border"]};
                border-radius: 8px;
                padding: 15px;
            }}
            QLabel {{
                padding: 5px 0; font-size: 11pt; color: {styles["label_color"]}; background-color: transparent;
            }}
            QLabel[class="value"] {{
                font-size: 11pt; font-weight: bold; padding: 5px; color: {styles["value_color"]};
            }}
        """

        # Table Style (for Trends tab)
        table_style = f"""
            QTableWidget {{
                border-radius: 8px; background-color: {styles["table_background"]}; gridline-color: {styles["border"]}; color: {styles["table_text_color"]};
            }}
            QTableWidget::item {{ padding: 10px; border: none; }}
            QTableWidget::item:selected {{ background-color: {styles["selection_background"]}; color: {styles["selection_color"]}; }}
            QTableWidget::item:hover {{ background-color: {styles["hover_background"]}; }}
            QTableWidget::alternate-background {{ background-color: {styles["alternate_background"]}; }}
            QHeaderView::section {{
                background-color: {styles["header_background"]}; padding: 10px; border: none;
                border-bottom: 1px solid {styles["border"]}; color: {styles["header_text_color"]}; font-weight: bold;
            }}
        """

        # Dropdown Style
        dropdown_style = f"""
            QComboBox {{
                background-color: {styles["dropdown_background"]}; border: 1px solid {styles["border"]}; border-radius: 6px;
                padding: 5px 12px; color: {styles["dropdown_text_color"]}; min-height: 25px;
            }}
            QComboBox:hover, QComboBox:focus {{ border: 1px solid {styles["focus_border"]}; }}
            QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 20px; border: none; }}
            QComboBox QAbstractItemView {{
                background-color: {styles["dropdown_background"]}; border: 1px solid {styles["border"]}; border-radius: 6px;
                selection-background-color: {styles["selection_background"]}; selection-color: {styles["selection_color"]};
                color: {styles["dropdown_text_color"]}; padding: 4px; outline: 0px;
            }}
            {scrollbar_style.replace('QScrollBar', 'QComboBox QAbstractItemView QScrollBar')}
        """

        # OK Button Style (overrides the global style from the factory)
        ok_button_style = f"""
            QPushButton {{
                background-color: {styles["button_background"]}; color: white; border-radius: 8px;
                padding: 8px 24px; border: none; font-weight: bold;
            }}
            QPushButton:hover:!disabled {{ background-color: {styles["button_hover"]}; }}
        """

        # --- UI Layout and Component Initialization ---
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 10, 15, 15)
        
        # Initialize tables
        revenue_columns = [
            {"name": "Month", "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "Revenue", "resize_mode": QHeaderView.ResizeMode.ResizeToContents}
        ]
        registrations_columns = [
            {"name": "Month", "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "New Learners", "resize_mode": QHeaderView.ResizeMode.ResizeToContents}
        ]
        active_learners_columns = [
            {"name": "Month", "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "Active Learners", "resize_mode": QHeaderView.ResizeMode.ResizeToContents}
        ]
        
        self.revenue_table = Table(self, revenue_columns).get_table()
        self.registrations_table = Table(self, registrations_columns).get_table()
        self.active_learners_table = Table(self, active_learners_columns).get_table()
        
        # Remove any table-specific styling since it's handled by Table component
        for table in [self.revenue_table, self.registrations_table, self.active_learners_table]:
            table.verticalScrollBar().setStyleSheet(scrollbar_style)

        # Date selector with theme-aware styles
        date_selector_layout = QHBoxLayout()
        self.year_selector, self.month_selector = self._create_date_selectors()
        self.year_selector.setStyleSheet(styles["dropdown"])
        self.month_selector.setStyleSheet(styles["dropdown"])

        date_selector_label = QLabel("Select Period:")
        date_selector_label.setStyleSheet(f"color: {STATS_TEXT_SECONDARY()}; font-weight: bold;")
        date_selector_layout.addWidget(date_selector_label)
        date_selector_layout.addSpacing(10)
        date_selector_layout.addWidget(self.year_selector)
        date_selector_layout.addSpacing(10)
        date_selector_layout.addWidget(self.month_selector)
        date_selector_layout.addStretch()
        main_layout.addLayout(date_selector_layout)

        # Tab Widget with theme-aware styles
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet(styles["tab_widget"])

        # Summary Tab with theme-aware frame style
        summary_tab = self._create_summary_tab(styles["frame"])
        tab_widget.addTab(summary_tab, "Summary")

        # Missed Payments Tab (new dedicated tab)
        missed_tab = self._create_missed_payments_tab(styles["frame"])
        tab_widget.addTab(missed_tab, "Missed Payments")

        # Trends Tab
        trends_tab = self._create_trends_tab()
        tab_widget.addTab(trends_tab, "Trends")
        
        main_layout.addWidget(tab_widget)
        
        # OK button
        ok_button = ButtonFactory.create_ok_button("OK")
        ok_button.setStyleSheet(ok_button_style)
        ok_button.clicked.connect(self.accept)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        # Export PDF button (saves the currently displayed statistics to a PDF)
        self.export_pdf_button = ButtonFactory.create_save_button("Export PDF")
        self.export_pdf_button.setStyleSheet(ok_button_style)
        self.export_pdf_button.clicked.connect(self.export_pdf)
        button_layout.addWidget(self.export_pdf_button)
        button_layout.addSpacing(8)
        button_layout.addWidget(ok_button)
        main_layout.addLayout(button_layout)

        self.add_layout(main_layout)

    def _create_date_selectors(self):
        """Creates and configures year and month dropdowns."""
        year_selector = RoundedDropdown()
        current_year = datetime.now().year
        year_selector.addItem("-- Select Year --")
        year_selector.addItems([str(y) for y in range(current_year - 7, current_year + 2)])
        year_selector.setCurrentText(str(current_year))
        year_selector.currentTextChanged.connect(self.loadStatistics)
        
        month_selector = RoundedDropdown()
        current_month = datetime.now().month
        month_selector.addItem("-- Select Month --")
        month_selector.addItems(list(calendar.month_name)[1:])
        month_selector.setCurrentIndex(current_month)
        month_selector.currentIndexChanged.connect(self.loadStatistics)
        return year_selector, month_selector

    def _create_summary_tab(self, frame_style):
        """Creates the content widget for the Summary tab."""
        summary_tab = QWidget()
        summary_tab.setStyleSheet("background-color: transparent;")
        summary_layout = QVBoxLayout(summary_tab)
        summary_layout.setContentsMargins(0,0,0,0)
        
        stats_frame = QFrame()
        stats_frame.setStyleSheet(frame_style)
        stats_layout = QGridLayout(stats_frame)
        
        self.collected_label = QLabel("Total Collected:")
        self.projected_label = QLabel("Projected Monthly Total:")
        self.registrations_label = QLabel("Active Learners:")
        self.collected_value = QLabel()
        self.outstanding_value = QLabel()
        self.projected_value = QLabel()
        self.registrations_value = QLabel()
        self.on_track_value = QLabel()
        self.missed_value = QLabel()
        for label in [self.collected_value, self.outstanding_value, self.projected_value, self.registrations_value]:
            label.setProperty("class", "value")
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for label in [self.on_track_value, self.missed_value]:
            label.setProperty("class", "value")
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        stats_layout.addWidget(self.collected_label, 0, 0)
        stats_layout.addWidget(self.collected_value, 0, 1)
        stats_layout.addWidget(self.projected_label, 2, 0)
        stats_layout.addWidget(self.projected_value, 2, 1)
        stats_layout.addWidget(self.registrations_label, 3, 0)
        stats_layout.addWidget(self.registrations_value, 3, 1)
        stats_layout.addWidget(QLabel("On Track:"), 4, 0)
        stats_layout.addWidget(self.on_track_value, 4, 1)
        stats_layout.addWidget(QLabel("Missed Payments:"), 5, 0)
        stats_layout.addWidget(self.missed_value, 5, 1)
        summary_layout.addWidget(stats_frame)

        comparison_frame = QFrame()
        comparison_frame.setStyleSheet(frame_style)
        comparison_layout = QGridLayout(comparison_frame)
        
        self.prev_month_label = QLabel("Previous Month Outstanding:")
        self.current_month_label = QLabel("Outstanding Amount:")
        self.combined_total_label = QLabel("Combined Total Outstanding:")
        self.prev_month_value = QLabel()
        self.current_month_value = QLabel()
        self.combined_total_value = QLabel()
        for label in [self.prev_month_value, self.current_month_value, self.combined_total_value]:
            label.setProperty("class", "value")
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        comparison_layout.addWidget(self.prev_month_label, 0, 0)
        comparison_layout.addWidget(self.prev_month_value, 0, 1)
        comparison_layout.addWidget(self.current_month_label, 1, 0)
        comparison_layout.addWidget(self.current_month_value, 1, 1)
        comparison_layout.addWidget(self.combined_total_label, 2, 0)
        comparison_layout.addWidget(self.combined_total_value, 2, 1)
        summary_layout.addWidget(comparison_frame)
        summary_layout.addStretch()
        # Keep a smaller missed table in summary for quick reference (optional)
        # Remove it if you only want the full table in the dedicated tab
        return summary_tab
        
    def _create_missed_payments_tab(self, frame_style):
        """Creates the dedicated Missed Payments tab with full table and details."""
        missed_tab = QWidget()
        missed_tab.setStyleSheet("background-color: transparent;")
        missed_layout = QVBoxLayout(missed_tab)
        missed_layout.setContentsMargins(0, 0, 0, 0)
        
        # Summary section showing counts
        summary_frame = QFrame()
        summary_frame.setStyleSheet(frame_style)
        summary_layout_inner = QGridLayout(summary_frame)
        
        self.missed_tab_on_track_label = QLabel("On Track:")
        self.missed_tab_on_track_value = QLabel("0")
        self.missed_tab_on_track_value.setProperty("class", "value")
        self.missed_tab_on_track_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.missed_tab_missed_label = QLabel("Missed Payments:")
        self.missed_tab_missed_value = QLabel("0")
        self.missed_tab_missed_value.setProperty("class", "value")
        self.missed_tab_missed_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Add total outstanding amount
        self.missed_tab_total_due_label = QLabel("Total Outstanding:")
        self.missed_tab_total_due_value = QLabel("R 0.00")
        self.missed_tab_total_due_value.setProperty("class", "value")
        self.missed_tab_total_due_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        summary_layout_inner.addWidget(self.missed_tab_on_track_label, 0, 0)
        summary_layout_inner.addWidget(self.missed_tab_on_track_value, 0, 1)
        summary_layout_inner.addWidget(self.missed_tab_missed_label, 1, 0)
        summary_layout_inner.addWidget(self.missed_tab_missed_value, 1, 1)
        summary_layout_inner.addWidget(self.missed_tab_total_due_label, 2, 0)
        summary_layout_inner.addWidget(self.missed_tab_total_due_value, 2, 1)
        
        missed_layout.addWidget(summary_frame)
        
        # Filter and search section
        filter_frame = QFrame()
        filter_frame.setStyleSheet(frame_style)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(10, 5, 10, 5)
        
        # Search box
        search_label = QLabel("Search:")
        self.missed_search_input = QLineEdit()
        self.missed_search_input.setPlaceholderText("Type to search by name, surname, or account...")
        self.missed_search_input.setMaximumWidth(250)
        self.missed_search_input.textChanged.connect(self._filter_missed_table)
        
        # Filter by status
        self.show_on_track_cb = QCheckBox("Show On Track")
        self.show_on_track_cb.setChecked(True)
        self.show_on_track_cb.stateChanged.connect(self._filter_missed_table)
        
        self.show_missed_cb = QCheckBox("Show Missed")
        self.show_missed_cb.setChecked(True)
        self.show_missed_cb.stateChanged.connect(self._filter_missed_table)
        
        # Filter by minimum due amount
        min_due_label = QLabel("Min Due:")
        self.min_due_input = QLineEdit()
        self.min_due_input.setPlaceholderText("R 0")
        self.min_due_input.setMaximumWidth(80)
        self.min_due_input.textChanged.connect(self._filter_missed_table)
        
        filter_layout.addWidget(search_label)
        filter_layout.addWidget(self.missed_search_input)
        filter_layout.addSpacing(20)
        filter_layout.addWidget(self.show_on_track_cb)
        filter_layout.addWidget(self.show_missed_cb)
        filter_layout.addSpacing(20)
        filter_layout.addWidget(min_due_label)
        filter_layout.addWidget(self.min_due_input)
        filter_layout.addStretch()
        
        missed_layout.addWidget(filter_frame)
        
        # Full missed payments table (adds Last Payment column and a hidden Status column)
        self.missed_tab_table = Table(self, [
            {"name": "Acc", "resize_mode": QHeaderView.ResizeMode.Fixed},
            {"name": "Name", "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "Surname", "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "Grade", "resize_mode": QHeaderView.ResizeMode.Fixed},
            {"name": "Expected", "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Paid", "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Due", "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Last Payment", "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Status", "resize_mode": QHeaderView.ResizeMode.Fixed}  # hidden
        ]).get_table()
        
        # Enable sorting
        self.missed_tab_table.setSortingEnabled(True)

        missed_layout.addWidget(self.missed_tab_table)
        # Hide the status column - it's used internally for export/logic
        try:
            self.missed_tab_table.setColumnHidden(8, True)
        except Exception:
            pass
        
        # Store full data for filtering
        self._missed_full_data = []
        
        missed_layout.addStretch()
        
        return missed_tab
    
    def _filter_missed_table(self):
        """Filter the missed payments table based on search and filter criteria."""
        try:
            search_text = self.missed_search_input.text().lower().strip()
            show_on_track = self.show_on_track_cb.isChecked()
            show_missed = self.show_missed_cb.isChecked()
            min_due = parse_min_due_amount(self.min_due_input.text().strip())

            filtered_rows = []
            for row_data in self._missed_full_data:
                acc, name, surname, grade, expected, paid, due, last_payment, status = row_data

                if status == 'on_track' and not show_on_track:
                    continue
                if status == 'missed' and not show_missed:
                    continue

                if due < min_due:
                    continue

                if search_text:
                    search_match = (
                        search_text in acc.lower() or
                        search_text in name.lower() or
                        search_text in surname.lower() or
                        search_text in str(grade).lower()
                    )
                    if not search_match:
                        continue

                filtered_rows.append(row_data)

            self._populate_missed_table(filtered_rows)
        except Exception as e:
            self.logger.error(f"Error filtering missed table: {e}")
        
    def _create_trends_tab(self):
        """Creates the content widget for the Trends tab."""
        trends_tab = QWidget()
        trends_tab.setStyleSheet("background-color: transparent;")
        trends_layout = QVBoxLayout(trends_tab)
        trends_layout.setContentsMargins(0,0,0,0)
        
        # List to track all collapsible sections
        self.collapsible_sections = []
        
        revenue_section = CollapsibleSection("Monthly Revenue Trend")
        revenue_section.add_widget(self.revenue_table)
        revenue_section.toggled.connect(lambda state: self._handle_section_toggle(revenue_section, state))
        self.collapsible_sections.append(revenue_section)
        trends_layout.addWidget(revenue_section)
        
        registrations_section = CollapsibleSection("Monthly New Registrations")
        registrations_section.add_widget(self.registrations_table)
        registrations_section.toggled.connect(lambda state: self._handle_section_toggle(registrations_section, state))
        self.collapsible_sections.append(registrations_section)
        trends_layout.addWidget(registrations_section)
        
        active_learners_section = CollapsibleSection("Monthly Active Learners")
        active_learners_section.add_widget(self.active_learners_table)
        active_learners_section.toggled.connect(lambda state: self._handle_section_toggle(active_learners_section, state))
        self.collapsible_sections.append(active_learners_section)
        trends_layout.addWidget(active_learners_section)
        
        trends_layout.addStretch()
        return trends_tab

    def _handle_section_toggle(self, opened_section, state):
        """Handle collapsible section toggling to ensure only one is open at a time."""
        if state:  # If a section is being opened
            for section in self.collapsible_sections:
                if section != opened_section and section.is_expanded():
                    section.toggle()

    def _populate_trend_table(self, table, rows, currency=False):
        """Populate a 2-column trend table with formatted values."""
        table.setRowCount(len(rows))
        for row_idx, (month_name, value) in enumerate(rows):
            table.setItem(row_idx, 0, QTableWidgetItem(month_name))
            if currency:
                value_item = QTableWidgetItem(f"R {float(value):,.2f}")
            else:
                value_item = QTableWidgetItem(str(int(value)))
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row_idx, 1, value_item)

    def _query_active_learners_count(self):
        result = self.db_manager.execute_query(ACTIVE_LEARNERS_COUNT_QUERY, fetchone=True)
        return int(result[0]) if result else 0

    def _query_projected_total(self, month_end_date, month_start_date):
        result = self.db_manager.execute_query(
            PROJECTED_TOTAL_QUERY,
            (month_end_date, month_start_date),
            fetchone=True,
        )
        return float(result[0] or 0) if result else 0.0

    def _query_collected_total(self, month_key):
        result = self.db_manager.execute_query(
            MONTHLY_COLLECTED_TOTAL_QUERY,
            (month_key,),
            fetchone=True,
        )
        return float(result[0] or 0) if result else 0.0

    @staticmethod
    def _set_metric_style(label, color):
        label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _set_missed_table_row(self, row_idx, row_data):
        acc, name, surname, grade, expected, paid, due, last_payment, status = row_data

        self.missed_tab_table.setItem(row_idx, 0, QTableWidgetItem(acc))
        self.missed_tab_table.setItem(row_idx, 1, QTableWidgetItem(name))
        self.missed_tab_table.setItem(row_idx, 2, QTableWidgetItem(surname))
        self.missed_tab_table.setItem(row_idx, 3, QTableWidgetItem(str(grade)))

        expected_item = QTableWidgetItem(f"R {expected:,.2f}")
        expected_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.missed_tab_table.setItem(row_idx, 4, expected_item)

        paid_item = QTableWidgetItem(f"R {paid:,.2f}")
        paid_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.missed_tab_table.setItem(row_idx, 5, paid_item)

        due_item = QTableWidgetItem(f"R {due:,.2f}")
        due_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.missed_tab_table.setItem(row_idx, 6, due_item)

        last_payment_item = QTableWidgetItem(last_payment)
        last_payment_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.missed_tab_table.setItem(row_idx, 7, last_payment_item)
        self.missed_tab_table.setItem(row_idx, 8, QTableWidgetItem(status))

        row_color = QColor(POSITIVE_VALUE_COLOR() if status == 'on_track' else NEGATIVE_VALUE_COLOR())
        for col in range(8):
            item = self.missed_tab_table.item(row_idx, col)
            if item:
                item.setForeground(row_color)

    def _populate_missed_table(self, rows):
        self.missed_tab_table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            self._set_missed_table_row(row_idx, row_data)

    def _update_missed_payments_data(self, selected_year, selected_month):
        month_key = f"{selected_year}-{selected_month:02d}"
        start_date, end_date = month_bounds(selected_year, selected_month)

        rows = self.db_manager.execute_query(
            ACTIVE_LEARNERS_FOR_MONTH_QUERY,
            (end_date, start_date),
            fetchall=True,
        ) or []

        payments_rows = self.db_manager.execute_query(
            PAYMENTS_BY_LEARNER_QUERY,
            (month_key,),
            fetchall=True,
        ) or []
        payments_by_learner = {learner_id: float(amount or 0) for learner_id, amount in payments_rows}

        family_pay_rows = self.db_manager.execute_query(
            PAYMENTS_BY_FAMILY_QUERY,
            (month_key,),
            fetchall=True,
        ) or []
        payments_by_family = {(family_id or ''): float(amount or 0) for family_id, amount in family_pay_rows}

        learners_list = []
        learner_by_acc = {}
        family_learners = {}
        for acc_no, name, surname, family_id, grade, base_fee, discount, payment_mode in rows:
            normalized_family_id = family_id or ''
            expected = float(base_fee or 0) * (1.0 - float(discount or 0) / 100.0)
            learner_entry = {
                'acc_no': acc_no,
                'name': name or '',
                'surname': surname or '',
                'family_id': normalized_family_id,
                'grade': grade or '',
                'expected': expected,
                'payment_mode': payment_mode,
            }
            learners_list.append(learner_entry)
            learner_by_acc[acc_no] = learner_entry
            family_learners.setdefault(normalized_family_id, []).append(acc_no)

        on_track = []
        missed = []
        missed_detail = []
        processed_learners = set()
        families_processed = set()

        for learner in learners_list:
            family_id = learner['family_id']
            if learner['payment_mode'] != 'single_coverage' or family_id in families_processed:
                continue

            families_processed.add(family_id)
            member_ids = family_learners.get(family_id, [])
            family_expected = max(
                (learner_by_acc[member_id]['expected'] for member_id in member_ids if member_id in learner_by_acc),
                default=0.0,
            )
            family_paid = payments_by_family.get(family_id, 0.0)

            is_on_track = family_paid >= family_expected
            status = 'on_track' if is_on_track else 'missed'
            due_amount = 0.0 if is_on_track else max(0.0, family_expected - family_paid)

            for member_id in member_ids:
                member = learner_by_acc.get(member_id)
                if not member:
                    continue
                if is_on_track:
                    on_track.append(member_id)
                else:
                    missed.append(member_id)
                paid_amount = payments_by_learner.get(member_id, 0.0)
                missed_detail.append(
                    (
                        member_id,
                        member['name'],
                        member['surname'],
                        member.get('grade', ''),
                        family_expected,
                        paid_amount,
                        due_amount,
                        status,
                    )
                )
                processed_learners.add(member_id)

        for learner in learners_list:
            learner_id = learner['acc_no']
            if learner_id in processed_learners or learner['payment_mode'] == 'single_coverage':
                continue

            expected = learner['expected']
            paid = payments_by_learner.get(learner_id, 0.0)
            if paid >= expected:
                status = 'on_track'
                due = 0.0
                on_track.append(learner_id)
            else:
                status = 'missed'
                due = max(0.0, expected - paid)
                missed.append(learner_id)

            missed_detail.append(
                (
                    learner_id,
                    learner['name'],
                    learner['surname'],
                    learner.get('grade', ''),
                    expected,
                    paid,
                    due,
                    status,
                )
            )

        last_payment_rows = self.db_manager.execute_query(LAST_PAYMENT_BY_LEARNER_QUERY, fetchall=True) or []
        last_payment_by_learner = {learner_id: last_date for learner_id, last_date in last_payment_rows}

        full_rows = []
        for acc, name, surname, grade, expected, paid, due, status in missed_detail:
            full_rows.append(
                (
                    acc,
                    name,
                    surname,
                    grade,
                    expected,
                    paid,
                    due,
                    format_last_payment_date(last_payment_by_learner.get(acc, "N/A")),
                    status,
                )
            )

        total_outstanding_amount = sum(due for _, _, _, _, _, _, due, _, status in full_rows if status == 'missed')

        self.on_track_value.setText(str(len(on_track)))
        self.missed_value.setText(str(len(missed)))
        self._set_metric_style(self.on_track_value, POSITIVE_VALUE_COLOR())
        self._set_metric_style(self.missed_value, NEGATIVE_VALUE_COLOR())

        self.missed_tab_on_track_value.setText(str(len(on_track)))
        self.missed_tab_missed_value.setText(str(len(missed)))
        self._set_metric_style(self.missed_tab_on_track_value, POSITIVE_VALUE_COLOR())
        self._set_metric_style(self.missed_tab_missed_value, NEGATIVE_VALUE_COLOR())

        self.missed_tab_total_due_value.setText(f"R {total_outstanding_amount:,.2f}")
        self._set_metric_style(self.missed_tab_total_due_value, NEGATIVE_VALUE_COLOR())

        self._missed_full_data = full_rows
        self._populate_missed_table(self._missed_full_data)

    def loadStatistics(self):
        """Load and display payment statistics for the selected month and year."""
        try:
            if not self.year_selector.currentText().isdigit():
                return

            selected_month_idx = self.month_selector.currentIndex()
            if selected_month_idx == 0:
                return
            selected_month = selected_month_idx

            selected_year = int(self.year_selector.currentText())
            month_key = f"{selected_year}-{selected_month:02d}"
            selected_start_date, selected_end_date = month_bounds(selected_year, selected_month)

            active_learners = self._query_active_learners_count()
            total_projected = self._query_projected_total(selected_end_date, selected_start_date)
            total_collected = self._query_collected_total(month_key)
            outstanding_amount = total_projected - total_collected

            prev_month_year, prev_month_num = previous_month(selected_year, selected_month)
            prev_month_key = f"{prev_month_year}-{prev_month_num:02d}"
            prev_start_date, prev_end_date = month_bounds(prev_month_year, prev_month_num)

            prev_month_collected = self._query_collected_total(prev_month_key)
            prev_month_projected = self._query_projected_total(prev_end_date, prev_start_date)
            prev_month_outstanding = prev_month_projected - prev_month_collected

            self.collected_value.setText(f"R {total_collected:,.2f}")
            self.outstanding_value.setText(f"R {outstanding_amount:,.2f}")
            self.projected_value.setText(f"R {total_projected:,.2f}")
            self.registrations_value.setText(str(active_learners))
            self._set_metric_style(
                self.outstanding_value,
                NEGATIVE_VALUE_COLOR() if outstanding_amount > 0 else POSITIVE_VALUE_COLOR(),
            )
            self._set_metric_style(self.collected_value, POSITIVE_VALUE_COLOR())
            self._set_metric_style(self.projected_value, NEUTRAL_VALUE_COLOR())

            self.prev_month_value.setText(f"R {prev_month_outstanding:,.2f}")
            self._set_metric_style(
                self.prev_month_value,
                NEGATIVE_VALUE_COLOR() if prev_month_outstanding > 0 else POSITIVE_VALUE_COLOR(),
            )

            self.current_month_value.setText(f"R {outstanding_amount:,.2f}")
            self._set_metric_style(
                self.current_month_value,
                NEGATIVE_VALUE_COLOR() if outstanding_amount > 0 else POSITIVE_VALUE_COLOR(),
            )

            combined_total = prev_month_outstanding + outstanding_amount
            self.combined_total_value.setText(f"R {combined_total:,.2f}")
            self._set_metric_style(
                self.combined_total_value,
                NEGATIVE_VALUE_COLOR() if combined_total > 0 else POSITIVE_VALUE_COLOR(),
            )

            self.updateRevenueTrend(selected_year, selected_month)
            self.updateRegistrationsTrend(selected_year, selected_month)
            self.updateActiveLearnersTrend(selected_year, selected_month)

            try:
                self._update_missed_payments_data(selected_year, selected_month)
            except Exception as e:
                self.logger.error(f"Error computing missed/on-track classification: {e}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load statistics: {str(e)}")
            
    def updateRevenueTrend(self, selected_year, selected_month):
        """Update the revenue trend table."""
        try:
            months_data = []
            for _, _, month_key, month_label in iter_recent_months(selected_year, selected_month):
                result = self.db_manager.execute_query(
                    "SELECT COALESCE(SUM(amount), 0) FROM Payments WHERE strftime('%Y-%m', date) = ? AND payment_type = 'tuition'",
                    (month_key,),
                    fetchone=True,
                )
                amount = float(result[0]) if result else 0
                months_data.append((month_label, amount))

            self._populate_trend_table(self.revenue_table, months_data, currency=True)
        except Exception as e:
            self.logger.error(f"Error updating revenue trend: {e}")
    
    def updateRegistrationsTrend(self, selected_year, selected_month):
        """Update the registrations trend table."""
        try:
            months_data = []
            for _, _, month_key, month_label in iter_recent_months(selected_year, selected_month):
                result = self.db_manager.execute_query(
                    "SELECT COUNT(DISTINCT s.acc_no) as new_registrations FROM Learners s JOIN LearnerPayments sp ON s.acc_no = sp.learner_id WHERE strftime('%Y-%m', sp.start_date) = ? AND s.is_active = 1",
                    (month_key,),
                    fetchone=True,
                )
                count = int(result[0]) if result else 0
                months_data.append((month_label, count))

            self._populate_trend_table(self.registrations_table, months_data, currency=False)
        except Exception as e:
            self.logger.error(f"Error updating registrations trend: {e}")

    def updateActiveLearnersTrend(self, selected_year, selected_month):
        """Update the active learners trend table."""
        try:
            months_data = []
            for year, month, _, month_label in iter_recent_months(selected_year, selected_month):
                month_start, month_end = month_bounds(year, month)
                result = self.db_manager.execute_query(
                    "SELECT COUNT(DISTINCT s.acc_no) as active_count FROM Learners s JOIN LearnerPayments sp ON s.acc_no = sp.learner_id WHERE s.is_active = 1 AND sp.start_date <= ? AND (sp.end_date IS NULL OR sp.end_date >= ?)",
                    (month_end, month_start),
                    fetchone=True,
                )
                count = int(result[0]) if result else 0
                months_data.append((month_label, count))

            self._populate_trend_table(self.active_learners_table, months_data, currency=False)
        except Exception as e:
            self.logger.error(f"Error updating active learners trend: {e}")

    def export_pdf(self):
        """Exports the currently displayed statistics (summary and missed list) to a colorized PDF."""
        try:
            # Build HTML content
            selected_month_idx = self.month_selector.currentIndex()
            if selected_month_idx == 0 or not self.year_selector.currentText().isdigit():
                QMessageBox.information(self, "Export PDF", "Select a valid month and year before exporting.")
                return
            selected_month = selected_month_idx
            selected_year = int(self.year_selector.currentText())
            month_name = f"{calendar.month_name[selected_month]} {selected_year}"

            collected = self.collected_value.text()
            projected = self.projected_value.text()
            outstanding = self.outstanding_value.text()
            on_track = self.on_track_value.text()
            missed = self.missed_value.text()

            pos_color = POSITIVE_VALUE_COLOR()
            neg_color = NEGATIVE_VALUE_COLOR()

            html = f"""
            <html><head><meta charset='utf-8'><style>
                body {{ font-family: Arial, Helvetica, sans-serif; color: #222; }}
                .summary {{ margin-bottom: 16px; }}
                .kpi {{ padding: 8px 0; }}
                .positive {{ color: {pos_color}; font-weight: bold; }}
                .negative {{ color: {neg_color}; font-weight: bold; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; }}
                th {{ background:#f4f4f4; text-align: left; }}
                tr.on_track td {{ color: {pos_color}; }}
                tr.missed td {{ color: {neg_color}; }}
            </style></head><body>
            <h2>Payment Statistics - {month_name}</h2>
            <div class='summary'>
                <div class='kpi'>Total Collected: <span class='positive'>{collected}</span></div>
                <div class='kpi'>Projected Total: <span>{projected}</span></div>
                <div class='kpi'>Outstanding: <span class='negative'>{outstanding}</span></div>
                <div class='kpi'>On Track: <span class='positive'>{on_track}</span></div>
                <div class='kpi'>Missed Payments: <span class='negative'>{missed}</span></div>
            </div>
            <h3>Missed Payments Details</h3>
            <table>
                <tr><th>Acc</th><th>Name</th><th>Surname</th><th>Grade</th><th>Expected</th><th>Paid</th><th>Due</th><th>Last Payment</th></tr>
            """

            # Add rows from the dedicated missed tab table (with Expected, Paid, Due, Last Payment columns)
            for r in range(self.missed_tab_table.rowCount()):
                acc = self.missed_tab_table.item(r, 0).text() if self.missed_tab_table.item(r, 0) else ''
                name = self.missed_tab_table.item(r, 1).text() if self.missed_tab_table.item(r, 1) else ''
                surname = self.missed_tab_table.item(r, 2).text() if self.missed_tab_table.item(r, 2) else ''
                grade = self.missed_tab_table.item(r, 3).text() if self.missed_tab_table.item(r, 3) else ''
                expected = self.missed_tab_table.item(r, 4).text() if self.missed_tab_table.item(r, 4) else ''
                paid = self.missed_tab_table.item(r, 5).text() if self.missed_tab_table.item(r, 5) else ''
                due = self.missed_tab_table.item(r, 6).text() if self.missed_tab_table.item(r, 6) else ''
                last_payment = self.missed_tab_table.item(r, 7).text() if self.missed_tab_table.item(r, 7) else 'N/A'
                # status is in hidden column 8
                status_item = self.missed_tab_table.item(r, 8)
                status = status_item.text() if status_item else ''
                row_class = 'on_track' if status == 'on_track' else 'missed'
                # Color the due cell red for missed, otherwise let row-style apply
                due_style = f"color:{neg_color};" if status == 'missed' else ''
                html += f"<tr class='{row_class}'><td>{acc}</td><td>{name}</td><td>{surname}</td><td>{grade}</td><td style='text-align:right;'>{expected}</td><td style='text-align:right;'>{paid}</td><td style='text-align:right; {due_style}'>{due}</td><td style='text-align:right;'>{last_payment}</td></tr>"

            html += "</table></body></html>"

            # Print to PDF
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            # Ask for save location using a temp filename in user's Documents
            from pathlib import Path
            now = datetime.now()
            default_dir = Path.home() / 'Documents'
            outname = default_dir / f"payment_statistics_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
            # Use the path (Qt will not show dialog here; we just save to default location)
            printer.setOutputFileName(str(outname))

            doc = QTextDocument()
            doc.setHtml(html)
            doc.print_(printer)

            QMessageBox.information(self, "Export PDF", f"Payment statistics exported to:\n{outname}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export PDF: {e}")
