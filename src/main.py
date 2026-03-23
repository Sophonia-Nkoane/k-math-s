import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from data.database_manager import DatabaseManager
from data.remote_backend_detector import detect_remote_backend
from presentation.main_window import LearnerManagementApp
from utils.theme_manager import ThemeManager
from data.repositories.learner_repository import LearnerRepository
from data.repositories.parent_repository import ParentRepository
from data.repositories.payment_repository import PaymentRepository
from data.repositories.family_repository import FamilyRepository
from business.services.learner_service import LearnerService
import traceback

APP_NAME = "Payment Management System"
COMPANY_NAME = "Learner Payment System"
APP_ID = "PaymentSystem_SingleInstance_Lock"
logger = logging.getLogger(__name__)


def _migrate_legacy_database_file(db_file: Path) -> None:
    """Move the legacy SQLite file to the renamed learner_* path once."""
    legacy_db_file = db_file.with_name("student_payments.db")
    if db_file.exists() or not legacy_db_file.exists():
        return

    for suffix in ("", "-wal", "-shm"):
        legacy_path = Path(f"{legacy_db_file}{suffix}")
        current_path = Path(f"{db_file}{suffix}")
        if not legacy_path.exists() or current_path.exists():
            continue
        legacy_path.replace(current_path)

    logger.info("Migrated legacy database file %s -> %s", legacy_db_file.name, db_file.name)

def setup_directories():
    """Creates necessary directories and returns a dictionary of paths."""
    try:
        base_dir = Path(__file__).resolve().parent
        is_dev = 'dev_src' in str(base_dir)

        paths = {
            'BASE_DIR': base_dir,
            'DATABASE_FILE': base_dir / 'learner_payments.db',
            'RESOURCES_DIR': base_dir / 'presentation' / 'resources',
            'CONFIG_FILE': base_dir / 'config.ini',
            'IS_DEV': is_dev
        }

        if is_dev:
            paths['LOG_DIR'] = base_dir / 'logs'
            os.makedirs(paths['LOG_DIR'], exist_ok=True)

        return paths
    except Exception as e:
        logger.exception(f"Failed to setup directories: {e}")
        return None

def setup_logging(log_dir):
    """Configures logging for the application."""
    try:
        # Create a formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Setup file handler
        file_handler = RotatingFileHandler(
            str(log_dir / 'app.log'),
            maxBytes=1024 * 1024,  # 1MB
            backupCount=3
        )
        file_handler.setFormatter(formatter)
        
        # Setup console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        root_logger.debug("Logging initialized")
        return True
    except Exception as e:
        sys.stderr.write(f"Failed to initialize logging: {e}\n")
        sys.stderr.flush()
        return False

def init_app(app_id):
    """Initializes the QApplication and handles single-instance logic."""
    logger.info("Starting application initialization")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(COMPANY_NAME)

    # Clean up any existing server socket
    QLocalServer.removeServer(app_id)
    
    server = QLocalServer()
    socket = QLocalSocket()
    
    logger.debug(f"Attempting to connect to existing server with ID: {app_id}")
    try:
        socket.connectToServer(app_id)
        if socket.waitForConnected(500):
            # Only exit if we can confirm another instance is really running
            if socket.state() == QLocalSocket.ConnectedState:
                logger.info("Another instance is running, sending SHOW command")
                socket.write(b"SHOW")
                socket.flush()
                socket.waitForBytesWritten(1000)
                sys.exit(0)
        else:
            logger.debug("No existing instance found, continuing startup")
    finally:
        socket.close()

    logger.debug(f"Attempting to listen with ID: {app_id}")
    if not server.listen(app_id):
        logger.warning(f"Server listen failed, removing stale server: {app_id}")
        try:
            server.removeServer(app_id)
        except Exception as e:
            logger.warning(f"Error removing stale server {app_id}: {e}")
            pass
        
        logger.debug(f"Retrying listen with ID: {app_id}")
        if not server.listen(app_id):
            try:
                err = server.errorString()
            except Exception:
                err = "Unknown error"
            logger.error(f"Could not create local server: {err}")
            sys.exit(1)

    logger.info("Application initialized successfully")
    return app, server

def init_database(db_file, mysql_config=None, enable_sync=False):
    """Initializes the database connection."""
    db_file = Path(db_file)
    _migrate_legacy_database_file(db_file)
    logger.info(f"Initializing database at {db_file}")

    db_manager = DatabaseManager(str(db_file), mysql_config=mysql_config, enable_sync=enable_sync)
    
    try:
        db_manager.setup_database()
        logger.debug("Database setup complete")
        
        exists = os.path.exists(db_file)
        logger.debug(f"Database file exists: {exists}")
        
        if exists:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM Users")
                count = cursor.fetchone()[0]
                logger.debug(f"Number of users in database: {count}")
            
        return db_manager
    except Exception as e:
        QMessageBox.critical(None, "Database Setup Error", f"Could not initialize database: {e}")
        logger.exception(f"Database setup failed: {e}")
        sys.exit(1)

def close_single_instance_server(server, app_id):
    """Best-effort cleanup for the single-instance local server socket."""
    if not server:
        return
    try:
        server.close()
    except Exception as e:
        logger.debug(f"Server close warning: {e}")
    try:
        server.removeServer(app_id)
    except Exception as e:
        logger.debug(f"Server socket cleanup warning: {e}")

