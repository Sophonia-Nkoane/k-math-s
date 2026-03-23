# --- START OF FILE colors.py ---

import logging
from PySide6.QtWidgets import QApplication

# --- EYE-FRIENDLY THEMES WITH USER'S PREFERRED COLORS ---
# Using green, blue, orange, white, and red with comfortable, low-strain variations

# Theme 1: Soft Light - "Ocean Breeze"
# Soft whites with blue-green accents, avoiding harsh contrasts
WARM_LIGHT_THEME = {
    "WHITE": "#FAFCFF",  # Very soft white with slight blue tint
    "BACKGROUND_COLOR": "#F8FAFC",  # Soft light gray-blue background
    "ALTERNATE_ROW_COLOR": "#F1F5F9",  # Light blue-gray for alternating rows
    "GRIDLINE_COLOR": "#E2E8F0",  # Subtle grid lines
    "FIELD_BACKGROUND": "#FFFFFF",  # Pure white for input fields
    "FIELD_BORDER_COLOR": "#CBD5E1",  # Soft blue-gray borders
    "FIELD_TEXT_COLOR": "#1E293B",  # Dark blue-gray text for readability
    "FIELD_FOCUS_BORDER_COLOR": "#3B82F6",  # Blue focus border
    "TEXT_COLOR": "#1E293B",  # Primary text in dark blue-gray
    "SECONDARY_TEXT_COLOR": "#64748B",  # Secondary text in medium gray
    "DIALOG_BACKGROUND": "#F8FAFC",
    "TABLE_HEADER_BG": "#F1F5F9",
    "TABLE_BORDER": "#E2E8F0",
    "PRIMARY_COLOR": "#3B82F6",  # Pleasant blue
    "PAUSED_ROW_COLOR": "#FED7AA",  # Light warm orange for paused items in light theme
    "STATUS_ACTIVE_COLOR": "#10B981",  # Fresh green for active status
    "STATUS_PAUSED_COLOR": "#F59E0B",  # Warm orange for paused
    "POSITIVE_VALUE_COLOR": "#10B981",  # Green for positive values
    "NEGATIVE_VALUE_COLOR": "#EF4444",  # Red for negative values
    "NEUTRAL_VALUE_COLOR": "#6B7280",  # Gray for neutral
    "FIELD_DISABLED_BACKGROUND": "#F1F5F9",
    "FIELD_DISABLED_TEXT_COLOR": "#9CA3AF",
    "SCROLLBAR_BACKGROUND": "#F1F5F9",
    "SCROLLBAR_HANDLE": "#CBD5E1",
    "SCROLLBAR_HANDLE_HOVER": "#94A3B8",
    "SELECTION_TEXT_COLOR": "#FFFFFF",

    # Status Bar
    "STATUS_BAR_BACKGROUND": "#F1F5F9",
    "STATUS_BAR_BORDER": "#E2E8F0",
    "STATUS_BAR_TEXT_COLOR": "#475569",

    # Button Colors - using your preferred colors
    "BUTTON_OK_BG": "#10B981",  # Green for OK/confirm
    "BUTTON_OK_HOVER": "#059669",
    "BUTTON_OK_DISABLED": "#A7F3D0",
    "BUTTON_NO_BG": "#EF4444",  # Red for cancel/no/close
    "BUTTON_NO_HOVER": "#DC2626",
    "BUTTON_NO_DISABLED": "#FCA5A5",
    "BUTTON_ADD_BG": "#3B82F6",  # Blue for add actions
    "BUTTON_ADD_HOVER": "#2563EB",
    "BUTTON_ADD_DISABLED": "#93C5FD",
    "BUTTON_UPDATE_BG": "#8B5CF6",  # Purple for update actions
    "BUTTON_UPDATE_HOVER": "#7C3AED",
    "BUTTON_UPDATE_DISABLED": "#C4B5FD",
    "BUTTON_CLEAR_BG": "#F59E0B",  # Orange for clear actions
    "BUTTON_CLEAR_HOVER": "#D97706",
    "BUTTON_CLEAR_DISABLED": "#FCD34D",
    "BUTTON_PRINT_BG": "#059669",  # Dark green for print/statement
    "BUTTON_PRINT_HOVER": "#047857",
    "BUTTON_PRINT_DISABLED": "#A7F3D0",
    "BUTTON_VIEW_BG": "#0891B2",  # Cyan for view details
    "BUTTON_VIEW_HOVER": "#0E7490",
    "BUTTON_VIEW_DISABLED": "#67E8F9",
    "BUTTON_BROWSE_BG": "#6B7280",  # Gray for browse
    "BUTTON_BROWSE_HOVER": "#4B5563",
    "BUTTON_BROWSE_DISABLED": "#D1D5DB",

    # Statistics Dialog Colors
    "STATS_BG_BASE": "#F8FAFC",
    "STATS_BG_SURFACE": "#FFFFFF",
    "STATS_BG_HIGHLIGHT": "#F1F5F9",
    "STATS_BORDER": "#E2E8F0",
    "STATS_TEXT_PRIMARY": "#1E293B",
    "STATS_TEXT_SECONDARY": "#64748B",
    "STATS_ACCENT_FOCUS": "#3B82F6",
}

