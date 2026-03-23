import os
from .colors import *

def get_statement_style():
    """
    Reads the statement.css file and returns its content.
    """
    style_path = os.path.join(os.path.dirname(__file__), 'styles.css')
    with open(style_path, 'r') as f:
        return f.read()

# Form Field Appearance
BUTTON_MIN_WIDTH = 100
FIELD_BORDER_RADIUS = "6px"

# Dialog styles
DIALOG_STYLE = f"""
QDialog {{
    background-color: {BACKGROUND_COLOR()};
}}
QLabel {{
    color: {TEXT_COLOR()};
}}
"""

# Input widget styles
INPUT_STYLE = f"""
QLineEdit, QSpinBox, QDateEdit, QComboBox {{
    background-color: {FIELD_BACKGROUND()};
    color: {FIELD_TEXT_COLOR()};
    border: 1px solid {FIELD_BORDER_COLOR()};
    border-radius: 4px;
    padding: 5px;
    min-height: 25px;
}}

QLineEdit:focus, QSpinBox:focus, QDateEdit:focus, QComboBox:focus {{
    border: 1px solid {FIELD_FOCUS_BORDER_COLOR()};
}}

QSpinBox::up-button, QSpinBox::down-button {{
    border: none;
    background: {FIELD_BACKGROUND()}; 
    border-radius: 2px;
}}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {FIELD_BORDER_COLOR()};
}}
"""

GROUP_BOX_STYLE = f"""
QGroupBox {{
    background-color: {FIELD_BACKGROUND()};
    border: 1px solid {FIELD_BORDER_COLOR()};
    border-radius: 6px;
    margin-top: 10px;
    font-weight: bold;
    padding: 10px;
    color: {TEXT_COLOR()};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: {TEXT_COLOR()};
}}

QGroupBox QLabel {{
    color: {TEXT_COLOR()};
    font-weight: normal;
    padding: 4px 0;
    background-color: transparent;
}}
"""

SCROLL_AREA_STYLE = ""

# Title label style for payment options dialog
PAYMENT_OPTIONS_TITLE_LABEL_STYLE = f"""
QLabel {{
    font-size: 16pt;
    font-weight: bold;
    color: {TEXT_COLOR()};
    margin-bottom: 10px;
    padding: 5px;
}}
"""

NO_PAYMENT_OPTIONS_LABEL_STYLE = f"""
QLabel {{
    color: {SECONDARY_TEXT_COLOR()};
    font-style: italic;
    padding: 12px;
}}
"""

BUTTON_DELETE_STYLE = f"""
QPushButton {{ background-color: {BUTTON_NO_BG()}; color: white; border-radius: 8px; padding: 5px 10px; border: none; }}
QPushButton:hover:!disabled {{ background-color: {BUTTON_NO_HOVER()}; }}
QPushButton:disabled {{ background-color: {BUTTON_NO_DISABLED()}; color: {FIELD_DISABLED_TEXT_COLOR()}; border: 1px solid {FIELD_BORDER_COLOR()}; border-radius: 8px; padding: 5px 10px; }}
"""

BUTTON_UPDATE_STYLE = f"""
QPushButton {{
    background-color: {BUTTON_UPDATE_BG()};
    color: white;
    border-radius: 8px;
    padding: 5px 10px;
    border: none;
}}
QPushButton:hover:!disabled {{
    background-color: {BUTTON_UPDATE_HOVER()};
}}
QPushButton:disabled {{
    background-color: {BUTTON_UPDATE_DISABLED()};
    color: {FIELD_DISABLED_TEXT_COLOR()};
    border: 1px solid {FIELD_BORDER_COLOR()};
    border-radius: 8px;
    padding: 5px 10px;
}}
"""

BUTTON_ADD_STYLE = f"""
QPushButton {{
    background-color: {BUTTON_ADD_BG()};
    color: white;
    border-radius: 8px;
    padding: 5px 10px;
    border: none;
}}
QPushButton:hover:!disabled {{
    background-color: {BUTTON_ADD_HOVER()};
}}
QPushButton:disabled {{
    background-color: {BUTTON_ADD_DISABLED()};
    color: #e3e3e3;
    border: 1px solid #bdbdbd;
}}
"""

BUTTON_YES_STYLE = f"""
QPushButton {{
    background-color: {BUTTON_OK_BG()};
    color: white;
    border-radius: 8px;
    padding: 5px 10px;
    border: none;
}}
QPushButton:hover:!disabled {{
    background-color: {BUTTON_OK_HOVER()};
}}
QPushButton:disabled {{
    background-color: {BUTTON_OK_DISABLED()};
    color: {FIELD_DISABLED_TEXT_COLOR()};
    border: 1px solid {FIELD_BORDER_COLOR()};
    border-radius: 8px;
    padding: 5px 10px;
}}
"""

# --- MODIFIED FOR DARK THEME ---
BUTTON_OK_STYLE = f"""
QPushButton {{
    background-color: {BUTTON_OK_BG()};
    color: white;
    border-radius: 8px;
    padding: 5px 10px;
    border: none;
}}
QPushButton:hover:!disabled {{
    background-color: {BUTTON_OK_HOVER()};
}}
QPushButton:disabled {{
    background-color: {BUTTON_OK_DISABLED()};
    color: #f5f5f5;
    border: 1px solid #bdbdbd;
}}
"""

