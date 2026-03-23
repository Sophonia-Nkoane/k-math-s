from PySide6.QtWidgets import QDialog, QVBoxLayout, QFrame, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent, QFont
from presentation.styles.colors import (
    FIELD_BACKGROUND, FIELD_BORDER_COLOR, PRIMARY_COLOR,
    SCROLLBAR_BACKGROUND, SCROLLBAR_HANDLE, SCROLLBAR_HANDLE_HOVER, TEXT_COLOR,
    BUTTON_OK_BG, BUTTON_OK_HOVER
)
from presentation.styles.styles import MODERN_SCROLLBAR_STYLE


class WindowComponent(QDialog):
    """A reusable window component with modern styling."""
    
    # Define DialogCode explicitly
    DialogCode = QDialog.DialogCode
    
    def __init__(self, parent=None, title="Window", size=(850, 650)):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._dragging = False
        self._offset = QPoint()
        self._setup_ui(title)
        self.set_size(*size)
        if parent:
            self.center_on_parent()
        else:
            self.center_on_screen()

        # Apply the modern, theme-aware scrollbar style from styles.py
        self.setStyleSheet(MODERN_SCROLLBAR_STYLE.format(
            SCROLLBAR_BACKGROUND=SCROLLBAR_BACKGROUND(),
            SCROLLBAR_HANDLE=SCROLLBAR_HANDLE(),
            SCROLLBAR_HANDLE_HOVER=SCROLLBAR_HANDLE_HOVER()
        ))

    def center_on_parent(self):
        """Center the dialog on its parent window."""
        if self.parent():
            parent_geo = self.parent().geometry()
            geo = self.geometry()
            x = parent_geo.center().x() - geo.width() // 2
            y = parent_geo.center().y() - geo.height() // 2
            self.move(x, y)

    def center_on_screen(self):
        """Center the dialog on the screen."""
        screen = self.screen()
        screen_geometry = screen.availableGeometry()
        geo = self.geometry()
        x = (screen_geometry.width() - geo.width()) // 2
        y = (screen_geometry.height() - geo.height()) // 2
        self.move(x, y)

    def _setup_ui(self, title):
        # Main layout with shadow margin
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)  # Margin for shadow
        self.main_layout.setSpacing(0)
        
        # Create main container with shadow - REMOVED BORDER
        self.container = QFrame()
        self.container.setObjectName("windowContainer")
        self.container.setFrameStyle(QFrame.Shape.NoFrame)
        self.container.setStyleSheet(f"""
            QFrame#windowContainer {{
                background-color: {FIELD_BACKGROUND()} ;
                border: 1px solid {FIELD_BORDER_COLOR()} ;
                border-radius: 10px;
                
            }}
        """) 
               
        # Container layout
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Title bar with gradient
        title_bar = QFrame()
        title_bar.setFixedHeight(45)  # Slightly taller
        title_bar.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 {PRIMARY_COLOR()} , 
                    stop:1 {PRIMARY_COLOR()} );
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }}
        """)
        
        # Title bar layout
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        
        # Title label with better font
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Segoe UI', Arial;
            }
        """)
        
        # Modern close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setFont(QFont("Segoe UI", 12))
        close_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: transparent;
                border: none;
                border-radius: 16px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #FF4444;
                color: white;
            }
            QPushButton:pressed {
                background-color: #CC0000;
                color: white;
            }
        """)
        close_btn.clicked.connect(self.reject)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(close_btn)
        
        # Content area
        self.content_area = QFrame()
        self.content_area.setStyleSheet("background: transparent; border: none;")
        self.content_area.setFrameStyle(QFrame.Shape.NoFrame)
        self.container_layout = QVBoxLayout(self.content_area)
        self.container_layout.setContentsMargins(10, 10, 10, 10)
        
        # Add components to container
        container_layout.addWidget(title_bar)
        container_layout.addWidget(self.content_area)
        
        # Add container to main layout
        self.main_layout.addWidget(self.container)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton and event.pos().y() <= 40:
            self._dragging = True
            self._offset = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events for window dragging."""
        if self._dragging:
            self.move(self.mapToParent(event.pos() - self._offset))

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release events for window dragging."""
        self._dragging = False

    def add_widget(self, widget):
        """Add a widget to the container layout."""
        self.container_layout.addWidget(widget)
        
    def add_layout(self, layout):
        """Add a layout to the container layout."""
        self.container_layout.addLayout(layout)
        
    def set_size(self, width, height):
        """Set the window size with margins for shadow."""
        self.setFixedSize(width + 20, height + 20)  # Add margin for shadow

    def show_styled_message(self, title, message, icon):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon)
        msg_box.setStyleSheet(
            f"""
            QMessageBox {{
                background-color: {FIELD_BACKGROUND()};
                color: {TEXT_COLOR()};
                font-size: 14px;
            }}
            QMessageBox QLabel {{
                color: {TEXT_COLOR()};
            }}
            QMessageBox QPushButton {{
                background-color: {BUTTON_OK_BG()};
                color: white;
                border: 1px solid {FIELD_BORDER_COLOR()};
                border-radius: 5px;
                padding: 5px 15px;
            }}
            QMessageBox QPushButton:hover {{
                background-color: {BUTTON_OK_HOVER()};
            }}
            """
        )
        msg_box.exec()
