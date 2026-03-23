from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, 
                             QGroupBox, QFormLayout, QMessageBox, QLabel, QFileDialog,
                             QCheckBox, QTimeEdit, QComboBox)
from PySide6.QtCore import QTime
from presentation.styles import styles
from presentation.styles.colors import TEXT_COLOR
from utils.settings_manager import SettingsManager
from presentation.components.rounded_field import RoundedPlainTextField, RoundedSpinner
from presentation.components.buttons import ButtonFactory
from presentation.components.window_component import WindowComponent

class SystemSettingsDialog(WindowComponent):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent, title="System Settings")
        self.db_manager = db_manager
        self.settings_manager = SettingsManager()
        self.setup_ui()
        self.load_settings()
        self.set_size(600, 500)  # Increased size for new automation settings

    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Billing Settings Group
        billing_group = QGroupBox("Billing Settings")
        billing_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        billing_layout = QFormLayout()
        
        self.billing_start_day = RoundedSpinner()
        self.billing_start_day.setRange(1, 28)  # Limit to 28 to ensure it works in February
        self.billing_start_day.setValue(25)  # Set default to 25th
        
        # Create label with theme-aware text color
        start_day_label = QLabel("Statement Cycle Start Day (bills through day-1 next month):")
        start_day_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        billing_layout.addRow(start_day_label, self.billing_start_day)
        
        self.grace_period = RoundedSpinner()
        self.grace_period.setRange(0, 14)  # Allow up to 14 days grace period
        self.grace_period.setValue(3)  # Default 3 days
        
        # Create label with theme-aware text color
        grace_label = QLabel("Payment Grace Period (days):")
        grace_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        billing_layout.addRow(grace_label, self.grace_period)
        
        billing_group.setLayout(billing_layout)
        layout.addWidget(billing_group)

        # Automatic Statement Generation Group
        auto_group = QGroupBox("Automatic Statement Generation")
        auto_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        auto_layout = QFormLayout()

        # Enable auto generation checkbox
        self.auto_generate_enabled = QCheckBox("Enable Automatic Statement Generation")
        self.auto_generate_enabled.setStyleSheet(f"color: {TEXT_COLOR()};")
        auto_layout.addRow(self.auto_generate_enabled)

        # Generation day selection
        self.auto_generate_day = RoundedSpinner()
        self.auto_generate_day.setRange(1, 28)  # Limit to 28 to ensure it works in February
        self.auto_generate_day.setValue(25)  # Default to 25th
        
        auto_day_label = QLabel("Generation Day of Month:")
        auto_day_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        auto_layout.addRow(auto_day_label, self.auto_generate_day)

        # Generation time selection
        self.auto_generate_time = QTimeEdit()
        self.auto_generate_time.setDisplayFormat("HH:mm")
        self.auto_generate_time.setTime(QTime(9, 0))  # Default to 9:00 AM
        
        auto_time_label = QLabel("Generation Time:")
        auto_time_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        auto_layout.addRow(auto_time_label, self.auto_generate_time)

        # Recipients selection
        self.recipients_combo = QComboBox()
        self.recipients_combo.addItems(["Admin Only", "Admin + Teachers", "Admin + Parents", "All"])
        self.recipients_combo.setCurrentText("Admin Only")
        
        recipients_label = QLabel("Email Recipients:")
        recipients_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        auto_layout.addRow(recipients_label, self.recipients_combo)

        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)

        # Advanced Settings Group for Model Paths
        advanced_group = QGroupBox("Advanced Settings")
        advanced_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        advanced_layout = QFormLayout()

        ocr_path_layout = QHBoxLayout()
        self.ocr_path_edit = RoundedPlainTextField()
        self.ocr_path_edit.setReadOnly(True) # Path should be changed via browser
        browse_button = ButtonFactory.create_browse_button("Browse")
        browse_button.clicked.connect(self.browse_ocr_path)
        ocr_path_layout.addWidget(self.ocr_path_edit)
        ocr_path_layout.addWidget(browse_button)

        ocr_label = QLabel("OCR Model Path:")
        ocr_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        advanced_layout.addRow(ocr_label, ocr_path_layout)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # Buttons
        button_layout = QHBoxLayout()
        save_btn = ButtonFactory.create_save_button("Save")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = ButtonFactory.create_cancel_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        # Add the main layout to the window component
        self.add_layout(layout)

    def load_settings(self):
        try:
            self.billing_start_day.setValue(int(self.settings_manager.get_system_setting("billing_cycle_day", 25)))
            self.grace_period.setValue(int(self.settings_manager.get_system_setting("grace_period_days", 3)))
            self.ocr_path_edit.setText(self.settings_manager.get_system_setting("ocr_model_path", ""))
            
            # Load automation settings
            auto_enabled = self.settings_manager.get_system_setting("auto_generate_enabled", False)
            self.auto_generate_enabled.setChecked(bool(auto_enabled))
            
            auto_day = self.settings_manager.get_system_setting("auto_generate_day", 25)
            self.auto_generate_day.setValue(int(auto_day))
            
            auto_hour = self.settings_manager.get_system_setting("auto_generate_hour", 9)
            auto_minute = self.settings_manager.get_system_setting("auto_generate_minute", 0)
            self.auto_generate_time.setTime(QTime(int(auto_hour), int(auto_minute)))
            
            recipients = self.settings_manager.get_system_setting("auto_generate_recipients", "Admin Only")
            index = self.recipients_combo.findText(recipients)
            if index >= 0:
                self.recipients_combo.setCurrentIndex(index)
                
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Error loading settings: {str(e)}")

    def browse_ocr_path(self):
        """Opens a dialog to select a directory for OCR models."""
        directory = QFileDialog.getExistingDirectory(self, "Select OCR Model Directory", self.ocr_path_edit.text())
        if directory:
            self.ocr_path_edit.setText(directory)

    def save_settings(self):
        try:
            self.settings_manager.set_system_setting("billing_cycle_day", self.billing_start_day.value())
            self.settings_manager.set_system_setting("grace_period_days", self.grace_period.value())
            self.settings_manager.set_system_setting("ocr_model_path", self.ocr_path_edit.text())
            
            # Save automation settings
            self.settings_manager.set_system_setting("auto_generate_enabled", self.auto_generate_enabled.isChecked())
            self.settings_manager.set_system_setting("auto_generate_day", self.auto_generate_day.value())
            self.settings_manager.set_system_setting("auto_generate_hour", self.auto_generate_time.time().hour())
            self.settings_manager.set_system_setting("auto_generate_minute", self.auto_generate_time.time().minute())
            self.settings_manager.set_system_setting("auto_generate_recipients", self.recipients_combo.currentText())
            
            QMessageBox.information(self, "Success", "Settings saved successfully")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")
            self.reject()