# Theme 2: Cozy Dark - "Midnight Garden"
# Dark theme using your preferred colors with reduced eye strain
# Soft blues and greens with warm accents, avoiding harsh black/white contrasts
WARM_DARK_THEME = {
    "WHITE": "#1E293B",  # Dark blue-gray instead of black
    "BACKGROUND_COLOR": "#0F172A",  # Very dark blue-gray background
    "ALTERNATE_ROW_COLOR": "#1E293B",  # Slightly lighter for alternating rows
    "GRIDLINE_COLOR": "#334155",  # Subtle blue-gray grid lines
    "FIELD_BACKGROUND": "#1E293B",  # Dark blue-gray for input fields
    "FIELD_BORDER_COLOR": "#475569",  # Medium gray borders
    "FIELD_TEXT_COLOR": "#F1F5F9",  # Very light blue-gray text
    "FIELD_FOCUS_BORDER_COLOR": "#60A5FA",  # Bright blue focus border
    "TEXT_COLOR": "#F1F5F9",  # Primary text in very light blue-gray
    "SECONDARY_TEXT_COLOR": "#CBD5E1",  # Secondary text in light gray
    "DIALOG_BACKGROUND": "#0F172A",
    "TABLE_HEADER_BG": "#1E293B",
    "TABLE_BORDER": "#334155",
    "PRIMARY_COLOR": "#60A5FA",  # Bright blue for primary elements
    "PAUSED_ROW_COLOR": "#C2410C",  # Dark warm orange for paused items in dark theme
    "STATUS_ACTIVE_COLOR": "#34D399",  # Bright green for active status
    "STATUS_PAUSED_COLOR": "#FBBF24",  # Warm yellow for paused
    "POSITIVE_VALUE_COLOR": "#34D399",  # Green for positive values
    "NEGATIVE_VALUE_COLOR": "#F87171",  # Soft red for negative values
    "NEUTRAL_VALUE_COLOR": "#94A3B8",  # Gray for neutral
    "FIELD_DISABLED_BACKGROUND": "#1E293B",
    "FIELD_DISABLED_TEXT_COLOR": "#64748B",
    "SCROLLBAR_BACKGROUND": "#1E293B",
    "SCROLLBAR_HANDLE": "#475569",
    "SCROLLBAR_HANDLE_HOVER": "#64748B",
    "SELECTION_TEXT_COLOR": "#0F172A",

    # Status Bar
    "STATUS_BAR_BACKGROUND": "#1E293B",
    "STATUS_BAR_BORDER": "#334155",
    "STATUS_BAR_TEXT_COLOR": "#94A3B8",

    # Button Colors - using your preferred colors with dark theme variations
    "BUTTON_OK_BG": "#22C55E",  # Bright green for OK/confirm
    "BUTTON_OK_HOVER": "#16A34A",
    "BUTTON_OK_DISABLED": "#4ADE80",
    "BUTTON_NO_BG": "#EF4444",  # Red for cancel/no/close
    "BUTTON_NO_HOVER": "#DC2626",
    "BUTTON_NO_DISABLED": "#F87171",
    "BUTTON_ADD_BG": "#3B82F6",  # Blue for add actions
    "BUTTON_ADD_HOVER": "#2563EB",
    "BUTTON_ADD_DISABLED": "#60A5FA",
    "BUTTON_UPDATE_BG": "#A855F7",  # Purple for update actions
    "BUTTON_UPDATE_HOVER": "#9333EA",
    "BUTTON_UPDATE_DISABLED": "#C4B5FD",
    "BUTTON_CLEAR_BG": "#F59E0B",  # Orange for clear actions
    "BUTTON_CLEAR_HOVER": "#D97706",
    "BUTTON_CLEAR_DISABLED": "#FCD34D",
    "BUTTON_PRINT_BG": "#16A34A",  # Dark green for print/statement
    "BUTTON_PRINT_HOVER": "#15803D",
    "BUTTON_PRINT_DISABLED": "#4ADE80",
    "BUTTON_VIEW_BG": "#06B6D4",  # Cyan for view details
    "BUTTON_VIEW_HOVER": "#0891B2",
    "BUTTON_VIEW_DISABLED": "#67E8F9",
    "BUTTON_BROWSE_BG": "#6B7280",  # Gray for browse
    "BUTTON_BROWSE_HOVER": "#4B5563",
    "BUTTON_BROWSE_DISABLED": "#D1D5DB",

    # Statistics Dialog Colors
    "STATS_BG_BASE": "#0F172A",
    "STATS_BG_SURFACE": "#1E293B",
    "STATS_BG_HIGHLIGHT": "#334155",
    "STATS_BORDER": "#475569",
    "STATS_TEXT_PRIMARY": "#F1F5F9",
    "STATS_TEXT_SECONDARY": "#CBD5E1",
    "STATS_ACCENT_FOCUS": "#60A5FA",
}


