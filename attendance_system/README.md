# Attendance System - Decoupled Architecture

A standalone attendance management system that integrates with the K-Maths payment system through well-defined interfaces.

## Overview

This attendance system has been decoupled from the payment system, allowing it to operate independently while still feeding payment information when needed. This architecture provides:

- **Independent Development**: Each system can be developed, tested, and deployed separately
- **Scalability**: Each system can scale independently based on load
- **Maintainability**: Clear separation of concerns
- **Fault Isolation**: Issues in one system don't directly affect the other
- **Technology Flexibility**: Each system can use different technologies if needed

## Directory Structure

```
attendance_system/
├── __init__.py                    # Package initialization
├── attendance_main.py             # Main entry point and facade
├── attendance_database.py         # Dedicated database layer
├── attendance_ocr_processor.py    # OCR processing for attendance
├── payment_integration.py         # Integration with payment system
├── README.md                      # This file
├── attendance_models/
│   ├── __init__.py
│   └── attendance_models.py       # Data models and DTOs
└── attendance_ui/
    ├── __init__.py
    └── attendance_dialogs/
        └── attendance_dialog.py   # UI components
```

## Components

### 1. Attendance Models (`attendance_models/`)

Data models for the attendance system:

- **AttendanceRecord**: Core attendance record with learner info, date, status, and payment data
- **AttendanceSummary**: Aggregated attendance statistics
- **AttendanceFilter**: Query filter criteria
- **AttendanceStatus**: Enum for attendance states (present, absent, late, excused)
- **PaymentFeedData**: Data structure for feeding payments to the payment system
- **OCRResult**: Result from OCR document processing

### 2. Attendance Database (`attendance_database.py`)

Dedicated SQLite database layer with:

- **attendance_records**: Main attendance data table
- **payment_feed_queue**: Queue for payments to be sent to payment system
- **attendance_summary_cache**: Cached summary statistics

Key features:
- Full CRUD operations
- Bulk operations for efficiency
- Query filtering
- Payment feed queue management

### 3. Attendance OCR Processor (`attendance_ocr_processor.py`)

OCR processing specifically for attendance documents:

- PDF and image processing
- Learner name matching
- Signature detection
- Payment data extraction

### 4. Payment Integration (`payment_integration.py`)

Integration layer between attendance and payment systems:

- **PaymentIntegrationService**: Main integration service
- **PaymentFeedWorker**: Background worker for processing payment feeds
- Direct database integration with payment system
- Email notification support

### 5. Attendance System Main (`attendance_main.py`)

Facade providing unified interface:

- Attendance recording and management
- OCR document processing
- Payment data integration
- Reporting and summaries

### 6. Attendance UI (`attendance_ui/`)

PySide6-based UI components:

- **AttendanceDialog**: Main attendance management dialog
- **AttendanceReportDialog**: Report viewing dialog

## Usage

### Standalone Mode

```python
from attendance_system import create_standalone_attendance_system

# Create standalone attendance system
attendance = create_standalone_attendance_system()

# Record attendance
attendance.record_attendance(
    learner_acc_no="KM123",
    learner_name="John",
    learner_surname="Doe",
    grade=5,
    record_date=date.today(),
    status=AttendanceStatus.PRESENT
)

# Get attendance for a date
records = attendance.get_attendance_for_date(date.today())
```

### With Payment System Integration

```python
from attendance_system import create_attendance_system
from data.database_manager import DatabaseManager
from business.services.email_service import EmailService

# Initialize payment system components
payment_db = DatabaseManager("learner_payments.db")
email_service = EmailService()

# Create attendance system with integration
attendance = create_attendance_system(
    payment_db_manager=payment_db,
    notification_service=email_service
)

# Process attendance document with payment extraction
result = attendance.process_attendance_document(
    file_path="attendance_sheet.pdf",
    extract_payments=True,
    auto_record=True
)

print(f"Attendance recorded: {result['attendance_recorded']}")
print(f"Payments detected: {result['payments_detected']}")
print(f"Payments fed to system: {result['payments_fed']}")
```

### Using the UI

```python
from attendance_system.attendance_ui import show_attendance_dialog

# Show the attendance dialog
dialog = show_attendance_dialog(
    payment_db_manager=db_manager,
    notification_service=email_service,
    parent=main_window
)
dialog.exec()
```

## Integration Points

### Payment Data Flow

1. **OCR Processing**: Attendance documents are processed, extracting both attendance and payment data
2. **Payment Queue**: Payment data is queued in the `payment_feed_queue` table
3. **Direct Feed**: If payment DB is available, payments are directly inserted into the payment system
4. **Notifications**: Email notifications are sent to parents for detected payments

### Database Integration

The attendance system can:
- Read learner data from the payment system database
- Write payment records to the payment system's Payments table
- Operate independently with its own database when payment system is unavailable

## API Reference

### AttendanceSystem

Main facade class for the attendance system.

#### Methods

| Method | Description |
|--------|-------------|
| `record_attendance(...)` | Record attendance for a single learner |
| `record_bulk_attendance(records)` | Record attendance for multiple learners |
| `update_attendance(id, status, notes)` | Update an existing record |
| `get_attendance(...)` | Query attendance with filters |
| `get_attendance_for_date(date, grade)` | Get all attendance for a date |
| `process_attendance_document(path, ...)` | Process OCR document |
| `get_attendance_summary(acc_no, start, end)` | Get learner summary |
| `get_grade_attendance_report(grade, start, end)` | Get grade report |
| `get_daily_attendance_report(date)` | Get daily report |
| `process_pending_payment_feeds()` | Process queued payments |
| `sync_with_payment_system()` | Sync with payment system |

## Configuration

The attendance system uses its own SQLite database (`attendance_system/attendance.db`) by default. This can be configured:

```python
attendance = create_attendance_system(
    attendance_db_path="custom/path/attendance.db",
    payment_db_manager=payment_db,
    notification_service=email_service
)
```

## Migration from Legacy System

The main application (`src/presentation/main_window.py`) has been updated to use the new decoupled system:

1. The `open_learner_attendance_dialog()` method now uses the integrated `AttendanceDialog`
2. Legacy attendance fallback has been retired
3. Payment data from attendance is automatically fed to the payment system

## Future Enhancements

Potential improvements:

1. **REST API**: Add REST API for remote access
2. **Message Queue**: Implement RabbitMQ/Redis for async integration
3. **Mobile App**: Create mobile interface for attendance recording
4. **Biometric Integration**: Add fingerprint/face recognition
5. **Real-time Sync**: WebSocket-based real-time synchronization
