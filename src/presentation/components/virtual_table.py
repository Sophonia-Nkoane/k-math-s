"""
Virtual Table Widget for Learner Payment Management Application

Implements virtual scrolling and lazy loading for handling large datasets efficiently.
Only renders visible rows to minimize memory usage and improve performance.

Features:
- Virtual scrolling for millions of rows
- Lazy data loading
- Memory-efficient rendering
- Configurable buffer size
- Search and filtering support
- Sorting capabilities
"""

from typing import Any, Callable, Dict, List, Optional, Union
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QScrollBar, QStyleOptionViewItem,
    QTableView, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QComboBox, QProgressBar
)
from PySide6.QtCore import (
    QAbstractTableModel, QModelIndex, Qt, Signal, QRect, QSize,
    QTimer, QThread
)
from PySide6.QtCore import Slot
from PySide6.QtGui import QPainter, QFontMetrics
import logging
from datetime import datetime
from functools import lru_cache


class VirtualTableModel(QAbstractTableModel):
    """
    Virtual table model that loads data on-demand.
    Only keeps a small buffer of actual data in memory.
    """
    
    # Signals
    dataRequested = Signal(int, int)  # start_row, count
    searchRequested = Signal(str, str)  # search_term, column
    
    def __init__(self, columns: List[Dict[str, Any]], data_loader: Callable = None):
        super().__init__()
        
        self.columns = columns
        self.column_names = [col.get('name', f'Column {i}') for i, col in enumerate(columns)]
        self.data_loader = data_loader
        
        # Virtual data management
        self._total_rows = 0
        self._buffer_size = 1000  # Number of rows to keep in memory
        self._data_buffer = {}  # Cache for loaded rows
        self._buffer_start = 0
        self._buffer_end = 0
        
        # Loading state
        self._loading_rows = set()
        self._failed_rows = set()
        
        # Search and filter
        self._search_term = ""
        self._search_column = ""
        self._filtered_indices = None
        
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def setDataLoader(self, loader: Callable):
        """Set the data loader function."""
        self.data_loader = loader
    
    def setTotalRows(self, count: int):
        """Set the total number of rows in the dataset."""
        old_count = self._total_rows
        self._total_rows = count
        
        if count != old_count:
            # Reset buffers when row count changes
            self._data_buffer.clear()
            self._buffer_start = 0
            self._buffer_end = 0
            self._filtered_indices = None
            
            self.modelReset.emit()
    
    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the total number of rows."""
        if self._filtered_indices is not None:
            return len(self._filtered_indices)
        return self._total_rows
    
    def columnCount(self, parent=QModelIndex()) -> int:
        """Return the number of columns."""
        return len(self.columns)
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        """Return header data."""
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.column_names):
                return self.column_names[section]
            elif orientation == Qt.Orientation.Vertical:
                return str(section + 1)
        return None
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Return data for the given index."""
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        # Convert to actual row index if filtered
        actual_row = self._filtered_indices[row] if self._filtered_indices is not None else row
        
        if role == Qt.ItemDataRole.DisplayRole:
            # Check if data is already loaded
            if actual_row in self._data_buffer:
                row_data = self._data_buffer[actual_row]
                if 0 <= col < len(row_data):
                    return row_data[col]
            
            # Check if we're currently loading this row
            if actual_row in self._loading_rows:
                return "Loading..."
            
            # Check if this row failed to load
            if actual_row in self._failed_rows:
                return "Error"
            
            # Request data loading for this range
            self._requestDataRange(actual_row)
            return "Loading..."
        
        elif role == Qt.ItemDataRole.ToolTipRole:
            if actual_row in self._loading_rows:
                return "Data is being loaded..."
            elif actual_row in self._failed_rows:
                return "Failed to load data for this row"
        
        return None
    
    def _requestDataRange(self, center_row: int):
        """Request loading of data around the specified row."""
        # Calculate buffer range centered on the requested row
        buffer_start = max(0, center_row - self._buffer_size // 2)
        buffer_end = min(self._total_rows, buffer_start + self._buffer_size)
        
        # Check if we need to load new data
        if (buffer_start < self._buffer_start or buffer_end > self._buffer_end or
            not any(row in self._data_buffer for row in range(buffer_start, min(buffer_end, buffer_start + 10)))):
            
            # Clear old buffer data outside the new range
            old_keys = list(self._data_buffer.keys())
            for row_idx in old_keys:
                if row_idx < buffer_start or row_idx >= buffer_end:
                    del self._data_buffer[row_idx]
            
            # Mark rows as loading
            for row_idx in range(buffer_start, buffer_end):
                if row_idx not in self._data_buffer:
                    self._loading_rows.add(row_idx)
            
            self._buffer_start = buffer_start
            self._buffer_end = buffer_end
            
            # Request data loading
            self.dataRequested.emit(buffer_start, buffer_end - buffer_start)
    
    def loadData(self, start_row: int, data: List[List[Any]]):
        """Load data into the buffer."""
        if not data:
            return
        
        # Store data in buffer
        for i, row_data in enumerate(data):
            row_idx = start_row + i
            if row_idx in self._loading_rows:
                self._loading_rows.discard(row_idx)
            
            self._data_buffer[row_idx] = row_data
        
        # Emit data changed for the loaded range
        start_index = self.index(max(0, start_row), 0)
        end_index = self.index(min(self._total_rows - 1, start_row + len(data) - 1), self.columnCount() - 1)
        self.dataChanged.emit(start_index, end_index)
        
        self.logger.debug(f"Loaded {len(data)} rows starting from row {start_row}")
    
    def loadDataFailed(self, start_row: int, count: int):
        """Mark data loading as failed for the specified range."""
        for i in range(count):
            row_idx = start_row + i
            self._loading_rows.discard(row_idx)
            self._failed_rows.add(row_idx)
        
        # Emit data changed for the failed range
        start_index = self.index(start_row, 0)
        end_index = self.index(start_row + count - 1, self.columnCount() - 1)
        self.dataChanged.emit(start_index, end_index)
    
    def search(self, term: str, column: str = ""):
        """Perform search on the dataset."""
        self._search_term = term
        self._search_column = column
        
        if not term:
            # Clear search
            self._filtered_indices = None
            self.modelReset.emit()
        else:
            # Request search from data source
            self.searchRequested.emit(term, column)
    
    def setSearchResults(self, matching_indices: List[int]):
        """Set the results of a search operation."""
        self._filtered_indices = matching_indices
        self.modelReset.emit()
        self.logger.debug(f"Search returned {len(matching_indices)} results")
    
    def clearCache(self):
        """Clear all cached data."""
        self._data_buffer.clear()
        self._loading_rows.clear()
        self._failed_rows.clear()
        self._buffer_start = 0
        self._buffer_end = 0
        self.modelReset.emit()


class DataLoaderThread(QThread):
    """
    Background thread for loading data without blocking the UI.
    """
    
    dataLoaded = Signal(int, list)  # start_row, data
    dataLoadFailed = Signal(int, int)  # start_row, count
    searchCompleted = Signal(str, str, list)  # term, column, indices
    
    def __init__(self, data_source):
        super().__init__()
        self.data_source = data_source
        self.pending_requests = []
        self.pending_searches = []
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def requestData(self, start_row: int, count: int):
        """Request data loading."""
        self.pending_requests.append((start_row, count))
        if not self.isRunning():
            self.start()
    
    def requestSearch(self, term: str, column: str):
        """Request search operation."""
        self.pending_searches.append((term, column))
        if not self.isRunning():
            self.start()
    
    def run(self):
        """Main thread execution."""
        try:
            # Process data requests
            while self.pending_requests:
                start_row, count = self.pending_requests.pop(0)
                try:
                    data = self.data_source.get_data_range(start_row, count)
                    self.dataLoaded.emit(start_row, data)
                except Exception as e:
                    self.logger.error(f"Failed to load data: {e}")
                    self.dataLoadFailed.emit(start_row, count)
            
            # Process search requests
            while self.pending_searches:
                term, column = self.pending_searches.pop(0)
                try:
                    indices = self.data_source.search_data(term, column)
                    self.searchCompleted.emit(term, column, indices)
                except Exception as e:
                    self.logger.error(f"Search failed: {e}")
                    self.searchCompleted.emit(term, column, [])
                    
        except Exception as e:
            self.logger.error(f"Error in data loader thread: {e}")


class VirtualTableView(QTableView):
    """
    Enhanced table view with virtual scrolling and lazy loading.
    """
    
    # Signals
    rowDoubleClicked = Signal(int, dict)  # row_index, row_data
    selectionChanged = Signal(list)  # selected_rows
    
    def __init__(self, columns: List[Dict[str, Any]], data_source, parent=None):
        super().__init__(parent)
        
        self.columns = columns
        self.data_source = data_source
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Set up model and loader
        self.virtual_model = VirtualTableModel(columns)
        self.data_loader_thread = DataLoaderThread(data_source)
        
        # Connect signals
        self.virtual_model.dataRequested.connect(self.data_loader_thread.requestData)
        self.virtual_model.searchRequested.connect(self.data_loader_thread.requestSearch)
        self.data_loader_thread.dataLoaded.connect(self.virtual_model.loadData)
        self.data_loader_thread.dataLoadFailed.connect(self.virtual_model.loadDataFailed)
        self.data_loader_thread.searchCompleted.connect(self._onSearchCompleted)
        
        self.setModel(self.virtual_model)
        self.setupView()
        
        # Initialize with data count
        try:
            total_count = data_source.get_total_count()
            self.virtual_model.setTotalRows(total_count)
            self.logger.info(f"Virtual table initialized with {total_count} rows")
        except Exception as e:
            self.logger.error(f"Failed to get total count: {e}")
    
    def setupView(self):
        """Configure the table view."""
        # Set selection behavior
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        # Enable sorting
        self.setSortingEnabled(False)  # We'll handle sorting in the data source
        
        # Configure headers
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        
        # Set column properties
        header = self.horizontalHeader()
        for i, column in enumerate(self.columns):
            if 'width' in column and column['width'] is not None:
                self.setColumnWidth(i, column['width'])
            
            if 'resize_mode' in column and column['resize_mode'] is not None:
                header.setSectionResizeMode(i, column['resize_mode'])
        
        # Connect selection changes
        selection_model = self.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._onSelectionChanged)
        
        # Connect double-click
        self.doubleClicked.connect(self._onDoubleClick)
    
    def setDataSource(self, data_source):
        """Change the data source and refresh."""
        self.data_source = data_source
        self.data_loader_thread.data_source = data_source
        
        try:
            total_count = data_source.get_total_count()
            self.virtual_model.setTotalRows(total_count)
            self.logger.info(f"Data source changed, {total_count} total rows")
        except Exception as e:
            self.logger.error(f"Failed to update data source: {e}")
    
    def refresh(self):
        """Refresh the table data."""
        self.virtual_model.clearCache()
        try:
            total_count = self.data_source.get_total_count()
            self.virtual_model.setTotalRows(total_count)
        except Exception as e:
            self.logger.error(f"Failed to refresh: {e}")
    
    def search(self, term: str, column: str = ""):
        """Search for data in the table."""
        self.virtual_model.search(term, column)
    
    def getSelectedRowData(self) -> Optional[Dict[str, Any]]:
        """Get data for the currently selected row."""
        current = self.currentIndex()
        if not current.isValid():
            return None
        
        row = current.row()
        # Get actual row index if filtered
        actual_row = (self.virtual_model._filtered_indices[row] 
                     if self.virtual_model._filtered_indices is not None else row)
        
        if actual_row in self.virtual_model._data_buffer:
            row_data = self.virtual_model._data_buffer[actual_row]
            return {
                self.columns[i].get('key', f'col_{i}'): value
                for i, value in enumerate(row_data) if i < len(self.columns)
            }
        
        return None
    
    @Slot(str, str, list)
    def _onSearchCompleted(self, term: str, column: str, indices: List[int]):
        """Handle search completion."""
        if term == self.virtual_model._search_term:
            self.virtual_model.setSearchResults(indices)
    
    def _onSelectionChanged(self):
        """Handle selection changes."""
        selected_rows = []
        for index in self.selectionModel().selectedRows():
            selected_rows.append(index.row())
        self.selectionChanged.emit(selected_rows)
    
    def _onDoubleClick(self, index: QModelIndex):
        """Handle double-click events."""
        if index.isValid():
            row_data = self.getSelectedRowData()
            if row_data:
                self.rowDoubleClicked.emit(index.row(), row_data)
    
    def closeEvent(self, event):
        """Clean up when closing."""
        if self.data_loader_thread.isRunning():
            self.data_loader_thread.quit()
            self.data_loader_thread.wait(3000)  # Wait up to 3 seconds
        super().closeEvent(event)


