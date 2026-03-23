"""
Base Repository Pattern Implementation

Provides a clean abstraction layer for database operations with caching,
validation, and transaction management.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
import sqlite3
from contextlib import contextmanager

from ..connection_pool import get_connection_pool

T = TypeVar('T')


@dataclass
class QueryResult:
    """Represents the result of a database query with metadata."""
    data: Any
    row_count: int
    execution_time_ms: float
    query: str
    success: bool = True
    error: Optional[str] = None


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository providing common database operations.
    
    Features:
    - Connection pooling
    - Query optimization
    - Caching integration
    - Transaction management
    - Automatic error handling
    - Query logging and metrics
    """
    
    def __init__(self, table_name: str, model_class: Type[T]):
        """
        Initialize the repository.
        
        Args:
            table_name: Database table name
            model_class: The model class for this repository
        """
        self.table_name = table_name
        self.model_class = model_class
        self._connection_pool = get_connection_pool()
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, datetime] = {}
        self._logger = logging.getLogger(f"{self.__class__.__name__}")
        
        if not self._connection_pool:
            raise RuntimeError("Connection pool not initialized. Call initialize_connection_pool() first.")
    
    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions.
        
        Usage:
            with repository.transaction():
                repository.create(item1)
                repository.update(item2)
                # Automatically commits on success, rolls back on exception
        """
        with self._connection_pool.get_connection() as conn:
            try:
                # Start transaction
                conn.execute("BEGIN")
                yield conn
                conn.commit()
                self._logger.debug("Transaction committed successfully")
            except Exception as e:
                conn.rollback()
                self._logger.error(f"Transaction rolled back due to error: {e}")
                raise
    
    def execute_query(self, 
                     query: str, 
                     params: tuple = (), 
                     fetch_one: bool = False,
                     fetch_all: bool = False,
                     use_cache: bool = False,
                     cache_key: Optional[str] = None,
                     cache_ttl_seconds: int = 300) -> QueryResult:
        """
        Execute a database query with comprehensive error handling and caching.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            fetch_one: Return single row
            fetch_all: Return all rows
            use_cache: Whether to use caching for this query
            cache_key: Custom cache key (auto-generated if not provided)
            cache_ttl_seconds: Cache time-to-live in seconds
        
        Returns:
            QueryResult with data and metadata
        """
        start_time = datetime.now()
        
        # Check cache first if enabled
        if use_cache and fetch_one or fetch_all:
            if not cache_key:
                cache_key = f"{hash(query + str(params))}"
            
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                return QueryResult(
                    data=cached_result,
                    row_count=len(cached_result) if isinstance(cached_result, list) else 1,
                    execution_time_ms=execution_time,
                    query=query,
                    success=True
                )
        
        try:
            result = self._connection_pool.execute_query(
                query=query,
                params=params,
                fetch_one=fetch_one,
                fetch_all=fetch_all
            )
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Cache the result if requested
            if use_cache and cache_key and (fetch_one or fetch_all):
                self._set_cache(cache_key, result, cache_ttl_seconds)
            
            row_count = 0
            if fetch_all and isinstance(result, list):
                row_count = len(result)
            elif fetch_one and result:
                row_count = 1
            
            self._logger.debug(f"Query executed successfully in {execution_time:.2f}ms: {query[:100]}...")
            
            return QueryResult(
                data=result,
                row_count=row_count,
                execution_time_ms=execution_time,
                query=query,
                success=True
            )
            
        except sqlite3.Error as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            self._logger.error(f"Database error in {execution_time:.2f}ms: {e} - Query: {query}")
            
            return QueryResult(
                data=None,
                row_count=0,
                execution_time_ms=execution_time,
                query=query,
                success=False,
                error=str(e)
            )
    
    def find_by_id(self, id_value: Any, use_cache: bool = True) -> Optional[T]:
        """Find a record by its primary key."""
        cache_key = f"{self.table_name}_by_id_{id_value}" if use_cache else None
        
        result = self.execute_query(
            query=f"SELECT * FROM {self.table_name} WHERE {self._get_primary_key()} = ?",
            params=(id_value,),
            fetch_one=True,
            use_cache=use_cache,
            cache_key=cache_key
        )
        
        if result.success and result.data:
            return self._row_to_model(result.data)
        return None
    
    def find_all(self, 
                 limit: Optional[int] = None,
                 offset: int = 0,
                 order_by: Optional[str] = None,
                 use_cache: bool = False) -> List[T]:
        """Find all records with optional pagination and ordering."""
        query = f"SELECT * FROM {self.table_name}"
        params = []
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        
        cache_key = f"{self.table_name}_all_{limit}_{offset}_{order_by}" if use_cache else None
        
        result = self.execute_query(
            query=query,
            params=tuple(params),
            fetch_all=True,
            use_cache=use_cache,
            cache_key=cache_key
        )
        
        if result.success and result.data:
            return [self._row_to_model(row) for row in result.data]
        return []
    
    def find_by_criteria(self, 
                        criteria: Dict[str, Any],
                        limit: Optional[int] = None,
                        order_by: Optional[str] = None,
                        use_cache: bool = False) -> List[T]:
        """Find records matching the given criteria."""
        if not criteria:
            return self.find_all(limit=limit, order_by=order_by, use_cache=use_cache)
        
        where_clauses = []
        params = []
        
        for column, value in criteria.items():
            if isinstance(value, list):
                placeholders = ','.join(['?' for _ in value])
                where_clauses.append(f"{column} IN ({placeholders})")
                params.extend(value)
            elif value is None:
                where_clauses.append(f"{column} IS NULL")
            else:
                where_clauses.append(f"{column} = ?")
                params.append(value)
        
        query = f"SELECT * FROM {self.table_name} WHERE {' AND '.join(where_clauses)}"
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cache_key = f"{self.table_name}_criteria_{hash(str(criteria))}" if use_cache else None
        
        result = self.execute_query(
            query=query,
            params=tuple(params),
            fetch_all=True,
            use_cache=use_cache,
            cache_key=cache_key
        )
        
        if result.success and result.data:
            return [self._row_to_model(row) for row in result.data]
        return []
    
    def create(self, entity: T) -> Optional[T]:
        """Create a new record."""
        data = self._model_to_dict(entity)
        columns = list(data.keys())
        placeholders = ['?' for _ in columns]
        
        query = f"""
            INSERT INTO {self.table_name} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """
        
        result = self.execute_query(
            query=query,
            params=tuple(data.values())
        )
        
        if result.success:
            # Clear relevant cache entries
            self._invalidate_cache_pattern(f"{self.table_name}_")
            
            # Return the created entity with the new ID if applicable
            if hasattr(entity, 'id') and result.data:
                setattr(entity, 'id', result.data)
            
            return entity
        else:
            raise RuntimeError(f"Failed to create {self.model_class.__name__}: {result.error}")
    
    def update(self, entity: T) -> bool:
        """Update an existing record."""
        data = self._model_to_dict(entity)
        primary_key = self._get_primary_key()
        
        if primary_key not in data:
            raise ValueError(f"Primary key '{primary_key}' not found in entity data")
        
        pk_value = data.pop(primary_key)
        
        set_clauses = [f"{column} = ?" for column in data.keys()]
        params = list(data.values()) + [pk_value]
        
        query = f"""
            UPDATE {self.table_name}
            SET {', '.join(set_clauses)}
            WHERE {primary_key} = ?
        """
        
        result = self.execute_query(query=query, params=tuple(params))
        
        if result.success:
            # Clear relevant cache entries
            self._invalidate_cache_pattern(f"{self.table_name}_")
            return True
        else:
            raise RuntimeError(f"Failed to update {self.model_class.__name__}: {result.error}")
    
    def delete(self, id_value: Any) -> bool:
        """Delete a record by its primary key."""
        primary_key = self._get_primary_key()
        
        result = self.execute_query(
            query=f"DELETE FROM {self.table_name} WHERE {primary_key} = ?",
            params=(id_value,)
        )
        
        if result.success:
            # Clear relevant cache entries
            self._invalidate_cache_pattern(f"{self.table_name}_")
            return True
        else:
            raise RuntimeError(f"Failed to delete {self.model_class.__name__}: {result.error}")
    
    def count(self, criteria: Optional[Dict[str, Any]] = None) -> int:
        """Count records matching the given criteria."""
        query = f"SELECT COUNT(*) FROM {self.table_name}"
        params = []
        
        if criteria:
            where_clauses = []
            for column, value in criteria.items():
                if value is None:
                    where_clauses.append(f"{column} IS NULL")
                else:
                    where_clauses.append(f"{column} = ?")
                    params.append(value)
            
            query += f" WHERE {' AND '.join(where_clauses)}"
        
        result = self.execute_query(
            query=query,
            params=tuple(params),
            fetch_one=True
        )
        
        if result.success and result.data:
            return result.data[0]
        return 0
    
    def exists(self, id_value: Any) -> bool:
        """Check if a record exists by its primary key."""
        primary_key = self._get_primary_key()
        
        result = self.execute_query(
            query=f"SELECT 1 FROM {self.table_name} WHERE {primary_key} = ? LIMIT 1",
            params=(id_value,),
            fetch_one=True
        )
        
        return result.success and result.data is not None
    
    # Cache management methods
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            if key in self._cache_ttl:
                if datetime.now() > self._cache_ttl[key]:
                    # Cache expired
                    del self._cache[key]
                    del self._cache_ttl[key]
                    return None
            return self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any, ttl_seconds: int):
        """Set value in cache with TTL."""
        self._cache[key] = value
        self._cache_ttl[key] = datetime.now().replace(microsecond=0) + \
                              datetime.fromtimestamp(ttl_seconds).replace(microsecond=0)
    
    def _invalidate_cache_pattern(self, pattern: str):
        """Invalidate cache entries matching a pattern."""
        keys_to_remove = [key for key in self._cache.keys() if pattern in key]
        for key in keys_to_remove:
            del self._cache[key]
            if key in self._cache_ttl:
                del self._cache_ttl[key]
    
    def clear_cache(self):
        """Clear all cache entries for this repository."""
        self._cache.clear()
        self._cache_ttl.clear()
    
    # Abstract methods that must be implemented by subclasses
    @abstractmethod
    def _get_primary_key(self) -> str:
        """Return the name of the primary key column."""
        pass
    
    @abstractmethod
    def _row_to_model(self, row) -> T:
        """Convert a database row to a model instance."""
        pass
    
    @abstractmethod
    def _model_to_dict(self, entity: T) -> Dict[str, Any]:
        """Convert a model instance to a dictionary."""
        pass
