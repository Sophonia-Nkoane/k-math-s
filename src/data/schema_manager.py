import logging
import mysql.connector
from typing import Dict, List, Optional

class SchemaManager:
    """
    Unified schema management for both SQLite and MySQL databases.
    Allows you to define schema changes once and apply to both databases.
    """
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    def create_table(self, table_name: str, columns: Dict[str, str], constraints: Optional[List[str]] = None):
        """
        Create a table in both SQLite and MySQL with unified column definitions.
        
        Args:
            table_name: Name of the table to create
            columns: Dictionary of column_name -> column_definition
            constraints: List of table constraints (foreign keys, checks, etc.)
        """
        # Convert column definitions to database-specific syntax
        sqlite_columns = self._convert_columns_for_sqlite(columns)
        mysql_columns = self._convert_columns_for_mysql(columns)
        
        # Build CREATE TABLE statements
        sqlite_cols = ",\n    ".join([f"{name} {definition}" for name, definition in sqlite_columns.items()])
        mysql_cols = ",\n    ".join([f"`{name}` {definition}" for name, definition in mysql_columns.items()])
        
        if constraints:
            sqlite_constraints = ",\n    ".join(constraints)
            mysql_constraints = ",\n    ".join(constraints)
            sqlite_cols += f",\n    {sqlite_constraints}"
            mysql_cols += f",\n    {mysql_constraints}"
        
        sqlite_query = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {sqlite_cols}
            )
        """
        
        mysql_query = f"""
            CREATE TABLE IF NOT EXISTS `{table_name}` (
                {mysql_cols}
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        
        logging.info(f"Creating table {table_name} in both databases")
        self.db_manager.apply_schema_change(sqlite_query, mysql_query)
        
    def add_column(self, table_name: str, column_name: str, column_definition: str):
        """Add a column to both databases."""
        sqlite_def = self._convert_column_for_sqlite(column_definition)
        mysql_def = self._convert_column_for_mysql(column_definition)
        
        sqlite_query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sqlite_def}"
        mysql_query = f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {mysql_def}"
        
        logging.info(f"Adding column {column_name} to table {table_name}")
        self.db_manager.apply_schema_change(sqlite_query, mysql_query)
        
    def drop_column(self, table_name: str, column_name: str):
        """Drop a column from both databases."""
        # Note: SQLite has limited ALTER TABLE support, might need to recreate table
        sqlite_query = f"-- SQLite doesn't support DROP COLUMN directly, manual migration needed"
        mysql_query = f"ALTER TABLE `{table_name}` DROP COLUMN `{column_name}`"
        
        logging.warning(f"Dropping column {column_name} from {table_name} - SQLite requires manual migration")
        # Only apply to MySQL for now, SQLite needs special handling
        if self.db_manager.mysql_config:
            mysql_conn = mysql.connector.connect(**self.db_manager.mysql_config)
            with mysql_conn:
                mysql_cursor = mysql_conn.cursor()
                mysql_cursor.execute(mysql_query)
                mysql_conn.commit()
                logging.info("MySQL column dropped successfully")
        
    def create_index(self, index_name: str, table_name: str, columns: List[str], unique: bool = False):
        """Create an index on both databases."""
        unique_keyword = "UNIQUE " if unique else ""
        column_list = ", ".join(columns)
        mysql_column_list = ", ".join([f"`{col}`" for col in columns])
        
        sqlite_query = f"CREATE {unique_keyword}INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_list})"
        mysql_query = f"CREATE {unique_keyword}INDEX `{index_name}` ON `{table_name}` ({mysql_column_list})"
        
        logging.info(f"Creating index {index_name} on table {table_name}")
        self.db_manager.apply_schema_change(sqlite_query, mysql_query)
        
    def drop_table(self, table_name: str):
        """Drop a table from both databases."""
        sqlite_query = f"DROP TABLE IF EXISTS {table_name}"
        mysql_query = f"DROP TABLE IF EXISTS `{table_name}`"
        
        logging.info(f"Dropping table {table_name}")
        self.db_manager.apply_schema_change(sqlite_query, mysql_query)
        
    def _convert_columns_for_sqlite(self, columns: Dict[str, str]) -> Dict[str, str]:
        """Convert generic column definitions to SQLite-specific syntax."""
        converted = {}
        for name, definition in columns.items():
            converted[name] = self._convert_column_for_sqlite(definition)
        return converted
        
    def _convert_columns_for_mysql(self, columns: Dict[str, str]) -> Dict[str, str]:
        """Convert generic column definitions to MySQL-specific syntax."""
        converted = {}
        for name, definition in columns.items():
            converted[name] = self._convert_column_for_mysql(definition)
        return converted
        
    def _convert_column_for_sqlite(self, definition: str) -> str:
        """Convert a column definition to SQLite syntax."""
        # Handle common type mappings
        definition = definition.replace("AUTO_INCREMENT", "AUTOINCREMENT")
        definition = definition.replace("VARCHAR", "TEXT")
        definition = definition.replace("DATETIME", "TEXT")
        definition = definition.replace("TIMESTAMP", "TEXT")
        return definition
        
    def _convert_column_for_mysql(self, definition: str) -> str:
        """Convert a column definition to MySQL syntax."""
        # Handle common type mappings
        definition = definition.replace("AUTOINCREMENT", "AUTO_INCREMENT")
        definition = definition.replace("TEXT DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        return definition

# Example usage functions
def create_example_table(schema_manager: SchemaManager):
    """Example of how to create a new table using SchemaManager."""
    columns = {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "uuid": "TEXT UNIQUE",
        "name": "TEXT NOT NULL",
        "email": "TEXT",
        "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        "is_active": "INTEGER DEFAULT 1",
        "last_modified_timestamp": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        "is_dirty": "INTEGER DEFAULT 0"
    }
    
    constraints = [
        "UNIQUE(email)"
    ]
    
    schema_manager.create_table("example_table", columns, constraints)
    
def add_example_column(schema_manager: SchemaManager):
    """Example of how to add a column to an existing table."""
    schema_manager.add_column("Learners", "middle_name", "TEXT")
    
def create_example_index(schema_manager: SchemaManager):
    """Example of how to create an index."""
    schema_manager.create_index("idx_learners_email", "Learners", ["email"], unique=True)

if __name__ == "__main__":
    # Example usage
    from data.database_manager import DatabaseManager
    
    # Initialize with your database configurations
    mysql_config = {
        'host': 'your_mysql_host',
        'user': 'your_username',
        'password': 'your_password',
        'database': 'your_database'
    }
    
    db_manager = DatabaseManager("school_management.db", mysql_config)
    schema_manager = SchemaManager(db_manager)
    
    # Example operations
    # create_example_table(schema_manager)
    # add_example_column(schema_manager)
    # create_example_index(schema_manager)
