import os
import bcrypt
import sqlite3
import logging
import mysql.connector
from .sync_engine import SyncEngine
from datetime import datetime
from .connection_pool import initialize_connection_pool, get_connection_pool, close_connection_pool


class _PooledConnectionHandle:
    """
    Backward-compatible pooled connection wrapper.

    Supports both patterns used across the codebase:
    1) conn = db_manager.get_connection(); conn.cursor()
    2) with db_manager.get_connection() as conn: ...
    """

    def __init__(self, connection_context):
        self._connection_context = connection_context
        self._connection = self._connection_context.__enter__()
        self._closed = False

    def __getattr__(self, item):
        return getattr(self._connection, item)

    def __enter__(self):
        return self._connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._release(exc_type, exc_val, exc_tb)

    def close(self):
        self._release(None, None, None)

    def _release(self, exc_type, exc_val, exc_tb):
        if self._closed:
            return False
        self._closed = True
        return bool(self._connection_context.__exit__(exc_type, exc_val, exc_tb))

    def __del__(self):
        try:
            if not getattr(self, "_closed", True):
                self._connection_context.__exit__(None, None, None)
                self._closed = True
        except Exception:
            # Best-effort safety on interpreter shutdown.
            pass

class DatabaseManager:
    """
    Production-ready database manager implementing singleton pattern.
    Handles all database operations for the Learner Payment Management System.
    Uses local-first architecture with real-time MySQL sync.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_file, mysql_config=None, enable_sync=False):
        if hasattr(self, 'is_initialized'):
            return  # Already initialized
        self.db_file = db_file
        self.mysql_config = mysql_config
        self.enable_sync = enable_sync
        self.sync_v2_enabled = str(os.getenv("SYNC_V2_ENABLED", "true")).lower() in {"1", "true", "yes"}
        self.sync_engine = None
        logging.info(f"DatabaseManager initializing with db_file: '{self.db_file}'")
        
        # Ensure the directory for the db file exists
        db_dir = os.path.dirname(db_file)
        if db_dir:
            try:
                os.makedirs(db_dir, exist_ok=True)
                logging.info(f"Verified database directory exists: {db_dir}")
            except OSError as e:
                error_msg = f"Failed to create/verify database directory {db_dir}: {e}"
                logging.error(error_msg)
                logging.debug(f"Current working directory: {os.getcwd()}")
                logging.debug(f"Full path attempted: {os.path.abspath(db_dir)}")
                raise RuntimeError(error_msg) from e
                
        # Initialize the global connection pool
        initialize_connection_pool(database_path=self.db_file)

        # Legacy real-time sync engine is only used when SYNC_V2 is disabled.
        if self.mysql_config and self.enable_sync and not self.sync_v2_enabled:
            self.sync_engine = SyncEngine(
                self,
                self.mysql_config,
                sync_intervals={"incremental": 30},
            )
            self.sync_engine.start()
            logging.info("Legacy sync engine started (30s interval)")
        
        self.is_initialized = True
        self._log_db_info()

    def _log_db_info(self):
        """Log database file information"""
        try:
            if os.path.exists(self.db_file):
                stats = os.stat(self.db_file)
                logging.info(f"Database file exists. Size: {stats.st_size/1024:.2f}KB")
                logging.info(f"Last modified: {datetime.fromtimestamp(stats.st_mtime)}")
            else:
                logging.info("Database file does not exist yet - will be created")
        except Exception as e:
            logging.warning(f"Could not get database file information: {e}")

    def get_connection(self):
        """
        Get a pooled database connection handle.

        Returned object behaves like a sqlite3 connection and can also be used
        as a context manager.
        """
        pool = get_connection_pool()
        if not pool:
            raise Exception("Connection pool is not initialized.")
        return _PooledConnectionHandle(pool.get_connection())

    def _connect(self):
        """
        Backward-compatible alias for legacy call sites.

        Older service/repository code expects a raw-like connection object from
        `db_manager._connect()` and manages commit/rollback/close itself. The
        pooled handle returned here preserves that behavior while routing
        everything through the shared connection pool.
        """
        return self.get_connection()

    def close(self):
        """Close database connection is handled by the pool and is now a no-op."""
        pass

    def apply_schema_change(self, sqlite_query, mysql_query):
        """Apply schema changes to both SQLite and MySQL databases."""
        try:
            # Apply to SQLite
            self.execute_query(sqlite_query, commit=True)
            logging.info("SQLite schema change applied successfully.")

            # Apply to MySQL
            if self.mysql_config:
                mysql_conn = mysql.connector.connect(**self.mysql_config)
                with mysql_conn:
                    mysql_cursor = mysql_conn.cursor()
                    mysql_cursor.execute(mysql_query)
                    mysql_conn.commit()
                    logging.info("MySQL schema change applied successfully.")

        except sqlite3.Error as e:
            logging.error(f"SQLite error applying schema change: {e}")
        except mysql.connector.Error as e:
            logging.error(f"MySQL error applying schema change: {e}")

    def setup_database(self):
        """Initialize the database with required tables by running migrations."""
        self.run_migrations()
        # Ensure missing columns are added after migrations
        with self.get_connection() as conn:
            cursor = conn.cursor()
            self._add_missing_columns(cursor)
            # conn.commit() # Removed: handled by context manager

    def _add_missing_columns(self, cursor):
        """Add missing columns to existing tables if they don't exist."""
        try:
            tables = ['Users', 'Parents', 'Families', 'Learners', 'PaymentOptions', 'PaymentTerms', 'Payments', 'LearnerPayments']
            for table in tables:
                # Check if table exists first
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
                if not cursor.fetchone():
                    continue
                    
                # Check if columns exist
                cursor.execute(f"PRAGMA table_info({table})")
                columns = {row[1] for row in cursor.fetchall()}
                
                try:
                    # Add columns without defaults first
                    if 'last_modified_timestamp' not in columns:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN last_modified_timestamp DATETIME")
                        # Update with current timestamp after adding
                        cursor.execute(f"UPDATE {table} SET last_modified_timestamp = CURRENT_TIMESTAMP")
                    
                    if 'is_dirty' not in columns:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN is_dirty INTEGER")
                        # Set default value after adding
                        cursor.execute(f"UPDATE {table} SET is_dirty = 1")
                    
                    if 'uuid' not in columns:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN uuid TEXT")
                        # Generate UUIDs for existing rows
                        cursor.execute(f"UPDATE {table} SET uuid = lower(hex(randomblob(16))) WHERE uuid IS NULL")
                    
                    logging.info(f"Successfully updated table {table} with missing columns")
                    
                except sqlite3.OperationalError as e:
                    logging.warning(f"Column addition failed for table {table}: {e}")
                    continue
                except Exception as e:
                    logging.error(f"Unexpected error updating table {table}: {e}")
                    continue

            logging.info("Successfully added missing columns to existing tables")
            
        except Exception as e:
            logging.error(f"Error in _add_missing_columns: {e}")
            raise

    def _create_version_table(self, cursor):
        """Creates the Version table to track current schema version."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Version (
                version INTEGER PRIMARY KEY
            )
        """)
        # Insert initial version if table is empty
        cursor.execute("INSERT OR IGNORE INTO Version (version) VALUES (0)")

    def run_migrations(self):
        """Runs the database migrations."""
        import importlib.util
        # Initialize version table and read current version in a short-lived connection.
        with self.get_connection() as conn:
            cursor = conn.cursor()
            self._create_version_table(cursor)
            cursor.execute("SELECT version FROM Version")
            row = cursor.fetchone()
            current_version = row[0] if row else 0

        migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        if not os.path.exists(migrations_dir):
            os.makedirs(migrations_dir)
        migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith('.py')])

        for migration_file in migration_files:
            version = int(migration_file.split('_')[0])
            if version <= current_version:
                continue

            module_name = migration_file[:-3]
            file_path = os.path.join(migrations_dir, migration_file)
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)

            logging.info(f"Running migration: {migration_file}")
            try:
                spec.loader.exec_module(module)
                module.upgrade(self)  # Pass self (DatabaseManager instance) to migration.

                # Persist migration version in a fresh connection to avoid nested-lock issues.
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE Version SET version = ?", (version,))

                current_version = version
                logging.info(f"Migration {migration_file} applied successfully.")
            except Exception as e:
                logging.error(f"Error applying migration {migration_file}: {e}", exc_info=True)
                raise

    def _create_triggers(self, cursor):
        """Creates triggers to automatically update last_modified_timestamp and is_dirty flag."""
        tables = ['Users', 'Parents', 'Families', 'Learners', 'PaymentOptions', 'PaymentTerms', 'Payments', 'LearnerPayments']
        for table in tables:
            # Trigger for INSERT operations
            cursor.execute(f'''
                CREATE TRIGGER IF NOT EXISTS {table}_insert_trigger
                AFTER INSERT ON {table}
                FOR EACH ROW
                BEGIN
                    UPDATE {table}
                    SET last_modified_timestamp = CURRENT_TIMESTAMP,
                        is_dirty = 1,
                        uuid = (select lower(hex(randomblob(16))))
                    WHERE rowid = NEW.rowid;
                END;
            ''')
            # Trigger for UPDATE operations
            cursor.execute(f'''
                CREATE TRIGGER IF NOT EXISTS {table}_update_trigger
                AFTER UPDATE ON {table}
                FOR EACH ROW
                BEGIN
                    UPDATE {table}
                    SET last_modified_timestamp = CURRENT_TIMESTAMP,
                        is_dirty = 1
                    WHERE rowid = NEW.rowid;
                END;
            ''')

    def _ensure_admin_user_exists(self, cursor):
        """Ensures system has an admin user with secure password handling."""
        cursor.execute("SELECT COUNT(*) FROM Users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            hashed_password = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt())
            cursor.execute(
                "INSERT INTO Users (username, password, role) VALUES (?, ?, ?)",
                ('admin', hashed_password.decode('utf-8'), 'admin')
            )
            logging.warning("Default admin user created - CHANGE PASSWORD IMMEDIATELY")

    def execute_query(self, query, params=(), fetchone=False, fetchall=False, commit=False, sync_to_mysql=True):
        """Executes a given SQL query with parameters and optionally triggers real-time sync."""
        return self._execute_query_with_retry(query, params, fetchone, fetchall, commit, sync_to_mysql)

    def _execute_query_with_retry(self, query, params=(), fetchone=False, fetchall=False, commit=False, sync_to_mysql=True, max_retries=3):
        """Executes a query using the connection pool with retry logic."""
        import time
        
        pool = get_connection_pool()
        if not pool:
            raise Exception("Connection pool not initialized.")

        for attempt in range(max_retries):
            start_time = datetime.now()
            try:
                # Use the pool's context manager to get a connection
                with pool.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(query, params)

                    result = None
                    if fetchone:
                        result = cursor.fetchone()
                    elif fetchall:
                        result = cursor.fetchall()
                    
                    if commit:
                        conn.commit()
                        if query.strip().upper().startswith("INSERT"):
                            result = cursor.lastrowid
                        else:
                            result = True

                        # Trigger sync for data modification
                        if sync_to_mysql and self.sync_engine and self._is_data_modification_query(query):
                            self.sync_engine.trigger_immediate_sync()
                    
                    execution_time = (datetime.now() - start_time).total_seconds()
                    logging.debug(f"Query execution time: {execution_time:.3f} seconds")
                    return result

            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "locked" in error_msg and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 0.1
                    logging.warning(f"Database locked, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error(f"Database query failed after {max_retries} attempts: {query}", exc_info=True)
                    if params: logging.error(f"Parameters: {params}")
                    raise
            except sqlite3.Error as e:
                logging.error(f"Database query failed: {query}", exc_info=True)
                if params: logging.error(f"Parameters: {params}")
                raise

    def _is_data_modification_query(self, query):
        """Checks if the query modifies data (INSERT, UPDATE, DELETE)."""
        query_upper = query.strip().upper()
        return any(query_upper.startswith(cmd) for cmd in ['INSERT', 'UPDATE', 'DELETE'])

    def get_all_families(self):
        """Fetches all families, ordered by name."""
        query = "SELECT family_id, family_name, family_account_no, payment_mode, discount_percentage FROM Families ORDER BY family_name"
        return self.execute_query(query, fetchall=True)

    def add_family(self, family_name, family_account_no, payment_mode_db, discount):
        """Adds a new family to the database."""
        query = """INSERT INTO Families (family_name, family_account_no, payment_mode, discount_percentage)
                   VALUES (?, ?, ?, ?)"""
        params = (family_name, family_account_no, payment_mode_db, discount)
        return self.execute_query(query, params, commit=True)

    def update_family(self, family_id, family_name, family_account_no, payment_mode_db, discount):
        """Updates an existing family."""
        query = """UPDATE Families SET family_name = ?, family_account_no = ?, payment_mode = ?, discount_percentage = ?
                   WHERE family_id = ?"""
        params = (family_name, family_account_no, payment_mode_db, discount, family_id)
        self.execute_query(query, params, commit=True)

    def delete_family(self, family_id):
        """Deletes a family by its ID. Fails if restricted by FK."""
        check_query = "SELECT COUNT(*) FROM Learners WHERE family_id = ?"
        try:
            result = self.execute_query(check_query, (family_id,), fetchone=True)
            if result and result[0] > 0:
                return False, "Cannot delete family: There are learners associated with it."

            delete_query = "DELETE FROM Families WHERE family_id = ?"
            self.execute_query(delete_query, (family_id,), commit=True)
            return True, ""
        except sqlite3.IntegrityError as e:
            error_msg = f"Database constraint violation: {str(e)}"
            logging.error(f"Failed to delete family {family_id}: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Error deleting family: {str(e)}"
            logging.error(f"Failed to delete family {family_id}: {error_msg}")
            return False, error_msg

    def get_learner_count_for_family(self, family_id):
        """Counts how many active learners are associated with a given family ID."""
        query = "SELECT COUNT(*) FROM Learners WHERE family_id = ? AND is_active = 1"
        result = self.execute_query(query, (family_id,), fetchone=True)
        return result[0] if result else 0

    def get_family_id_by_account_no(self, account_no):
        """Gets a family's ID using their account number."""
        query = "SELECT family_id FROM Families WHERE family_account_no = ?"
        result = self.execute_query(query, (account_no,), fetchone=True)
        return result[0] if result else None

    def shutdown(self):
        """Safely shuts down the database manager and sync engine."""
        if self.sync_engine:
            self.sync_engine.stop()
            logging.info("Sync engine stopped")
        try:
            close_connection_pool()
            logging.info("Connection pool closed successfully.")
        except Exception as e:
            logging.error(f"Error closing database during shutdown: {e}")


# Example Usage (main guard)
if __name__ == "__main__":
    logging.info("Running DatabaseManager setup directly...")
    db_file_path = "school_management.db"
    logging.info(f"Database file: {os.path.abspath(db_file_path)}")

    db_manager = DatabaseManager(db_file_path)
    try:
        db_manager.setup_database()
        logging.info("--- Database setup execution finished ---")

    except RuntimeError as e:
        logging.error(f"A runtime error occurred during database operations: {e}")
    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")
