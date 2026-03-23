import threading
import time
import sqlite3
import mysql.connector
import logging
import uuid
from datetime import datetime
import queue

class SyncEngine(threading.Thread):
    def __init__(self, db_manager, mysql_config, sync_intervals=None):
        super().__init__()
        self.db_manager = db_manager
        self.mysql_config = mysql_config
        self.daemon = True
        self._stop_event = threading.Event()
        self._immediate_sync_queue = queue.Queue()
        
        # Configurable sync intervals (in seconds)
        default_intervals = {
            'full_sync': 300,      # 5 minutes for full synchronization
            'incremental': 60,     # 1 minute for incremental updates
            'learners': 120,       # 2 minutes for learner data
            'payments': 90,        # 1.5 minutes for payment data
            'families': 180,       # 3 minutes for family data
            'payment_options': 300, # 5 minutes for payment options
            'settings': 600        # 10 minutes for system settings
        }
        
        self.sync_intervals = sync_intervals or default_intervals
        self.sync_interval = self.sync_intervals.get('incremental', 60)  # Default interval
        
        # Track last sync times for different data types
        self.last_sync_times = {
            'full_sync': None,
            'incremental': None,
            'learners': None,
            'payments': None,
            'families': None,
            'payment_options': None,
            'settings': None
        }
        
        # Memory optimization settings
        self.batch_size = 500  # Process records in smaller batches
        self.max_memory_records = 1000  # Maximum records to hold in memory
        
        # Categorize tables by sync frequency
        self.table_categories = {
            'high_frequency': ['Payments', 'LearnerPayments', 'AuditLog'],
            'medium_frequency': ['Learners', 'Users'],
            'low_frequency': ['Families', 'Parents', 'PaymentOptions', 'PaymentTerms']
        }
        
        self.tables_to_sync = [
            'Users', 'Parents', 'Families', 'Learners', 'PaymentOptions', 
            'PaymentTerms', 'Payments', 'LearnerPayments', 'AuditLog'
        ]

    def stop(self):
        self._stop_event.set()
        
    def trigger_immediate_sync(self):
        """Triggers an immediate sync by adding to the queue."""
        try:
            self._immediate_sync_queue.put_nowait("sync_now")
        except queue.Full:
            logging.warning("Immediate sync queue is full, sync request ignored")

    def run(self):
        while not self._stop_event.is_set():
            try:
                # Check for immediate sync requests (non-blocking)
                try:
                    self._immediate_sync_queue.get_nowait()
                    logging.info("Processing immediate sync request")
                    self.sync()
                except queue.Empty:
                    pass
                
                # Regular interval sync
                if self._stop_event.wait(self.sync_interval):
                    break  # Stop event was set
                
                self.sync()
                
            except Exception as e:
                logging.error(f"Error during sync: {e}")
                time.sleep(1)  # Brief pause on error

    def sync(self):
        logging.info("Starting database synchronization...")
        mysql_conn = None
        try:
            mysql_conn = mysql.connector.connect(**self.mysql_config)
            self.upload_changes(mysql_conn)
            self.download_changes(mysql_conn)
            logging.info("Database synchronization finished.")
        except mysql.connector.Error as err:
            logging.error(f"MySQL error during sync: {err}")
        finally:
            if mysql_conn and mysql_conn.is_connected():
                mysql_conn.close()

    def upload_changes(self, mysql_conn):
        logging.info("Uploading changes to MySQL...")
        sqlite_conn = self.db_manager.get_connection()
        total_uploaded = 0
        
        try:
            with sqlite_conn:
                mysql_cursor = mysql_conn.cursor(dictionary=True)
                
                for table_name in self.tables_to_sync:
                    cursor = sqlite_conn.cursor()
                    cursor.execute(f"SELECT * FROM {table_name} WHERE is_dirty = 1")
                    dirty_rows = cursor.fetchall()
                    
                    if not dirty_rows:
                        continue
                    
                    logging.info(f"Uploading {len(dirty_rows)} dirty rows from {table_name}")
                    
                    # Get column names from the local table
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns_info = cursor.fetchall()
                    column_names = [info[1] for info in columns_info if info[1] not in ('is_dirty')]

                    for row in dirty_rows:
                        row_dict = dict(zip([c[1] for c in columns_info], row))
                        
                        # Prepare the INSERT ... ON DUPLICATE KEY UPDATE query
                        cols = ", ".join([f"`{c}`" for c in column_names])
                        placeholders = ", ".join(["%s"] * len(column_names))
                        update_clause = ", ".join([f"`{c}`=VALUES(`{c}`)" for c in column_names if c not in ['uuid']])
                        
                        query = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_clause}"
                        values = [row_dict.get(col) for col in column_names]

                        try:
                            mysql_cursor.execute(query, tuple(values))
                            
                            # If successful, mark the row as not dirty in SQLite
                            sqlite_conn.execute(f"UPDATE {table_name} SET is_dirty = 0 WHERE uuid = ?", (row_dict['uuid'],))
                            total_uploaded += 1
                            
                        except mysql.connector.Error as err:
                            logging.error(f"Failed to upload record {row_dict.get('uuid')} to {table_name}: {err}")
                
                mysql_conn.commit()
                if total_uploaded > 0:
                    logging.info(f"Successfully uploaded {total_uploaded} records to MySQL")

        except sqlite3.Error as e:
            logging.error(f"SQLite error during upload: {e}")
        finally:
            if sqlite_conn:
                sqlite_conn.close()


    def download_changes(self, mysql_conn):
        logging.info("Downloading changes from MySQL...")
        sqlite_conn = self.db_manager.get_connection()
        total_downloaded = 0
        
        try:
            with sqlite_conn:
                cursor = sqlite_conn.cursor()
                
                # Get the timestamp of the last successful sync
                cursor.execute("SELECT setting_value FROM SystemSettings WHERE setting_name = 'last_sync_timestamp'")
                last_sync_timestamp = cursor.fetchone()
                if last_sync_timestamp:
                    last_sync_timestamp = last_sync_timestamp[0]
                else:
                    # First sync, get all records
                    last_sync_timestamp = '1970-01-01 00:00:00'

                mysql_cursor = mysql_conn.cursor(dictionary=True)
                
                for table_name in self.tables_to_sync:
                    try:
                        # Check if table exists in MySQL
                        check_table_query = f"SHOW TABLES LIKE '{table_name}'"
                        mysql_cursor.execute(check_table_query)
                        if not mysql_cursor.fetchone():
                            logging.warning(f"Table {table_name} does not exist in MySQL, skipping")
                            continue
                        
                        mysql_cursor.execute(f"SELECT * FROM {table_name} WHERE last_modified_timestamp > %s", (last_sync_timestamp,))
                        new_rows = mysql_cursor.fetchall()
                        
                        if not new_rows:
                            continue
                        
                        logging.info(f"Downloading {len(new_rows)} new/updated rows from {table_name}")

                        for row in new_rows:
                            # Check for conflicts: if the local record is dirty, use last-write-wins strategy
                            cursor.execute(f"SELECT is_dirty, last_modified_timestamp FROM {table_name} WHERE uuid = ?", (row['uuid'],))
                            local_record = cursor.fetchone()

                            if local_record and local_record[0] == 1:  # is_dirty is true
                                try:
                                    local_timestamp = datetime.fromisoformat(local_record[1])
                                    remote_timestamp = row['last_modified_timestamp']
                                    if isinstance(remote_timestamp, str):
                                        remote_timestamp = datetime.fromisoformat(remote_timestamp)
                                    
                                    if local_timestamp > remote_timestamp:
                                        logging.warning(f"Conflict detected for record {row['uuid']} in {table_name}. Local changes are newer, skipping download.")
                                        continue
                                except (ValueError, TypeError) as e:
                                    logging.warning(f"Error comparing timestamps for {row['uuid']}: {e}")

                            # Get column names from the remote row to build the query
                            column_names = list(row.keys())
                            cols = ", ".join(column_names)
                            placeholders = ", ".join(["?"] * len(column_names))
                            
                            # Use INSERT OR REPLACE to handle both new records and updates
                            # Set is_dirty = 0 since this is coming from the authoritative source
                            values = list(row.values())
                            if 'is_dirty' in row:
                                dirty_index = column_names.index('is_dirty')
                                values[dirty_index] = 0  # Mark as clean since it's from MySQL
                            
                            query = f"INSERT OR REPLACE INTO {table_name} ({cols}) VALUES ({placeholders})"
                            cursor.execute(query, tuple(values))
                            total_downloaded += 1
                            
                    except mysql.connector.Error as err:
                        logging.error(f"MySQL error downloading from {table_name}: {err}")
                    except sqlite3.Error as err:
                        logging.error(f"SQLite error updating {table_name}: {err}")

                # Update the last sync timestamp
                new_sync_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("INSERT OR REPLACE INTO SystemSettings (setting_name, setting_value) VALUES ('last_sync_timestamp', ?)", (new_sync_timestamp,))
                
                sqlite_conn.commit()
                
                if total_downloaded > 0:
                    logging.info(f"Successfully downloaded {total_downloaded} records from MySQL")

        except sqlite3.Error as e:
            logging.error(f"SQLite error during download: {e}")
        except mysql.connector.Error as err:
            logging.error(f"MySQL error during download: {err}")
        finally:
            if sqlite_conn:
                sqlite_conn.close()

if __name__ == '__main__':
    # This is for testing purposes
    logging.basicConfig(level=logging.INFO)
    # You would need to provide a mock db_manager and mysql_config here
    # sync_engine = SyncEngine(db_manager_mock, mysql_config_mock)
    # sync_engine.start()
    # time.sleep(300) # run for 5 minutes
    # sync_engine.stop()
