from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, 
                               QComboBox, QTextEdit, QMessageBox,
                               QFileDialog, QCheckBox, QRadioButton,
                               QButtonGroup, QGroupBox, QProgressDialog)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont, QIcon
import webbrowser
import logging

from utils.class_list_generator import ClassListGenerator
from presentation.components.window_component import WindowComponent
from presentation.components.buttons import ButtonFactory
from presentation.styles.colors import TEXT_COLOR, PRIMARY_COLOR, FIELD_BACKGROUND, FIELD_BORDER_COLOR
from presentation.styles import styles


class ClassListGeneratorThread(QThread):
    """Thread for generating class lists without blocking UI."""
    finished = Signal(str)
    error = Signal(str)
    
    def __init__(self, db_manager, grade, include_learners=True, month=None, year=None):
        super().__init__()
        self.db_manager = db_manager
        self.grade = grade
        self.include_learners = include_learners
        self.month = month
        self.year = year
        self.is_school_list = False
        
    def run(self):
        try:
            generator = ClassListGenerator()
            
            if self.is_school_list:
                # Generate whole school list
                output_path = generator.generate_school_list(self.db_manager)
            elif self.include_learners:
                output_path = generator.generate_from_database(self.db_manager, self.grade)
            else:
                output_path = generator.generate_class_list(self.grade)
            
            self.finished.emit(output_path)
            
        except Exception as e:
            self.error.emit(str(e))


class SchoolListGeneratorThread(QThread):
    """Thread for generating school lists without blocking UI."""
    finished = Signal(str)
    error = Signal(str)
    
    def __init__(self, db_manager, include_inactive=False, grades=None):
        super().__init__()
        self.db_manager = db_manager
        self.include_inactive = include_inactive
        self.grades = grades
        
    def run(self):
        try:
            generator = ClassListGenerator()
            output_path = generator.generate_school_list(
                self.db_manager, 
                include_inactive=self.include_inactive,
                grades=self.grades
            )
            self.finished.emit(output_path)
            
        except Exception as e:
            self.error.emit(str(e))


