from PySide6.QtWidgets import QCalendarWidget, QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QApplication
from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QMouseEvent

from presentation.styles import styles

class CalendarWidget(QCalendarWidget):
    selectionChanged = Signal() # Custom signal to emit when date is selected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup) # Make it a popup window
        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.setNavigationBarVisible(True)
        self.clicked.connect(self.on_date_clicked)
        self.setFixedSize(350, 300) # Increased size to display all dates properly
        self.setStyleSheet(styles.CALENDAR_WIDGET_STYLE)

    def on_date_clicked(self, date):
        self.setSelectedDate(date)
        self.selectionChanged.emit() # Emit signal on date click
        self.close()

    def leaveEvent(self, event: QMouseEvent):
        """Close the calendar when the mouse leaves its area."""
        self.close()
        super().leaveEvent(event)

    def focusOutEvent(self, event):
        """Close the calendar when it loses focus."""
        self.close()
        super().focusOutEvent(event)
