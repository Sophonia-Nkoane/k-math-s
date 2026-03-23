from PySide6.QtWidgets import QSpinBox, QCheckBox, QComboBox, QStyle, QLineEdit, QStyleOptionSpinBox, QStyleOptionButton, QTextEdit
from PySide6.QtCore import Qt, QDate, Signal, QEvent
from PySide6.QtGui import QPainter, QColor, QPen
from .calendar_widget import CalendarWidget
# Update imports to use functions instead of direct variables
from ..styles.colors import (
    FIELD_BACKGROUND, FIELD_BORDER_COLOR, FIELD_TEXT_COLOR,
    FIELD_FOCUS_BORDER_COLOR, FIELD_DISABLED_BACKGROUND, 
    FIELD_DISABLED_TEXT_COLOR, SECONDARY_TEXT_COLOR,
)
# Import the generic scrollbar style
from ..styles.styles import FIELD_BORDER_RADIUS, MODERN_SCROLLBAR_STYLE

class ThemedWidgetMixin:
    """A mixin to handle theme changes by re-applying styles."""
    def changeEvent(self, event: QEvent):
        """Handle style changes to re-apply theme-dependent styles."""
        if event.type() == QEvent.Type.StyleChange:
            # Check for a recursion flag to prevent infinite loops when setStyleSheet is called.
            if not getattr(self, '_updating_style', False):
                if hasattr(self, '_apply_styles') and callable(self._apply_styles):
                    # Set the flag before applying styles.
                    self._updating_style = True
                    try:
                        self._apply_styles()
                    finally:
                        # Unset the flag after applying styles.
                        self._updating_style = False
        
        super().changeEvent(event)


