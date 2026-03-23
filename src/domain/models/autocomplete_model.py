from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex
import sqlite3

class AutocompleteModel(QAbstractItemModel):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.results = []

    def rowCount(self, parent=QModelIndex()):
        return len(self.results)

    def columnCount(self, parent=QModelIndex()):
        return 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and index.isValid():
            return self.results[index.row()]
        return None

    def index(self, row, column, parent=QModelIndex()):
        if 0 <= row < len(self.results) and column == 0:
            return self.createIndex(row, column)
        return QModelIndex()

    def parent(self, index):
        return QModelIndex()

    def update_completer(self, text):
        # Clean the input text
        text = text.strip()
        
        # Show results immediately when user starts typing
        if len(text) < 1:
            self.beginResetModel()
            self.results = []
            self.endResetModel()
            return

        try:
            # Enhanced query to search in both name and surname, and also handle partial matches
            query = """
                SELECT name, surname, acc_no FROM Learners 
                WHERE (name LIKE ? OR surname LIKE ? OR (name || ' ' || surname) LIKE ?) 
                AND is_active = 1
                ORDER BY 
                    CASE 
                        WHEN name LIKE ? THEN 1
                        WHEN surname LIKE ? THEN 2
                        ELSE 3
                    END,
                    name, surname 
                LIMIT 15
            """
            # Create search patterns
            starts_with = f'{text}%'
            contains = f'%{text}%'
            
            params = (starts_with, starts_with, contains, starts_with, starts_with)
            learners = self.db_manager.execute_query(query, params, fetchall=True)
            
            self.beginResetModel()
            self.results = []
            if learners:
                for name, surname, acc_no in learners:
                    # Handle cases where acc_no might not have the expected format
                    try:
                        if '-' in acc_no:
                            acc_no_display = acc_no.split('-')[0][-4:]
                        else:
                            acc_no_display = acc_no[-4:]
                    except (IndexError, TypeError):
                        acc_no_display = str(acc_no)[-4:] if acc_no else "0000"
                    
                    display_name = f"{name} {surname} ({acc_no_display})"
                    self.results.append(display_name)
            
            # Force the model to notify about the update
            self.endResetModel()

        except sqlite3.Error as e:
            logging.exception(f"Error fetching autocomplete suggestions: {e}")
            self.beginResetModel()
            self.results = []
            self.endResetModel()
        except Exception as e:
            logging.exception(f"Unexpected error in autocomplete: {e}")
            self.beginResetModel()
            self.results = []
            self.endResetModel()
