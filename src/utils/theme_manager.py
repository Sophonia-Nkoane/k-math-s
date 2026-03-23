from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication
import configparser
from pathlib import Path
import logging
from .system_theme_detector import SystemThemeDetector
from presentation.styles import colors, styles

class ThemeManager(QObject):
    themeChanged = Signal(bool)  # Signal emitted when theme changes
    
    def __init__(self, config_file):
        super().__init__()
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.system_detector = SystemThemeDetector()
        self._timer = None
        self._load_config()
        
        # Apply the initial theme based on the configuration
        if self.is_following_system():
            self.update_system_theme()
        else:
            self._apply_theme(self.is_dark_mode())
        
        # Start monitoring if following system
        if self.is_following_system():
            self._start_monitoring()

    def _apply_theme(self, is_dark):
        """Core function to apply the theme globally."""
        # 1. Update the color module's state
        colors.set_theme(is_dark)
        
        # 2. Regenerate all stylesheet strings in the styles module
        styles.update_theme_styles(colors.CURRENT_THEME)
        
        # 3. Emit signal to notify the main window to rebuild the UI
        self.themeChanged.emit(is_dark)

    def _start_monitoring(self):
        if not self._timer:
            self._timer = QTimer()
            self._timer.timeout.connect(self._check_system_theme)
            self._timer.start(1000)  # Check every second

    def _stop_monitoring(self):
        if self._timer:
            self._timer.stop()
            self._timer = None

    def _check_system_theme(self):
        # This check is now implicit in set_theme, but we keep the logic here
        if self.is_following_system():
            is_dark = self.system_detector.is_dark_theme()
            if is_dark != self.is_dark_mode():
                self.set_theme(is_dark)

    def _load_config(self):
        self.config.read(self.config_file)
        if not self.config.has_section('Theme'):
            self.config.add_section('Theme')
            self.config.set('Theme', 'dark_mode', 'false')
            self.config.set('Theme', 'follow_system', 'true')
            self._save_config()
    
    def _save_config(self):
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def set_theme(self, is_dark):
        # Prevent redundant updates
        if is_dark == self.is_dark_mode() and not self.is_following_system():
            return
            
        self.config.set('Theme', 'dark_mode', str(is_dark).lower())
        self._save_config()
        self._apply_theme(is_dark)
    
    def set_follow_system(self, follow):
        self.config.set('Theme', 'follow_system', str(follow).lower())
        self._save_config()
        if follow:
            self._start_monitoring()
            self.update_system_theme()
        else:
            self._stop_monitoring()

    def update_system_theme(self):
        if not self.is_following_system():
            return
        is_dark = self.system_detector.is_dark_theme()
        self.set_theme(is_dark)
        
    def _handle_system_theme_change(self, is_dark):
        """Handle theme changes from system"""
        if self.is_following_system():
            self.set_theme(is_dark)
    
    def is_dark_mode(self):
        return self.config.getboolean('Theme', 'dark_mode', fallback=False)
    
    def is_following_system(self):
        return self.config.getboolean('Theme', 'follow_system', fallback=True)