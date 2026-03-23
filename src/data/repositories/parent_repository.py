# src/data/repositories/parent_repository.py

import sqlite3
import logging

class ParentRepository:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_parent_by_id(self, parent_id):
        """Retrieves a parent by their ID."""
        try:
            query = "SELECT * FROM Parents WHERE id = ?"
            return self.db_manager.execute_query(query, (parent_id,), fetchone=True)
        except sqlite3.Error as e:
            self.logger.error(f"Database error fetching parent: {e}")
            return None
