"""Standalone progress tracking panel - shows only when Grade 1-7 learner is selected."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QSlider, QLabel, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from presentation.styles import styles


class ProgressTrackerPanel(QWidget):
    """
    A standalone panel for tracking learner progress (Grades 1-7).
    Only visible when a Grade 1-7 learner is selected in the main table.
    """
    progress_updated = Signal(str, int)  # Emits (acc_no, progress_percentage)

    def __init__(self, learner_service=None, parent=None):
        super().__init__(parent)
        self.learner_service = learner_service
        self.current_learner_dto = None  # Currently displayed learner
        self._create_widgets()
        self.setup_layout()
        self._connect_signals()
        # Set minimum size so panel is visible
        self.setMinimumHeight(180)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())

    def _create_widgets(self):
        """Creates all widgets for the progress tracker."""
        # Learner info label (shows selected learner name)
        self.learner_info_label = QLabel("No learner selected")
        font = self.learner_info_label.font()
        font.setPointSize(11)
        font.setBold(True)
        self.learner_info_label.setFont(font)
        self.learner_info_label.setMinimumHeight(30)

        # Progress slider
        self.progress_slider = QSlider()
        self.progress_slider.setOrientation(Qt.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(False)

        # Progress percentage label
        self.progress_label = QLabel("0%")
        self.progress_label.setMinimumWidth(40)
        self.progress_label.setAlignment(Qt.AlignCenter)

        # Quick preset buttons (0, 25, 50, 75, 100)
        self.quick_buttons = []
        for pct in (0, 25, 50, 75, 100):
            btn = QPushButton(f"{pct}%")
            btn.setProperty('progress_value', pct)
            btn.setEnabled(False)
            btn.setMaximumWidth(60)
            self.quick_buttons.append(btn)

        # Save button
        self.save_button = QPushButton("Save Progress")
        self.save_button.setEnabled(False)
        self.save_button.setMaximumWidth(120)

    def setup_layout(self):
        """Sets up the layout."""
        layout = QVBoxLayout(self)

        # Learner info section (shows selected learner name)
        selector_group = QGroupBox("Selected Learner")
        selector_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        selector_layout = QFormLayout(selector_group)
        selector_layout.addRow(self.learner_info_label)
        layout.addWidget(selector_group)

        # Progress tracking section
        progress_group = QGroupBox("Update Progress")
        progress_group.setStyleSheet(styles.GROUP_BOX_STYLE)
        progress_layout = QFormLayout(progress_group)

        # Slider + label row
        slider_row = QHBoxLayout()
        slider_row.addWidget(self.progress_slider, 5)
        slider_row.addWidget(self.progress_label, 1)
        progress_layout.addRow("Progress:", slider_row)

        # Quick preset buttons row
        buttons_row = QHBoxLayout()
        for btn in self.quick_buttons:
            buttons_row.addWidget(btn)
        buttons_row.addStretch()
        progress_layout.addRow("Quick Set:", buttons_row)

        # Save button row
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_row.addWidget(self.save_button)
        progress_layout.addRow(save_row)

        layout.addWidget(progress_group)
        layout.addStretch()

    def _connect_signals(self):
        """Connects widget signals to slots."""
        self.progress_slider.valueChanged.connect(self._on_slider_changed)
        self.save_button.clicked.connect(self._on_save_clicked)

        for btn in self.quick_buttons:
            btn.clicked.connect(self._on_quick_button_clicked)

    def _on_slider_changed(self, value):
        """Updates label when slider changes."""
        self.progress_label.setText(f"{int(value)}%")

    def _on_quick_button_clicked(self):
        """Handles quick preset button clicks."""
        sender = self.sender()
        if not sender:
            return
        pct = sender.property('progress_value')
        try:
            pct = int(pct)
            self.progress_slider.setValue(pct)
        except Exception:
            pass

    def load_single_learner(self, learner_dto):
        """Loads a single learner (called from main window on table selection)."""
        if not learner_dto:
            self.current_learner_dto = None
            self.learner_info_label.setText("No learner selected")
            self.progress_slider.setEnabled(False)
            self.save_button.setEnabled(False)
            for btn in self.quick_buttons:
                btn.setEnabled(False)
            return

        self.current_learner_dto = learner_dto
        display_text = f"{learner_dto.name} {learner_dto.surname} (Grade {learner_dto.grade})"
        self.learner_info_label.setText(display_text)

        # Load the learner's current progress
        current_progress = learner_dto.progress_percentage or 0
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(int(current_progress))
        self.progress_label.setText(f"{int(current_progress)}%")
        self.progress_slider.blockSignals(False)

        # Enable controls
        self.progress_slider.setEnabled(True)
        self.save_button.setEnabled(True)
        for btn in self.quick_buttons:
            btn.setEnabled(True)

    def _on_save_clicked(self):
        """Saves the progress for the selected learner."""
        if not self.current_learner_dto or not self.learner_service:
            QMessageBox.warning(self, "No Selection", "Please select a learner first.")
            return

        progress_value = self.progress_slider.value()
        
        try:
            # Update progress on current learner DTO
            self.current_learner_dto.progress_percentage = progress_value

            # Save to database
            success, message = self.learner_service.add_or_update_learner(self.current_learner_dto, None)

            if success:
                QMessageBox.information(self, "Success", f"Progress saved: {progress_value}%")
                if self.current_learner_dto.acc_no:
                    self.progress_updated.emit(self.current_learner_dto.acc_no, progress_value)
            else:
                QMessageBox.critical(self, "Error", f"Failed to save progress: {message}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
