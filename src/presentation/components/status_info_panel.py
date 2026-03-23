from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget
from PySide6.QtCore import QTimer, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QColor, QPixmap
from datetime import datetime
import platform
import psutil
import logging
from presentation.styles import styles
from presentation.styles.colors import LIGHT_THEME, DARK_THEME
from data.learner_operations import get_total_learners_count

# --- Helper Function to Colorize Icons ---
def get_colored_pixmap(icon_name: str, color: str, size: int = 16) -> QPixmap:
    """
    Creates a colorized QPixmap from a system-themed icon.
    This is more robust than relying on the system theme to provide the right icon color.
    """
    icon = QIcon.fromTheme(icon_name)
    if icon.isNull():
        # If the icon is not found in the theme, return a transparent placeholder
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        return pm

    # Get the original pixmap from the icon
    original_pixmap = icon.pixmap(QSize(size, size))

    # Create a new pixmap to be the colored version
    colored_pixmap = QPixmap(original_pixmap.size())
    colored_pixmap.fill(Qt.GlobalColor.transparent)

    # Use QPainter to "tint" the original pixmap with the desired color
    painter = QPainter(colored_pixmap)
    painter.drawPixmap(0, 0, original_pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(colored_pixmap.rect(), QColor(color))
    painter.end()
    
    return colored_pixmap

class StatusInfoPanel(QWidget):
    def __init__(self, db_manager, theme_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.theme_manager = theme_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self.init_ui()
        
        # Connect to theme changes and apply initial styles
        self.theme_manager.themeChanged.connect(self.update_styles)
        self.update_styles()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(15)

        # Prepare icon labels
        self.os_icon = QLabel()
        self.memory_icon = QLabel()
        self.clock_icon = QLabel()
        self.learner_icon = QLabel()

        # System info
        self.os_label = QLabel(f"{platform.system()} {platform.release()}")
        system_layout = QHBoxLayout()
        system_layout.setSpacing(5)
        system_layout.addWidget(self.os_icon)
        system_layout.addWidget(self.os_label)
        
        # Memory usage
        self.memory_label = QLabel()
        memory_layout = QHBoxLayout()
        memory_layout.setSpacing(5)
        memory_layout.addWidget(self.memory_icon)
        memory_layout.addWidget(self.memory_label)
        
        # Date/time
        self.datetime_label = QLabel()
        datetime_layout = QHBoxLayout()
        datetime_layout.setSpacing(5)
        datetime_layout.addWidget(self.clock_icon)
        datetime_layout.addWidget(self.datetime_label)

        # Learner count
        self.learner_count_label = QLabel()
        learner_layout = QHBoxLayout()
        learner_layout.setSpacing(5)
        learner_layout.addWidget(self.learner_icon)
        learner_layout.addWidget(self.learner_count_label)
        
        # Add layouts to main layout
        layout.addLayout(system_layout)
        layout.addStretch()
        layout.addLayout(memory_layout)
        layout.addStretch()
        layout.addLayout(learner_layout)
        layout.addStretch()
        layout.addLayout(datetime_layout)
        
        self.setLayout(layout)
        
        # Initialize values and start timer
        self.update_info()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_info)
        self.timer.start(1000)

        # Set initial learner count
        self.update_learner_count(0)
        
    def update_info(self):
        self.update_datetime()
        self.update_memory_usage()
        
    def update_datetime(self):
        current = datetime.now()
        self.datetime_label.setText(current.strftime("%I:%M %p   %Y/%m/%d"))
        
    def update_memory_usage(self):
        try:
            memory = psutil.virtual_memory()
            used_gb = memory.used / (1024**3)
            total_gb = memory.total / (1024**3)
            self.memory_label.setText(f"Memory: {used_gb:.1f}GB / {total_gb:.1f}GB")
        except Exception as e:
            self.memory_label.setText("Memory: N/A")
            self.logger.warning(f"Could not retrieve memory info: {e}")

    def update_learner_count(self, count):
        try:
            self.learner_count_label.setText(f"Total Learners: {count}")
        except Exception as e:
            self.learner_count_label.setText("Total Learners: N/A")
            self.logger.warning(f"Could not retrieve learner count: {e}")

    def update_styles(self):
        """Update styles and icons based on the current theme."""
        is_dark = self.theme_manager.is_dark_mode()
        theme = DARK_THEME if is_dark else LIGHT_THEME

        # Set the panel's background to transparent to let the parent QStatusBar's style show through.
        # This ensures a seamless look, including the top border from the status bar.
        self.setStyleSheet("background: transparent;")
        
        # Update label colors using the current theme's color
        label_style = styles.STATUS_LABEL_STYLE_TEMPLATE.format(
            color=theme["STATUS_BAR_TEXT_COLOR"]
        )
        self.os_label.setStyleSheet(label_style)
        self.memory_label.setStyleSheet(label_style)
        self.datetime_label.setStyleSheet(label_style)
        self.learner_count_label.setStyleSheet(label_style)
        
        # Update icons to match the theme
        self.update_icons(is_dark)

    def update_icons(self, is_dark):
        """Update icons based on the theme."""
        # Use a light gray for dark theme icons, and a dark gray for light theme icons
        icon_color = "#D8DEE9" if is_dark else "#4C566A"
        
        # Use the helper function to generate colorized pixmaps using standard icon names
        self.os_icon.setPixmap(get_colored_pixmap("computer", icon_color))
        self.memory_icon.setPixmap(get_colored_pixmap("drive-harddisk", icon_color))
        self.clock_icon.setPixmap(get_colored_pixmap("accessories-clock", icon_color))
        self.learner_icon.setPixmap(get_colored_pixmap("system-users", icon_color))
