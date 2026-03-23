from PySide6.QtWidgets import (QVBoxLayout, QTableWidgetItem, QHeaderView,
                            QMessageBox, QHBoxLayout, QLabel)
from PySide6.QtCore import Qt
import sqlite3
import logging
from presentation.components.table import Table
from presentation.components.buttons import ButtonFactory
from presentation.components.rounded_field import RoundedPlainTextField, RoundedSpinner
from presentation.styles.colors import TEXT_COLOR
from presentation.components.window_component import WindowComponent

class IndividualDiscountsDialog(WindowComponent):
    """Dialog for managing individual learner discount rates by grade."""

    def __init__(self, db_manager, current_user_id=None, parent=None):
        super().__init__(parent, "Individual Learner Discounts")
        self.db_manager = db_manager
        self.current_user_id = current_user_id
        self.logger = logging.getLogger(self.__class__.__name__)
        self.set_size(800, 600)

        self.table_columns = [
            {"name": "Learner", "width": None, "resize_mode": QHeaderView.ResizeMode.Stretch},
            {"name": "Family Account", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Payment Mode", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents},
            {"name": "Discount %", "width": None, "resize_mode": QHeaderView.ResizeMode.ResizeToContents}
        ]

        self.setup_ui()
        self.load_discounts()

    def setup_ui(self):
        layout = self.get_container_layout()

        search_layout = QHBoxLayout()
        self.search_entry = RoundedPlainTextField("Search by learner name...")
        self.search_entry.textChanged.connect(self.filter_discounts)
        search_layout.addWidget(self.search_entry)

        layout.addLayout(search_layout)

        table = Table(self, self.table_columns)
        self.discount_table = table.get_table()
        layout.addWidget(self.discount_table)

        button_layout = QHBoxLayout()

        edit_button = ButtonFactory.create_update_button("Edit Discount")
        edit_button.clicked.connect(self.edit_discount)

        close_button = ButtonFactory.create_close_button("Close")
        close_button.clicked.connect(self.accept)

        button_layout.addWidget(edit_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def show_styled_message(self, title, text, icon_type=QMessageBox.Icon.Information):
         if hasattr(self.parent(), 'dialog_service'):
             self.parent().dialog_service.show_styled_message(title, text, icon_type)
         else:
             msg = QMessageBox(self)
             msg.setWindowTitle(title)
             msg.setText(text)
             msg.setIcon(icon_type)
             ok_button = msg.addButton(QMessageBox.StandardButton.Ok)
             ButtonFactory.style_dialog_buttons(msg)
             msg.exec()

    def load_discounts(self):
        try:
            self.discount_table.setRowCount(0)
            query = """
                SELECT s.learner_id, s.first_name, s.last_name,
                       f.family_account_no, f.payment_mode,
                       COALESCE(s.individual_discount, f.discount_percentage) as discount
                FROM Learners s
                JOIN Families f ON s.family_id = f.family_account_no
                ORDER BY s.last_name, s.first_name
            """
            discounts = self.db_manager.execute_query(query, fetchall=True)

            self.discount_table.setRowCount(len(discounts))
            for row, discount in enumerate(discounts):
                learner_id, fname, lname, acc_no, mode, disc = discount

                learner_item = self.create_table_item(f"{fname} {lname}")
                learner_item.setData(Qt.ItemDataRole.UserRole, learner_id)
                self.discount_table.setItem(row, 0, learner_item)

                items = [
                    self.create_table_item(acc_no),
                    self.create_table_item(mode),
                    self.create_table_item(f"{disc}%" if disc is not None else "0%", Qt.AlignmentFlag.AlignCenter)
                ]

                for col, item in enumerate(items):
                    self.discount_table.setItem(row, col + 1, item)

        except sqlite3.Error as e:
             self.show_styled_message(
                "Database Error",
                f"Error loading discounts: {e}",
                QMessageBox.Icon.Critical
            )

    def create_table_item(self, text, alignment=Qt.AlignmentFlag.AlignLeft):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def filter_discounts(self):
        search_text = self.search_entry.text().lower()

        for row in range(self.discount_table.rowCount()):
            learner_name_item = self.discount_table.item(row, 0)
            if learner_name_item:
                learner_name = learner_name_item.text().lower()
                self.discount_table.setRowHidden(row, search_text not in learner_name)

    def edit_discount(self):
        selected_items = self.discount_table.selectedItems()
        if not selected_items:
            self.show_styled_message(
                "Selection Required",
                "Please select a learner to edit their discount.",
                QMessageBox.Icon.Warning
            )
            return

        row = selected_items[0].row()
        learner_id_item = self.discount_table.item(row, 0)
        if learner_id_item:
            learner_id = learner_id_item.data(Qt.ItemDataRole.UserRole)
        else:
             self.show_styled_message(
                "Error",
                "Could not retrieve learner ID for selected row.",
                QMessageBox.Icon.Critical
            )
             return

        current_discount_item = self.discount_table.item(row, 3)
        current_discount = 0.0
        if current_discount_item:
            try:
                discount_text = current_discount_item.text().rstrip('%').strip()
                current_discount = float(discount_text) if discount_text else 0.0
            except ValueError:
                self.logger.warning(f"Could not parse discount from table text: '{current_discount_item.text()}'")
                current_discount = 0.0

        dialog = DiscountEditDialog(learner_id, int(current_discount), self.db_manager, self)
        if dialog.exec() == WindowComponent.DialogCode.Accepted:
            self.load_discounts()

class DiscountEditDialog(WindowComponent):
    def __init__(self, learner_id, current_discount, db_manager, parent=None):
        super().__init__(parent, "Edit Learner Discount")
        self.learner_id = learner_id
        self.db_manager = db_manager

        self.setModal(True)
        self.set_size(300, 150)

        layout = self.get_container_layout()

        discount_layout = QHBoxLayout()
        discount_label = QLabel("New Discount Percentage:")
        discount_label.setStyleSheet(f"color: {TEXT_COLOR()};")

        self.discount_spin = RoundedSpinner(minimum=0, maximum=100)
        self.discount_spin.setValue(int(current_discount))
        self.discount_spin.setSuffix("%")

        discount_layout.addWidget(discount_label)
        discount_layout.addWidget(self.discount_spin)

        layout.addLayout(discount_layout)

        button_layout = QHBoxLayout()

        save_button = ButtonFactory.create_save_button("Save")
        save_button.clicked.connect(self.save_discount)

        cancel_button = ButtonFactory.create_cancel_button("Cancel")
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def save_discount(self):
        try:
            new_discount = self.discount_spin.value()
            query = """
                UPDATE Learners
                SET individual_discount = ?
                WHERE learner_id = ?
            """
            self.db_manager.execute_query(query, (new_discount, self.learner_id))
            self.accept()

        except sqlite3.Error as e:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText(f"Failed to update discount: {str(e)}")
            msg.setIcon(QMessageBox.Icon.Critical)
            ButtonFactory.style_dialog_buttons(msg)
            msg.exec()
