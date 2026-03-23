from PySide6.QtWidgets import QPushButton, QHBoxLayout, QApplication, QStyle
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import QSize

from presentation.styles import styles

class ButtonFactory:
    """Factory class for creating styled buttons."""
    
    # Basic dialog buttons
    @staticmethod
    def create_ok_button(text="OK"):
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_OK_STYLE)
        return button

    @staticmethod
    def create_cancel_button(text="Cancel"):
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_CANCEL_STYLE)
        return button

    @staticmethod
    def create_yes_button(text="Yes"):
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_YES_STYLE)
        return button

    @staticmethod
    def create_no_button(text="No"):
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_NO_STYLE)
        return button

    # Action buttons
    @staticmethod
    def create_add_button(text="Add"):
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_ADD_STYLE)
        return button

    @staticmethod
    def create_update_button(text="Update"):
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_UPDATE_STYLE)
        return button

    @staticmethod
    def create_delete_button(text="Delete"):
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_DELETE_STYLE)
        return button

    @staticmethod
    def create_delete_icon_button(tooltip="Delete"):
        """Creates a small, icon-based delete button ideal for tables."""
        button = QPushButton()
        # Use a built-in Qt icon for the trash can for portability
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        button.setIcon(icon)
        button.setIconSize(QSize(16, 16))    # Keep the icon itself small
        button.setFixedSize(QSize(28, 28))   # Give it a slightly larger, circular clickable area
        button.setToolTip(tooltip)           # Essential for accessibility
        
        # Modern, flat styling with a hover effect
        button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 14px; /* Makes it a circle */
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: #E81123; /* A bright red for danger */
            }
            QPushButton:pressed {
                background-color: #A30D18; /* A darker red when clicked */
            }
        """)
        return button

    @staticmethod
    def create_view_button(text="View"):
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_VIEW_STYLE)
        return button

    @staticmethod
    def create_browse_button(text="Browse"):
        """Creates a browse button using view styling."""
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_BROWSE_STYLE)
        return button

    @staticmethod
    def create_print_button(text="Print"):
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_PRINT_STYLE)
        return button

    @staticmethod
    def create_save_button(text="Save"):
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_SAVE_STYLE)
        return button

    @staticmethod
    def create_record_payment_button(text="Record Payment"):
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_RECORD_PAYMENT_STYLE)
        return button

    @staticmethod
    def create_sync_button(text="Sync Data"):
        """Creates a sync button using success/save styling."""
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_SAVE_STYLE)
        # Use a network/sync icon if possible
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        button.setIcon(icon)
        return button

    # Convenience methods
    @staticmethod
    def create_clear_button(text="Clear"):
        """Creates a clear button using cancel styling."""
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_CLEAR_STYLE)
        return button

    @staticmethod
    def create_refresh_button(text="Refresh"):
        """Creates a refresh button using view styling."""
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_VIEW_STYLE)
        return button

    @staticmethod
    def create_close_button(text="Close"):
        """Creates a close button using cancel styling."""
        button = QPushButton(text)
        button.setStyleSheet(styles.BUTTON_CANCEL_STYLE)
        return button

    # New method for creating menu actions
    @staticmethod
    def create_menu_action(text, parent, callback=None, icon=None):
        """Creates a menu action with consistent styling.
        
        Args:
            text (str): The text to show in the menu
            parent: The parent widget for the action
            callback: Optional callback function to connect to triggered signal
            icon: Optional icon path or QIcon object
            
        Returns:
            QAction: The created and configured menu action
        """
        action = QAction(text, parent)
        if callback:
            action.triggered.connect(callback)
        if icon:
            from PySide6.QtGui import QIcon
            if isinstance(icon, str):
                action.setIcon(QIcon(icon))
            else:
                action.setIcon(icon)
        return action

    # Utility methods
    @staticmethod
    def style_dialog_buttons(button_box):
        """Styles buttons in a QDialogButtonBox based on their role."""
        for button in button_box.buttons():
            button_text = button.text().lower()
            if "ok" in button_text:
                button.setStyleSheet(styles.BUTTON_OK_STYLE)
            elif "cancel" in button_text or "close" in button_text:
                button.setStyleSheet(styles.BUTTON_CANCEL_STYLE)
            elif "yes" in button_text:
                button.setStyleSheet(styles.BUTTON_YES_STYLE)
            elif "no" in button_text:
                button.setStyleSheet(styles.BUTTON_NO_STYLE)
            elif "add" in button_text:
                button.setStyleSheet(styles.BUTTON_ADD_STYLE)
            elif "update" in button_text or "edit" in button_text:
                button.setStyleSheet(styles.BUTTON_UPDATE_STYLE)
            elif "delete" in button_text or "remove" in button_text:
                button.setStyleSheet(styles.BUTTON_DELETE_STYLE)
            elif "view" in button_text or "show" in button_text:
                button.setStyleSheet(styles.BUTTON_VIEW_STYLE)
            elif "print" in button_text:
                button.setStyleSheet(styles.BUTTON_PRINT_STYLE)
            elif "save" in button_text:
                button.setStyleSheet(styles.BUTTON_SAVE_STYLE)

    @staticmethod
    def create_button_by_type(button_type, text=None):
        """
        Creates a button based on type string.
        Useful for dynamic button creation.
        """
        button_map = {
            'ok': ButtonFactory.create_ok_button,
            'cancel': ButtonFactory.create_cancel_button,
            'yes': ButtonFactory.create_yes_button,
            'no': ButtonFactory.create_no_button,
            'add': ButtonFactory.create_add_button,
            'update': ButtonFactory.create_update_button,
            'delete': ButtonFactory.create_delete_button,
            'view': ButtonFactory.create_view_button,
            'print': ButtonFactory.create_print_button,
            'save': ButtonFactory.create_save_button,
            'clear': ButtonFactory.create_clear_button,
            'close': ButtonFactory.create_close_button,
            'refresh': ButtonFactory.create_refresh_button,
            'record_payment': ButtonFactory.create_record_payment_button
        }
        
        if button_type.lower() in button_map:
            if text:
                return button_map[button_type.lower()](text)
            else:
                return button_map[button_type.lower()]()
        else:
            # Fallback to OK button with custom text
            return ButtonFactory.create_ok_button(text or button_type)


class ButtonFrame:
    """Enhanced ButtonFrame with better factory usage."""
    def __init__(self, parent):
        self.parent = parent
        self.layout = QHBoxLayout()
        self.setup_buttons()

    def setup_buttons(self):
        # Use ButtonFactory for all buttons
        self.add_button = ButtonFactory.create_add_button("Add Learner")
        self.add_button.clicked.connect(lambda: self.parent.dialog_service.show_add_learner_dialog(self.parent.current_user_id))

        self.update_button = ButtonFactory.create_update_button("Update Selected")
        self.update_button.clicked.connect(self.parent.open_update_selected_learner_dialog)

        self.delete_button = ButtonFactory.create_delete_button("Delete Selected")
        self.delete_button.clicked.connect(self.parent.delete_learner)

        self.print_all_button = ButtonFactory.create_print_button("Print All Statements")
        self.print_all_button.clicked.connect(self.parent.print_all_statements)

        self.save_all_pdf_button = ButtonFactory.create_save_button("Save All Statements PDF")
        self.save_all_pdf_button.clicked.connect(self.parent.save_all_to_pdf)

        self.sync_button = ButtonFactory.create_sync_button("Sync Data")
        self.sync_button.clicked.connect(self.parent.trigger_manual_sync)

        # Add buttons to layout
        self.layout.addWidget(self.add_button)
        self.layout.addWidget(self.update_button)
        self.layout.addWidget(self.save_all_pdf_button)
        self.layout.addWidget(self.sync_button)
        self.layout.addStretch()
        self.layout.addWidget(self.print_all_button)
        self.layout.addWidget(self.delete_button)

    def update_button_states(self, has_selection=False):
        """Update button enabled states based on selection."""
        self.update_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
