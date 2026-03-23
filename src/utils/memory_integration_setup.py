"""
Memory Integration Setup for Learner Payment Management Application

This module sets up and integrates all memory optimization features:
- Virtual table scrolling for large datasets
- Lazy loading service for learner details
- Configurable sync intervals
- OCR model management with automatic unloading

Usage:
    from utils.memory_integration_setup import setup_memory_optimization
    setup_memory_optimization(main_window, db_manager)
"""

import logging
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import QMainWindow

# Import memory optimization components
from utils.memory_optimizer import MemoryOptimizer
from utils.memory_integration import LearnerAppMemoryManager
from domain.services.lazy_loading_service import (
    initialize_lazy_loading_service, 
    DataType,
    create_learner_loader,
    create_payment_history_loader
)
from presentation.components.virtual_table import VirtualTableWidget
from data.sync_engine import SyncEngine
from domain.services.dialog_service import DialogService # Added import


class LearnerDataSource:
    """Data source adapter for virtual table with learner data."""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_total_count(self) -> int:
        """Get total number of learners."""
        try:
            result = self.db_manager.execute_query(
                "SELECT COUNT(*) FROM Learners", 
                fetchone=True
            )
            return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"Failed to get learner count: {e}")
            return 0
    
    def get_data_range(self, start_row: int, count: int) -> List[List[Any]]:
        """Get a range of learner data for virtual scrolling."""
        try:
            query = """
                SELECT s.acc_no, s.name, s.surname, s.gender, s.grade, 
                       s.subjects_count, po.option_name, po.fees, s.payment_status
                FROM Learners s
                LEFT JOIN PaymentOptions po ON s.payment_option_id = po.option_id
                ORDER BY s.acc_no
                LIMIT ? OFFSET ?
            """
            
            results = self.db_manager.execute_query(query, (count, start_row), fetchall=True)
            return [list(row) for row in results] if results else []
            
        except Exception as e:
            self.logger.error(f"Failed to get learner data range: {e}")
            return []
    
    def search_data(self, term: str, column: str = "") -> List[int]:
        """Search for learners and return matching row indices."""
        try:
            if column and column != "":
                # Search in specific column
                query = f"""
                    SELECT ROW_NUMBER() OVER (ORDER BY acc_no) - 1 as row_index
                    FROM Learners s
                    LEFT JOIN PaymentOptions po ON s.payment_option_id = po.option_id
                    WHERE LOWER({column}) LIKE LOWER(?)
                    ORDER BY s.acc_no
                """
                search_term = f"%{term}%"
            else:
                # Search in all text columns
                query = """
                    SELECT ROW_NUMBER() OVER (ORDER BY acc_no) - 1 as row_index
                    FROM Learners s
                    LEFT JOIN PaymentOptions po ON s.payment_option_id = po.option_id
                    WHERE LOWER(s.acc_no) LIKE LOWER(?) 
                       OR LOWER(s.name) LIKE LOWER(?)
                       OR LOWER(s.surname) LIKE LOWER(?)
                       OR LOWER(po.option_name) LIKE LOWER(?)
                    ORDER BY s.acc_no
                """
                search_term = f"%{term}%"
            
            if column:
                results = self.db_manager.execute_query(query, (search_term,), fetchall=True)
            else:
                results = self.db_manager.execute_query(
                    query, (search_term, search_term, search_term, search_term), fetchall=True
                )
            
            return [row[0] for row in results] if results else []
            
        except Exception as e:
            self.logger.error(f"Failed to search learner data: {e}")
            return []


