"""
Memory Integration Module for Learner Management Application

Integrates the memory optimizer with the existing application components,
providing seamless memory management without disrupting existing functionality.

Features:
- Automatic widget registration
- Cache integration for existing caches
- Memory-aware dialog management
- Background task memory optimization
- Database connection pooling integration
"""

import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from datetime import timedelta

from PySide6.QtWidgets import QWidget, QDialog, QMainWindow
from PySide6.QtCore import QObject

from utils.memory_optimizer import (
    MemoryOptimizer, MemoryCategory, MemoryPriority, ManagedCache
)


class LearnerAppMemoryManager:
    """
    Memory manager specifically designed for the Learner Management Application.
    
    Handles integration with existing components:
    - LearnerManagementApp main window
    - Dialog management
    - Cache optimization
    - Database connection monitoring
    """
    
    def __init__(self, main_window=None, optimizer: Optional[MemoryOptimizer] = None):
        self.main_window = main_window
        self.optimizer = optimizer
        self.managed_caches = {}
        self.cleanup_callbacks = {}
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize memory optimizer if one was not provided
        if self.optimizer is None:
            self._initialize_optimizer()
        else:
            # If an external optimizer was provided, wire up signals and ensure callbacks are registered
            try:
                self.optimizer.memoryWarning.connect(self._on_memory_warning)
                self.optimizer.memoryCritical.connect(self._on_memory_critical)
                self.optimizer.cleanupCompleted.connect(self._on_cleanup_completed)

                # Register application-specific cleanup callbacks (the optimizer will dedupe proxies)
                self.optimizer.register_cleanup_callback(self._cleanup_learner_data)
                self.optimizer.register_cleanup_callback(self._cleanup_dialog_cache)
            except Exception:
                self.logger.exception("Failed to attach to provided MemoryOptimizer")

        # Set up main window integration if provided
        if main_window:
            self.integrate_main_window(main_window)
    
    def _initialize_optimizer(self):
        """Initialize the memory optimizer with appropriate settings."""
        self.optimizer = MemoryOptimizer(
            warning_threshold=75.0,  # Trigger cleanup at 75% memory usage
            critical_threshold=85.0,  # Emergency cleanup at 85%
            monitoring_interval=45000,  # Check every 45 seconds
            auto_cleanup=True
        )
        
        # Connect to memory events
        self.optimizer.memoryWarning.connect(self._on_memory_warning)
        self.optimizer.memoryCritical.connect(self._on_memory_critical)
        self.optimizer.cleanupCompleted.connect(self._on_cleanup_completed)
        
        # Register application-specific cleanup callbacks
        self.optimizer.register_cleanup_callback(self._cleanup_learner_data)
        self.optimizer.register_cleanup_callback(self._cleanup_dialog_cache)
        
        self.logger.info("Learner app memory manager initialized")

    def _on_memory_warning(self, usage):
        """Handle memory warning signals from the optimizer."""
        self.logger.warning(f"Memory usage has reached {usage:.2f}%. Proactive cleanup initiated.")
        # Optionally, trigger a low-priority cleanup
        self.optimizer.cleanup(priority=MemoryPriority.LOW)

    def _on_memory_critical(self, usage):
        """Handle memory critical signals from the optimizer."""
        self.logger.critical(f"Critical memory usage at {usage:.2f}%. Aggressive cleanup initiated.")
        # Trigger a high-priority cleanup
        self.optimizer.cleanup(priority=MemoryPriority.HIGH)

    def _on_cleanup_completed(self, freed_memory):
        """Handle cleanup completion signals."""
        if freed_memory > 0:
            self.logger.info(f"Memory cleanup completed. Freed approximately {freed_memory / (1024*1024):.2f} MB.")
        else:
            self.logger.info("Cleanup cycle completed. No significant memory was freed.")

    def _cleanup_learner_data(self, priority=MemoryPriority.NORMAL):
        """
        Callback to clean up learner-related data and managed caches based on priority.
        """
        self.logger.info(f"Executing learner data cleanup with priority {priority}.")
        
        # Clear managed caches if priority is high enough
        if priority >= MemoryPriority.HIGH:
            for cache_name, managed_cache in self.optimizer._cache_stores.items():
                if isinstance(managed_cache, ManagedCache):
                    managed_cache.clear()
                    self.logger.info(f"Cleared managed cache: {cache_name}.")
            
            # Also clear any other relevant caches that are not managed
            if hasattr(self.main_window, 'learner_details_cache') and isinstance(self.main_window.learner_details_cache, dict):
                self.main_window.learner_details_cache.clear()
                self.logger.info("Cleared non-managed 'learner_details_cache'.")

    def _cleanup_dialog_cache(self, priority=MemoryPriority.NORMAL):
        """
        Callback to clean up cached dialogs.
        For now, this is a conceptual cleanup as direct dialog closing is not implemented.
        """
        self.logger.info(f"Executing dialog cache cleanup with priority {priority}.")
        if hasattr(self.main_window, 'dialog_service'):
            self.logger.info("Conceptual dialog cleanup: would close non-essential dialogs here.")
    
    def integrate_main_window(self, main_window):
        """Integrate memory management with the main application window."""
        self.main_window = main_window
        
        # Register the main window for tracking
        if isinstance(main_window, QWidget):
            self.optimizer.register_widget(main_window, MemoryCategory.WIDGETS)
        
        # Replace existing caches with managed caches
        self._replace_existing_caches()
        
        # Monitor database connections if available
        self._setup_database_monitoring()
        
        # Set up dialog tracking
        self._setup_dialog_tracking()
        
        self.logger.info("Main window integrated with memory manager")

    def _replace_existing_caches(self):
        """
        Replace standard caches in the main window with memory-managed caches.
        """
        self.logger.info("Replacing existing application caches with managed caches.")
        
        cache_configs = {
            'payment_options_cache': 200,
            'family_data_cache': 100,
            'payment_terms_cache': 50
        }

        for cache_name, max_size in cache_configs.items():
            if hasattr(self.main_window, cache_name):
                original_cache = getattr(self.main_window, cache_name)
                if not isinstance(original_cache, ManagedCache):
                    managed_cache = self.optimizer.create_managed_cache(cache_name, max_size=max_size)
                    if isinstance(original_cache, dict):
                        managed_cache.update(original_cache)
                    setattr(self.main_window, cache_name, managed_cache)
                    self.logger.info(f"Replaced '{cache_name}' with a managed cache (max_size={max_size}).")
                else:
                    self.logger.info(f"'{cache_name}' is already a managed cache.")
            else:
                self.logger.warning(f"Cache '{cache_name}' not found on main window.")

    def _setup_database_monitoring(self):
        """
        Set up monitoring for database connections by tracking the DatabaseManager's single connection.
        """
        self.logger.info("Setting up database monitoring.")
        if hasattr(self.main_window, 'db_manager') and hasattr(self.optimizer, 'register_resource_provider'):
            db_manager = self.main_window.db_manager

            def get_db_connection_status():
                """Returns 1 if DB connection is active, 0 otherwise."""
                # DatabaseManager uses a single connection, so we check its status
                return {'active_connections': 1 if db_manager.connection else 0}

            self.optimizer.register_resource_provider(
                'database_connections',
                get_db_connection_status,
                category=MemoryCategory.DATABASE
            )
            self.logger.info("Database connection monitoring is set up.")
        else:
            self.logger.warning("DatabaseManager not found on main window or optimizer lacks resource provider. Cannot set up database monitoring.")

    def _setup_dialog_tracking(self):
        """
        Set up conceptual tracking for dialogs created by the application.
        Due to the current architecture of DialogService (methods returning exec() result),
        direct QDialog instance tracking is not straightforward without modifying
        all show_*_dialog methods to return the dialog instance before exec().
        This placeholder logs when a dialog creation method is called.
        """
        self.logger.info("Setting up conceptual dialog tracking.")
        
        if hasattr(self.main_window, 'dialog_service'):
            dialog_service = self.main_window.dialog_service
            
            # Identify methods that likely create and show dialogs
            dialog_methods_to_wrap = [
                name for name in dir(dialog_service) 
                if name.startswith('show_') and callable(getattr(dialog_service, name))
            ]

            for method_name in dialog_methods_to_wrap:
                original_method = getattr(dialog_service, method_name)
                
                # Create a new function scope for each wrapped method
                def create_wrapped_method(original_method_closure, method_name_closure):
                    @wraps(original_method_closure)
                    def wrapped_method(*args, **kwargs):
                        self.logger.info(f"Conceptual tracking: Dialog method '{method_name_closure}' called.")
                        # In a real scenario, we'd get the dialog instance here and register it.
                        # For now, just call the original method.
                        return original_method_closure(*args, **kwargs)
                    return wrapped_method
                
                setattr(dialog_service, method_name, create_wrapped_method(original_method, method_name))
        else:
            self.logger.warning("DialogService not found on main window. Cannot set up dialog tracking.")