class ClassListDialog(WindowComponent):
    """Dialog for generating class lists and school lists."""
    
    def __init__(self, parent=None, db_manager=None):
        super().__init__(parent, "Generate Class List", size=(600, 650))
        self.db_manager = db_manager
        self.setModal(True)
        self.progress_dialog = None
        
        self.setup_ui()
        self.load_grades()
        
    def setup_ui(self):
        """Setup the user interface with improved styling."""
        layout = self.container_layout
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title section
        title_label = QLabel("Class List Generator")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {PRIMARY_COLOR()};")
        layout.addWidget(title_label)
        
        # Divider
        divider = QLabel()
        divider.setStyleSheet(f"background-color: {PRIMARY_COLOR()}; height: 2px;")
        divider.setFixedHeight(2)
        layout.addWidget(divider)
        
        layout.addSpacing(10)
        
        # List type selection with better styling
        type_group = QGroupBox("📋 List Type")
        type_group.setStyleSheet(styles.GROUP_BOX_STYLE if hasattr(styles, 'GROUP_BOX_STYLE') else "")
        type_layout = QVBoxLayout(type_group)
        type_layout.setSpacing(10)
        
        self.list_type_group = QButtonGroup(self)
        
        self.single_grade_radio = QRadioButton("Single Grade Class List")
        self.single_grade_radio.setChecked(True)
        self.single_grade_radio.setToolTip("Generate a list for a specific grade")
        self.list_type_group.addButton(self.single_grade_radio, 0)
        type_layout.addWidget(self.single_grade_radio)
        
        self.whole_school_radio = QRadioButton("Whole School List (All Grades)")
        self.whole_school_radio.setToolTip("Generate a comprehensive list for all grades")
        self.list_type_group.addButton(self.whole_school_radio, 1)
        type_layout.addWidget(self.whole_school_radio)
        
        self.list_type_group.buttonClicked.connect(self._on_list_type_changed)
        layout.addWidget(type_group)
        
        # Grade selection (for single grade) with improved styling
        self.grade_group = QGroupBox("🎓 Grade Selection")
        self.grade_group.setStyleSheet(styles.GROUP_BOX_STYLE if hasattr(styles, 'GROUP_BOX_STYLE') else "")
        grade_layout = QHBoxLayout(self.grade_group)
        grade_layout.setSpacing(10)
        
        grade_label = QLabel("Select Grade:")
        grade_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        grade_layout.addWidget(grade_label)
        
        self.grade_combo = QComboBox()
        self.grade_combo.setMinimumWidth(150)
        grade_layout.addWidget(self.grade_combo)
        grade_layout.addStretch()
        
        layout.addWidget(self.grade_group)
        
        # Options with icons and better organization
        options_group = QGroupBox("⚙️ Options")
        options_group.setStyleSheet(styles.GROUP_BOX_STYLE if hasattr(styles, 'GROUP_BOX_STYLE') else "")
        options_layout = QVBoxLayout(options_group)
        options_layout.setSpacing(12)
        
        self.include_learners_cb = QCheckBox("✓ Include existing learner names")
        self.include_learners_cb.setChecked(True)
        self.include_learners_cb.setToolTip("Uncheck to generate empty template with only signature cells")
        self.include_learners_cb.setStyleSheet(f"color: {TEXT_COLOR()};")
        options_layout.addWidget(self.include_learners_cb)
        
        self.include_inactive_cb = QCheckBox("⏸ Include inactive/paused learners")
        self.include_inactive_cb.setToolTip("Include learners with paused billing in the list")
        self.include_inactive_cb.setStyleSheet(f"color: {TEXT_COLOR()};")
        options_layout.addWidget(self.include_inactive_cb)
        
        layout.addWidget(options_group)
        
        # Preview area with better styling
        preview_label = QLabel("📄 Preview:")
        preview_font = QFont()
        preview_font.setBold(True)
        preview_label.setFont(preview_font)
        preview_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        layout.addWidget(preview_label)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(140)
        self.preview_text.setStyleSheet(
            f"""QTextEdit {{
                background-color: {FIELD_BACKGROUND()};
                border: 1px solid {FIELD_BORDER_COLOR()};
                border-radius: 5px;
                padding: 10px;
                color: {TEXT_COLOR()};
                font-family: 'Courier New';
            }}"""
        )
        layout.addWidget(self.preview_text)
        
        layout.addSpacing(5)
        
        # Buttons with improved layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.preview_btn = ButtonFactory.create_view_button("👁 Preview")
        self.preview_btn.clicked.connect(self.preview_class_list)
        self.preview_btn.setMinimumWidth(120)
        button_layout.addWidget(self.preview_btn)
        
        self.generate_btn = ButtonFactory.create_add_button("▶ Generate & Open")
        self.generate_btn.clicked.connect(self.generate_class_list)
        self.generate_btn.setMinimumWidth(140)
        button_layout.addWidget(self.generate_btn)
        
        self.save_btn = ButtonFactory.create_save_button("💾 Generate & Save")
        self.save_btn.clicked.connect(self.save_class_list)
        self.save_btn.setMinimumWidth(140)
        button_layout.addWidget(self.save_btn)
        
        button_layout.addStretch()
        
        close_btn = ButtonFactory.create_cancel_button("✕ Close")
        close_btn.clicked.connect(self.close)
        close_btn.setMinimumWidth(100)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Initial state
        self._on_list_type_changed()
        
    def _on_list_type_changed(self):
        """Handle list type selection change."""
        is_single_grade = self.single_grade_radio.isChecked()
        
        # Enable/disable grade selection
        self.grade_group.setEnabled(is_single_grade)
        self.include_learners_cb.setEnabled(is_single_grade)
        
        # Update preview
        self._update_preview_text()
        
    def _update_preview_text(self):
        """Update the preview text based on current selection."""
        if self.whole_school_radio.isChecked():
            options = []
            if self.include_inactive_cb.isChecked():
                options.append("✓ Include inactive learners")
            else:
                options.append("✗ Exclude inactive learners")
            
            options_text = "\n".join(options)
            
            self.preview_text.setPlainText(
                "📊 WHOLE SCHOOL CLASS LIST\n"
                "=" * 50 + "\n\n"
                "📝 Output Structure:\n"
                "  • School summary page\n"
                "  • Grade-by-grade organization\n"
                "  • Learner count per grade\n\n"
                "👥 Data Included:\n"
                "  • Learner names and surnames\n"
                "  • Grade assignments\n"
                "  • Attendance signature columns (by week)\n\n"
                "⚙️ Current Settings:\n"
                f"  {options_text}\n\n"
                "💾 Output: HTML file with professional formatting"
            )
        else:
            grade = self.grade_combo.currentText() or "1"
            options = []
            
            if self.include_learners_cb.isChecked():
                options.append("✓ Include learner names")
            else:
                options.append("✗ Exclude learner names")
            
            if self.include_inactive_cb.isChecked():
                options.append("✓ Include inactive learners")
            else:
                options.append("✗ Exclude inactive learners")
            
            options_text = "\n".join(options)
            
            self.preview_text.setPlainText(
                f"📊 GRADE {grade} CLASS LIST\n"
                "=" * 50 + "\n\n"
                "📝 Output Structure:\n"
                "  • Grade header with title\n"
                "  • Learner roster (if enabled)\n"
                "  • Attendance signature columns\n\n"
                "👥 Data Columns:\n"
                "  • Name & Surname\n"
                "  • Weekly attendance signatures\n"
                "  • Space for teacher notes\n\n"
                "⚙️ Current Settings:\n"
                f"  {options_text}\n\n"
                "💾 Output: HTML file ready to print or save as PDF"
            )
        
    def load_grades(self):
        """Load available grades from database."""
        try:
            if not self.db_manager:
                grades = [str(i) for i in range(1, 13)]
                self.grade_combo.addItems(grades)
                return
                
            query = "SELECT DISTINCT grade FROM Learners WHERE is_active = 1 ORDER BY grade"
            grades_data = self.db_manager.execute_query(query, fetchall=True)
            
            if grades_data:
                grades = [str(row[0]) for row in grades_data]
                self.grade_combo.addItems(grades)
            else:
                grades = [str(i) for i in range(1, 13)]
                self.grade_combo.addItems(grades)
                
        except Exception as e:
            logging.error(f"Failed to load grades: {e}")
            QMessageBox.warning(self, "Warning", f"Could not load grades from database: {e}")
            
    def preview_class_list(self):
        """Preview the class list content."""
        self._update_preview_text()
            
    def generate_class_list(self):
        """Generate class list and open it."""
        self._generate_class_list(open_file=True)
        
    def save_class_list(self):
        """Generate class list and save to chosen location."""
        self._generate_class_list(open_file=False, save_dialog=True)
        
    def _generate_class_list(self, open_file=False, save_dialog=False):
        """Internal method to generate class list."""
        try:
            # Check if generating whole school list
            if self.whole_school_radio.isChecked():
                self._generate_school_list(open_file, save_dialog)
                return
            
            # Single grade generation
            grade = self.grade_combo.currentText()
            if not grade:
                QMessageBox.warning(self, "Warning", "Please select a grade.")
                return
                
            include_learners = self.include_learners_cb.isChecked()
            
            self.generate_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.preview_btn.setEnabled(False)
            
            self.generation_thread = ClassListGeneratorThread(
                self.db_manager, grade, include_learners
            )
            self.generation_thread.finished.connect(
                lambda path: self._on_generation_finished(path, open_file, save_dialog)
            )
            self.generation_thread.error.connect(self._on_generation_error)
            self.generation_thread.start()
            
        except Exception as e:
            logging.error(f"Generation failed: {e}")
            QMessageBox.critical(self, "Error", f"Generation failed: {e}")
            self._enable_buttons()
    
    def _generate_school_list(self, open_file=False, save_dialog=False):
        """Generate whole school list."""
        try:
            include_inactive = self.include_inactive_cb.isChecked()
            
            self.generate_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.preview_btn.setEnabled(False)
            
            self.school_thread = SchoolListGeneratorThread(
                self.db_manager, include_inactive
            )
            self.school_thread.finished.connect(
                lambda path: self._on_generation_finished(path, open_file, save_dialog)
            )
            self.school_thread.error.connect(self._on_generation_error)
            self.school_thread.start()
            
        except Exception as e:
            logging.error(f"School list generation failed: {e}")
            QMessageBox.critical(self, "Error", f"School list generation failed: {e}")
            self._enable_buttons()
            
    def _on_generation_finished(self, output_path, open_file, save_dialog):
        """Handle successful generation."""
        try:
            if save_dialog:
                list_type = "school" if self.whole_school_radio.isChecked() else f"grade_{self.grade_combo.currentText()}"
                save_path, _ = QFileDialog.getSaveFileName(
                    self, "Save Class List", 
                    f"class_list_{list_type}.html",
                    "HTML Files (*.html);;All Files (*)"
                )
                
                if save_path:
                    import shutil
                    shutil.copy2(output_path, save_path)
                    output_path = save_path
                else:
                    self._enable_buttons()
                    return
                    
            if open_file:
                webbrowser.open(f"file://{output_path}")
                
            list_type = "School list" if self.whole_school_radio.isChecked() else f"Class list for Grade {self.grade_combo.currentText()}"
            QMessageBox.information(
                self, "Success", 
                f"{list_type} generated successfully!\n\nSaved to: {output_path}"
            )
            
        except Exception as e:
            logging.error(f"Post-generation handling failed: {e}")
            QMessageBox.critical(self, "Error", f"Failed to handle generated file: {e}")
            
        finally:
            self._enable_buttons()
            
    def _on_generation_error(self, error_message):
        """Handle generation error."""
        QMessageBox.critical(self, "Generation Error", f"Failed to generate class list:\n{error_message}")
        self._enable_buttons()
        
    def _enable_buttons(self):
        """Re-enable buttons after generation."""
        self.generate_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.preview_btn.setEnabled(True)
