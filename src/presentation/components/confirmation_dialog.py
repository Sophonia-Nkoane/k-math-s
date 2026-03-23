from presentation.components.window_component import WindowComponent
from PySide6.QtWidgets import QLabel, QHBoxLayout
from PySide6.QtCore import Qt
from presentation.styles.colors import TEXT_COLOR
from presentation.components.buttons import ButtonFactory

class ConfirmationDialog(WindowComponent):
    """A reusable confirmation dialog component with modern styling."""
    
    def __init__(self, parent=None, title="Confirm", message="Are you sure?", 
                 icon=None, size=(300, 150),
                 accept_button_text="Yes", reject_button_text="No",
                 default_button="reject"):
        super().__init__(parent, title=title)
        self.set_size(*size)
        self.setup_ui(message, icon, accept_button_text, reject_button_text, default_button)

    def setup_ui(self, message, icon, accept_button_text, reject_button_text, default_button):
        # Message layout
        msg_label = QLabel(message)
        msg_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        accept_button = ButtonFactory.create_yes_button()
        accept_button.setText(accept_button_text)
        reject_button = ButtonFactory.create_no_button() 
        reject_button.setText(reject_button_text)
        
        if default_button.lower() == "accept":
            accept_button.setDefault(True)
            accept_button.setFocus()
        else:
            reject_button.setDefault(True)
            reject_button.setFocus()
            
        accept_button.clicked.connect(self.accept)
        reject_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(accept_button)
        button_layout.addWidget(reject_button)
        
        # Add to container
        self.add_widget(msg_label)
        self.add_layout(button_layout)
        
    def setDefaultButton(self, button):
        """Sets the default button that gets focus."""
        button.setDefault(True)
        button.setFocus()
        
    @classmethod
    def show_dialog(cls, parent=None, **kwargs):
        """Shows the dialog and returns True if accepted, False if rejected."""
        dialog = cls(parent, **kwargs)
        result = dialog.exec()
        return result == WindowComponent.DialogCode.Accepted
