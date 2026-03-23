from PySide6.QtWidgets import QMainWindow
from presentation.components.window_component import WindowComponent

class MainWindowComponent(WindowComponent):
    """Base class for main windows that provides WindowComponent functionality."""
    
    def __init__(self, parent=None, title=""):
        # Initialize WindowComponent with a QMainWindow parent
        super().__init__(parent, title)
        
        # Configure main window specific settings
        self.setMinimumSize(800, 600)
        self.setWindowTitle(title)

    def add_to_main_layout(self, widget):
        """Add widget to the main window's central widget layout"""
        if self.container_layout:
            self.container_layout.addWidget(widget)

    def add_toolbar(self, toolbar):
        """Add toolbar to the main window"""
        self.addToolBar(toolbar)

    def add_menubar(self, menubar):
        """Add menubar to the main window"""
        self.setMenuBar(menubar)

    def set_status_bar(self, status_bar):
        """Set the window's status bar"""
        self.setStatusBar(status_bar)
