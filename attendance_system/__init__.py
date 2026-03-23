"""
Attendance System Package

A decoupled attendance management system that integrates with
the payment system through well-defined interfaces.

Usage:
    from attendance_system import AttendanceSystem, create_attendance_system
    
    # Create with payment system integration
    attendance = create_attendance_system(
        payment_db_manager=db_manager,
        notification_service=email_service
    )
    
    # Or create standalone
    attendance = create_standalone_attendance_system()
"""

from attendance_main import (
    AttendanceSystem,
    create_attendance_system,
    create_standalone_attendance_system
)
from attendance_database import AttendanceDatabase
from attendance_ocr_processor import AttendanceOCRProcessor
from payment_integration import PaymentIntegrationService
from attendance_models.attendance_models import (
    AttendanceRecord,
    AttendanceSummary,
    AttendanceFilter,
    AttendanceStatus,
    PaymentFeedStatus,
    PaymentFeedData,
    OCRResult
)

__version__ = "1.0.0"
__all__ = [
    # Main system
    "AttendanceSystem",
    "create_attendance_system",
    "create_standalone_attendance_system",
    
    # Components
    "AttendanceDatabase",
    "AttendanceOCRProcessor",
    "PaymentIntegrationService",
    
    # Models
    "AttendanceRecord",
    "AttendanceSummary",
    "AttendanceFilter",
    "AttendanceStatus",
    "PaymentFeedStatus",
    "PaymentFeedData",
    "OCRResult"
]