BUTTON_NO_STYLE = f"""
QPushButton {{
    background-color: {BUTTON_NO_BG()};
    color: white;
    border-radius: 8px;
    padding: 5px 10px;
    border: none;
}}
QPushButton:hover:!disabled {{
    background-color: {BUTTON_NO_HOVER()};
}}
QPushButton:disabled {{
    background-color: {BUTTON_NO_DISABLED()};
    color: #f5f5f5;
    border: 1px solid #bdbdbd;
}}
"""

BUTTON_CANCEL_STYLE = BUTTON_NO_STYLE

BUTTON_CLEAR_STYLE = f"""
QPushButton {{
    background-color: {BUTTON_CLEAR_BG()};
    color: white;
    border-radius: 8px;
    padding: 5px 10px;
    border: none;
}}
QPushButton:hover:!disabled {{
    background-color: {BUTTON_CLEAR_HOVER()};
}}
QPushButton:disabled {{
    background-color: {BUTTON_CLEAR_DISABLED()};
    color: {FIELD_DISABLED_TEXT_COLOR()};
    border: 1px solid {FIELD_BORDER_COLOR()};
    border-radius: 8px;
    padding: 5px 10px;
}}
"""

BUTTON_PAUSE_STYLE = BUTTON_CLEAR_STYLE
BUTTON_RESUME_STYLE = BUTTON_YES_STYLE

BUTTON_VIEW_STYLE = f"""
QPushButton {{
    background-color: {BUTTON_VIEW_BG()};
    color: white;
    border-radius: 8px;
    padding: 5px 10px;
    border: none;
}}
QPushButton:hover:!disabled {{
    background-color: {BUTTON_VIEW_HOVER()};
}}
QPushButton:disabled {{
    background-color: {BUTTON_VIEW_DISABLED()};
    color: {FIELD_DISABLED_TEXT_COLOR()};
    border: 1px solid {FIELD_BORDER_COLOR()};
    border-radius: 8px;
    padding: 5px 10px;
}}
"""

BUTTON_SAVE_STYLE = BUTTON_YES_STYLE

BUTTON_PRINT_STYLE = f"""
QPushButton {{
    background-color: {BUTTON_PRINT_BG()};
    color: white;
    border-radius: 8px;
    padding: 5px 10px;
    border: none;
}}
QPushButton:hover:!disabled {{
    background-color: {BUTTON_PRINT_HOVER()};
}}
QPushButton:disabled {{
    background-color: {BUTTON_PRINT_DISABLED()};
    color: #bdbdbd;
    border: 1px solid #bdbdbd;
}}
"""

BUTTON_EDIT_STYLE = """
QPushButton { background-color: #2196F3; color: white; border-radius: 8px; padding: 5px 10px; border: none; }
QPushButton:hover:!disabled { background-color: #1976D2; }
QPushButton:disabled { background-color: #90CAF9; color: #e3e3e3; border: 1px solid #bdbdbd; border-radius: 8px; padding: 5px 10px; }
"""

BUTTON_EXPORT_STYLE = BUTTON_YES_STYLE
BUTTON_REFRESH_STYLE = BUTTON_EDIT_STYLE

BUTTON_BROWSE_STYLE = f"""
QPushButton {{
    background-color: {BUTTON_BROWSE_BG()};
    color: white;
    border-radius: 8px;
    padding: 5px 10px;
    border: none;
}}
QPushButton:hover:!disabled {{
    background-color: {BUTTON_BROWSE_HOVER()};
}}
QPushButton:disabled {{
    background-color: {BUTTON_BROWSE_DISABLED()};
    color: #f5f5f5;
    border: 1px solid #d7ccc8;
}}
"""

BUTTON_RECORD_PAYMENT_STYLE = """
QPushButton { background-color: #FFEB3B; color: #212121; border-radius: 8px; padding: 5px 10px; border: none; }
QPushButton:hover:!disabled { background-color: #FDD835; }
QPushButton:disabled { background-color: #FFF59D; color: #bdbdbd; border: 1px solid #fff9c4; border-radius: 8px; padding: 5px 10px; }
"""

# --- MODIFIED FOR DARK THEME ---
VIEW_DETAILS_STYLE = """
QDialog {
    background-color: #2E3440;
}
"""

# --- MODIFIED FOR DARK THEME ---
CONTENT_WIDGET_STYLE = """
QWidget {
    background-color: transparent;
}
"""

PAYMENT_LABEL_STYLE = f"""
QLabel {{
    font-style: italic;
    color: {SECONDARY_TEXT_COLOR()};
}}
"""

PAYMENT_INPUT_STYLE = f"""
QLineEdit {{
    background-color: {FIELD_BACKGROUND()};
    color: {FIELD_TEXT_COLOR()};
    padding: 5px;
    border: 1px solid {FIELD_BORDER_COLOR()};
    border-radius: 3px;
}}
"""

TOTAL_AMOUNT_STYLE = """
QLabel {
    font-weight: bold;
    font-size: 14pt;
    margin-top: 10px;
}
"""

STATISTICS_LABEL_STYLE = """
QLabel {
    font-size: 14pt;
    font-weight: bold;
    margin: 10px 0;
}
"""

