"""
Migration: Enhanced Attendance System

Adds comprehensive attendance tracking tables to the main database,
enabling full integration with the payment system.
"""

import logging


def upgrade(db_manager):
    """
    Creates enhanced attendance tables for integrated attendance and payment system.
    
    Tables created:
    - AttendanceRecords: Main attendance tracking
    - AttendanceSummary: Aggregated attendance statistics
    - AttendancePaymentFeed: Queue for attendance-detected payments
    - AttendanceConfig: System configuration
    """
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    # Drop old Attendance table if exists and create new enhanced version
    cursor.execute('DROP TABLE IF EXISTS Attendance')
    
    # Main attendance records table with full integration
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS AttendanceRecords (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            learner_acc_no TEXT NOT NULL,
            learner_name TEXT NOT NULL,
            learner_surname TEXT NOT NULL,
            grade INTEGER NOT NULL DEFAULT 1,
            date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'present',
            check_in_time TEXT,
            check_out_time TEXT,
            signature_image BLOB,
            notes TEXT,
            recorded_by TEXT,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            
            -- Payment integration fields
            has_payment INTEGER DEFAULT 0,
            payment_amount REAL,
            payment_date TEXT,
            payment_reference TEXT,
            payment_feed_status TEXT DEFAULT 'not_applicable',
            
            -- Sync tracking
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_synced INTEGER DEFAULT 0,
            uuid TEXT DEFAULT (lower(hex(randomblob(16)))),
            
            -- Constraints
            UNIQUE(learner_acc_no, date),
            FOREIGN KEY (learner_acc_no) REFERENCES Learners(acc_no) ON DELETE CASCADE
        )
    ''')
    
    # Attendance summary cache for performance
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS AttendanceSummary (
            summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
            learner_acc_no TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            total_days INTEGER DEFAULT 0,
            present_days INTEGER DEFAULT 0,
            absent_days INTEGER DEFAULT 0,
            late_days INTEGER DEFAULT 0,
            excused_days INTEGER DEFAULT 0,
            attendance_rate REAL DEFAULT 0.0,
            calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE(learner_acc_no, period_start, period_end),
            FOREIGN KEY (learner_acc_no) REFERENCES Learners(acc_no) ON DELETE CASCADE
        )
    ''')
    
    # Payment feed queue for attendance-detected payments
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS AttendancePaymentFeed (
            feed_id INTEGER PRIMARY KEY AUTOINCREMENT,
            learner_acc_no TEXT NOT NULL,
            learner_name TEXT NOT NULL,
            learner_surname TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            source_document TEXT,
            source_type TEXT DEFAULT 'attendance_ocr',
            reference_number TEXT,
            notes TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            processed_at TEXT,
            error_message TEXT,
            
            FOREIGN KEY (learner_acc_no) REFERENCES Learners(acc_no) ON DELETE CASCADE
        )
    ''')
    
    # Attendance configuration
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS AttendanceConfig (
            config_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT NOT NULL UNIQUE,
            config_value TEXT,
            description TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes for performance
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_attendance_learner 
        ON AttendanceRecords(learner_acc_no)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_attendance_date 
        ON AttendanceRecords(date)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_attendance_grade 
        ON AttendanceRecords(grade)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_attendance_status 
        ON AttendanceRecords(status)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_attendance_payment_status 
        ON AttendanceRecords(payment_feed_status)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_payment_feed_status 
        ON AttendancePaymentFeed(status)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_summary_learner 
        ON AttendanceSummary(learner_acc_no)
    ''')
    
    # Insert default configuration
    default_configs = [
        ('attendance_time_start', '07:00', 'Default school start time'),
        ('attendance_time_end', '15:00', 'Default school end time'),
        ('late_threshold_minutes', '15', 'Minutes after start time to be marked late'),
        ('auto_mark_absent', 'true', 'Auto-mark learners absent if no record by end of day'),
        ('payment_detection_enabled', 'true', 'Enable payment detection during attendance'),
        ('notification_enabled', 'true', 'Send notifications for attendance events'),
    ]
    
    for key, value, description in default_configs:
        cursor.execute('''
            INSERT OR IGNORE INTO AttendanceConfig (config_key, config_value, description)
            VALUES (?, ?, ?)
        ''', (key, value, description))
    
    # Create triggers for automatic timestamp updates
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS attendance_records_update_trigger
        AFTER UPDATE ON AttendanceRecords
        FOR EACH ROW
        BEGIN
            UPDATE AttendanceRecords
            SET updated_at = CURRENT_TIMESTAMP
            WHERE attendance_id = OLD.attendance_id;
        END;
    ''')
    
    logging.info("Enhanced attendance system tables created successfully")


def downgrade(db_manager):
    """Remove attendance system tables."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DROP TABLE IF EXISTS AttendanceRecords')
    cursor.execute('DROP TABLE IF EXISTS AttendanceSummary')
    cursor.execute('DROP TABLE IF EXISTS AttendancePaymentFeed')
    cursor.execute('DROP TABLE IF EXISTS AttendanceConfig')
    
    logging.info("Attendance system tables removed")