class RoundedSpinner(ThemedWidgetMixin, QSpinBox):
    """A modern, rounded spinner widget with styling that matches RoundedField."""

    def __init__(self, parent=None, minimum=0, maximum=100, step=1):
        super().__init__(parent)
        self.setMinimum(minimum)
        self.setMaximum(maximum)
        self.setSingleStep(step)
        
        # Adjust width based on the maximum value
        self.setMinimumWidth(max(80, len(str(maximum)) * 15 + 40))
        
        self._apply_styles()
        
    def _apply_styles(self):
        self.setStyleSheet(f"""
            QSpinBox {{
                background-color: {FIELD_BACKGROUND()};
                border: 1px solid {FIELD_BORDER_COLOR()};
                border-radius: {FIELD_BORDER_RADIUS};
                padding-left: 10px;
                padding-right: 2px;
                color: {FIELD_TEXT_COLOR()};
                min-height: 30px;
                font-size: 14px;
            }}
            
            QSpinBox:focus {{
                border: 1px solid {FIELD_FOCUS_BORDER_COLOR()};
            }}
            
            QSpinBox:disabled {{
                background-color: {FIELD_DISABLED_BACKGROUND()};
                color: {FIELD_DISABLED_TEXT_COLOR()};
            }}
            
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 22px;
                border: none;
                background: transparent;
                margin-right: 3px;
            }}
            
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                top: 2px;
                right: 2px;
                height: 15%;
            }}
            
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                bottom: 2px;
                right: 2px;
                height: 15%;
            }}
            
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: rgba(0, 0, 0, 0.05);
                border-radius: 3px;
            }}
            
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
                background-color: rgba(0, 0, 0, 0.1);
                border-radius: 3px;
            }}
            
            QSpinBox::up-arrow, QSpinBox::down-arrow {{
                width: 10px;
                height: 10px;
                background: transparent;
            }}
        """)
        
    # Custom paint event to draw modern up/down arrows
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get button rects
        style = self.style()
        opt = QStyleOptionSpinBox()
        opt.initFrom(self)
        
        up_rect = style.subControlRect(QStyle.ComplexControl.CC_SpinBox, 
                                     opt, 
                                     QStyle.SubControl.SC_SpinBoxUp, 
                                     self)
        
        down_rect = style.subControlRect(QStyle.ComplexControl.CC_SpinBox, 
                                       opt, 
                                       QStyle.SubControl.SC_SpinBoxDown, 
                                       self)
                
        # Use a slightly muted color for the arrow
        arrow_color = QColor(FIELD_TEXT_COLOR())  # Add parentheses to call the function
        arrow_color.setAlpha(180)
        
        # Configure pen
        pen = QPen(arrow_color, 1.8, Qt.PenStyle.SolidLine, 
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Draw up arrow (chevron style)
        up_center_x = up_rect.center().x()
        up_center_y = up_rect.center().y()
        
        painter.drawLine(up_center_x - 4, up_center_y + 2, 
                       up_center_x, up_center_y - 2)
        painter.drawLine(up_center_x + 4, up_center_y + 2, 
                       up_center_x, up_center_y - 2)
        
        # Draw down arrow (chevron style)
        down_center_x = down_rect.center().x()
        down_center_y = down_rect.center().y()
        
        painter.drawLine(down_center_x - 4, down_center_y - 2, 
                       down_center_x, down_center_y + 2)
        painter.drawLine(down_center_x + 4, down_center_y - 2, 
                       down_center_x, down_center_y + 2)
        
        painter.end()

class RoundedCheckBox(ThemedWidgetMixin, QCheckBox):
    """A modern checkbox with rounded styling."""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._apply_styles()
        self.setMinimumHeight(30)  
        
    def _apply_styles(self):
        self.setStyleSheet(f"""
            QCheckBox {{
                color: {FIELD_TEXT_COLOR()};
                spacing: 10px;
                font-size: 14px;
            }}
            
            QCheckBox:disabled {{
                color: {FIELD_DISABLED_TEXT_COLOR()};
            }}
            
            QCheckBox::indicator {{
                width: 22px;
                height: 22px;
                border-radius: 6px;
                border: 1.5px solid {FIELD_BORDER_COLOR()};
                background-color: {FIELD_BACKGROUND()};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {FIELD_FOCUS_BORDER_COLOR()};
                border: 1.5px solid {FIELD_FOCUS_BORDER_COLOR()};
            }}
            
            QCheckBox::indicator:hover {{
                border: 1.5px solid {FIELD_FOCUS_BORDER_COLOR()};
            }}
            
            QCheckBox::indicator:disabled {{
                background-color: {FIELD_DISABLED_BACKGROUND()};
                border: 1.5px solid {FIELD_DISABLED_TEXT_COLOR()};
            }}
        """)
        
    # Custom paint event to draw a modern checkmark
    def paintEvent(self, event):
        super().paintEvent(event)
        
        # Only draw our custom checkmark if checked
        if self.isChecked():
            painter = QPainter(self)
            option = QStyleOptionButton()
            option.initFrom(self)
            # Fix: Use QStyle.StateFlag for PySide6
            option.state |= QStyle.StateFlag.State_On | QStyle.StateFlag.State_Enabled
            indicator_rect = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, 
                                                    option, 
                                                    self)
            
            # Draw checkmark with rounded caps and joins for smooth appearance
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Use white for the checkmark with a thicker pen
            painter.setPen(QPen(QColor("white"), 2.3, Qt.PenStyle.SolidLine, 
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            
            # Calculate checkmark points for a modern, slightly larger checkmark
            x, y, w, h = indicator_rect.x(), indicator_rect.y(), indicator_rect.width(), indicator_rect.height()
            
            # Draw the checkmark with a smoother curve (convert to int for drawLine)
            painter.drawLine(int(x + w*0.2), int(y + h*0.5), int(x + w*0.4), int(y + h*0.7))
            painter.drawLine(int(x + w*0.4), int(y + h*0.7), int(x + w*0.8), int(y + h*0.3))
            
            painter.end()
            
class RoundedDropdown(ThemedWidgetMixin, QComboBox):
    """A modern, rounded dropdown menu widget with consistently rounded popup."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.view().setMinimumWidth(200)
        self.clear()
        self._apply_styles()
        
    def _apply_styles(self):
        from ..styles.colors import SCROLLBAR_BACKGROUND, SCROLLBAR_HANDLE, SCROLLBAR_HANDLE_HOVER
        # Use MODERN_SCROLLBAR_STYLE, format it with colors, and scope it
        # to the dropdown's item view
        dropdown_scrollbar_style = MODERN_SCROLLBAR_STYLE.format(
            SCROLLBAR_BACKGROUND=SCROLLBAR_BACKGROUND(),
            SCROLLBAR_HANDLE=SCROLLBAR_HANDLE(),
            SCROLLBAR_HANDLE_HOVER=SCROLLBAR_HANDLE_HOVER()
        ).replace("QScrollBar", "QComboBox QAbstractItemView QScrollBar")

        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {FIELD_BACKGROUND()};
                border: 1px solid {FIELD_BORDER_COLOR()};
                border-radius: {FIELD_BORDER_RADIUS};
                padding-left: 12px;
                padding-right: 35px;
                min-height: 30px;
                min-width: 50px;
                font-size: 14px;
                color: {FIELD_TEXT_COLOR()};
            }}
            
            QComboBox:hover {{
                border: 1px solid {FIELD_FOCUS_BORDER_COLOR()};
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            
            QComboBox::down-arrow {{
                background: transparent;
            }}

            QComboBox QAbstractItemView {{
                background-color: {FIELD_BACKGROUND()};
                border: 1px solid {FIELD_BORDER_COLOR()};
                border-radius: {FIELD_BORDER_RADIUS};
                selection-background-color: {FIELD_FOCUS_BORDER_COLOR()};
                selection-color: white;
                color: {FIELD_TEXT_COLOR()};  /* Add this line to ensure text color follows theme */
                padding: 4px;
                margin: 0px;
            }}

            /* Import scrollbar style */
            {dropdown_scrollbar_style}
            
            QComboBox QAbstractItemView::item {{
                border-radius: {FIELD_BORDER_RADIUS};
                min-height: 24px;
                padding: 4px 8px;
                color: {FIELD_TEXT_COLOR()};  /* Add this line to ensure item text color follows theme */
            }}

            QComboBox QAbstractItemView::item:hover {{
                background-color: rgba(0, 0, 0, 0.05);
            }}

            QComboBox QAbstractItemView::item:selected {{
                background-color: {FIELD_FOCUS_BORDER_COLOR()};
                color: white;
            }}
        """)

    def showPopup(self):
        """Override to customize popup behavior"""
        super().showPopup()
        # Only disable the first item if it's a placeholder
        if self.count() > 0:
            first_item = self.model().item(0)
            if first_item and self.itemText(0).startswith('-- ') and self.itemText(0).endswith(' --'):
                first_item.setEnabled(False)

    def hidePopup(self):
        """Override to restore state when popup hides"""
        super().hidePopup()
        # Re-enable the first item when popup hides
        if self.count() > 0:
            first_item = self.model().item(0)
            if first_item and self.itemText(0).startswith('-- ') and self.itemText(0).endswith(' --'):
                first_item.setEnabled(True)

    def setText(self, text):
        """Sets the text by updating the current item's text"""
        if self.count() == 0:
            self.addItem(text)
        else:
            self.setItemText(0, text)
        self.setCurrentText(text)
    
    def text(self):
        """Returns the current text"""
        return self.currentText()

    def paintEvent(self, event):
        # For RoundedDropdown
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate arrow position
        arrow_rect = self.rect()
        arrow_rect.setLeft(arrow_rect.right() - 30)
        
        # Use a slightly muted color for the arrow
        arrow_color = QColor(FIELD_TEXT_COLOR())  # Add parentheses to call the function
        arrow_color.setAlpha(180)
        
        # Configure pen
        pen = QPen(arrow_color, 1.8, Qt.PenStyle.SolidLine, 
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        # Draw down arrow (chevron style)
        center_x = arrow_rect.center().x()
        center_y = arrow_rect.center().y()
        
        painter.drawLine(center_x - 4, center_y - 2, 
                        center_x, center_y + 2)
        painter.drawLine(center_x + 4, center_y - 2, 
                        center_x, center_y + 2)
        
        painter.end()


class RoundedPlainTextField(ThemedWidgetMixin, QLineEdit):
    """A modern, rounded plain text field that matches RoundedField styling."""
    
    # Import EchoMode for password fields
    EchoMode = QLineEdit.EchoMode
    
    def __init__(self, placeholder_text="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder_text)
        self._apply_styles()
        
    def _apply_styles(self):
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {FIELD_BACKGROUND()};
                border: 1px solid {FIELD_BORDER_COLOR()};
                border-radius: {FIELD_BORDER_RADIUS};
                padding-left: 12px;
                padding-right: 12px;
                color: {FIELD_TEXT_COLOR()};
                selection-background-color: {FIELD_FOCUS_BORDER_COLOR()};
                selection-color: white;
                min-height: 30px;
                font-size: 14px;
            }}
            
            QLineEdit:focus {{
                border: 1px solid {FIELD_FOCUS_BORDER_COLOR()};
                outline: none;
            }}
            
            QLineEdit:hover:!focus {{
                border: 1px solid rgba(0, 0, 0, 0.2);
            }}
            
            QLineEdit:disabled {{
                background-color: {FIELD_DISABLED_BACKGROUND()};
                color: {FIELD_DISABLED_TEXT_COLOR()};
            }}
            
            QLineEdit::placeholder {{
                color: {SECONDARY_TEXT_COLOR()};
            }}
        """)

class RoundedCalendarDropdown(RoundedDropdown):
    """A modern, rounded dropdown with calendar functionality."""
    dateChanged = Signal(str)  # Signal emitted when date changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.calendar_popup = None
        self._current_date = QDate.currentDate()
        self.setText(self._current_date.toString("yyyy-MM-dd"))

    def date(self):
        """Returns the current date as a QDate object."""
        return QDate.fromString(self.text(), "yyyy-MM-dd")

    def setDate(self, date):
        """Sets the current date."""
        if isinstance(date, QDate):
            self._current_date = date
            self.setText(date.toString("yyyy-MM-dd"))
        elif isinstance(date, str):
            qdate = QDate.fromString(date, "yyyy-MM-dd")
            if qdate.isValid():
                self._current_date = qdate
                self.setText(date)

    def mousePressEvent(self, event):
        """Shows calendar popup when clicked."""
        if not self.calendar_popup:
            self.calendar_popup = CalendarWidget(self)
            self.calendar_popup.setWindowFlags(Qt.WindowType.Tool) # Changed from Popup
            self.calendar_popup.setAttribute(Qt.WA_NoMouseReplay) # Add this line
            self.calendar_popup.selectionChanged.connect(self._update_date_from_calendar)
        
        current_date = self.date()
        if current_date.isValid():
            self.calendar_popup.setSelectedDate(current_date)
        else:
            self.calendar_popup.setSelectedDate(QDate.currentDate())

        # Position and show calendar
        global_pos = self.mapToGlobal(self.rect().bottomLeft())
        self.calendar_popup.move(global_pos)
        self.calendar_popup.show()
        self.calendar_popup.activateWindow()
        self.calendar_popup.raise_()

    def _update_date_from_calendar(self):
        """Updates the date text from calendar selection."""
        if self.calendar_popup:
            selected_date = self.calendar_popup.selectedDate()
            self._current_date = selected_date
            date_str = selected_date.toString("yyyy-MM-dd")
            self.setText(date_str)
            self.dateChanged.emit(date_str)
            self.calendar_popup.close()


class RoundedTextEdit(ThemedWidgetMixin, QTextEdit):
    """A modern, rounded multi-line text field that matches RoundedField styling."""
    
    def __init__(self, placeholder_text="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder_text)
        self._apply_styles()
        
    def _apply_styles(self):
        from ..styles.colors import SCROLLBAR_BACKGROUND, SCROLLBAR_HANDLE, SCROLLBAR_HANDLE_HOVER
        # Use MODERN_SCROLLBAR_STYLE and format it with colors
        text_edit_scrollbar_style = MODERN_SCROLLBAR_STYLE.format(
            SCROLLBAR_BACKGROUND=SCROLLBAR_BACKGROUND(),
            SCROLLBAR_HANDLE=SCROLLBAR_HANDLE(),
            SCROLLBAR_HANDLE_HOVER=SCROLLBAR_HANDLE_HOVER()
        )

        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {FIELD_BACKGROUND()};
                border: 1px solid {FIELD_BORDER_COLOR()};
                border-radius: {FIELD_BORDER_RADIUS};
                padding: 8px 12px;
                color: {FIELD_TEXT_COLOR()};
                selection-background-color: {FIELD_FOCUS_BORDER_COLOR()};
                selection-color: white;
                font-size: 14px;
            }}
            
            QTextEdit:focus {{
                border: 1px solid {FIELD_FOCUS_BORDER_COLOR()};
                outline: none;
            }}
            
            QTextEdit:hover:!focus {{
                border: 1px solid rgba(0, 0, 0, 0.2);
            }}
            
            QTextEdit:disabled {{
                background-color: {FIELD_DISABLED_BACKGROUND()};
                color: {FIELD_DISABLED_TEXT_COLOR()};
            }}
            
            QTextEdit::placeholder {{
                color: {SECONDARY_TEXT_COLOR()};
            }}

            /* Import scrollbar style */
            {text_edit_scrollbar_style}
        """)