# Aliases for backwards compatibility or easier reference
LIGHT_THEME = WARM_LIGHT_THEME.copy()
DARK_THEME = WARM_DARK_THEME.copy()

# Current theme (default to light)
CURRENT_THEME = LIGHT_THEME.copy()

# Color getter functions
def WHITE(): return CURRENT_THEME.get("WHITE", "#000000")
def BACKGROUND_COLOR(): return CURRENT_THEME.get("BACKGROUND_COLOR", "#000000")
def ALTERNATE_ROW_COLOR(): return CURRENT_THEME.get("ALTERNATE_ROW_COLOR", "#000000")
def GRIDLINE_COLOR(): return CURRENT_THEME.get("GRIDLINE_COLOR", "#000000")
def FIELD_BACKGROUND(): return CURRENT_THEME.get("FIELD_BACKGROUND", "#000000")
def FIELD_BORDER_COLOR(): return CURRENT_THEME.get("FIELD_BORDER_COLOR", "#000000")
def FIELD_TEXT_COLOR(): return CURRENT_THEME.get("FIELD_TEXT_COLOR", "#000000")
def FIELD_FOCUS_BORDER_COLOR(): return CURRENT_THEME.get("FIELD_FOCUS_BORDER_COLOR", "#000000")
def FIELD_DISABLED_BACKGROUND(): return CURRENT_THEME.get("FIELD_DISABLED_BACKGROUND", "#000000")
def FIELD_DISABLED_TEXT_COLOR(): return CURRENT_THEME.get("FIELD_DISABLED_TEXT_COLOR", "#000000")
def PRIMARY_COLOR(): return CURRENT_THEME.get("PRIMARY_COLOR", "#000000")
def STATUS_ACTIVE_COLOR(): return CURRENT_THEME.get("STATUS_ACTIVE_COLOR", "#000000")
def STATUS_PAUSED_COLOR(): return CURRENT_THEME.get("STATUS_PAUSED_COLOR", "000000")
def POSITIVE_VALUE_COLOR(): return CURRENT_THEME.get("POSITIVE_VALUE_COLOR", "#000000")
def NEGATIVE_VALUE_COLOR(): return CURRENT_THEME.get("NEGATIVE_VALUE_COLOR", "#000000")
def NEUTRAL_VALUE_COLOR(): return CURRENT_THEME.get("NEUTRAL_VALUE_COLOR", "#000000")
def TEXT_COLOR(): return CURRENT_THEME.get("TEXT_COLOR", "#000000")
def SECONDARY_TEXT_COLOR(): return CURRENT_THEME.get("SECONDARY_TEXT_COLOR", "#757575")
def TABLE_HEADER_BG(): return CURRENT_THEME.get("TABLE_HEADER_BG", "#000000")
def TABLE_BORDER(): return CURRENT_THEME.get("TABLE_BORDER", "#000000")

def SELECTION_TEXT_COLOR(): return CURRENT_THEME.get("SELECTION_TEXT_COLOR", "#FFFFFF")

def SCROLLBAR_BACKGROUND(): return CURRENT_THEME.get("SCROLLBAR_BACKGROUND", "#F1F5F9")
def SCROLLBAR_HANDLE(): return CURRENT_THEME.get("SCROLLBAR_HANDLE", "#CBD5E1")
def SCROLLBAR_HANDLE_HOVER(): return CURRENT_THEME.get("SCROLLBAR_HANDLE_HOVER", "#94A3B8")

# Status Bar color getters
def STATUS_BAR_BACKGROUND(): return CURRENT_THEME.get("STATUS_BAR_BACKGROUND", "#F0F0F0")
def STATUS_BAR_BORDER(): return CURRENT_THEME.get("STATUS_BAR_BORDER", "#DCDCDC")
def STATUS_BAR_TEXT_COLOR(): return CURRENT_THEME.get("STATUS_BAR_TEXT_COLOR", "#333333")