SECTION_TITLE_STYLE = """
QLabel {
    font-size: 12pt;
    font-weight: bold;
    margin: 10px 0;
}
"""

SUBSECTION_TITLE_STYLE = """
QLabel {
    font-size: 12pt;
    margin-bottom: 5px;
}
"""

PAYMENT_OPTIONS_HEADER_STYLE = f"""
QWidget {{
    border-radius: 8px;
    padding: 8px;
    margin: 0;
}}
QLabel {{
    font-size: 14px;
    color: {TEXT_COLOR()};
    margin: 0;
    padding: 0;
}}
"""

PAYMENT_OPTIONS_TOGGLE_STYLE = f"""
QToolButton {{
    background-color: transparent;
    border: none;
    padding: 5px;
    margin-right: 5px;
    min-width: 24px;
    min-height: 24px;
}}
QToolButton:hover {{
    background-color: {SCROLLBAR_HANDLE_HOVER()};
    border-radius: 4px;
}}
"""

STATISTICS_FRAME_STYLE = f"""
QFrame {{
    background-color: {FIELD_BACKGROUND()};
    border: 1px solid {FIELD_BORDER_COLOR()};
    border-radius: 8px;
    padding: 15px;
}}
QLabel {{
    padding: 5px 0;
    font-size: 11pt;
    color: {TEXT_COLOR()};
    background-color: transparent;
}}
QLabel[class="header"] {{
    font-weight: bold;
    font-size: 14pt;
    color: {TEXT_COLOR()};
}}
QLabel[class="value"] {{
    font-size: 11pt;
    font-weight: bold;
    padding: 5px;
    color: {TEXT_COLOR()};
}}
"""

STATISTICS_TABLE_STYLE = f"""
QTableWidget {{
    border-radius: 8px;
    background-color: {WHITE()};
    gridline-color: {FIELD_BORDER_COLOR()};
    color: {TEXT_COLOR()};
}}
QTableWidget::item {{ padding: 10px; border: none; }}
QTableWidget::item:selected {{
    background-color: {PRIMARY_COLOR()};
    color: {SELECTION_TEXT_COLOR()};
}}
QTableWidget::alternate-background {{ background-color: {ALTERNATE_ROW_COLOR()}; }}
QHeaderView::section {{
    background-color: {TABLE_HEADER_BG()};
    padding: 10px;
    border: none;
    border-bottom: 1px solid {FIELD_BORDER_COLOR()};
    color: {TEXT_COLOR()};
    font-weight: bold;
}}
"""

PAYMENT_VIEW_TABLE_STYLE = f"""
QTableWidget {{
    border: 1px solid {TABLE_BORDER()};
    border-radius: 3px;
    background-color: {WHITE()};
    color: {TEXT_COLOR()};
}}
QTableWidget::item {{ padding: 5px; }}
QTableWidget::item:selected {{
    background-color: {PRIMARY_COLOR()};
    color: {SELECTION_TEXT_COLOR()};
}}
QTableWidget:alternate {{ background-color: {ALTERNATE_ROW_COLOR()}; }}
QHeaderView::section {{
    background-color: {TABLE_HEADER_BG()};
    padding: 5px;
    border: none;
    border-right: 1px solid {TABLE_BORDER()};
    border-bottom: 1px solid {TABLE_BORDER()};
    color: {TEXT_COLOR()};
}}
"""

# --- MODIFIED FOR DARK THEME ---
ROUNDED_DROPDOWN_STYLE = """
QComboBox { background-color: #3B4252; border: 1px solid #4C566A; border-radius: 6px; padding: 5px 12px; color: #ECEFF4; min-height: 25px; }
QComboBox:hover, QComboBox:focus { border: 1px solid #81A1C1; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 20px; border: none; }
QComboBox QAbstractItemView { background-color: #3B4252; border: 1px solid #4C566A; border-radius: 6px; selection-background-color: #81A1C1; selection-color: #2E3440; color: #ECEFF4; padding: 4px; outline: 0px; }
QComboBox QAbstractItemView::item { min-height: 24px; padding: 4px 8px; }
QComboBox QAbstractItemView::item:selected { color: #2E3440; }
QComboBox QAbstractItemView::item:first { color: #8892A7; }
"""

# --- NEWLY ADDED FOR DARK THEME TABS ---
DARK_TAB_WIDGET_STYLE = """ 
QTabWidget::pane { border: 1px solid #4C566A; background-color: #2E3440; border-radius: 8px; }
QTabBar::tab { background-color: #3B4252; color: #D8DEE9; border: 1px solid #4C566A; border-bottom: none; padding: 8px 24px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:selected { background-color: #2E3440; color: #ECEFF4; }
QTabBar::tab:!selected:hover { background-color: #434C5E; }
"""

STATUS_BAR_STYLE = """"""

STATUS_LABEL_STYLE_TEMPLATE = "QLabel {{ color: {color}; font-weight: bold; }}"
MAIN_WINDOW_STYLE = f"QMainWindow {{ background-color: {BACKGROUND_COLOR()}; color: {TEXT_COLOR()}; }}"
CALENDAR_WIDGET_STYLE = ""