def setup_memory_optimization(main_window: QMainWindow, db_manager, mysql_config: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Set up all memory optimization features for the application.
    
    Args:
        main_window: The main application window
        db_manager: Database manager instance
        mysql_config: MySQL configuration for sync (optional)
        
    Returns:
        Dictionary containing references to initialized services
    """
    logger = logging.getLogger('MemoryIntegrationSetup')
    logger.info("Setting up memory optimization features...")
    
    services = {}
    
    try:
        # 1. Initialize core memory optimizer
        logger.info("Initializing memory optimizer...")
        memory_optimizer = MemoryOptimizer(
            warning_threshold=75.0,
            critical_threshold=85.0,
            monitoring_interval=45000,  # 45 seconds
            auto_cleanup=True
        )
        services['memory_optimizer'] = memory_optimizer
        
        # 2. Initialize application-specific memory manager
        logger.info("Initializing application memory manager...")
        # Reuse the created memory optimizer to avoid creating multiple monitor timers
        app_memory_manager = LearnerAppMemoryManager(main_window, optimizer=memory_optimizer)
        services['app_memory_manager'] = app_memory_manager
        
        # 3. Initialize lazy loading service
        logger.info("Initializing lazy loading service...")
        lazy_service = initialize_lazy_loading_service(
            max_cache_size=800,
            max_memory_mb=150,
            cleanup_interval=180  # 3 minutes
        )
        services['lazy_service'] = lazy_service
        
        # Register data loaders
        lazy_service.register_loader(DataType.LEARNER_DETAILS, create_learner_loader(db_manager))
        lazy_service.register_loader(DataType.PAYMENT_HISTORY, create_payment_history_loader(db_manager))
        
        # 4. Initialize OCR model manager (deferred import)
        logger.info("Initializing OCR model manager (deferred import)...")
        try:
            from business.ocr.ocr_model_manager import initialize_ocr_model_manager  # type: ignore
            ocr_manager = initialize_ocr_model_manager(
                default_ttl=180,  # 3 minutes
                cleanup_interval=60,  # 1 minute
                max_memory_mb=400  # 400MB limit for OCR models
            )
            services['ocr_manager'] = ocr_manager
        except Exception as e:
            logger.warning(f"OCR model manager not initialized (import failed): {e}")
        
        # 5. Replace main table with virtual table if needed
        if hasattr(main_window, 'learner_table') and hasattr(main_window, 'all_learners_data'):
            logger.info("Setting up virtual table for learner data...")
            
            # Define columns for virtual table
            virtual_table_columns = [
                {"name": "Acc", "width": 105, "key": "acc_no"},
                {"name": "Name", "width": None, "key": "name"},
                {"name": "Surname", "width": None, "key": "surname"},
                {"name": "Gender", "width": 70, "key": "gender"},
                {"name": "Grade", "width": 55, "key": "grade"},
                {"name": "Subjects", "width": 85, "key": "subjects_count"},
                {"name": "Option", "width": None, "key": "option_name"},
                {"name": "Fees", "width": None, "key": "fees"},
                {"name": "Status", "width": 85, "key": "payment_status"}
            ]
            
            # Create data source
            data_source = LearnerDataSource(db_manager)
            
            # Create virtual table widget
            virtual_table_widget = VirtualTableWidget(virtual_table_columns, data_source)
            
            # Store reference for potential replacement
            services['virtual_table'] = virtual_table_widget
            services['learner_data_source'] = data_source
        
        # 6. Set up configurable sync intervals if MySQL config is provided
        if mysql_config:
            logger.info("Setting up configurable sync engine...")
            
            # Define custom sync intervals
            sync_intervals = {
                'full_sync': 600,      # 10 minutes for full sync
                'incremental': 120,    # 2 minutes for incremental
                'learners': 180,       # 3 minutes for learner data
                'payments': 90,        # 1.5 minutes for payment data
                'families': 300,       # 5 minutes for family data
                'payment_options': 600, # 10 minutes for payment options
                'settings': 1200       # 20 minutes for system settings
            }
            
            # Create optimized sync engine
            sync_engine = SyncEngine(db_manager, mysql_config, sync_intervals)
            services['sync_engine'] = sync_engine
        
        # 7. Set up automatic cleanup callbacks
        logger.info("Setting up cleanup callbacks...")
        
        def cleanup_learner_data(priority):
            """Cleanup callback for learner data."""
            if hasattr(main_window, 'all_learners_data'):
                original_count = len(main_window.all_learners_data)
                if priority.value >= 3:  # HIGH or CRITICAL
                    # Keep only first 200 learners
                    main_window.all_learners_data = main_window.all_learners_data[:200]
                    cleared = original_count - len(main_window.all_learners_data)
                    if cleared > 0:
                        logger.info(f"Cleared {cleared} learner records due to memory pressure")
        
        def cleanup_dialog_cache(priority):
            """Cleanup callback for dialog cache."""
            if hasattr(main_window, 'individual_statements_queue'):
                main_window.individual_statements_queue.clear()
        
        # Register cleanup callbacks
        if 'memory_optimizer' in services:
            services['memory_optimizer'].register_cleanup_callback(cleanup_learner_data)
            services['memory_optimizer'].register_cleanup_callback(cleanup_dialog_cache)
        
        # 8. Add memory monitoring to main window
        if hasattr(main_window, 'statusBar'):
            def update_memory_status():
                """Update memory status in status bar."""
                try:
                    stats = memory_optimizer.get_memory_stats()
                    memory_text = f"Memory: {stats.memory_percent:.1f}%"
                    if stats.memory_percent > 80:
                        memory_text += " (High)"
                    main_window.statusBar().showMessage(memory_text, 3000)
                except Exception:
                    pass
            
            # Connect to memory warning signals
            memory_optimizer.memoryWarning.connect(lambda pct: update_memory_status())
            services['memory_status_callback'] = update_memory_status
        
        # 9. Add method to main window for getting optimized services
        def get_lazy_service():
            return services.get('lazy_service')
        
        def get_ocr_manager():
            return services.get('ocr_manager')
        
        def get_virtual_table():
            return services.get('virtual_table')
        
        # Attach to main window
        main_window.get_lazy_service = get_lazy_service
        main_window.get_ocr_manager = get_ocr_manager
        main_window.get_virtual_table = get_virtual_table
        
        logger.info("Memory optimization setup completed successfully")
        
        # Log summary
        logger.info(f"Initialized services: {list(services.keys())}")
        
        return services
        
    except Exception as e:
        logger.error(f"Failed to setup memory optimization: {e}", exc_info=True)
        
        # Cleanup any partially initialized services
        for service_name, service in services.items():
            try:
                if hasattr(service, 'shutdown'):
                    service.shutdown()
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup {service_name}: {cleanup_error}")
        
        return {}


def setup_lazy_loading_for_dialogs(main_window: QMainWindow, lazy_service) -> None:
    """
    Set up lazy loading for dialog data.
    
    Args:
        main_window: Main application window
        lazy_service: Initialized lazy loading service
    """
    logger = logging.getLogger('LazyDialogSetup')
    
    try:
        # Wrap dialog methods to use lazy loading
        if hasattr(main_window, 'dialog_service'):
            dialog_service = main_window.dialog_service
            
            # Example: Lazy load learner details for dialogs
            # Get the unbound method from the class
            original_show_view_details_dialog_unbound = DialogService.show_view_details_dialog
            if original_show_view_details_dialog_unbound:
                def lazy_show_view_details_dialog(self_dialog_service, acc_no):
                    # Pre-load learner data
                    cache_key = f"learner_details_{acc_no}"
                    lazy_service.get_data(cache_key, DataType.LEARNER_DETAILS, (acc_no,))
                    
                    # Call the original unbound method with the instance and arguments
                    return original_show_view_details_dialog_unbound(self_dialog_service, acc_no)
                
                dialog_service.show_view_details_dialog = lazy_show_view_details_dialog
        
        logger.info("Lazy loading setup for dialogs completed")
        
    except Exception as e:
        logger.error(f"Failed to setup lazy loading for dialogs: {e}")


def optimize_table_for_virtual_scrolling(main_window: QMainWindow, virtual_table_widget) -> None:
    """
    Replace the main learner table with virtual scrolling table.
    
    Args:
        main_window: Main application window
        virtual_table_widget: Virtual table widget to use
    """
    logger = logging.getLogger('VirtualTableSetup')
    
    try:
        if not hasattr(main_window, 'learner_table'):
            logger.warning("Main window does not have learner_table attribute")
            return
        
        # Get the current table's parent layout
        current_table = main_window.learner_table
        parent_layout = current_table.parent().layout()
        
        if parent_layout:
            # Find the table in the layout
            for i in range(parent_layout.count()):
                item = parent_layout.itemAt(i)
                if item and item.widget() == current_table:
                    # Replace with virtual table
                    parent_layout.removeItem(item)
                    parent_layout.insertWidget(i, virtual_table_widget)
                    
                    # Update reference
                    main_window.learner_table = virtual_table_widget.table
                    main_window.virtual_table_widget = virtual_table_widget
                    
                    # Connect signals
                    virtual_table_widget.table.selectionChanged.connect(
                        lambda rows: main_window.on_learner_select() if hasattr(main_window, 'on_learner_select') else None
                    )
                    
                    # Clean up old table
                    current_table.deleteLater()
                    
                    logger.info("Successfully replaced table with virtual scrolling table")
                    break
        else:
            logger.warning("Could not find parent layout for learner table")
            
    except Exception as e:
        logger.error(f"Failed to optimize table for virtual scrolling: {e}")


def shutdown_memory_optimization(services: Dict[str, Any]) -> None:
    """
    Shutdown all memory optimization services.
    
    Args:
        services: Dictionary of initialized services
    """
    logger = logging.getLogger('MemoryIntegrationShutdown')
    logger.info("Shutting down memory optimization services...")
    
    shutdown_order = [
        'sync_engine',
        'virtual_table', 
        'ocr_manager',
        'lazy_service',
        'app_memory_manager',
        'memory_optimizer'
    ]
    
    for service_name in shutdown_order:
        if service_name in services:
            try:
                service = services[service_name]
                if hasattr(service, 'shutdown'):
                    service.shutdown()
                    logger.info(f"Shutdown {service_name}")
                elif hasattr(service, 'stop'):
                    service.stop()
                    logger.info(f"Stopped {service_name}")
            except Exception as e:
                logger.error(f"Failed to shutdown {service_name}: {e}")
    
    # Clear services
    services.clear()
    
    logger.info("Memory optimization shutdown completed")