class VirtualTableWidget(QWidget):
    """
    Complete virtual table widget with search and controls.
    """
    
    def __init__(self, columns: List[Dict[str, Any]], data_source, parent=None):
        super().__init__(parent)
        
        self.columns = columns
        self.data_source = data_source
        
        self.setupUI()
        self.connectSignals()
    
    def setupUI(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Search and controls
        controls_layout = QHBoxLayout()
        
        # Search
        controls_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Enter search term...")
        controls_layout.addWidget(self.search_edit)
        
        # Search column selection
        self.search_column_combo = QComboBox()
        self.search_column_combo.addItem("All Columns", "")
        for i, col in enumerate(self.columns):
            self.search_column_combo.addItem(col.get('name', f'Column {i}'), col.get('key', f'col_{i}'))
        controls_layout.addWidget(self.search_column_combo)
        
        # Search button
        self.search_btn = QPushButton("Search")
        controls_layout.addWidget(self.search_btn)
        
        # Clear search
        self.clear_search_btn = QPushButton("Clear")
        controls_layout.addWidget(self.clear_search_btn)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        controls_layout.addWidget(self.refresh_btn)
        
        controls_layout.addStretch()
        
        # Status
        self.status_label = QLabel("Ready")
        controls_layout.addWidget(self.status_label)
        
        layout.addLayout(controls_layout)
        
        # Virtual table
        self.table = VirtualTableView(self.columns, self.data_source)
        layout.addWidget(self.table)
        
        # Progress bar for loading
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
    
    def connectSignals(self):
        """Connect UI signals."""
        self.search_btn.clicked.connect(self.performSearch)
        self.clear_search_btn.clicked.connect(self.clearSearch)
        self.refresh_btn.clicked.connect(self.refresh)
        self.search_edit.returnPressed.connect(self.performSearch)
        
        # Table signals
        self.table.rowDoubleClicked.connect(self.onRowDoubleClicked)
        self.table.selectionChanged.connect(self.onSelectionChanged)
    
    def performSearch(self):
        """Perform search operation."""
        term = self.search_edit.text().strip()
        column = self.search_column_combo.currentData()
        
        if term:
            self.status_label.setText(f"Searching for '{term}'...")
            self.progress_bar.setVisible(True)
            self.table.search(term, column)
        else:
            self.clearSearch()
    
    def clearSearch(self):
        """Clear search and show all data."""
        self.search_edit.clear()
        self.table.search("", "")
        self.status_label.setText("Ready")
        self.progress_bar.setVisible(False)
    
    def refresh(self):
        """Refresh the table."""
        self.status_label.setText("Refreshing...")
        self.progress_bar.setVisible(True)
        self.table.refresh()
        self.status_label.setText("Ready")
        self.progress_bar.setVisible(False)
    
    def onRowDoubleClicked(self, row: int, data: dict):
        """Handle row double-click - override in subclass."""
        pass
    
    def onSelectionChanged(self, selected_rows: List[int]):
        """Handle selection changes - override in subclass."""
        if selected_rows:
            self.status_label.setText(f"Selected row: {selected_rows[0] + 1}")
        else:
            self.status_label.setText("Ready")
    
    def getSelectedRowData(self) -> Optional[Dict[str, Any]]:
        """Get data for the currently selected row."""
        return self.table.getSelectedRowData()
    
    def setDataSource(self, data_source):
        """Change the data source."""
        self.data_source = data_source
        self.table.setDataSource(data_source)