def update_theme_styles(theme):
    """Update all theme-dependent styles with new theme colors."""
    global DIALOG_STYLE, GROUP_BOX_STYLE, PAYMENT_OPTIONS_TABLE_STYLE, SCROLL_AREA_STYLE
    global PAYMENT_OPTIONS_HEADER_STYLE, MAIN_WINDOW_STYLE, INPUT_STYLE, STATUS_BAR_STYLE, CALENDAR_WIDGET_STYLE
    global PAYMENT_OPTIONS_TITLE_LABEL_STYLE, NO_PAYMENT_OPTIONS_LABEL_STYLE, STATISTICS_FRAME_STYLE, STATISTICS_TABLE_STYLE, PAYMENT_VIEW_TABLE_STYLE
    global BUTTON_DELETE_STYLE, BUTTON_UPDATE_STYLE, BUTTON_ADD_STYLE, BUTTON_YES_STYLE, BUTTON_OK_STYLE
    global BUTTON_NO_STYLE, BUTTON_CANCEL_STYLE, BUTTON_CLEAR_STYLE, BUTTON_PAUSE_STYLE, BUTTON_RESUME_STYLE
    global BUTTON_VIEW_STYLE, BUTTON_SAVE_STYLE, BUTTON_PRINT_STYLE, BUTTON_BROWSE_STYLE, BUTTON_RECORD_PAYMENT_STYLE
    global PAYMENT_LABEL_STYLE, PAYMENT_INPUT_STYLE, PAYMENT_OPTIONS_TOGGLE_STYLE

    # Move the style definition here
    PAYMENT_OPTIONS_TITLE_LABEL_STYLE = f"""
    QLabel {{
        font-size: 16pt;
        font-weight: bold;
        color: {theme["TEXT_COLOR"]};
        margin-bottom: 10px;
        padding: 5px;
    }}
    """

    NO_PAYMENT_OPTIONS_LABEL_STYLE = f"""
    QLabel {{
        color: {theme["SECONDARY_TEXT_COLOR"]};
        font-style: italic;
        padding: 12px;
    }}
    """

    DIALOG_STYLE = f"""
    QDialog {{
        background-color: {theme["BACKGROUND_COLOR"]};
    }}
    QLabel {{
        color: {theme["TEXT_COLOR"]};
    }}
    """

    GROUP_BOX_STYLE = f"""
    QGroupBox {{
        background-color: {theme["FIELD_BACKGROUND"]};
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
        border-radius: 6px;
        margin-top: 10px;
        font-weight: bold;
        padding: 10px;
        color: {theme["TEXT_COLOR"]};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
        color: {theme["TEXT_COLOR"]};
    }}

    QGroupBox QLabel {{
        color: {theme["TEXT_COLOR"]};
        font-weight: normal;
        padding: 4px 0;
        background-color: transparent;
    }}
    """

    PAYMENT_OPTIONS_TABLE_STYLE = f"""
    QTableWidget {{
        border: 1px solid {theme["TABLE_BORDER"]};
        background-color: {theme["WHITE"]};
        border-radius: 0 0 8px 8px;
        color: {theme["TEXT_COLOR"]};
        gridline-color: {theme["GRIDLINE_COLOR"]};
    }}
    QTableWidget::item {{
        padding: 5px;
    }}
    QTableWidget::item:selected {{
        background-color: {theme["PRIMARY_COLOR"]};
        color: {theme["SELECTION_TEXT_COLOR"]};
    }}
    QTableWidget:alternate {{
        background-color: {theme["ALTERNATE_ROW_COLOR"]};
    }}
    QHeaderView::section {{
        background-color: {theme["TABLE_HEADER_BG"]};
        padding: 8px;
        border: none;
        border-right: 1px solid {theme["TABLE_BORDER"]};
        border-bottom: 1px solid {theme["TABLE_BORDER"]};
        color: {theme["TEXT_COLOR"]};
    }}
    """

    PAYMENT_OPTIONS_HEADER_STYLE = f"""
    QWidget {{
        border-radius: 8px;
        padding: 8px;
        margin: 0;
    }}
    QLabel {{
        font-size: 14px;
        color: {theme["TEXT_COLOR"]};
        margin: 0;
        padding: 0;
    }}
    """

    STATISTICS_FRAME_STYLE = f"""
    QFrame {{
        background-color: {theme["FIELD_BACKGROUND"]};
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
        border-radius: 12px;
        padding: 15px;
    }}

    QLabel {{
        padding: 5px;
        font-size: 12pt;
        border-radius: 6px;
        color: {theme["TEXT_COLOR"]};
    }}

    QLabel[class="header"] {{
        font-weight: bold;
        font-size: 14pt;
        color: {theme["TEXT_COLOR"]};
    }}

    QLabel[class="value"] {{
        font-size: 13pt;
        background: {theme["WHITE"]};
        padding: 8px 12px;
        color: {theme["TEXT_COLOR"]};
    }}
    """

    STATISTICS_TABLE_STYLE = f"""
    QTableWidget {{
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
        border-radius: 12px;
        background-color: {theme["WHITE"]};
        padding: 5px;
    }}

    QTableWidget::item {{
        padding: 8px;
        border-radius: 6px;
        color: {theme["TEXT_COLOR"]};
    }}

    QTableWidget::item:selected {{
        background-color: {theme["PRIMARY_COLOR"]};
        color: {theme["SELECTION_TEXT_COLOR"]};
    }}

    QTableWidget:alternate {{
        background-color: {theme["ALTERNATE_ROW_COLOR"]};
    }}

    QHeaderView::section {{
        background-color: {theme["TABLE_HEADER_BG"]};
        padding: 10px;
        border: none;
        border-right: 1px solid {theme["FIELD_BORDER_COLOR"]};
        border-bottom: 1px solid {theme["FIELD_BORDER_COLOR"]};
        border-radius: 6px;
        color: {theme["TEXT_COLOR"]};
    }}
    """

    PAYMENT_VIEW_TABLE_STYLE = f"""
    QTableWidget {{
        border: 1px solid {theme["TABLE_BORDER"]};
        border-radius: 3px;
        background-color: {theme["WHITE"]};
        color: {theme["TEXT_COLOR"]};
        gridline-color: {theme["GRIDLINE_COLOR"]};
    }}
    QTableWidget::item {{
        padding: 5px;
    }}
    QTableWidget::item:selected {{
        background-color: {theme["PRIMARY_COLOR"]};
        color: {theme["SELECTION_TEXT_COLOR"]};
    }}
    QTableWidget:alternate {{
        background-color: {theme["ALTERNATE_ROW_COLOR"]};
    }}
    QHeaderView::section {{
        background-color: {theme["TABLE_HEADER_BG"]};
        padding: 5px;
        border: none;
        border-right: 1px solid {theme["TABLE_BORDER"]};
        border-bottom: 1px solid {theme["TABLE_BORDER"]};
        color: {theme["TEXT_COLOR"]};
    }}
    """

    MAIN_WINDOW_STYLE = f"""
    QMainWindow {{
        background-color: {theme["BACKGROUND_COLOR"]};
        color: {theme["TEXT_COLOR"]};
    }}
    """

    INPUT_STYLE = f"""
    QLineEdit, QSpinBox, QDateEdit, QComboBox {{
        background-color: {theme["FIELD_BACKGROUND"]};
        color: {theme["FIELD_TEXT_COLOR"]};
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
        border-radius: 4px;
        padding: 5px;
        min-height: 25px;
    }}

    QLineEdit:focus, QSpinBox:focus, QDateEdit:focus, QComboBox:focus {{
        border: 1px solid {theme["FIELD_FOCUS_BORDER_COLOR"]};
    }}
    """

    BUTTON_DELETE_STYLE = f"""
    QPushButton {{ background-color: {theme["BUTTON_NO_BG"]}; color: white; border-radius: 8px; padding: 5px 10px; border: none; }}
    QPushButton:hover:!disabled {{ background-color: {theme["BUTTON_NO_HOVER"]}; }}
    QPushButton:disabled {{ background-color: {theme["BUTTON_NO_DISABLED"]}; color: {theme["FIELD_DISABLED_TEXT_COLOR"]}; border: 1px solid {theme["FIELD_BORDER_COLOR"]}; border-radius: 8px; padding: 5px 10px; }}
    """

    BUTTON_UPDATE_STYLE = f"""
    QPushButton {{
        background-color: {theme["BUTTON_UPDATE_BG"]};
        color: white;
        border-radius: 8px;
        padding: 5px 10px;
        border: none;
    }}
    QPushButton:hover:!disabled {{
        background-color: {theme["BUTTON_UPDATE_HOVER"]};
    }}
    QPushButton:disabled {{
        background-color: {theme["BUTTON_UPDATE_DISABLED"]};
        color: {theme["FIELD_DISABLED_TEXT_COLOR"]};
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
        border-radius: 8px;
        padding: 5px 10px;
    }}
    """

    BUTTON_ADD_STYLE = f"""
    QPushButton {{
        background-color: {theme["BUTTON_ADD_BG"]};
        color: white;
        border-radius: 8px;
        padding: 5px 10px;
        border: none;
    }}
    QPushButton:hover:!disabled {{
        background-color: {theme["BUTTON_ADD_HOVER"]};
    }}
    QPushButton:disabled {{
        background-color: {theme["BUTTON_ADD_DISABLED"]};
        color: {theme["FIELD_DISABLED_TEXT_COLOR"]};
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
    }}
    """

    BUTTON_YES_STYLE = f"""
    QPushButton {{
        background-color: {theme["BUTTON_OK_BG"]};
        color: white;
        border-radius: 8px;
        padding: 5px 10px;
        border: none;
    }}
    QPushButton:hover:!disabled {{
        background-color: {theme["BUTTON_OK_HOVER"]};
    }}
    QPushButton:disabled {{
        background-color: {theme["BUTTON_OK_DISABLED"]};
        color: {theme["FIELD_DISABLED_TEXT_COLOR"]};
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
        border-radius: 8px;
        padding: 5px 10px;
    }}
    """

    BUTTON_OK_STYLE = BUTTON_YES_STYLE

    BUTTON_NO_STYLE = f"""
    QPushButton {{
        background-color: {theme["BUTTON_NO_BG"]};
        color: white;
        border-radius: 8px;
        padding: 5px 10px;
        border: none;
    }}
    QPushButton:hover:!disabled {{
        background-color: {theme["BUTTON_NO_HOVER"]};
    }}
    QPushButton:disabled {{
        background-color: {theme["BUTTON_NO_DISABLED"]};
        color: {theme["FIELD_DISABLED_TEXT_COLOR"]};
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
        border-radius: 8px;
        padding: 5px 10px;
    }}
    """

    BUTTON_CANCEL_STYLE = BUTTON_NO_STYLE

    BUTTON_CLEAR_STYLE = f"""
    QPushButton {{
        background-color: {theme["BUTTON_CLEAR_BG"]};
        color: white;
        border-radius: 8px;
        padding: 5px 10px;
        border: none;
    }}
    QPushButton:hover:!disabled {{
        background-color: {theme["BUTTON_CLEAR_HOVER"]};
    }}
    QPushButton:disabled {{
        background-color: {theme["BUTTON_CLEAR_DISABLED"]};
        color: {theme["FIELD_DISABLED_TEXT_COLOR"]};
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
        border-radius: 8px;
        padding: 5px 10px;
    }}
    """

    BUTTON_PAUSE_STYLE = BUTTON_CLEAR_STYLE
    BUTTON_RESUME_STYLE = BUTTON_YES_STYLE

    BUTTON_VIEW_STYLE = f"""
    QPushButton {{
        background-color: {theme["BUTTON_VIEW_BG"]};
        color: white;
        border-radius: 8px;
        padding: 5px 10px;
        border: none;
    }}
    QPushButton:hover:!disabled {{
        background-color: {theme["BUTTON_VIEW_HOVER"]};
    }}
    QPushButton:disabled {{
        background-color: {theme["BUTTON_VIEW_DISABLED"]};
        color: {theme["FIELD_DISABLED_TEXT_COLOR"]};
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
        border-radius: 8px;
        padding: 5px 10px;
    }}
    """

    BUTTON_SAVE_STYLE = BUTTON_YES_STYLE

    BUTTON_PRINT_STYLE = f"""
    QPushButton {{
        background-color: {theme["BUTTON_PRINT_BG"]};
        color: white;
        border-radius: 8px;
        padding: 5px 10px;
        border: none;
    }}
    QPushButton:hover:!disabled {{
        background-color: {theme["BUTTON_PRINT_HOVER"]};
    }}
    QPushButton:disabled {{
        background-color: {theme["BUTTON_PRINT_DISABLED"]};
        color: {theme["FIELD_DISABLED_TEXT_COLOR"]};
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
    }}
    """

    BUTTON_BROWSE_STYLE = f"""
    QPushButton {{
        background-color: {theme["BUTTON_BROWSE_BG"]};
        color: white;
        border-radius: 8px;
        padding: 5px 10px;
        border: none;
    }}
    QPushButton:hover:!disabled {{
        background-color: {theme["BUTTON_BROWSE_HOVER"]};
    }}
    QPushButton:disabled {{
        background-color: {theme["BUTTON_BROWSE_DISABLED"]};
        color: {theme["FIELD_DISABLED_TEXT_COLOR"]};
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
    }}
    """

    BUTTON_RECORD_PAYMENT_STYLE = """
    QPushButton { background-color: #FFEB3B; color: #212121; border-radius: 8px; padding: 5px 10px; border: none; }
    QPushButton:hover:!disabled { background-color: #FDD835; }
    QPushButton:disabled { background-color: #FFF59D; color: #bdbdbd; border: 1px solid #fff9c4; border-radius: 8px; padding: 5px 10px; }
    """

    PAYMENT_LABEL_STYLE = f"""
    QLabel {{
        font-style: italic;
        color: {theme["SECONDARY_TEXT_COLOR"]};
    }}
    """

    PAYMENT_INPUT_STYLE = f"""
    QLineEdit {{
        background-color: {theme["FIELD_BACKGROUND"]};
        color: {theme["FIELD_TEXT_COLOR"]};
        padding: 5px;
        border: 1px solid {theme["FIELD_BORDER_COLOR"]};
        border-radius: 3px;
    }}
    """

    PAYMENT_OPTIONS_TOGGLE_STYLE = f"""
    QToolButton {{
        background-color: transparent;
        border: none;
        padding: 5px;
        margin-right: 5px;
        min-width: 24px;
        min-height: 24px;
    }}
    QToolButton:hover {{
        background-color: {theme["SCROLLBAR_HANDLE_HOVER"]};
        border-radius: 4px;
    }}
    """
    
    # Format the modern scrollbar style with the current theme
    themed_scrollbar_style = MODERN_SCROLLBAR_STYLE.format(
        SCROLLBAR_BACKGROUND=theme["SCROLLBAR_BACKGROUND"],
        SCROLLBAR_HANDLE=theme["SCROLLBAR_HANDLE"],
        SCROLLBAR_HANDLE_HOVER=theme["SCROLLBAR_HANDLE_HOVER"]
    )

    # Update the SCROLL_AREA_STYLE to be theme-aware
    SCROLL_AREA_STYLE = f"""
    QScrollArea {{
        background: transparent;
        border: none;
        border-radius: 8px;
    }}
    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}
    """ + themed_scrollbar_style

    STATUS_BAR_STYLE = f"""
    QStatusBar {{
        background: {theme["STATUS_BAR_BACKGROUND"]};
        border-top: 1px solid {theme["STATUS_BAR_BORDER"]};
    }}
    QStatusBar QLabel {{
        color: {theme["STATUS_BAR_TEXT_COLOR"]};
        font-size: 11px;
        padding: 2px;
    }}
    """
    
    CALENDAR_WIDGET_STYLE = f"""
        QCalendarWidget {{
            background-color: {theme["BACKGROUND_COLOR"]};
            color: {theme["TEXT_COLOR"]};
            border: 1px solid {theme["FIELD_BORDER_COLOR"]};
            border-radius: 8px;
        }}

        /* Navigation Bar */
        QCalendarWidget QWidget#qt_calendar_navigationbar {{
            background-color: {theme["TABLE_HEADER_BG"]};
            border-bottom: 1px solid {theme["GRIDLINE_COLOR"]};
            min-height: 40px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }}

        QCalendarWidget QToolButton {{
            color: {theme["TEXT_COLOR"]};
            font-size: 14px;
            padding: 5px 10px;
            background-color: transparent;
            border: none;
            border-radius: 6px;
            margin: 4px;
        }}

        QCalendarWidget QToolButton:hover {{
            background-color: {theme["SCROLLBAR_HANDLE_HOVER"]};
        }}
        
        QCalendarWidget QToolButton:pressed {{
            background-color: {theme["FIELD_BORDER_COLOR"]};
        }}

        /* Month/Year Dropdown Menus */
        QCalendarWidget QMenu {{
            background-color: {theme["FIELD_BACKGROUND"]};
            color: {theme["TEXT_COLOR"]};
            padding: 4px;
            font-size: 12px;
            border: 1px solid {theme["FIELD_BORDER_COLOR"]};
            border-radius: 6px;
        }}

        QCalendarWidget QMenu::item:selected {{
            background-color: {theme["PRIMARY_COLOR"]};
            color: {theme["SELECTION_TEXT_COLOR"]};
        }}

        /* Year SpinBox in the navigation bar */
        QCalendarWidget QSpinBox {{
            font-size: 14px;
            font-weight: bold;
            color: {theme["TEXT_COLOR"]};
            background-color: transparent;
            border: none;
            padding: 0 5px;
        }}
        QCalendarWidget QSpinBox::up-button, QCalendarWidget QSpinBox::down-button {{
            width: 0px; /* Hide default buttons */
        }}

        /* Main Calendar View (Dates) */
        QCalendarWidget QTableView {{
            selection-background-color: {theme["PRIMARY_COLOR"]};
            selection-color: {theme["SELECTION_TEXT_COLOR"]};
            background-color: {theme["BACKGROUND_COLOR"]};
            alternate-background-color: {theme["ALTERNATE_ROW_COLOR"]};
            border: none;
            gridline-color: {theme["GRIDLINE_COLOR"]};
            padding: 4px;
        }}
        
        QCalendarWidget QTableView::item {{
            padding: 6px 4px;
            margin: 2px;
        }}
        
        QCalendarWidget QTableView#qt_calendar_calendarview::item:today {{
            background-color: transparent;
            color: {theme["PRIMARY_COLOR"]};
            font-weight: bold;
            border: 1px solid {theme["PRIMARY_COLOR"]};
            border-radius: 4px;
        }}
        
        QCalendarWidget QTableView#qt_calendar_calendarview::item:today:selected {{
            background-color: {theme["PRIMARY_COLOR"]};
            color: {theme["SELECTION_TEXT_COLOR"]};
            border: 1px solid {theme["PRIMARY_COLOR"]};
        }}

        /* Header (Day Names) */
        QCalendarWidget QHeaderView::section {{
            color: {theme["SECONDARY_TEXT_COLOR"]};
            background-color: {theme["TABLE_HEADER_BG"]};
            padding: 8px 5px;
            font-weight: bold;
            text-transform: uppercase;
            border: none;
        }}
    """

