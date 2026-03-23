"""
Database Connection Pool for Learner Payment Management Application

Provides efficient connection pooling, prepared statements, and connection lifecycle management.
Improves performance by reusing connections and reducing connection overhead.
"""

import sqlite3
import threading
import time
import logging
from typing import Optional, List, Dict, Any, Callable
from contextlib import contextmanager
from queue import Queue, Empty
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class ConnectionInfo:
    """Information about a pooled connection."""
    connection: sqlite3.Connection
    created_at: datetime
    last_used: datetime
    in_use: bool = False
    query_count: int = 0


class ConnectionPool:
    """
    Thread-safe SQLite connection pool with automatic cleanup and monitoring.
    
    Features:
    - Connection reuse and pooling
    - Automatic connection cleanup
    - Thread safety
    - Connection health monitoring
    - Prepared statement caching
    """
    
    def __init__(self, 
                 database_path: str, 
                 min_connections: int = 2,
                 max_connections: int = 10,
                 max_idle_time: timedelta = timedelta(minutes=30),
                 check_interval: timedelta = timedelta(minutes=5)):
        """
        Initialize the connection pool.
        
        Args:
            database_path: Path to the SQLite database
            min_connections: Minimum number of connections to maintain
            max_connections: Maximum number of connections allowed
            max_idle_time: Maximum time a connection can be idle before cleanup
            check_interval: How often to check for idle connections
        """
        self.database_path = database_path
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.check_interval = check_interval
        
        # Thread safety
        self._lock = threading.RLock()
        self._connections: Dict[int, ConnectionInfo] = {}
        self._available_connections = Queue(maxsize=max_connections)
        self._connection_counter = 0
        
        # Prepared statements cache
        self._prepared_statements: Dict[str, sqlite3.Statement] = {}
        
        # Monitoring
        self._stats = {
            'total_created': 0,
            'total_closed': 0,
            'current_active': 0,
            'peak_active': 0,
            'total_queries': 0
        }
        
        # Background cleanup thread
        self._cleanup_thread = None
        self._shutdown_event = threading.Event()
        
        # Initialize pool
        self._initialize_pool()
        self._start_cleanup_thread()
        
        logging.info(f"Connection pool initialized: {min_connections}-{max_connections} connections")
    
    def _initialize_pool(self):
        """Create initial connections."""
        with self._lock:
            for _ in range(self.min_connections):
                conn = self._create_connection()
                if conn:
                    self._add_connection_to_pool(conn)
    
    def _create_connection(self) -> Optional[sqlite3.Connection]:
        """Create a new database connection with optimal settings."""
        try:
            conn = sqlite3.connect(
                self.database_path,
                timeout=30,  # Increased timeout
                check_same_thread=False  # Allow cross-thread usage
            )
            
            # Optimize connection settings
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging for better concurrency
            conn.execute("PRAGMA synchronous = NORMAL")  # Balance between safety and speed
            conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA mmap_size = 268435456")  # 256MB memory map
            
            # Row factory for easier data access
            conn.row_factory = sqlite3.Row
            
            with self._lock:
                self._stats['total_created'] += 1
                
            logging.debug(f"Created new database connection (total: {self._stats['total_created']})")
            return conn
            
        except sqlite3.Error as e:
            logging.error(f"Failed to create database connection: {e}")
            return None
    
    def _add_connection_to_pool(self, conn: sqlite3.Connection):
        """Add a connection to the pool."""
        conn_id = self._connection_counter
        self._connection_counter += 1
        
        conn_info = ConnectionInfo(
            connection=conn,
            created_at=datetime.now(),
            last_used=datetime.now()
        )
        
        self._connections[conn_id] = conn_info
        self._available_connections.put(conn_id)
    
    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool using context manager.
        
        Usage:
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users")
        """
        conn_id = None
        try:
            conn_id = self._acquire_connection()
            if conn_id is not None:
                conn_info = self._connections[conn_id]
                conn_info.last_used = datetime.now()
                conn_info.query_count += 1
                
                with self._lock:
                    self._stats['total_queries'] += 1

                conn = conn_info.connection
                try:
                    yield conn
                    # Commit on successful context exit so callers can rely on
                    # context-manager transaction semantics.
                    conn.commit()
                except Exception:
                    try:
                        conn.rollback()
                    except sqlite3.Error:
                        pass
                    raise
            else:
                raise Exception("Could not acquire database connection")
        finally:
            if conn_id is not None:
                self._release_connection(conn_id)
    
    def _acquire_connection(self) -> Optional[int]:
        """Acquire a connection from the pool."""
        try:
            # Try to get an available connection
            conn_id = self._available_connections.get(timeout=5)
            
            with self._lock:
                if conn_id in self._connections:
                    conn_info = self._connections[conn_id]
                    conn_info.in_use = True
                    self._stats['current_active'] += 1
                    self._stats['peak_active'] = max(
                        self._stats['peak_active'], 
                        self._stats['current_active']
                    )
                    return conn_id
                
        except Empty:
            # No connections available, try to create a new one
            with self._lock:
                if len(self._connections) < self.max_connections:
                    conn = self._create_connection()
                    if conn:
                        self._add_connection_to_pool(conn)
                        return self._acquire_connection()  # Recursive call
        
        logging.warning("Could not acquire database connection")
        return None
    
    def _release_connection(self, conn_id: int):
        """Release a connection back to the pool."""
        with self._lock:
            if conn_id in self._connections:
                conn_info = self._connections[conn_id]
                conn_info.in_use = False
                conn_info.last_used = datetime.now()
                self._stats['current_active'] -= 1
                
                # Check if connection is still healthy
                try:
                    conn_info.connection.execute("SELECT 1")
                    self._available_connections.put(conn_id)
                except sqlite3.Error:
                    # Connection is broken, remove it
                    self._remove_connection(conn_id)
    
    def _remove_connection(self, conn_id: int):
        """Remove a connection from the pool."""
        if conn_id in self._connections:
            conn_info = self._connections[conn_id]
            try:
                conn_info.connection.close()
            except sqlite3.Error:
                pass  # Connection already closed or broken
            
            del self._connections[conn_id]
            with self._lock:
                self._stats['total_closed'] += 1
            
            logging.debug(f"Removed connection {conn_id} from pool")
    
    def _start_cleanup_thread(self):
        """Start background thread for connection cleanup."""
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            name="ConnectionPool-Cleanup",
            daemon=True
        )
        self._cleanup_thread.start()
    
    def _cleanup_worker(self):
        """Background worker for cleaning up idle connections."""
        while not self._shutdown_event.wait(self.check_interval.total_seconds()):
            self._cleanup_idle_connections()
    
    def _cleanup_idle_connections(self):
        """Remove idle connections that exceed max_idle_time."""
        current_time = datetime.now()
        connections_to_remove = []
        
        with self._lock:
            for conn_id, conn_info in self._connections.items():
                if (not conn_info.in_use and 
                    current_time - conn_info.last_used > self.max_idle_time and
                    len(self._connections) > self.min_connections):
                    connections_to_remove.append(conn_id)
        
        for conn_id in connections_to_remove:
            self._remove_connection(conn_id)
            
        if connections_to_remove:
            logging.debug(f"Cleaned up {len(connections_to_remove)} idle connections")
    
    def execute_query(self, 
                     query: str, 
                     params: tuple = (), 
                     fetch_one: bool = False,
                     fetch_all: bool = False) -> Any:
        """
        Execute a query using a pooled connection.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            fetch_one: Return single row
            fetch_all: Return all rows
            
        Returns:
            Query result based on fetch parameters
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            else:
                conn.commit()
                return cursor.lastrowid if query.strip().upper().startswith("INSERT") else True
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Execute a query with multiple parameter sets."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        with self._lock:
            return {
                **self._stats,
                'available_connections': self._available_connections.qsize(),
                'total_connections': len(self._connections),
                'in_use_connections': sum(1 for c in self._connections.values() if c.in_use)
            }
    
    def close(self):
        """Close all connections and shut down the pool."""
        logging.info("Shutting down connection pool...")
        
        # Signal cleanup thread to stop
        self._shutdown_event.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        
        # Close all connections
        with self._lock:
            for conn_id in list(self._connections.keys()):
                self._remove_connection(conn_id)
        
        logging.info("Connection pool shut down complete")
    
    def __enter__(self):
        return self
    
    @contextmanager
    def transaction(self):
        """
        Provides a transactional context manager.
        
        Usage:
            with pool.transaction() as conn:
                conn.execute("INSERT INTO ...")
                conn.execute("UPDATE ...")
        """
        conn_id = None
        conn = None
        try:
            conn_id = self._acquire_connection()
            if conn_id is not None:
                conn_info = self._connections[conn_id]
                conn = conn_info.connection
                # sqlite3 defaults to DEFERRED; explicit BEGIN is not strictly needed
                # but can make intent clearer. For simplicity, relying on default.
                yield conn
                conn.commit()
            else:
                raise Exception("Could not acquire database connection for transaction")
        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"Transaction rolled back due to error: {e}")
            raise
        finally:
            if conn_id is not None:
                self._release_connection(conn_id)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Global connection pool instance
_connection_pool: Optional[ConnectionPool] = None


def initialize_connection_pool(database_path: str, **kwargs) -> ConnectionPool:
    """Initialize the global connection pool."""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.close()
    
    _connection_pool = ConnectionPool(database_path, **kwargs)
    return _connection_pool


def get_connection_pool() -> Optional[ConnectionPool]:
    """Get the global connection pool instance."""
    return _connection_pool


def close_connection_pool():
    """Close the global connection pool."""
    global _connection_pool
    if _connection_pool:
        _connection_pool.close()
        _connection_pool = None