def log_runtime_context(paths, remote_backend, sync_enabled):
    """Logs startup context to help diagnose environment-specific issues."""
    backend_name = "sqlite"
    if remote_backend and getattr(remote_backend, "backend", None):
        backend_name = remote_backend.backend
    logger.info(
        "Runtime context | base_dir=%s | backend=%s | sync_enabled=%s",
        paths['BASE_DIR'],
        backend_name,
        sync_enabled,
    )

def main():
    try:
        sys.stderr.write("=== Application Starting ===\n")
        sys.stderr.flush()

        paths = setup_directories()
        if not paths:
            sys.stderr.write("ERROR: Directory setup failed\n")
            sys.stderr.flush()
            sys.exit(1)

        if paths.get('IS_DEV'):
            if not setup_logging(paths['LOG_DIR']):
                sys.stderr.write("ERROR: Logging setup failed\n")
                sys.stderr.flush()
                sys.exit(1)
        else:
            logging.disable(logging.CRITICAL)
        logger.info("Setup complete")
    except Exception as e:
        sys.stderr.write(f"An error occurred during setup: {e}\n")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)

    app, server = init_app(APP_ID)

    remote_backend = detect_remote_backend(logger)
    mysql_config = None
    if remote_backend and remote_backend.backend == "mysql":
        mysql_config = remote_backend.config
    sync_enabled = bool(mysql_config)
    log_runtime_context(paths, remote_backend, sync_enabled)

    db_manager = init_database(
        paths['DATABASE_FILE'],
        mysql_config=mysql_config,
        enable_sync=sync_enabled,
    )

    try:
        try:
            import torchvision
            if getattr(sys, 'frozen', False):
                torch_lib_path = os.path.join(os.path.dirname(sys.executable), 'torch', 'lib')
                if os.path.exists(torch_lib_path):
                    os.add_dll_directory(torch_lib_path)
        except Exception as e:
            logging.warning(f"Torchvision initialization warning: {e}")

        # Instantiate repositories
        learner_repository = LearnerRepository(db_manager)
        parent_repository = ParentRepository(db_manager)
        payment_repository = PaymentRepository(db_manager)
        family_repository = FamilyRepository(db_manager)

        # Instantiate service
        learner_service = LearnerService(
            learner_repository,
            parent_repository,
            payment_repository,
            family_repository
        )

        theme_manager = ThemeManager(paths['CONFIG_FILE'])
        window = LearnerManagementApp(learner_service, str(paths['RESOURCES_DIR'] / 'App.ico'), theme_manager)

        if window and hasattr(window, 'current_user_id') and window.current_user_id is not None:
            daily_sync_scheduler = None
            try:
                from utils.memory_integration_setup import setup_memory_optimization
                memory_services = setup_memory_optimization(window, db_manager, mysql_config)
                logging.info(f"Memory optimization enabled: {len(memory_services)} services initialized")
            except Exception as e:
                logging.warning(f"Memory optimization setup failed: {e}")

            # Initialize automatic statement scheduler
            auto_scheduler = None
            try:
                from utils.auto_statement_scheduler import AutoStatementScheduler
                auto_scheduler = AutoStatementScheduler(window, db_manager)
                auto_scheduler.start()
                logging.info("Automatic statement scheduler initialized and started")
            except Exception as e:
                logging.warning(f"Auto statement scheduler setup failed: {e}")

            if sync_enabled:
                try:
                    from utils.daily_sync_scheduler import DailySyncScheduler
                    daily_sync_scheduler = DailySyncScheduler(window, db_manager)
                    daily_sync_scheduler.syncStarted.connect(
                        lambda: window.statusBar().showMessage("Daily sync started...", 5000)
                    )
                    daily_sync_scheduler.syncFinished.connect(
                        lambda result: window.statusBar().showMessage(
                            f"Daily sync complete: up={result.get('uploaded_count', 0)}, "
                            f"down={result.get('downloaded_count', 0)}, "
                            f"conflicts={result.get('conflict_count', 0)}",
                            10000,
                        )
                    )
                    daily_sync_scheduler.syncFailed.connect(
                        lambda err: window.statusBar().showMessage(f"Daily sync failed: {err}", 10000)
                    )
                    daily_sync_scheduler.start()
                    window.sync_scheduler = daily_sync_scheduler
                    logging.info("Daily sync scheduler initialized and started")
                except Exception as e:
                    logging.warning(f"Daily sync scheduler setup failed: {e}")

            window.show()

            def handle_connection():
                client = server.nextPendingConnection()
                if client and client.waitForReadyRead(1000):
                    window.showNormal()
                    window.raise_()
                    window.activateWindow()
                if client:
                    client.close()
                    client.deleteLater()

            server.newConnection.connect(handle_connection)
            exit_code = app.exec()

            # Cleanup: Stop the auto scheduler before exiting
            if auto_scheduler:
                try:
                    auto_scheduler.stop()
                    logging.info("Automatic statement scheduler stopped")
                except Exception as e:
                    logging.warning(f"Error stopping auto scheduler: {e}")

            if daily_sync_scheduler:
                try:
                    daily_sync_scheduler.stop()
                    logging.info("Daily sync scheduler stopped")
                except Exception as e:
                    logging.warning(f"Error stopping daily sync scheduler: {e}")

            db_manager.close()
            close_single_instance_server(server, APP_ID)
            sys.exit(exit_code)
        else:
            close_single_instance_server(server, APP_ID)
            sys.exit(1)

    except Exception as e:
        logger.exception(f"Fatal application error: {e}")
        QMessageBox.critical(None, "Fatal Error", f"An unexpected error occurred: {e}")
        close_single_instance_server(server, APP_ID)
        sys.exit(1)

if __name__ == "__main__":
    main()