# Button color getters
def BUTTON_OK_BG(): return CURRENT_THEME.get("BUTTON_OK_BG", "#000000")
def BUTTON_OK_HOVER(): return CURRENT_THEME.get("BUTTON_OK_HOVER", "#000000")
def BUTTON_OK_DISABLED(): return CURRENT_THEME.get("BUTTON_OK_DISABLED", "#000000")
def BUTTON_NO_BG(): return CURRENT_THEME.get("BUTTON_NO_BG", "#000000")
def BUTTON_NO_HOVER(): return CURRENT_THEME.get("BUTTON_NO_HOVER", "#000000")
def BUTTON_NO_DISABLED(): return CURRENT_THEME.get("BUTTON_NO_DISABLED", "#000000")
def BUTTON_ADD_BG(): return CURRENT_THEME.get("BUTTON_ADD_BG", "#000000")
def BUTTON_ADD_HOVER(): return CURRENT_THEME.get("BUTTON_ADD_HOVER", "#000000")
def BUTTON_ADD_DISABLED(): return CURRENT_THEME.get("BUTTON_ADD_DISABLED", "#000000")
def BUTTON_UPDATE_BG(): return CURRENT_THEME.get("BUTTON_UPDATE_BG", "#000000")
def BUTTON_UPDATE_HOVER(): return CURRENT_THEME.get("BUTTON_UPDATE_HOVER", "#000000")
def BUTTON_UPDATE_DISABLED(): return CURRENT_THEME.get("BUTTON_UPDATE_DISABLED", "#000000")
def BUTTON_CLEAR_BG(): return CURRENT_THEME.get("BUTTON_CLEAR_BG", "#000000")
def BUTTON_CLEAR_HOVER(): return CURRENT_THEME.get("BUTTON_CLEAR_HOVER", "#000000")
def BUTTON_CLEAR_DISABLED(): return CURRENT_THEME.get("BUTTON_CLEAR_DISABLED", "#000000")
def BUTTON_PRINT_BG(): return CURRENT_THEME.get("BUTTON_PRINT_BG", "#000000")
def BUTTON_PRINT_HOVER(): return CURRENT_THEME.get("BUTTON_PRINT_HOVER", "#000000")
def BUTTON_PRINT_DISABLED(): return CURRENT_THEME.get("BUTTON_PRINT_DISABLED", "#000000")
def BUTTON_VIEW_BG(): return CURRENT_THEME.get("BUTTON_VIEW_BG", "#000000")
def BUTTON_VIEW_HOVER(): return CURRENT_THEME.get("BUTTON_VIEW_HOVER", "#000000")
def BUTTON_VIEW_DISABLED(): return CURRENT_THEME.get("BUTTON_VIEW_DISABLED", "#000000")
def BUTTON_BROWSE_BG(): return CURRENT_THEME.get("BUTTON_BROWSE_BG", "#000000")
def BUTTON_BROWSE_HOVER(): return CURRENT_THEME.get("BUTTON_BROWSE_HOVER", "#000000")
def BUTTON_BROWSE_DISABLED(): return CURRENT_THEME.get("BUTTON_BROWSE_DISABLED", "#000000")

# Statistics Dialog color getters
def STATS_BG_BASE(): return CURRENT_THEME.get("STATS_BG_BASE", "#000000")
def STATS_BG_SURFACE(): return CURRENT_THEME.get("STATS_BG_SURFACE", "#000000")
def STATS_BG_HIGHLIGHT(): return CURRENT_THEME.get("STATS_BG_HIGHLIGHT", "#000000")
def STATS_BORDER(): return CURRENT_THEME.get("STATS_BORDER", "#000000")
def STATS_TEXT_PRIMARY(): return CURRENT_THEME.get("STATS_TEXT_PRIMARY", "#000000")
def STATS_TEXT_SECONDARY(): return CURRENT_THEME.get("STATS_TEXT_SECONDARY", "#000000")
def STATS_ACCENT_FOCUS(): return CURRENT_THEME.get("STATS_ACCENT_FOCUS", "#000000")
def PAUSED_ROW_COLOR(): return CURRENT_THEME.get("PAUSED_ROW_COLOR", "#000000")

def set_theme(is_dark):
    """Update the current theme colors and apply to styles."""
    global CURRENT_THEME
    CURRENT_THEME = DARK_THEME.copy() if is_dark else LIGHT_THEME.copy()

    # Force style update on all widgets
    try:
        app = QApplication.instance()
        if app:
            for widget in app.allWidgets():
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
    except Exception as e:
        logging.error(f"Error updating theme: {e}")

    logging.info(f"Theme changed to: {'dark' if is_dark else 'light'}")


# Initialize with light theme
set_theme(False)
# --- END OF FILE colors.py ---
