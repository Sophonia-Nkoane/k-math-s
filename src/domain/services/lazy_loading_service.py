"""
Lazy Loading Service for Learner Payment Management Application

Provides lazy loading functionality for learner details, payment information,
and other data that should only be loaded when needed.

Features:
- On-demand data loading
- Intelligent caching with LRU eviction
- Memory usage monitoring
- Background loading for better UX
- Cache prewarming for frequently accessed data
- Automatic cleanup of unused data
"""

import logging
import threading
import time
import weakref
from typing import Any, Dict, List, Optional, Callable, Set, Union
from datetime import datetime, timedelta
from collections import OrderedDict
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum, auto

from PySide6.QtCore import QObject, QThread, Signal, QTimer


class DataType(Enum):
    """Types of data that can be lazy loaded."""
    LEARNER_DETAILS = auto()
    PAYMENT_HISTORY = auto()
    FAMILY_DATA = auto()
    PAYMENT_OPTIONS = auto()
    INVOICE_DATA = auto()
    TEMPORARY = auto()


@dataclass
class CacheEntry:
    """Represents a cached data entry."""
    data: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    size_estimate: int = 0
    data_type: DataType = DataType.TEMPORARY


class LazyLoadingService(QObject):
    """
    Service for lazy loading and caching data with memory management.
    """
    
    # Signals
    dataLoaded = Signal(str, object)  # cache_key, data
    dataLoadFailed = Signal(str, str)  # cache_key, error_message
    cacheWarming = Signal(int, int)  # current, total
    
    def __init__(self, 
                 max_cache_size: int = 500,
                 max_memory_mb: int = 100,
                 cleanup_interval: int = 300):  # 5 minutes
        """
        Initialize the lazy loading service.
        
        Args:
            max_cache_size: Maximum number of items to cache
            max_memory_mb: Maximum estimated memory usage in MB
            cleanup_interval: Cache cleanup interval in seconds
        """
        super().__init__()
        
        self.max_cache_size = max_cache_size
        self.max_memory_mb = max_memory_mb
        self.cleanup_interval = cleanup_interval
        
        # Cache storage
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._cache_lock = threading.RLock()
        
        # Loading management
        self._loading_keys: Set[str] = set()
        self._loading_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="LazyLoader")
        self._pending_futures: Dict[str, Future] = {}
        
        # Data loaders registry
        self._loaders: Dict[DataType, Callable] = {}
        
        # Statistics
        self._stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'load_requests': 0,
            'load_failures': 0,
            'memory_cleanups': 0
        }
        
        # Cleanup timer
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._cleanup_cache)
        self._cleanup_timer.start(cleanup_interval * 1000)
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Lazy loading service initialized (max_size: {max_cache_size}, max_memory: {max_memory_mb}MB)")
    
    def register_loader(self, data_type: DataType, loader_func: Callable):
        """
        Register a data loader function for a specific data type.
        
        Args:
            data_type: Type of data this loader handles
            loader_func: Function that loads the data (should accept cache_key as parameter)
        """
        self._loaders[data_type] = loader_func
        self.logger.debug(f"Registered loader for {data_type.name}")
    
    def get_data(self, 
                cache_key: str, 
                data_type: DataType,
                loader_args: tuple = (),
                loader_kwargs: Dict[str, Any] = None,
                force_reload: bool = False) -> Optional[Any]:
        """
        Get data with lazy loading.
        
        Args:
            cache_key: Unique key for caching
            data_type: Type of data to load
            loader_args: Arguments to pass to the loader function
            loader_kwargs: Keyword arguments to pass to the loader function
            force_reload: Force reloading even if cached
            
        Returns:
            Cached data if available, None if loading asynchronously
        """
        loader_kwargs = loader_kwargs or {}
        
        # Check cache first (unless forcing reload)
        if not force_reload:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                self._stats['cache_hits'] += 1
                return cached_data
        
        self._stats['cache_misses'] += 1
        
        # Check if already loading
        with self._loading_lock:
            if cache_key in self._loading_keys:
                return None  # Loading in progress
            
            self._loading_keys.add(cache_key)
        
        # Get loader function
        loader_func = self._loaders.get(data_type)
        if not loader_func:
            self.logger.error(f"No loader registered for data type {data_type.name}")
            with self._loading_lock:
                self._loading_keys.discard(cache_key)
            return None
        
        # Submit loading task
        future = self._executor.submit(
            self._load_data_worker,
            cache_key, data_type, loader_func, loader_args, loader_kwargs
        )
        
        self._pending_futures[cache_key] = future
        self._stats['load_requests'] += 1
        
        return None  # Data will be loaded asynchronously
    
    def get_data_sync(self,
                     cache_key: str,
                     data_type: DataType,
                     loader_args: tuple = (),
                     loader_kwargs: Dict[str, Any] = None,
                     timeout: float = 10.0) -> Optional[Any]:
        """
        Get data synchronously with timeout.
        
        Args:
            cache_key: Unique key for caching
            data_type: Type of data to load
            loader_args: Arguments to pass to the loader function
            loader_kwargs: Keyword arguments to pass to the loader function
            timeout: Maximum time to wait for data
            
        Returns:
            The loaded data or None if failed/timeout
        """
        loader_kwargs = loader_kwargs or {}
        
        # Try cache first
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            return cached_data
        
        # Load synchronously
        loader_func = self._loaders.get(data_type)
        if not loader_func:
            return None
        
        try:
            data = loader_func(cache_key, *loader_args, **loader_kwargs)
            if data is not None:
                self._store_in_cache(cache_key, data, data_type)
            return data
        except Exception as e:
            self.logger.error(f"Sync load failed for {cache_key}: {e}")
            return None
    
    def _load_data_worker(self,
                         cache_key: str,
                         data_type: DataType,
                         loader_func: Callable,
                         loader_args: tuple,
                         loader_kwargs: Dict[str, Any]):
        """Worker function for loading data in background."""
        try:
            self.logger.debug(f"Loading data for key: {cache_key}")
            
            # Call the loader function
            data = loader_func(cache_key, *loader_args, **loader_kwargs)
            
            if data is not None:
                # Store in cache
                self._store_in_cache(cache_key, data, data_type)
                
                # Emit success signal
                self.dataLoaded.emit(cache_key, data)
                
                self.logger.debug(f"Successfully loaded data for key: {cache_key}")
            else:
                self.logger.warning(f"Loader returned None for key: {cache_key}")
                self.dataLoadFailed.emit(cache_key, "Loader returned no data")
                
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Failed to load data for key {cache_key}: {error_msg}")
            self.dataLoadFailed.emit(cache_key, error_msg)
            self._stats['load_failures'] += 1
            
        finally:
            # Remove from loading set
            with self._loading_lock:
                self._loading_keys.discard(cache_key)
            
            # Remove from pending futures
            self._pending_futures.pop(cache_key, None)
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get data from cache and update access information."""
        with self._cache_lock:
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                entry.last_accessed = datetime.now()
                entry.access_count += 1
                
                # Move to end (most recently used)
                self._cache.move_to_end(cache_key)
                
                return entry.data
            
            return None
    
    def _store_in_cache(self, cache_key: str, data: Any, data_type: DataType):
        """Store data in cache with memory management."""
        with self._cache_lock:
            # Calculate size estimate
            size_estimate = self._estimate_size(data)
            
            # Create cache entry
            entry = CacheEntry(
                data=data,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                access_count=1,
                size_estimate=size_estimate,
                data_type=data_type
            )
            
            # Store in cache
            self._cache[cache_key] = entry
            
            # Check if we need to cleanup
            self._enforce_limits()
    
    def _estimate_size(self, data: Any) -> int:
        """Estimate the memory size of data in bytes."""
        try:
            import sys
            
            if hasattr(data, '__dict__'):
                # For objects with attributes
                size = sys.getsizeof(data)
                for attr_value in data.__dict__.values():
                    size += sys.getsizeof(attr_value)
                return size
            elif isinstance(data, (list, tuple)):
                # For collections
                size = sys.getsizeof(data)
                for item in data:
                    size += sys.getsizeof(item)
                return size
            elif isinstance(data, dict):
                # For dictionaries
                size = sys.getsizeof(data)
                for key, value in data.items():
                    size += sys.getsizeof(key) + sys.getsizeof(value)
                return size
            else:
                return sys.getsizeof(data)
                
        except Exception:
            return 1024  # Default estimate
    
    def _enforce_limits(self):
        """Enforce cache size and memory limits."""
        # Remove oldest entries if over size limit
        while len(self._cache) > self.max_cache_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        # Check memory limit
        total_memory = sum(entry.size_estimate for entry in self._cache.values())
        max_memory_bytes = self.max_memory_mb * 1024 * 1024
        
        if total_memory > max_memory_bytes:
            # Remove least recently used entries until under limit
            entries_by_access = sorted(
                self._cache.items(),
                key=lambda x: x[1].last_accessed
            )
            
            for key, entry in entries_by_access:
                del self._cache[key]
                total_memory -= entry.size_estimate
                
                if total_memory <= max_memory_bytes * 0.8:  # 20% buffer
                    break
            
            self._stats['memory_cleanups'] += 1
            self.logger.debug(f"Memory cleanup completed, cache size: {len(self._cache)}")
    
    def _cleanup_cache(self):
        """Periodic cache cleanup based on age and access patterns."""
        with self._cache_lock:
            current_time = datetime.now()
            keys_to_remove = []
            
            for key, entry in self._cache.items():
                # Remove entries older than 1 hour that haven't been accessed recently
                age = current_time - entry.created_at
                time_since_access = current_time - entry.last_accessed
                
                # Different cleanup rules for different data types
                if entry.data_type == DataType.TEMPORARY:
                    # Aggressive cleanup for temporary data
                    if age > timedelta(minutes=10) or time_since_access > timedelta(minutes=5):
                        keys_to_remove.append(key)
                elif entry.data_type == DataType.LEARNER_DETAILS:
                    # Keep learner details longer
                    if age > timedelta(hours=2) and time_since_access > timedelta(minutes=30):
                        keys_to_remove.append(key)
                else:
                    # Default cleanup rule
                    if age > timedelta(hours=1) and time_since_access > timedelta(minutes=15):
                        keys_to_remove.append(key)
            
            # Remove identified entries
            for key in keys_to_remove:
                del self._cache[key]
            
            if keys_to_remove:
                self.logger.debug(f"Periodic cleanup removed {len(keys_to_remove)} cache entries")
    
    def prefetch_data(self, 
                     cache_keys: List[str], 
                     data_type: DataType,
                     loader_args_list: List[tuple] = None,
                     loader_kwargs_list: List[Dict[str, Any]] = None):
        """
        Prefetch data for improved performance.
        
        Args:
            cache_keys: List of cache keys to prefetch
            data_type: Type of data to prefetch
            loader_args_list: List of argument tuples for each key
            loader_kwargs_list: List of keyword argument dicts for each key
        """
        if not cache_keys:
            return
        
        loader_args_list = loader_args_list or [() for _ in cache_keys]
        loader_kwargs_list = loader_kwargs_list or [{} for _ in cache_keys]
        
        self.logger.info(f"Starting prefetch for {len(cache_keys)} items")
        
        for i, cache_key in enumerate(cache_keys):
            # Skip if already cached
            if self._get_from_cache(cache_key) is not None:
                continue
            
            # Start loading
            args = loader_args_list[i] if i < len(loader_args_list) else ()
            kwargs = loader_kwargs_list[i] if i < len(loader_kwargs_list) else {}
            
            self.get_data(cache_key, data_type, args, kwargs)
            
            # Emit progress
            self.cacheWarming.emit(i + 1, len(cache_keys))
    
    def invalidate(self, cache_key: str):
        """Remove specific data from cache."""
        with self._cache_lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                self.logger.debug(f"Invalidated cache for key: {cache_key}")
    
    def invalidate_type(self, data_type: DataType):
        """Remove all cached data of a specific type."""
        with self._cache_lock:
            keys_to_remove = [
                key for key, entry in self._cache.items()
                if entry.data_type == data_type
            ]
            
            for key in keys_to_remove:
                del self._cache[key]
            
            if keys_to_remove:
                self.logger.debug(f"Invalidated {len(keys_to_remove)} entries of type {data_type.name}")
    
    def clear_cache(self):
        """Clear all cached data."""
        with self._cache_lock:
            cache_size = len(self._cache)
            self._cache.clear()
            
            if cache_size > 0:
                self.logger.info(f"Cleared {cache_size} entries from cache")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._cache_lock:
            total_memory = sum(entry.size_estimate for entry in self._cache.values())
            
            # Group by data type
            type_stats = {}
            for entry in self._cache.values():
                type_name = entry.data_type.name
                if type_name not in type_stats:
                    type_stats[type_name] = {'count': 0, 'memory': 0}
                
                type_stats[type_name]['count'] += 1
                type_stats[type_name]['memory'] += entry.size_estimate
            
            return {
                'cache_size': len(self._cache),
                'max_cache_size': self.max_cache_size,
                'total_memory_bytes': total_memory,
                'max_memory_bytes': self.max_memory_mb * 1024 * 1024,
                'loading_count': len(self._loading_keys),
                'type_breakdown': type_stats,
                **self._stats
            }
    
    def shutdown(self):
        """Shutdown the service and cleanup resources."""
        self.logger.info("Shutting down lazy loading service")
        
        # Stop cleanup timer
        self._cleanup_timer.stop()
        
        # Cancel pending futures
        for future in self._pending_futures.values():
            future.cancel()
        
        # Shutdown executor
        self._executor.shutdown(wait=True, timeout=5)
        
        # Clear cache
        self.clear_cache()
        
        self.logger.info("Lazy loading service shutdown complete")


# Decorator for creating lazy-loaded properties
def lazy_property(data_type: DataType, loader_service_attr: str = 'lazy_service'):
    """
    Decorator for creating lazy-loaded properties.
    
    Args:
        data_type: Type of data to load
        loader_service_attr: Name of the attribute containing the LazyLoadingService
    """
    def decorator(func):
        property_name = f"_{func.__name__}_lazy_cache"
        
        @wraps(func)
        def wrapper(self):
            # Check if already loaded
            if hasattr(self, property_name):
                return getattr(self, property_name)
            
            # Get cache key and loader service
            cache_key = func(self)  # Should return cache key
            service = getattr(self, loader_service_attr, None)
            
            if not service:
                raise AttributeError(f"No {loader_service_attr} found on {type(self).__name__}")
            
            # Try to get data
            data = service.get_data_sync(cache_key, data_type, timeout=5.0)
            
            # Cache the result
            setattr(self, property_name, data)
            return data
        
        return property(wrapper)
    
    return decorator


# Global service instance
_lazy_loading_service: Optional[LazyLoadingService] = None


def get_lazy_loading_service() -> Optional[LazyLoadingService]:
    """Get the global lazy loading service instance."""
    return _lazy_loading_service


def initialize_lazy_loading_service(**kwargs) -> LazyLoadingService:
    """Initialize the global lazy loading service."""
    global _lazy_loading_service
    
    if _lazy_loading_service:
        _lazy_loading_service.shutdown()
    
    _lazy_loading_service = LazyLoadingService(**kwargs)
    return _lazy_loading_service


def shutdown_lazy_loading_service():
    """Shutdown the global lazy loading service."""
    global _lazy_loading_service
    
    if _lazy_loading_service:
        _lazy_loading_service.shutdown()
        _lazy_loading_service = None


# Helper functions for common data loading patterns
def create_learner_loader(db_manager):
    """Create a loader function for learner details."""
    def load_learner_details(cache_key: str, learner_id: str) -> Optional[Dict[str, Any]]:
        try:
            # Load learner details from database
            query = """
                SELECT s.*, 
                       f.family_name, f.contact_info,
                       po.option_name, po.fees, po.subjects_count
                FROM Learners s
                LEFT JOIN Families f ON s.family_id = f.family_id
                LEFT JOIN PaymentOptions po ON s.payment_option_id = po.option_id
                WHERE s.learner_id = ? OR s.acc_no = ?
            """
            
            result = db_manager.execute_query(query, (learner_id, learner_id), fetchone=True)
            if result:
                # Convert to dictionary
                columns = [desc[0] for desc in db_manager.connection.description]
                return dict(zip(columns, result))
            
            return None
            
        except Exception as e:
            logging.error(f"Failed to load learner details for {learner_id}: {e}")
            raise
    
    return load_learner_details


def create_payment_history_loader(db_manager):
    """Create a loader function for payment history."""
    def load_payment_history(cache_key: str, learner_id: str, limit: int = 50) -> Optional[List[Dict[str, Any]]]:
        try:
            query = """
                SELECT payment_id, amount, payment_date, payment_method, 
                       invoice_month, notes, created_at
                FROM Payments 
                WHERE learner_id = ?
                ORDER BY payment_date DESC, created_at DESC
                LIMIT ?
            """
            
            results = db_manager.execute_query(query, (learner_id, limit), fetchall=True)
            if results:
                columns = [desc[0] for desc in db_manager.connection.description]
                return [dict(zip(columns, row)) for row in results]
            
            return []
            
        except Exception as e:
            logging.error(f"Failed to load payment history for {learner_id}: {e}")
            raise
    
    return load_payment_history
