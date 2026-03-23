"""
Memory Optimization Manager for Learner Payment Management Application

Provides comprehensive memory management including:
- Memory usage monitoring and profiling
- Automatic garbage collection optimization
- Cache management with intelligent eviction
- Widget and object lifecycle management
- Memory leak detection and prevention
- Resource cleanup automation
"""

import os
import gc
import sys
import threading
import time
import weakref
import psutil
import traceback
from typing import Any, Dict, List, Optional, Set, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, OrderedDict
from functools import wraps
from contextlib import contextmanager
from enum import Enum, auto
import logging

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QWidget, QDialog


class MemoryPriority(Enum):
    """Memory cleanup priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class MemoryCategory(Enum):
    """Categories for memory usage tracking."""
    WIDGETS = auto()
    DIALOGS = auto()
    CACHE = auto()
    DATABASE = auto()
    IMAGES = auto()
    TEMPORARY = auto()
    BACKGROUND_TASKS = auto()


@dataclass
class MemoryStats:
    """Memory usage statistics."""
    total_memory: float = 0.0
    used_memory: float = 0.0
    available_memory: float = 0.0
    memory_percent: float = 0.0
    gc_collections: int = 0
    objects_tracked: int = 0
    cache_size: int = 0
    last_cleanup: Optional[datetime] = None


@dataclass
class ObjectInfo:
    """Information about tracked objects."""
    obj_id: int
    obj_type: str
    category: MemoryCategory
    created_at: datetime
    size_estimate: int = 0
    last_accessed: Optional[datetime] = None
    ref_count: int = 0
    cleanup_callback: Optional[Callable] = None


class ManagedCache(OrderedDict):
    """An OrderedDict with a fixed size, automatically evicting least recently used items."""
    def __init__(self, *args, max_size=128, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_size = max_size

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.max_size:
            self.popitem(last=False)

    def __getitem__(self, key):
        if key not in self:
            raise KeyError(key)
        self.move_to_end(key)
        return super().__getitem__(key)


class MemoryOptimizer(QObject):
    """
    Main memory optimization manager with real-time monitoring and automatic cleanup.
    
    Features:
    - Automatic garbage collection tuning
    - Widget lifecycle management
    - Cache size management with LRU eviction
    - Memory leak detection
    - Background monitoring
    - Emergency cleanup procedures
    """
    
    # Signals for memory events
    memoryWarning = Signal(float)  # Memory usage percentage
    memoryCritical = Signal(float)
    cleanupCompleted = Signal(int)  # Objects cleaned up
    
    def __init__(self, 
                 warning_threshold: float = 80.0,
                 critical_threshold: float = 90.0,
                 monitoring_interval: int = 30000,  # 30 seconds
                 auto_cleanup: bool = True):
        """
        Initialize the memory optimizer.
        
        Args:
            warning_threshold: Memory usage % to trigger warning
            critical_threshold: Memory usage % to trigger emergency cleanup
            monitoring_interval: Monitoring interval in milliseconds
            auto_cleanup: Enable automatic cleanup
        """
        super().__init__()
        
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.auto_cleanup = auto_cleanup
        
        # Tracking structures
        self._tracked_objects: Dict[int, ObjectInfo] = {}
        self._object_categories: Dict[MemoryCategory, Set[int]] = defaultdict(set)
        self._cache_stores: Dict[str, OrderedDict] = {}
        # _cleanup_callbacks stores callables (mostly proxy wrappers). Use a list to preserve order.
        self._cleanup_callbacks: List[Callable] = []
        self._widget_registry: Set[weakref.ReferenceType] = set()
        
        # Statistics
        self._stats = MemoryStats()
        self._memory_history: List[tuple] = []  # (timestamp, memory_usage)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Monitoring timer
        self._monitor_timer = QTimer()
        self._monitor_timer.timeout.connect(self._monitor_memory)
        self._monitor_timer.start(monitoring_interval)
        
        self._logger = logging.getLogger(self.__class__.__name__)
        
        # GC optimization
        self._optimize_garbage_collection()
        
        self._logger.info("Memory optimizer initialized")
    
    def _optimize_garbage_collection(self):
        """Optimize garbage collection settings for the application."""
        # Adjust GC thresholds for better performance
        # Default thresholds are (700, 10, 10)
        # We'll use more aggressive collection for generation 0
        gc.set_threshold(500, 15, 15)
        
        # Enable debugging to track uncollectable objects
        if __debug__:
            gc.set_debug(gc.DEBUG_LEAK)
        
        self._logger.debug("Garbage collection optimized")

    def _monitor_memory(self):
        """Periodically monitors memory usage and triggers cleanup if necessary."""
        with self._lock:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            
            self._stats.used_memory = mem_info.rss / (1024 * 1024)  # in MB
            self._stats.total_memory = psutil.virtual_memory().total / (1024 * 1024)
            self._stats.available_memory = psutil.virtual_memory().available / (1024 * 1024)
            self._stats.memory_percent = (self._stats.used_memory / self._stats.total_memory) * 100
            self._stats.last_cleanup = datetime.now() # Update last cleanup time

            self._memory_history.append((time.time(), self._stats.memory_percent))
            # Keep history limited
            if len(self._memory_history) > 100:
                self._memory_history.pop(0)

            self._logger.debug(f"Current memory usage: {self._stats.memory_percent:.2f}%")

            if self._stats.memory_percent >= self.critical_threshold:
                self._logger.warning(f"Critical memory usage detected: {self._stats.memory_percent:.2f}%")
                self.memoryCritical.emit(self._stats.memory_percent)
                if self.auto_cleanup:
                    self._perform_cleanup(MemoryPriority.CRITICAL)
            elif self._stats.memory_percent >= self.warning_threshold:
                self._logger.warning(f"High memory usage detected: {self._stats.memory_percent:.2f}%")
                self.memoryWarning.emit(self._stats.memory_percent)
                if self.auto_cleanup:
                    self._perform_cleanup(MemoryPriority.HIGH)

    def register_cleanup_callback(self, callback: Callable[[MemoryPriority], None]):
        """
        Register a callback function to be executed during cleanup.
        
        Args:
            callback: A function that accepts a MemoryPriority level.
        """
        # Wrap bound methods with WeakMethod proxies so callbacks don't keep their owners alive.
        def _make_proxy(cb: Callable):
            # Bound method -> use WeakMethod
            try:
                if hasattr(cb, '__self__') and hasattr(cb, '__func__') and cb.__self__ is not None:
                    wm = weakref.WeakMethod(cb)

                    def _proxy(priority: MemoryPriority):
                        fn = wm()
                        if fn:
                            try:
                                return fn(priority)
                            except Exception:
                                self._logger.exception("Error in cleanup proxy for bound method")
                        # If target gone, silently ignore
                        return None

                    # Attach original identity for dedupe checks
                    _proxy._orig = (getattr(cb, '__self__', None), getattr(cb, '__func__', None))
                    return _proxy
            except Exception:
                # Fallthrough to function wrapper for unexpected callable types
                pass

            # Regular function - wrap in a simple proxy that forwards calls
            def _func_proxy(priority: MemoryPriority):
                try:
                    return callback(priority)
                except Exception:
                    self._logger.exception("Error in cleanup function callback")

            _func_proxy._orig = callback
            return _func_proxy

        with self._lock:
            proxy = _make_proxy(callback)

            # Avoid registering duplicates by comparing stored _orig markers
            def _is_same(existing, new_proxy):
                return getattr(existing, '_orig', None) == getattr(new_proxy, '_orig', None)

            for existing in self._cleanup_callbacks:
                if _is_same(existing, proxy):
                    self._logger.debug("Cleanup callback already registered (skipping duplicate)")
                    return

            self._cleanup_callbacks.append(proxy)
            try:
                name = getattr(callback, '__name__', repr(callback))
            except Exception:
                name = repr(callback)
            self._logger.info(f"Registered cleanup callback: {name}")

    def _perform_cleanup(self, priority: MemoryPriority):
        """Performs cleanup based on priority."""
        self._logger.info(f"Performing memory cleanup with priority: {priority.name}")
        cleaned_objects_count = 0
        
        # Run Python's garbage collector
        gc.collect()
        self._stats.gc_collections += 1
        self._logger.debug(f"Python GC collected. Total collections: {self._stats.gc_collections}")

        # Execute registered cleanup callbacks. Call proxies which internally check weakrefs.
        new_callbacks = []
        for callback in list(self._cleanup_callbacks):
            try:
                # Call the proxy; proxies will ignore if target has been GC'd.
                callback(priority)
                # Keep the proxy in the list; no automatic removal here. If proxy._orig indicates
                # a dead weakref we could prune in future iterations.
                new_callbacks.append(callback)
            except Exception as e:
                # Log and keep going
                try:
                    name = getattr(callback, '__name__', repr(callback))
                except Exception:
                    name = repr(callback)
                self._logger.error(f"Error in cleanup callback {name}: {e}")

        # Replace callbacks with filtered list
        self._cleanup_callbacks = new_callbacks

        # Clean up expired weak references
        self._widget_registry = {ref for ref in self._widget_registry if ref() is not None}
        
        self.cleanupCompleted.emit(cleaned_objects_count)
        self._logger.info(f"Memory cleanup completed. Cleaned {cleaned_objects_count} objects.")

    def cleanup(self, priority: MemoryPriority = MemoryPriority.NORMAL):
        """
        Manually trigger memory cleanup at the specified priority level.
        
        Args:
            priority: The priority level for cleanup (LOW, NORMAL, HIGH, CRITICAL)
        """
        self._perform_cleanup(priority)

    def get_memory_stats(self) -> MemoryStats:
        """Returns current memory usage statistics."""
        with self._lock:
            # Ensure stats are up-to-date before returning
            self._monitor_memory() 
            return self._stats

    def create_managed_cache(self, cache_name: str, max_size: int = 100) -> 'ManagedCache':
        """
        Create a cache that is managed by the memory optimizer.
        
        Args:
            cache_name: A unique name for the cache.
            max_size: The maximum size of the cache.
            
        Returns:
            A ManagedCache instance.
        """
        with self._lock:
            if cache_name in self._cache_stores:
                self._logger.warning(f"Cache '{cache_name}' already exists. Returning existing cache.")
                return self._cache_stores[cache_name]
            
            cache = ManagedCache(max_size=max_size)
            self._cache_stores[cache_name] = cache
            self._logger.info(f"Created managed cache: {cache_name} with max_size={max_size}")
            return cache

    def register_resource_provider(self, name: str, provider: Callable, category: MemoryCategory):
        """
        Register a provider function that can be called to get information about a resource.
        
        Args:
            name: The name of the resource.
            provider: A callable that returns the resource information.
            category: The memory category of the resource.
        """
        with self._lock:
            # This is a placeholder for a more complex resource tracking system.
            self._logger.info(f"Resource provider '{name}' registered in category {category.name}.")
            # In a real implementation, we might store and periodically query this provider.
            pass

    def _on_widget_destroyed(self, obj_id: int):
        """Callback when a widget is destroyed."""
        with self._lock:
            if obj_id in self._tracked_objects:
                del self._tracked_objects[obj_id]
                self._logger.info(f"Widget with ID {obj_id} destroyed and untracked.")

    def _estimate_widget_size(self, widget: QWidget) -> int:
        """
        Estimate the memory size of a widget and its children.
        This is a basic estimation. For more accuracy, a recursive approach
        and introspection of widget properties would be needed.
        """
        size = sys.getsizeof(widget)
        for child in widget.findChildren(QObject):
            size += sys.getsizeof(child)
        return size

    def register_widget(self, widget: QWidget, category: MemoryCategory = MemoryCategory.WIDGETS):
        """Register a widget for memory tracking."""
        if not isinstance(widget, QWidget):
            return
        
        with self._lock:
            obj_id = id(widget)
            
            # Create weak reference to avoid circular references
            weak_ref = weakref.ref(widget, lambda ref: self._on_widget_destroyed(obj_id))
            self._widget_registry.add(weak_ref)
            
            # Track object information
            obj_info = ObjectInfo(
                obj_id=obj_id,
                obj_type=type(widget).__name__,
                category=category,
                created_at=datetime.now(),
                size_estimate=self._estimate_widget_size(widget),
                ref_count=sys.getrefcount(widget)
            )

    def shutdown(self):
        """Shutdown the memory optimizer and clean up resources."""
        self._logger.info("Shutting down memory optimizer...")
        
        # Stop monitoring timer
        if self._monitor_timer.isActive():
            self._monitor_timer.stop()
        
        # Perform final cleanup
        self._perform_cleanup(MemoryPriority.NORMAL)
        
        # Clear all tracked objects
        with self._lock:
            self._tracked_objects.clear()
            self._object_categories.clear()
            self._cache_stores.clear()
            self._cleanup_callbacks.clear()
            self._widget_registry.clear()
            self._memory_history.clear()
        
        self._logger.info("Memory optimizer shutdown complete")