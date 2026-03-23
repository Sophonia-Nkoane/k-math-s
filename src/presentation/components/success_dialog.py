from PySide6.QtWidgets import QLabel, QHBoxLayout
from PySide6.QtCore import Qt
from .buttons import ButtonFactory
from .window_component import WindowComponent
from presentation.styles.colors import TEXT_COLOR

class SuccessDialog(WindowComponent):
    """A reusable success dialog component."""
    
    def __init__(self, message, parent=None):
        super().__init__(parent, title="Success")
        self.set_size(300, 150)
        self.setup_ui(message)

    def setup_ui(self, message):
        """Sets up the dialog's UI components."""
        # Message layout
        message_label = QLabel(message)
        message_label.setStyleSheet(f"color:{TEXT_COLOR()};")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Button layout 
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        ok_button = ButtonFactory.create_ok_button("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addStretch()

        # Add to container
        self.add_widget(message_label)
        self.add_layout(button_layout)

    @staticmethod
    def show_success(parent, message):
        """Static method to show success dialog."""
        dialog = SuccessDialog(message, parent)
        return dialog.exec()