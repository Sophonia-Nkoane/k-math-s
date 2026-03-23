from typing import Dict, List
from PySide6.QtWidgets import QTableWidget, QAbstractItemView
from presentation.styles.colors import (
    WHITE, ALTERNATE_ROW_COLOR, GRIDLINE_COLOR, 
    TEXT_COLOR, FIELD_FOCUS_BORDER_COLOR,
    TABLE_HEADER_BG, TABLE_BORDER,
    SCROLLBAR_BACKGROUND, SCROLLBAR_HANDLE, SCROLLBAR_HANDLE_HOVER
)
from presentation.styles.styles import MODERN_SCROLLBAR_STYLE

DEFAULT_TABLE_ROW_HEIGHT = 36
DEFAULT_TABLE_HEADER_HEIGHT = 40


def apply_standard_table_metrics(table: QTableWidget) -> None:
    """Apply consistent row/header sizing across all QTableWidget instances."""
    table.verticalHeader().setDefaultSectionSize(DEFAULT_TABLE_ROW_HEIGHT)
    table.verticalHeader().setMinimumSectionSize(DEFAULT_TABLE_ROW_HEIGHT)
    table.horizontalHeader().setFixedHeight(DEFAULT_TABLE_HEADER_HEIGHT)


class Table:
    def __init__(self, parent, columns: List[Dict]):
        """Initialize a new Table.
        
        Args:
            parent: The parent widget
            columns: List of column configurations, each with:
                    - name: The column header text
                    - width: Fixed width in pixels, or None for auto
                    - resize_mode: QHeaderView.ResizeMode or None for fixed width
        """
        self.parent = parent
        self.table = QTableWidget()
        
        if not columns:
            raise ValueError("columns parameter is required")
            
        self.columns = columns
        self.setup_table()

    def setup_table(self):
        # Set up columns
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels([col["name"] for col in self.columns])

        # Configure columns
        header = self.table.horizontalHeader()
        for idx, column in enumerate(self.columns):
            # Safely access "width"
            width = column.get("width")
            if width is not None:
                self.table.setColumnWidth(idx, width)
            
            # Safely access "resize_mode"
            resize_mode = column.get("resize_mode")
            if resize_mode is not None:
                header.setSectionResizeMode(idx, resize_mode)

        # Table settings
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        apply_standard_table_metrics(self.table)

        # Connect selection signal if parent has handler
        if hasattr(self.parent, 'on_learner_select'):
            self.table.itemSelectionChanged.connect(self.parent.on_learner_select)

        # Styling
        stylesheet = f"""
            QTableWidget {{
                background-color: {WHITE()};
                gridline-color: {GRIDLINE_COLOR()};
                alternate-background-color: {ALTERNATE_ROW_COLOR()};
                color: {TEXT_COLOR()};
                border: 1px solid {TABLE_BORDER()};
                border-radius: 6px;
                padding: 0;
            }}
            
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {GRIDLINE_COLOR()};
            }}
            
            QTableWidget::item:selected {{
                background-color: {FIELD_FOCUS_BORDER_COLOR()};
                color: {WHITE()};
            }}
            
            QHeaderView::section {{
                background-color: {TABLE_HEADER_BG()};
                color: {TEXT_COLOR()};
                padding: 12px 8px;
                border: none;
                border-bottom: 2px solid {TABLE_BORDER()};
                border-right: 1px solid {GRIDLINE_COLOR()};
                font-weight: bold;
            }}

            QHeaderView::section:first {{
                border-top-left-radius: 6px;
            }}

            QHeaderView::section:last {{
                border-top-right-radius: 6px;
                border-right: none;
            }}

            QHeaderView {{
                background-color: {TABLE_HEADER_BG()};
            }}

            QHeaderView:horizontal {{
                min-height: 40px;
            }}
        """

        # Add scrollbar styling
        scrollbar_style = MODERN_SCROLLBAR_STYLE.format(
            SCROLLBAR_BACKGROUND=SCROLLBAR_BACKGROUND(),
            SCROLLBAR_HANDLE=SCROLLBAR_HANDLE(),
            SCROLLBAR_HANDLE_HOVER=SCROLLBAR_HANDLE_HOVER()
        )

        self.table.setStyleSheet(stylesheet + scrollbar_style)
    
    def get_table(self) -> QTableWidget:
        """Returns the underlying QTableWidget."""
        return self.table