STATISTICS_FRAME_STYLE = f""" 
QFrame {{
    background-color: {FIELD_BACKGROUND()};
    border: 1px solid {FIELD_BORDER_COLOR()};
    border-radius: 12px;
    padding: 15px;
}}

QLabel {{
    padding: 5px;
    font-size: 12pt;
    border-radius: 6px;
    color: {TEXT_COLOR()};
}}

QLabel[class="header"] {{
    font-weight: bold;
    font-size: 14pt;
    color: {TEXT_COLOR()};
}}

QLabel[class="value"] {{
    font-size: 13pt;
    background: {WHITE()};
    padding: 8px 12px;
    color: {TEXT_COLOR()};
}}
"""

STATISTICS_TABLE_STYLE = f"""
QTableWidget {{
    border: 1px solid {FIELD_BORDER_COLOR()};
    border-radius: 12px;
    background-color: {WHITE()};
    padding: 5px;
}}

QTableWidget::item {{
    padding: 8px;
    border-radius: 6px;
    color: {TEXT_COLOR()};
}}

QTableWidget::item:selected {{
    background-color: {PRIMARY_COLOR()};
    color: {SELECTION_TEXT_COLOR()};
}}

QTableWidget:alternate {{
    background-color: {ALTERNATE_ROW_COLOR()};
}}

QHeaderView::section {{
    background-color: {TABLE_HEADER_BG()};
    padding: 10px;
    border: none;
    border-right: 1px solid {FIELD_BORDER_COLOR()};
    border-bottom: 1px solid {FIELD_BORDER_COLOR()};
    border-radius: 6px;
    color: {TEXT_COLOR()};
}}
"""

