"""
Attendance Database Layer

This module provides a dedicated database layer for the attendance system,
completely decoupled from the payment system while maintaining compatibility
for data sharing.
"""

import sqlite3
import logging
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager
import os

from attendance_models.attendance_models import (
    AttendanceRecord, AttendanceSummary, AttendanceFilter,
    AttendanceStatus, PaymentFeedStatus
)


class AttendanceDatabase:
    """
    Dedicated database manager for the attendance system.
    
    This class handles all attendance-related database operations independently
    of the payment system, providing a clean separation of concerns.
    """
    
    def __init__(self, db_path: str = "attendance_system/attendance.db"):
        """
        Initialize the attendance database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Ensure the database file and tables exist."""
        # Create directory if it doesn't exist
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        # Create tables
        with self.get_connection() as conn:
            self._create_tables(conn)
    
    @contextmanager
    def get_connection(self):
        """Get a database connection with context management."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def _create_tables(self, conn):
        """Create the attendance tables if they don't exist."""
        cursor = conn.cursor()
        
        # Main attendance records table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance_records (
                attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                learner_acc_no TEXT NOT NULL,
                learner_name TEXT NOT NULL,
                learner_surname TEXT NOT NULL,
                grade INTEGER NOT NULL DEFAULT 1,
                date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'present',
                signature_image BLOB,
                notes TEXT,
                recorded_by TEXT,
                recorded_at TEXT NOT NULL,
                has_payment INTEGER DEFAULT 0,
                payment_amount REAL,
                payment_date TEXT,
                payment_feed_status TEXT DEFAULT 'not_applicable',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_synced INTEGER DEFAULT 0,
                UNIQUE(learner_acc_no, date)
            )
        ''')
        
        # Payment feed queue - stores payment data to be sent to payment system
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_feed_queue (
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
                created_at TEXT NOT NULL,
                sent_at TEXT,
                error_message TEXT
            )
        ''')
        
        # Attendance summary cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance_summary_cache (
                cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
                learner_acc_no TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                total_days INTEGER DEFAULT 0,
                present_days INTEGER DEFAULT 0,
                absent_days INTEGER DEFAULT 0,
                late_days INTEGER DEFAULT 0,
                excused_days INTEGER DEFAULT 0,
                attendance_rate REAL DEFAULT 0.0,
                calculated_at TEXT NOT NULL,
                UNIQUE(learner_acc_no, period_start, period_end)
            )
        ''')
        
        # Create indexes for better query performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_attendance_learner 
            ON attendance_records(learner_acc_no)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_attendance_date 
            ON attendance_records(date)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_attendance_grade 
            ON attendance_records(grade)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_payment_feed_status 
            ON payment_feed_queue(status)
        ''')
        
        self.logger.info("Attendance database tables created/verified")
    
    # ==================== CRUD Operations ====================
    
    def create_attendance_record(self, record: AttendanceRecord) -> int:
        """
        Create a new attendance record.
        
        Args:
            record: AttendanceRecord to create
            
        Returns:
            The ID of the created record
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT OR REPLACE INTO attendance_records (
                    learner_acc_no, learner_name, learner_surname, grade,
                    date, status, signature_image, notes, recorded_by,
                    recorded_at, has_payment, payment_amount, payment_date,
                    payment_feed_status, created_at, updated_at, is_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.learner_acc_no,
                record.learner_name,
                record.learner_surname,
                record.grade,
                record.date.isoformat(),
                record.status.value,
                record.signature_image,
                record.notes,
                record.recorded_by,
                record.recorded_at.isoformat(),
                1 if record.has_payment else 0,
                record.payment_amount,
                record.payment_date.isoformat() if record.payment_date else None,
                record.payment_feed_status.value,
                now,
                now,
                0
            ))
            
            record_id = cursor.lastrowid
            self.logger.info(f"Created attendance record ID {record_id} for learner {record.learner_acc_no}")
            
            return record_id
    
    def get_attendance_record(self, attendance_id: int) -> Optional[AttendanceRecord]:
        """Get a single attendance record by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM attendance_records WHERE attendance_id = ?",
                (attendance_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return self._row_to_record(row)
            return None
    
    def get_attendance_by_learner_and_date(
        self, learner_acc_no: str, date: date
    ) -> Optional[AttendanceRecord]:
        """Get attendance record for a specific learner on a specific date."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM attendance_records 
                WHERE learner_acc_no = ? AND date = ?
            ''', (learner_acc_no, date.isoformat()))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_record(row)
            return None
    
    def update_attendance_record(self, record: AttendanceRecord) -> bool:
        """Update an existing attendance record."""
        if not record.attendance_id:
            return False
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute('''
                UPDATE attendance_records SET
                    learner_name = ?, learner_surname = ?, grade = ?,
                    status = ?, signature_image = ?, notes = ?,
                    has_payment = ?, payment_amount = ?, payment_date = ?,
                    payment_feed_status = ?, updated_at = ?, is_synced = 0
                WHERE attendance_id = ?
            ''', (
                record.learner_name,
                record.learner_surname,
                record.grade,
                record.status.value,
                record.signature_image,
                record.notes,
                1 if record.has_payment else 0,
                record.payment_amount,
                record.payment_date.isoformat() if record.payment_date else None,
                record.payment_feed_status.value,
                now,
                record.attendance_id
            ))
            
            return cursor.rowcount > 0
    
    def delete_attendance_record(self, attendance_id: int) -> bool:
        """Delete an attendance record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM attendance_records WHERE attendance_id = ?",
                (attendance_id,)
            )
            return cursor.rowcount > 0
    
    # ==================== Query Operations ====================
    
    def query_attendance_records(
        self, 
        filter_criteria: Optional[AttendanceFilter] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[AttendanceRecord]:
        """
        Query attendance records with optional filtering.
        
        Args:
            filter_criteria: Optional filter criteria
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of matching attendance records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM attendance_records"
            params = []
            
            if filter_criteria:
                where_clause, where_params = filter_criteria.to_where_clause()
                query += f" WHERE {where_clause}"
                params = list(where_params)
            
            query += " ORDER BY date DESC, grade, learner_surname, learner_name"
            
            if limit:
                query += f" LIMIT {limit} OFFSET {offset}"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [self._row_to_record(row) for row in rows]
    
    def get_attendance_by_grade(self, grade: int, date_filter: Optional[date] = None) -> List[AttendanceRecord]:
        """Get all attendance records for a specific grade."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if date_filter:
                cursor.execute('''
                    SELECT * FROM attendance_records 
                    WHERE grade = ? AND date = ?
                    ORDER BY learner_surname, learner_name
                ''', (grade, date_filter.isoformat()))
            else:
                cursor.execute('''
                    SELECT * FROM attendance_records 
                    WHERE grade = ?
                    ORDER BY date DESC, learner_surname, learner_name
                ''', (grade,))
            
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    def get_attendance_by_date_range(
        self, 
        start_date: date, 
        end_date: date,
        grade: Optional[int] = None
    ) -> List[AttendanceRecord]:
        """Get attendance records for a date range."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if grade:
                cursor.execute('''
                    SELECT * FROM attendance_records 
                    WHERE date >= ? AND date <= ? AND grade = ?
                    ORDER BY date, grade, learner_surname, learner_name
                ''', (start_date.isoformat(), end_date.isoformat(), grade))
            else:
                cursor.execute('''
                    SELECT * FROM attendance_records 
                    WHERE date >= ? AND date <= ?
                    ORDER BY date, grade, learner_surname, learner_name
                ''', (start_date.isoformat(), end_date.isoformat()))
            
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    # ==================== Summary Operations ====================
    
    def get_attendance_summary(
        self,
        learner_acc_no: str,
        period_start: date,
        period_end: date
    ) -> Optional[AttendanceSummary]:
        """
        Get attendance summary for a learner over a period.
        
        Args:
            learner_acc_no: Learner account number
            period_start: Start date of the period
            period_end: End date of the period
            
        Returns:
            AttendanceSummary or None if no records found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get learner info first
            cursor.execute('''
                SELECT learner_name, learner_surname, grade
                FROM attendance_records
                WHERE learner_acc_no = ?
                LIMIT 1
            ''', (learner_acc_no,))
            learner_info = cursor.fetchone()
            
            if not learner_info:
                return None
            
            # Get summary statistics
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_days,
                    SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_days,
                    SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent_days,
                    SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) as late_days,
                    SUM(CASE WHEN status = 'excused' THEN 1 ELSE 0 END) as excused_days
                FROM attendance_records
                WHERE learner_acc_no = ? AND date >= ? AND date <= ?
            ''', (learner_acc_no, period_start.isoformat(), period_end.isoformat()))
            
            stats = cursor.fetchone()
            
            summary = AttendanceSummary(
                learner_acc_no=learner_acc_no,
                learner_name=learner_info['learner_name'],
                learner_surname=learner_info['learner_surname'],
                grade=learner_info['grade'],
                period_start=period_start,
                period_end=period_end,
                total_days=stats['total_days'] or 0,
                present_days=stats['present_days'] or 0,
                absent_days=stats['absent_days'] or 0,
                late_days=stats['late_days'] or 0,
                excused_days=stats['excused_days'] or 0
            )
            summary.calculate_attendance_rate()
            
            return summary
    
    # ==================== Payment Feed Operations ====================
    
    def add_payment_to_feed_queue(
        self,
        learner_acc_no: str,
        learner_name: str,
        learner_surname: str,
        amount: float,
        payment_date: date,
        source_document: Optional[str] = None,
        source_type: str = "attendance_ocr",
        reference_number: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """
        Add a payment record to the feed queue for the payment system.
        
        This is the integration point - payment data is queued here
        and will be picked up by the payment system.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT INTO payment_feed_queue (
                    learner_acc_no, learner_name, learner_surname, amount,
                    payment_date, source_document, source_type, reference_number,
                    notes, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            ''', (
                learner_acc_no, learner_name, learner_surname, amount,
                payment_date.isoformat(), source_document, source_type,
                reference_number, notes, now
            ))
            
            feed_id = cursor.lastrowid
            self.logger.info(f"Added payment to feed queue: ID {feed_id}, Amount R{amount:.2f}")
            
            return feed_id
    
    def get_pending_payment_feeds(self) -> List[Dict[str, Any]]:
        """Get all pending payment feed records."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM payment_feed_queue 
                WHERE status = 'pending'
                ORDER BY created_at
            ''')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def mark_payment_feed_sent(self, feed_id: int) -> bool:
        """Mark a payment feed record as sent."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE payment_feed_queue 
                SET status = 'sent', sent_at = ?
                WHERE feed_id = ?
            ''', (datetime.now().isoformat(), feed_id))
            return cursor.rowcount > 0
    
    def mark_payment_feed_failed(self, feed_id: int, error_message: str) -> bool:
        """Mark a payment feed record as failed."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE payment_feed_queue 
                SET status = 'failed', error_message = ?
                WHERE feed_id = ?
            ''', (error_message, feed_id))
            return cursor.rowcount > 0
    
    # ==================== Bulk Operations ====================
    
    def bulk_create_attendance_records(
        self, 
        records: List[AttendanceRecord]
    ) -> Tuple[int, int]:
        """
        Create multiple attendance records in a single transaction.
        
        Args:
            records: List of AttendanceRecord objects to create
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        success_count = 0
        failure_count = 0
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            for record in records:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO attendance_records (
                            learner_acc_no, learner_name, learner_surname, grade,
                            date, status, signature_image, notes, recorded_by,
                            recorded_at, has_payment, payment_amount, payment_date,
                            payment_feed_status, created_at, updated_at, is_synced
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        record.learner_acc_no,
                        record.learner_name,
                        record.learner_surname,
                        record.grade,
                        record.date.isoformat(),
                        record.status.value,
                        record.signature_image,
                        record.notes,
                        record.recorded_by,
                        record.recorded_at.isoformat(),
                        1 if record.has_payment else 0,
                        record.payment_amount,
                        record.payment_date.isoformat() if record.payment_date else None,
                        record.payment_feed_status.value,
                        now,
                        now,
                        0
                    ))
                    success_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to create attendance record: {e}")
                    failure_count += 1
        
        self.logger.info(f"Bulk create: {success_count} successful, {failure_count} failed")
        return success_count, failure_count
    
    # ==================== Helper Methods ====================
    
    def _row_to_record(self, row: sqlite3.Row) -> AttendanceRecord:
        """Convert a database row to an AttendanceRecord."""
        return AttendanceRecord(
            attendance_id=row['attendance_id'],
            learner_acc_no=row['learner_acc_no'],
            learner_name=row['learner_name'],
            learner_surname=row['learner_surname'],
            grade=row['grade'],
            date=date.fromisoformat(row['date']),
            status=AttendanceStatus(row['status']),
            signature_image=row['signature_image'],
            notes=row['notes'],
            recorded_by=row['recorded_by'],
            recorded_at=datetime.fromisoformat(row['recorded_at']),
            has_payment=bool(row['has_payment']),
            payment_amount=row['payment_amount'],
            payment_date=date.fromisoformat(row['payment_date']) if row['payment_date'] else None,
            payment_feed_status=PaymentFeedStatus(row['payment_feed_status']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            is_synced=bool(row['is_synced'])
        )
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Total records
            cursor.execute("SELECT COUNT(*) FROM attendance_records")
            stats['total_records'] = cursor.fetchone()[0]
            
            # Records by status
            cursor.execute('''
                SELECT status, COUNT(*) as count 
                FROM attendance_records 
                GROUP BY status
            ''')
            stats['by_status'] = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # Pending payment feeds
            cursor.execute(
                "SELECT COUNT(*) FROM payment_feed_queue WHERE status = 'pending'"
            )
            stats['pending_payment_feeds'] = cursor.fetchone()[0]
            
            # Date range
            cursor.execute("SELECT MIN(date), MAX(date) FROM attendance_records")
            date_range = cursor.fetchone()
            stats['date_range'] = {
                'earliest': date_range[0],
                'latest': date_range[1]
            }
            
            return stats