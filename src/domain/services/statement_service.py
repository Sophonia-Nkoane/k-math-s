# src/domain/services/statement_service.py

import os
import re
import logging
from datetime import datetime
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import QApplication, QLabel, QHBoxLayout, QMessageBox, QDialog, QVBoxLayout

from utils.settings_manager import SettingsManager
from presentation.dialogs.statement import generate_learner_statement_html, generate_family_statement_html
from presentation.statement_pdf import (
    build_statement_pdf_bytes,
    render_statement_pdf_documents_to_printer,
    render_statement_pdf_bytes_to_printer,
    save_statement_pdf_bytes,
)
from presentation.components.window_component import WindowComponent
from presentation.components.buttons import ButtonFactory
from presentation.components.success_dialog import SuccessDialog
from presentation.styles.colors import TEXT_COLOR

class StatementService:
    def __init__(self, main_window, learner_repository, family_repository, payment_repository, logo_path, db_manager):
        self.main_window = main_window
        self.learner_repository = learner_repository
        self.family_repository = family_repository
        self.payment_repository = payment_repository
        self.logo_path = logo_path
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def print_all_statements(self, parent, items_to_print):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        print_dialog = QPrintDialog(printer, parent)
        if print_dialog.exec() == QDialog.DialogCode.Accepted:
            self.print_all_statements_internal(printer, items_to_print)

    def print_selected_statement(self, parent, acc_no, family_id):
        print_html = ""
        statement_type = ""
        settings_manager = SettingsManager()
        statement_settings = settings_manager.load_statement_settings()

        if family_id:
            print_html = generate_family_statement_html(self.main_window, family_id, statement_settings)
            statement_type = "family"
        else:
            print_html = generate_learner_statement_html(self.main_window, acc_no, statement_settings)
            statement_type = "individual learner"

        if not print_html or "Error" in print_html:
            parent.show_styled_message("Error", f"Could not generate the {statement_type} statement.", QMessageBox.Icon.Critical)
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        print_dialog = QPrintDialog(printer, parent)
        if print_dialog.exec() == QDialog.DialogCode.Accepted:
            render_statement_pdf_bytes_to_printer(build_statement_pdf_bytes(print_html), printer)
            parent.show_styled_message("Print", f"{statement_type.capitalize()} statement sent to printer.")

    def save_all_to_pdf(self, parent, family_groups, individual_learners_data):
        num_items = len(family_groups) + len(individual_learners_data)
        
        if num_items == 0:
            parent.show_styled_message("Save All to PDF", "No active learners found to generate statements for.")
            return

        progress_dialog = WindowComponent(parent, "Save All Statements PDF")
        progress_dialog.set_size(450, 150)
        
        progress_label = QLabel("Processing...")
        progress_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        progress_counter = QLabel("0 / 0 items")
        progress_counter.setStyleSheet(f"color: {TEXT_COLOR()};")
        
        cancel_button = ButtonFactory.create_cancel_button("Cancel")
        cancel_button.clicked.connect(progress_dialog.reject)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addStretch()
        
        progress_dialog.add_widget(progress_label)
        progress_dialog.add_widget(progress_counter)
        progress_dialog.add_layout(button_layout)
        
        progress_dialog.show()

        saved_count = 0
        processed_count = 0
        now = datetime.now()
        now_str = now.strftime('%Y%m%d')
        base_dir_statements = os.path.join(os.path.expanduser("~"), "Documents", f"LearnerStatements/{now.year}")
        base_dir_families = os.path.join(base_dir_statements, f"FamilyStatements {now.strftime('%Y')}")
        base_dir_individuals = os.path.join(base_dir_statements, f"IndividualStatements {now.strftime('%Y')}")
        month_name = now.strftime("%B %Y")

        os.makedirs(base_dir_families, exist_ok=True)
        os.makedirs(base_dir_individuals, exist_ok=True)

        month_dir_families = os.path.join(base_dir_families, month_name)
        month_dir_individuals = os.path.join(base_dir_individuals, month_name)
        os.makedirs(month_dir_families, exist_ok=True)
        os.makedirs(month_dir_individuals, exist_ok=True)

        for family_id, learner_list in family_groups.items():
            processed_count += 1
            if not progress_dialog.isVisible(): break
            
            progress_label.setText(f"Processing Family ID: {family_id}...")
            progress_counter.setText(f"{processed_count} of {num_items} items")
            QApplication.processEvents()

            try:
                settings_manager = SettingsManager()
                statement_settings = settings_manager.load_statement_settings()
                html = generate_family_statement_html(self.main_window, family_id, statement_settings)
                if html and "Error" not in html:
                    learner_details_part = ""
                    sorted_learner_list = sorted(learner_list, key=lambda s: (s.get('surname', ''), s.get('name', '')))

                    if sorted_learner_list:
                        s1_name = sorted_learner_list[0].get('name', 'Unknown')
                        s1_surname = sorted_learner_list[0].get('surname', 'Unknown')
                        learner_details_part = f"{s1_name}_{s1_surname}"
                        if len(sorted_learner_list) == 2:
                            s2_name = sorted_learner_list[1].get('name', 'Unknown')
                            s2_surname = sorted_learner_list[1].get('surname', 'Unknown')
                            learner_details_part += f"_and_{s2_name}_{s2_surname}"
                        elif len(sorted_learner_list) > 2:
                            learner_details_part += "_and_others"

                    if learner_details_part:
                         filename = f"Family_{learner_details_part}_ID{family_id}_{now_str}.pdf"
                    else:
                         filename = f"Family_ID{family_id}_{now_str}.pdf"

                    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
                    save_path = os.path.join(month_dir_families, filename)
                    save_statement_pdf_bytes(build_statement_pdf_bytes(html), save_path)
                    saved_count += 1
                    self.logger.info(f"Successfully saved family PDF: {filename}")
                else:
                    self.logger.warning(f"Skipped family {family_id}: HTML generation failed or contains errors")

            except Exception as e:
                self.logger.error(f"Error saving family statement {family_id}: {e}", exc_info=True)

        for learner_data in individual_learners_data:
            processed_count += 1
            if not progress_dialog.isVisible(): break

            acc_no = learner_data['acc_no']
            name = learner_data['name']
            surname = learner_data['surname']
            grade = learner_data['grade']

            progress_label.setText(f"Processing Learner: {name} {surname} (Grade {grade})...")
            progress_counter.setText(f"{processed_count} of {num_items} items")
            QApplication.processEvents()

            try:
                settings_manager = SettingsManager()
                statement_settings = settings_manager.load_statement_settings()
                html = generate_learner_statement_html(self.main_window, acc_no, statement_settings)
                if html and "Error" not in html:
                    filename = f"Learner_{name}_{surname}_Grade{grade}_{acc_no}_{now_str}.pdf"
                    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
                    save_path = os.path.join(month_dir_individuals, filename)
                    save_statement_pdf_bytes(build_statement_pdf_bytes(html), save_path)
                    saved_count += 1
                    self.logger.info(f"Successfully saved individual PDF: {filename}")
                else:
                    self.logger.warning(f"Skipped learner {acc_no}: HTML generation failed or contains errors")

            except Exception as e:
                self.logger.error(f"Error saving individual statement {acc_no}: {e}", exc_info=True)

        progress_dialog.close()
        parent.show_styled_message("Success", 
            f"Successfully saved {saved_count} statement(s) to PDF.\nLocation: {base_dir_statements}")

    def print_all_statements_internal(self, printer, items_to_print):
        """Internal method to handle batch printing of statements."""
        try:
            progress = WindowComponent(self, "Printing Statements")
            progress.setFixedSize(400, 100)
            
            progress_layout = QVBoxLayout()
            progress_label = QLabel("Printing statements...")
            progress_label.setStyleSheet(f"color: {TEXT_COLOR()};")
            progress_layout.addWidget(progress_label)
            
            progress.add_layout(progress_layout)
            progress.show()
            QApplication.processEvents()

            settings_manager = SettingsManager()
            statement_settings = settings_manager.load_statement_settings()

            pdf_documents = []
            for i, family_id in enumerate(items_to_print['families']):
                progress_label.setText(f"Printing family statement {i+1}/{len(items_to_print['families'])}...")
                QApplication.processEvents()
                
                html = generate_family_statement_html(self.main_window, family_id, statement_settings)
                if html and "Error" not in html:
                    pdf_documents.append(build_statement_pdf_bytes(html))
            
            for i, acc_no in enumerate(items_to_print['individuals']):
                progress_label.setText(f"Printing individual statement {i+1}/{len(items_to_print['individuals'])}...")
                QApplication.processEvents()
                
                html = generate_learner_statement_html(self.main_window, acc_no, statement_settings)
                if html and "Error" not in html:
                    pdf_documents.append(build_statement_pdf_bytes(html))

            if not pdf_documents:
                raise RuntimeError("No statements were available to print.")

            render_statement_pdf_documents_to_printer(pdf_documents, printer)
            
            progress.close()
            SuccessDialog.show_success(self, "All statements sent to printer.")
        except Exception as e:
            self.main_window.show_styled_message("Error", f"Error printing statements: {str(e)}", QMessageBox.Icon.Critical)