PAYMENT_VIEW_TABLE_STYLE = f"""
QTableWidget {{
    border: 1px solid {TABLE_BORDER()};
    border-radius: 3px;
    background-color: {WHITE()};
    color: {TEXT_COLOR()};
    gridline-color: {GRIDLINE_COLOR()};
}}
QTableWidget::item {{
    padding: 5px;
}}
QTableWidget::item:selected {{
    background-color: {PRIMARY_COLOR()};
    color: {SELECTION_TEXT_COLOR()};
}}
QTableWidget:alternate {{
    background-color: {ALTERNATE_ROW_COLOR()};
}}
QHeaderView::section {{
    background-color: {TABLE_HEADER_BG()};
    padding: 5px;
    border: none;
    border-right: 1px solid {TABLE_BORDER()};
    border-bottom: 1px solid {TABLE_BORDER()};
    color: {TEXT_COLOR()};
}}
"""

# Modern, consistent scrollbar style for all components
MODERN_SCROLLBAR_STYLE = """
QScrollBar:vertical {{
    background: {SCROLLBAR_BACKGROUND};
    width: 8px;
    border-radius: 4px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {SCROLLBAR_HANDLE};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {SCROLLBAR_HANDLE_HOVER};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none;
    background: none;
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
QScrollBar:horizontal {{
    background: {SCROLLBAR_BACKGROUND};
    height: 8px;
    border-radius: 4px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: {SCROLLBAR_HANDLE};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {SCROLLBAR_HANDLE_HOVER};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    border: none;
    background: none;
    width: 0px;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}
"""

