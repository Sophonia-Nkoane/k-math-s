from PySide6.QtWidgets import (QTableWidgetItem, QMessageBox, QHeaderView, QLabel,
                            QHBoxLayout, QFileDialog)
from PySide6.QtCore import Qt, QDate
import csv
from datetime import datetime
from core.desktop_shared_services import get_desktop_shared_services
from presentation.components.window_component import WindowComponent
from presentation.components.table import Table
from presentation.components.rounded_field import RoundedCalendarDropdown, RoundedDropdown
from presentation.components.buttons import ButtonFactory
from presentation.styles.colors import TEXT_COLOR

class AuditLogDialog(WindowComponent):
    """Dialog for viewing the audit log."""
    def __init__(self, db_manager, parent=None):
        super().__init__(parent, title="Audit Log")
        self.db_manager = db_manager
        self.shared_services = get_desktop_shared_services(db_manager)
        self.set_size(1000, 600)
        
        # Initialize date range to last 30 days
        today = QDate.currentDate()
        self.start_date = RoundedCalendarDropdown()
        self.start_date.setDate(today.addDays(-30))
        self.end_date = RoundedCalendarDropdown()
        self.end_date.setDate(today)
        
        self.setup_ui()
        self.load_log_entries()

    def setup_ui(self):
        """Sets up the dialog's UI components."""
        # Filter controls
        filter_layout = QHBoxLayout()
        
        # Date range filter
        date_filter_layout = QHBoxLayout()
        from_label = QLabel("From:")
        from_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        date_filter_layout.addWidget(from_label)
        date_filter_layout.addWidget(self.start_date)
        to_label = QLabel("To:")
        to_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        date_filter_layout.addWidget(to_label)
        date_filter_layout.addWidget(self.end_date)
        filter_layout.addLayout(date_filter_layout)
        
        filter_layout.addSpacing(20)
        
        # Action type filter using RoundedDropdown
        self.action_combo = RoundedDropdown()
        self.action_combo.addItem("All Actions")
        self.action_combo.addItems([
            "LOGIN", "LOGOUT",
            "CREATE_USER", "UPDATE_USER", "DELETE_USER",
            "CREATE_LEARNER", "UPDATE_LEARNER", "DELETE_LEARNER",
            "CREATE_FAMILY", "UPDATE_FAMILY", "DELETE_FAMILY",
            "CREATE_PAYMENT", "DELETE_PAYMENT",
            "CREATE_PAYMENT_OPTION", "UPDATE_PAYMENT_OPTION", "DELETE_PAYMENT_OPTION",
            "CREATE_PAYMENT_TERM", "UPDATE_PAYMENT_TERM", "DELETE_PAYMENT_TERM",
            "RECORD_ATTENDANCE"
        ])
        action_type_label = QLabel("Action Type:")
        action_type_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        filter_layout.addWidget(action_type_label)
        filter_layout.addWidget(self.action_combo)
        
        # User filter using RoundedDropdown
        self.user_combo = RoundedDropdown()
        self.user_combo.addItem("All Users")
        self.load_users()
        user_label = QLabel("User:")
        user_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        filter_layout.addWidget(user_label)
        filter_layout.addWidget(self.user_combo)
        
        # Apply filters button
        apply_button = ButtonFactory.create_ok_button("Apply Filters")
        apply_button.clicked.connect(self.load_log_entries)
        filter_layout.addWidget(apply_button)
        
        # Log entries table
        log_columns = [
            {"name": "Timestamp", "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "User", "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Action", "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Object", "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Details", "resize_mode": QHeaderView.ResizeMode.Stretch}
        ]
        
        self.table_component = Table(self, columns=log_columns)
        self.log_table = self.table_component.get_table()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        export_button = ButtonFactory.create_save_button("Export to CSV")
        export_button.clicked.connect(self.export_log)
        
        refresh_button = ButtonFactory.create_refresh_button("Refresh")
        refresh_button.clicked.connect(self.load_log_entries)
        
        close_button = ButtonFactory.create_close_button("Close")
        close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(export_button)
        button_layout.addWidget(refresh_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        # Add layouts to window component
        self.add_layout(filter_layout)
        self.add_widget(self.log_table)
        self.add_layout(button_layout)
        
        # Connect date change signals to refresh
        self.start_date.dateChanged.connect(self.load_log_entries)
        self.end_date.dateChanged.connect(self.load_log_entries)

    def load_users(self):
        """Loads the list of users into the user filter combo box."""
        try:
            users = self.shared_services.admin_use_case.list_users()
            
            self.user_combo.clear()
            self.user_combo.addItem("All Users")
            for user in users:
                self.user_combo.addItem(str(user.get("username") or ""))
                
        except Exception as e:
            self.parent().dialog_service.show_styled_message(
                "Error",
                f"Error loading users: {e}",
                QMessageBox.Icon.Critical
            )

    def load_log_entries(self):
        """Loads log entries based on current filters."""
        try:
            entries = self.shared_services.audit_use_case.list_audit(
                start_date=self.start_date.date().toString("yyyy-MM-dd"),
                end_date=self.end_date.date().toString("yyyy-MM-dd"),
                action_type=None if self.action_combo.currentText() == "All Actions" else self.action_combo.currentText(),
                username=None if self.user_combo.currentText() == "All Users" else self.user_combo.currentText(),
            )
            
            self.log_table.setRowCount(len(entries))
            for row, entry in enumerate(entries):
                timestamp = str(entry.get("timestamp") or "")
                user = str(entry.get("username") or "System")
                action = str(entry.get("action_type") or "")
                object_type = str(entry.get("object_type") or "").strip()
                object_id = str(entry.get("object_id") or "").strip()
                details = str(entry.get("details") or "-")
                entity = f"{object_type}: {object_id}" if object_type and object_id else (object_type or object_id or "-")

                try:
                    formatted_timestamp = datetime.fromisoformat(timestamp.replace(" ", "T", 1)).strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    formatted_timestamp = timestamp or "-"
                
                items = [
                    self.create_table_item(formatted_timestamp, Qt.AlignmentFlag.AlignCenter),
                    self.create_table_item(user),
                    self.create_table_item(action),
                    self.create_table_item(entity),
                    self.create_table_item(details)
                ]
                
                for col, item in enumerate(items):
                    self.log_table.setItem(row, col, item)
            
            # Auto-resize columns to content
            self.log_table.resizeColumnsToContents()
            
        except Exception as e:
            self.parent().dialog_service.show_styled_message(
                "Error",
                f"Error loading audit log: {e}",
                QMessageBox.Icon.Critical
            )

    def create_table_item(self, text, alignment=Qt.AlignmentFlag.AlignLeft):
        """Creates a table item with the specified text and alignment."""
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        return item

    def export_log(self):
        """Exports the current log entries to a CSV file."""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Export Audit Log",
                "",
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if filename:
                if not filename.lower().endswith('.csv'):
                    filename += '.csv'
                    
                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write headers
                    headers = []
                    for col in range(self.log_table.columnCount()):
                        headers.append(self.log_table.horizontalHeaderItem(col).text())
                    writer.writerow(headers)
                    
                    # Write data
                    for row in range(self.log_table.rowCount()):
                        row_data = []
                        for col in range(self.log_table.columnCount()):
                            item = self.log_table.item(row, col)
                            row_data.append(item.text() if item else '')
                        writer.writerow(row_data)
                        
                self.parent().dialog_service.show_styled_message(
                    "Export Success",
                    f"Audit log exported to {filename}"
                )
                
        except Exception as e:
            self.parent().dialog_service.show_styled_message(
                "Export Error",
                f"Error exporting audit log: {e}",
                QMessageBox.Icon.Critical
            )
