from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFrame
from PySide6.QtCore import Qt, Signal
from presentation.styles.colors import (
    TEXT_COLOR, BACKGROUND_COLOR, FIELD_BACKGROUND,
    FIELD_BORDER_COLOR, TABLE_HEADER_BG
)

class CollapsibleSection(QWidget):
    # Signal emitted when the section is toggled (expanded or collapsed)
    toggled = Signal(bool)

    def __init__(self, title="", parent=None, expanded=False):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)

        # Toggle button with improved header styling
        self.toggle_button = QPushButton(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 12px 16px;
                border: 1px solid {FIELD_BORDER_COLOR()};
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
                background-color: {TABLE_HEADER_BG()};
                color: {TEXT_COLOR()};
            }}
            QPushButton:hover {{
                background-color: {BACKGROUND_COLOR()};
            }}
            QPushButton:checked {{
                border-bottom-left-radius: 0;
                border-bottom-right-radius: 0;
                border-bottom: none;
            }}
        """)
        self.toggle_button.toggled.connect(self._on_button_toggled)

        # Content area with improved styling
        self.content = QFrame()
        self.content.setLayout(QVBoxLayout())
        self.content.layout().setContentsMargins(0, 0, 0, 0)  # Remove internal padding
        self.content.setStyleSheet(f"""
            QFrame {{
                background-color: {FIELD_BACKGROUND()};
                border: 1px solid {FIELD_BORDER_COLOR()};
                border-top: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                padding: 0px;  /* Remove padding to fit table better */
            }}
        """)
        
        # Add widgets to main layout
        self.layout().addWidget(self.toggle_button)
        self.layout().addWidget(self.content)
        self.content.setVisible(expanded)

    def _on_button_toggled(self, checked):
        """Internal slot to handle button toggle and emit the public signal."""
        self.content.setVisible(checked)
        self.toggled.emit(checked)

    def add_widget(self, widget):
        self.content.layout().addWidget(widget)

    def is_expanded(self):
        """Returns True if the section is currently expanded."""
        return self.toggle_button.isChecked()

    def toggle(self, expand=None):
        """Toggles the section's visibility.

        Args:
            expand (bool, optional): If True, expands the section. If False, collapses it.
                                     If None, toggles the current state.
        """
        if expand is None:
            self.toggle_button.toggle()
        else:
            self.toggle_button.setChecked(expand)