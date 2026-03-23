import sys
import subprocess
from PySide6.QtCore import QObject, Signal
import logging

class SystemThemeDetector(QObject):
    themeChanged = Signal(bool)  # Emitted when system theme changes
    
    def __init__(self):
        super().__init__()
        self._last_known_state = None
        
    def is_dark_theme(self):
        """Determine if the current system theme is dark."""
        # Windows: read registry
        if sys.platform == "win32":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                )
                val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return val == 0
            except Exception:
                return False

        # Linux (GNOME/GTK): try gsettings gtk-theme or color-scheme
        if sys.platform.startswith("linux"):
            try:
                out = subprocess.check_output(
                    ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                    stderr=subprocess.DEVNULL,
                    text=True
                ).strip().strip("'\"")
                return "dark" in out.lower()
            except Exception:
                try:
                    out = subprocess.check_output(
                        ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                        stderr=subprocess.DEVNULL,
                        text=True
                    ).strip().strip("'\"")
                    return "prefer-dark" in out.lower() or "dark" in out.lower()
                except Exception:
                    return False

        # macOS: use defaults
        if sys.platform == "darwin":
            try:
                out = subprocess.check_output(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    stderr=subprocess.DEVNULL,
                    text=True
                ).strip()
                return out.lower() == "dark"
            except subprocess.CalledProcessError:
                return False
            except Exception:
                return False

        # Unknown platform: assume light
        return False

    def check_theme_change(self):
        """Check if theme has changed and emit signal if it has"""
        current_state = self.is_dark_theme()
        if self._last_known_state != current_state:
            self._last_known_state = current_state
            self.themeChanged.emit(current_state)
