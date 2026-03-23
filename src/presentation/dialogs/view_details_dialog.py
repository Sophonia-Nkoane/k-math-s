from presentation.components.window_component import WindowComponent
from PySide6.QtWidgets import QVBoxLayout, QLabel, QMessageBox, QScrollArea, QWidget, QFormLayout, QGroupBox, QHBoxLayout
import logging
from presentation.styles import styles
from presentation.styles.colors import STATUS_ACTIVE_COLOR, STATUS_PAUSED_COLOR, TEXT_COLOR, SECONDARY_TEXT_COLOR
from presentation.components.buttons import ButtonFactory
from presentation.dialogs.payment_view_dialog import PaymentViewDialog
from utils.payment_schedule import format_due_days, format_scheduled_dates

class ViewDetailsDialog(WindowComponent):
    """Dialog for viewing detailed learner information."""
    def __init__(self, db_manager, acc_no, parent=None):
        super().__init__(parent, title="Learner Details")
        self.db_manager = db_manager
        self.acc_no = acc_no
        self.set_size(600, 450)
        
        # Update the field name and value styles to use theme-aware colors
        self.label_field_name_style = f"color: {SECONDARY_TEXT_COLOR()}; font-weight: normal;"
        self.label_field_value_style = f"color: {TEXT_COLOR()}; font-weight: bold;"
        
        self.setup_ui()
        self.populate_details()

    def setup_ui(self):
        """Sets up the dialog's UI components using global styles."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        # The scrollbar itself is styled by the parent WindowComponent.
        # We only need to make the scroll area's frame and viewport transparent.
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent; border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet(styles.CONTENT_WIDGET_STYLE)
        scroll_area.setWidget(content_widget)

        self.details_layout = QVBoxLayout(content_widget)
        self.details_layout.setSpacing(10)
        self.details_layout.setContentsMargins(15, 10, 15, 15)

        # Buttons area: Close and View Statement
        button_layout = QHBoxLayout()
        # View Statement button
        view_stmt_btn = ButtonFactory.create_view_button("View Statement")
        view_stmt_btn.clicked.connect(self._open_payment_view)
        # Close button
        close_button = ButtonFactory.create_cancel_button("Close")
        close_button.clicked.connect(self.accept)

        button_layout.addStretch()
        button_layout.addWidget(view_stmt_btn)
        button_layout.addWidget(close_button)

        self.add_widget(scroll_area)
        self.add_layout(button_layout)

    # ... The rest of the file (show_styled_message, create_info_label, populate_details, etc.) remains exactly the same as the previous correct version ...
    def show_styled_message(self, title, text, icon_type=QMessageBox.Icon.Critical):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon_type)
        ok_button = ButtonFactory.create_ok_button("OK")
        msg.addButton(ok_button, QMessageBox.ButtonRole.AcceptRole)
        msg.exec()

    def create_info_label(self, text, is_field_name=False):
        label = QLabel(text)
        style = self.label_field_name_style if is_field_name else self.label_field_value_style
        label.setStyleSheet(style)
        label.setWordWrap(True)
        return label

    def add_form_row(self, layout, field_name, value):
        layout.addRow(
            self.create_info_label(f"{field_name}:", True),
            self.create_info_label(str(value) or "N/A")
        )

    def populate_details(self):
        while self.details_layout.count():
            child = self.details_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        if not self.acc_no:
            self.details_layout.addWidget(self.create_info_label("No account number provided."))
            return

        try:
            query = """
                SELECT
                    s.acc_no, s.name, s.surname, s.date_of_birth, s.gender, s.country_code, s.contact_number, 
                    COALESCE(s.email, '') as email, s.subjects_count, s.payment_option, COALESCE(s.grade, 1) as grade,
                    p1.title AS p1_title, p1.name AS p1_name, p1.surname AS p1_surname, p1.country_code AS p1_code, 
                    p1.contact_number AS p1_contact, COALESCE(p1.email, '') AS p1_email,
                    p2.title AS p2_title, p2.name AS p2_name, p2.surname AS p2_surname, p2.country_code AS p2_code, 
                    p2.contact_number AS p2_contact, COALESCE(p2.email, '') AS p2_email,
                    g.title AS g_title, g.name AS g_name, g.surname AS g_surname, g.country_code AS g_code, 
                    g.contact_number AS g_contact, COALESCE(g.email, '') AS g_email,
                    s.is_new_learner, s.is_active, 
                    CAST(COALESCE(sp.due_day_of_month, 1) as INTEGER) as due_day_of_month,
                    COALESCE(sp.due_days_of_month, '') as due_days_of_month,
                    COALESCE(sp.scheduled_payment_dates, '') as scheduled_payment_dates,
                    pt.term_name, f.family_account_no
                FROM Learners s
                LEFT JOIN Parents p1 ON s.parent_id = p1.id LEFT JOIN Parents p2 ON s.parent2_id = p2.id
                LEFT JOIN Parents g ON s.guardian_id = g.id LEFT JOIN Families f ON s.family_id = f.family_id
                LEFT JOIN LearnerPayments sp ON s.acc_no = sp.learner_id LEFT JOIN PaymentTerms pt ON sp.term_id = pt.term_id
                WHERE s.acc_no = ?
            """
            learner_data = self.db_manager.execute_query(query, (self.acc_no,), fetchone=True)

            if not learner_data:
                self.details_layout.addWidget(self.create_info_label(f"No learner found with Account Number: {self.acc_no}"))
                return

            (acc_no_db, name, surname, dob, gender, s_code, s_contact, email, subjects,
             payment_opt, grade, p1_title, p1_name, p1_surname, p1_code, p1_contact, p1_email,
             p2_title, p2_name, p2_surname, p2_code, p2_contact, p2_email, g_title, g_name,
             g_surname, g_code, g_contact, g_email, is_new, is_active, due_day, due_days_raw, scheduled_dates_raw, term_name, family_acc_no) = learner_data

            self._add_details_group("Learner Information", [
                ("Acc No", acc_no_db), ("Name", name), ("Surname", surname),
                ("DOB", dob), ("Gender", gender), ("Contact", self.format_contact_for_display(s_code, s_contact)), ("Email", email)
            ])
            self._add_details_group("Parent 1 Information", [
                ("Title", p1_title), ("Name", p1_name), ("Surname", p1_surname),
                ("Contact", self.format_contact_for_display(p1_code, p1_contact)), ("Email", p1_email)
            ])
            if p2_name:
                self._add_details_group("Parent 2 Information", [
                    ("Title", p2_title), ("Name", p2_name), ("Surname", p2_surname),
                    ("Contact", self.format_contact_for_display(p2_code, p2_contact)), ("Email", p2_email)
                ])
            if g_name:
                self._add_details_group("Guardian Information", [
                    ("Title", g_title), ("Name", g_name), ("Surname", g_surname),
                    ("Contact", self.format_contact_for_display(g_code, g_contact)), ("Email", g_email)
                ])
            
            academic_group = QGroupBox("Academic & Payment")
            academic_group.setStyleSheet(styles.GROUP_BOX_STYLE)
            academic_layout = QFormLayout(academic_group)
            
            self.add_form_row(academic_layout, "Grade", grade)
            self.add_form_row(academic_layout, "Subjects", subjects)
            self.add_form_row(academic_layout, "Payment Option", payment_opt)
            self.add_form_row(academic_layout, "Payment Term", term_name)
            schedule_display = format_scheduled_dates(scheduled_dates_raw) or format_due_days(due_days_raw, due_day)
            self.add_form_row(academic_layout, "Payment Schedule", schedule_display)
            self.add_form_row(academic_layout, "Calculated Fee", self.get_current_fees_display(payment_opt, subjects, grade, self.acc_no))
            if family_acc_no: self.add_form_row(academic_layout, "Family Account", family_acc_no)

            status_label_value = QLabel("Active" if is_active else "Paused")
            status_color = STATUS_ACTIVE_COLOR() if is_active else STATUS_PAUSED_COLOR()
            status_label_value.setStyleSheet(styles.STATUS_LABEL_STYLE_TEMPLATE.format(color=status_color))
            academic_layout.addRow(self.create_info_label("Status:", True), status_label_value)
            
            if not is_active:
                self.add_form_row(academic_layout, "Pause Reason", self._get_pause_reason())
            
            self.details_layout.addWidget(academic_group)

        except Exception as e:
             self.show_styled_message("Error", f"An unexpected error occurred while loading details: {e}")

    def _add_details_group(self, title, details_list):
        group = QGroupBox(title)
        group.setStyleSheet(styles.GROUP_BOX_STYLE)
        layout = QFormLayout(group)
        for name, value in details_list:
            self.add_form_row(layout, name, value)
        self.details_layout.addWidget(group)

    def _get_pause_reason(self):
        try:
            query = "SELECT reason FROM Archive WHERE learner_acc_no = ? AND reactivation_date IS NULL ORDER BY archive_date DESC LIMIT 1"
            reason = self.db_manager.execute_query(query, (self.acc_no,), fetchone=True)
            return reason[0] if reason and reason[0] else "N/A"
        except Exception as e:
            logging.error(f"Error fetching pause reason for {self.acc_no}: {e}")
            return "Error"

    def _open_payment_view(self):
        """Open the PaymentViewDialog for this learner (or its family) from the details dialog."""
        try:
            # Prefer using dialog_service from parent window if available
            parent_window = self.parent() if self.parent() is not None else None
            # Attempt to find family_id from DB
            family_id = None
            try:
                q = "SELECT family_id FROM Learners WHERE acc_no = ?"
                row = self.db_manager.execute_query(q, (self.acc_no,), fetchone=True)
                if row and row[0] is not None:
                    family_id = row[0]
            except Exception:
                family_id = None

            if parent_window and hasattr(parent_window, 'dialog_service') and parent_window.dialog_service:
                parent_window.dialog_service.show_payment_view_dialog(self.acc_no, family_id)
            else:
                dlg = PaymentViewDialog(self.db_manager, self.acc_no, family_id, parent=parent_window)
                dlg.exec()
        except Exception as e:
            logging.error(f"Failed to open payment view for {self.acc_no}: {e}")
            self.show_styled_message("Error", f"Could not open statement: {e}")

    def format_contact_for_display(self, country_code, contact_number):
        if not contact_number: return "N/A"
        prefix_map = {"ZA": "+27", "UK": "+44", "US": "+1"}
        prefix = prefix_map.get(str(country_code).upper(), country_code)
        return f"{prefix} {contact_number}"

    def get_current_fees_display(self, payment_option, subjects_count, grade, learner_acc_no):
        if not all([payment_option, subjects_count is not None, grade is not None]): return "N/A"
        try:
            base_fee_query = "SELECT monthly_fee FROM PaymentOptions WHERE option_name = ? AND subjects_count = ? AND grade = ?"
            result = self.db_manager.execute_query(base_fee_query, (payment_option, subjects_count, grade), fetchone=True)
            if result and result[0] is not None:
                return f"R {float(result[0]):.2f}"
            return "R 0.00"
        except Exception as e:
            logging.error(f"Fee calculation error in ViewDetails for {learner_acc_no}: {e}")
            return "Error"