def get_statistics_dialog_styles():
    """Get theme-aware styles for statistics dialog."""
    return {
        "dialog": f"background-color: {STATS_BG_BASE()};",
        
        "tab_widget": f"""
            QTabWidget::pane {{
                border: 1px solid {STATS_BORDER()};
                background-color: {STATS_BG_HIGHLIGHT()};
                border-radius: 8px;
                border-top-left-radius: 0px;
                padding: 15px;
            }}
            QTabBar::tab {{
                background-color: {STATS_BG_SURFACE()};
                color: {STATS_TEXT_SECONDARY()};
                border: 1px solid {STATS_BORDER()};
                border-bottom: none;
                padding: 8px 24px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected, QTabBar::tab:hover {{
                background-color: {STATS_BG_HIGHLIGHT()};
                color: {STATS_TEXT_PRIMARY()};
            }}
        """,
        
        "frame": f"""
            QFrame {{
                background-color: {STATS_BG_SURFACE()};
                border: 1px solid {STATS_BORDER()};
                border-radius: 8px;
                padding: 15px;
            }}
            QLabel {{
                padding: 5px 0;
                font-size: 11pt;
                color: {STATS_TEXT_SECONDARY()};
                background-color: transparent;
            }}
            QLabel[class="value"] {{
                font-size: 11pt;
                font-weight: bold;
                padding: 5px;
                color: {STATS_TEXT_PRIMARY()};
            }}
        """,
        
        "dropdown": f"""
            QComboBox {{
                background-color: {STATS_BG_SURFACE()};
                border: 1px solid {STATS_BORDER()};
                border-radius: 6px;
                padding: 5px 12px;
                color: {STATS_TEXT_PRIMARY()};
                min-height: 25px;
            }}
            QComboBox:hover, QComboBox:focus {{
                border: 1px solid {STATS_ACCENT_FOCUS()};
            }}
            QComboBox QAbstractItemView {{
                background-color: {STATS_BG_SURFACE()};
                border: 1px solid {STATS_BORDER()};
                border-radius: 6px;
                selection-background-color: {STATS_ACCENT_FOCUS()};
                selection-color: {STATS_BG_BASE()};
                color: {STATS_TEXT_PRIMARY()};
            }}
        """,
        
        # Direct property access for tab styles
        "border": STATS_BORDER(),
        "tab_background": STATS_BG_HIGHLIGHT(),
        "tab_button_background": STATS_BG_SURFACE(),
        "tab_button_color": STATS_TEXT_SECONDARY(),
        "tab_hover_background": STATS_BG_HIGHLIGHT(),
        "tab_hover_color": STATS_TEXT_PRIMARY(),
        "frame_background": STATS_BG_SURFACE(),
        "label_color": STATS_TEXT_SECONDARY(),
        "value_color": STATS_TEXT_PRIMARY(),
        "table_background": STATS_BG_SURFACE(),
        "table_text_color": STATS_TEXT_SECONDARY(),
        "selection_background": STATS_ACCENT_FOCUS(),
        "selection_color": STATS_BG_BASE(),
        "hover_background": STATS_BG_HIGHLIGHT(),
        "alternate_background": STATS_BG_HIGHLIGHT(),
        "header_background": STATS_BG_BASE(),
        "header_text_color": STATS_TEXT_PRIMARY(),
        "dropdown_background": STATS_BG_SURFACE(),
        "dropdown_text_color": STATS_TEXT_PRIMARY(),
        "focus_border": STATS_ACCENT_FOCUS(),
        "button_background": BUTTON_OK_BG(),
        "button_hover": BUTTON_OK_HOVER()
    }
