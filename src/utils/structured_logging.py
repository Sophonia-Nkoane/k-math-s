"""
Structured Logging Module for K-Maths Production
Provides JSON-formatted logs for better monitoring and debugging
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import os


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data
        
        return json.dumps(log_data)


class StructuredLogger:
    """Structured logger with context support"""
    
    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Add structured handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
    
    def _log(self, level: int, message: str, **kwargs):
        """Log with extra data"""
        if kwargs:
            record = self.logger.makeRecord(
                self.logger.name, level, "", 0, message, (), None
            )
            record.extra_data = kwargs
            self.logger.handle(record)
        else:
            self.logger.log(level, message)
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)


# Application-specific loggers
class AppLogger:
    """Application logger with context"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._loggers: Dict[str, StructuredLogger] = {}
        
        # Set root log level from environment
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        self._level = getattr(logging, log_level, logging.INFO)
    
    def get_logger(self, name: str) -> StructuredLogger:
        """Get or create a logger by name"""
        if name not in self._loggers:
            self._loggers[name] = StructuredLogger(name, self._level)
        return self._loggers[name]
    
    def set_level(self, level: int):
        """Set log level for all loggers"""
        self._level = level
        for logger in self._loggers.values():
            logger.logger.setLevel(level)


# Global logger instance
app_logger = AppLogger()


# Convenience functions
def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger"""
    return app_logger.get_logger(name)


def log_database_operation(operation: str, table: str, duration_ms: float = None, **kwargs):
    """Log database operations with context"""
    logger = get_logger("database")
    data = {"operation": operation, "table": table, **kwargs}
    if duration_ms:
        data["duration_ms"] = round(duration_ms, 2)
    logger.info(f"Database operation: {operation} on {table}", **data)


def log_ocr_operation(operation: str, document: str = None, duration_ms: float = None, success: bool = True):
    """Log OCR operations with context"""
    logger = get_logger("ocr")
    data = {"operation": operation, "success": success}
    if document:
        data["document"] = document
    if duration_ms:
        data["duration_ms"] = round(duration_ms, 2)
    
    if success:
        logger.info(f"OCR operation: {operation}", **data)
    else:
        logger.warning(f"OCR operation failed: {operation}", **data)


def log_payment_operation(operation: str, learner_acc_no: str, amount: float = None, **kwargs):
    """Log payment operations with context"""
    logger = get_logger("payment")
    data = {"operation": operation, "learner_acc_no": learner_acc_no, **kwargs}
    if amount:
        data["amount"] = amount
    logger.info(f"Payment operation: {operation}", **data)


def log_attendance_operation(operation: str, learner_acc_no: str, date: str = None, **kwargs):
    """Log attendance operations with context"""
    logger = get_logger("attendance")
    data = {"operation": operation, "learner_acc_no": learner_acc_no, **kwargs}
    if date:
        data["date"] = date
    logger.info(f"Attendance operation: {operation}", **data)


def log_error(component: str, error: Exception, context: Dict[str, Any] = None):
    """Log errors with context"""
    logger = get_logger(component)
    data = {"error_type": type(error).__name__}
    if context:
        data["context"] = context
    logger.error(f"Error in {component}: {str(error)}", **data)