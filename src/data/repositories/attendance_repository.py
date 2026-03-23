"""
Attendance Repository

Provides data access for attendance records with full integration
to the payment system using the same database.
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import sqlite3

from .base_repository import BaseRepository, QueryResult


class AttendanceStatus(Enum):
    """Attendance status enumeration."""
    PRESENT = 'present'
    ABSENT = 'absent'
    LATE = 'late'
    EXCUSED = 'excused'
    HALF_DAY = 'half_day'


class PaymentFeedStatus(Enum):
    """Payment feed status enumeration."""
    NOT_APPLICABLE = 'not_applicable'
    PENDING = 'pending'
    SENT = 'sent'
    FAILED = 'failed'


@dataclass
class AttendanceRecord:
    """Attendance record data model."""
    attendance_id: Optional[int] = None
    learner_acc_no: str = ''
    learner_name: str = ''
    learner_surname: str = ''
    grade: int = 1
    date: date = None
    status: AttendanceStatus = AttendanceStatus.PRESENT
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    signature_image: Optional[bytes] = None
    notes: Optional[str] = None
    recorded_by: Optional[str] = None
    recorded_at: datetime = None
    has_payment: bool = False
    payment_amount: Optional[float] = None
    payment_date: Optional[date] = None
    payment_reference: Optional[str] = None
    payment_feed_status: PaymentFeedStatus = PaymentFeedStatus.NOT_APPLICABLE
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.date is None:
            self.date = date.today()
        if self.recorded_at is None:
            self.recorded_at = datetime.now()
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'attendance_id': self.attendance_id,
            'learner_acc_no': self.learner_acc_no,
            'learner_name': self.learner_name,
            'learner_surname': self.learner_surname,
            'grade': self.grade,
            'date': self.date.isoformat() if self.date else None,
            'status': self.status.value if isinstance(self.status, AttendanceStatus) else self.status,
            'check_in_time': self.check_in_time,
            'check_out_time': self.check_out_time,
            'notes': self.notes,
            'recorded_by': self.recorded_by,
            'has_payment': self.has_payment,
            'payment_amount': self.payment_amount,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'payment_reference': self.payment_reference,
            'payment_feed_status': self.payment_feed_status.value if isinstance(self.payment_feed_status, PaymentFeedStatus) else self.payment_feed_status,
        }


@dataclass
class AttendanceSummary:
    """Attendance summary statistics."""
    summary_id: Optional[int] = None
    learner_acc_no: str = ''
    learner_name: str = ''
    learner_surname: str = ''
    grade: int = 1
    period_start: date = None
    period_end: date = None
    total_days: int = 0
    present_days: int = 0
    absent_days: int = 0
    late_days: int = 0
    excused_days: int = 0
    attendance_rate: float = 0.0
    
    def calculate_attendance_rate(self):
        """Calculate the attendance rate percentage."""
        if self.total_days > 0:
            self.attendance_rate = (self.present_days / self.total_days) * 100
        else:
            self.attendance_rate = 0.0


@dataclass
class PaymentFeedData:
    """Payment data for feeding to payment system."""
    feed_id: Optional[int] = None
    learner_acc_no: str = ''
    learner_name: str = ''
    learner_surname: str = ''
    amount: float = 0.0
    payment_date: date = None
    source_document: Optional[str] = None
    source_type: str = 'attendance_ocr'
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    status: str = 'pending'


class AttendanceRepository(BaseRepository[AttendanceRecord]):
    """
    Repository for attendance records with payment system integration.
    
    Features:
    - Full CRUD operations for attendance records
    - Bulk operations for efficiency
    - Summary calculations
    - Payment feed integration
    - Cross-system queries with payment data
    """
    
    def __init__(self, db_manager):
        """
        Initialize the attendance repository.
        
        Args:
            db_manager: Database manager instance
        """
        # Temporarily set connection pool
        from ..connection_pool import get_connection_pool
        self._connection_pool = get_connection_pool()
        
        self.table_name = 'AttendanceRecords'
        self.model_class = AttendanceRecord
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, datetime] = {}
        self._logger = logging.getLogger(f"{self.__class__.__name__}")
        self.db_manager = db_manager
        
        if not self._connection_pool:
            raise RuntimeError("Connection pool not initialized")
    
    def _get_primary_key(self) -> str:
        """Return the primary key column name."""
        return 'attendance_id'
    
    def _row_to_model(self, row) -> AttendanceRecord:
        """Convert a database row to an AttendanceRecord."""
        if isinstance(row, sqlite3.Row):
            row = dict(row)
        
        return AttendanceRecord(
            attendance_id=row.get('attendance_id'),
            learner_acc_no=row.get('learner_acc_no', ''),
            learner_name=row.get('learner_name', ''),
            learner_surname=row.get('learner_surname', ''),
            grade=row.get('grade', 1),
            date=date.fromisoformat(row['date']) if row.get('date') else None,
            status=AttendanceStatus(row.get('status', 'present')),
            check_in_time=row.get('check_in_time'),
            check_out_time=row.get('check_out_time'),
            signature_image=row.get('signature_image'),
            notes=row.get('notes'),
            recorded_by=row.get('recorded_by'),
            recorded_at=datetime.fromisoformat(row['recorded_at']) if row.get('recorded_at') else None,
            has_payment=bool(row.get('has_payment', 0)),
            payment_amount=row.get('payment_amount'),
            payment_date=date.fromisoformat(row['payment_date']) if row.get('payment_date') else None,
            payment_reference=row.get('payment_reference'),
            payment_feed_status=PaymentFeedStatus(row.get('payment_feed_status', 'not_applicable')),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row.get('updated_at') else None,
        )
    
    def _model_to_dict(self, entity: AttendanceRecord) -> Dict[str, Any]:
        """Convert an AttendanceRecord to a dictionary."""
        return {
            'learner_acc_no': entity.learner_acc_no,
            'learner_name': entity.learner_name,
            'learner_surname': entity.learner_surname,
            'grade': entity.grade,
            'date': entity.date.isoformat() if entity.date else None,
            'status': entity.status.value if isinstance(entity.status, AttendanceStatus) else entity.status,
            'check_in_time': entity.check_in_time,
            'check_out_time': entity.check_out_time,
            'signature_image': entity.signature_image,
            'notes': entity.notes,
            'recorded_by': entity.recorded_by,
            'recorded_at': entity.recorded_at.isoformat() if entity.recorded_at else None,
            'has_payment': 1 if entity.has_payment else 0,
            'payment_amount': entity.payment_amount,
            'payment_date': entity.payment_date.isoformat() if entity.payment_date else None,
            'payment_reference': entity.payment_reference,
            'payment_feed_status': entity.payment_feed_status.value if isinstance(entity.payment_feed_status, PaymentFeedStatus) else entity.payment_feed_status,
        }
    
    # ==================== Core CRUD Operations ====================
    
    def create(self, record: AttendanceRecord) -> AttendanceRecord:
        """
        Create a new attendance record.
        
        Args:
            record: AttendanceRecord to create
            
        Returns:
            Created record with ID populated
        """
        data = self._model_to_dict(record)
        columns = list(data.keys())
        placeholders = ['?' for _ in columns]
        
        query = f'''
            INSERT OR REPLACE INTO {self.table_name} (
                {', '.join(columns)}
            ) VALUES ({', '.join(placeholders)})
        '''
        
        result = self.execute_query(query, tuple(data.values()))
        
        if result.success:
            record.attendance_id = result.data if result.data else self._get_last_insert_id()
            self._invalidate_cache_pattern(f"{self.table_name}_")
            return record
        else:
            raise RuntimeError(f"Failed to create attendance record: {result.error}")
    
    def _get_last_insert_id(self) -> Optional[int]:
        """Get the last inserted row ID."""
        result = self.execute_query(
            "SELECT last_insert_rowid()",
            fetch_one=True
        )
        return result.data[0] if result.success and result.data else None
    
    def find_by_learner_and_date(
        self, 
        learner_acc_no: str, 
        record_date: date
    ) -> Optional[AttendanceRecord]:
        """
        Find attendance record for a specific learner on a specific date.
        
        Args:
            learner_acc_no: Learner account number
            record_date: Date to check
            
        Returns:
            AttendanceRecord if found, None otherwise
        """
        cache_key = f"{self.table_name}_learner_date_{learner_acc_no}_{record_date}"
        
        result = self.execute_query(
            f"SELECT * FROM {self.table_name} WHERE learner_acc_no = ? AND date = ?",
            (learner_acc_no, record_date.isoformat()),
            fetch_one=True,
            use_cache=True,
            cache_key=cache_key
        )
        
        if result.success and result.data:
            return self._row_to_model(result.data)
        return None
    
    def find_by_date(
        self, 
        record_date: date,
        grade: Optional[int] = None
    ) -> List[AttendanceRecord]:
        """
        Find all attendance records for a specific date.
        
        Args:
            record_date: Date to query
            grade: Optional grade filter
            
        Returns:
            List of attendance records
        """
        if grade:
            query = f'''
                SELECT * FROM {self.table_name} 
                WHERE date = ? AND grade = ?
                ORDER BY learner_surname, learner_name
            '''
            params = (record_date.isoformat(), grade)
        else:
            query = f'''
                SELECT * FROM {self.table_name} 
                WHERE date = ?
                ORDER BY grade, learner_surname, learner_name
            '''
            params = (record_date.isoformat(),)
        
        result = self.execute_query(query, params, fetch_all=True)
        
        if result.success and result.data:
            return [self._row_to_model(row) for row in result.data]
        return []
    
    def find_by_date_range(
        self,
        start_date: date,
        end_date: date,
        learner_acc_no: Optional[str] = None,
        grade: Optional[int] = None
    ) -> List[AttendanceRecord]:
        """
        Find attendance records within a date range.
        
        Args:
            start_date: Start date
            end_date: End date
            learner_acc_no: Optional learner filter
            grade: Optional grade filter
            
        Returns:
            List of attendance records
        """
        conditions = ["date >= ?", "date <= ?"]
        params = [start_date.isoformat(), end_date.isoformat()]
        
        if learner_acc_no:
            conditions.append("learner_acc_no = ?")
            params.append(learner_acc_no)
        
        if grade:
            conditions.append("grade = ?")
            params.append(grade)
        
        query = f'''
            SELECT * FROM {self.table_name}
            WHERE {' AND '.join(conditions)}
            ORDER BY date, grade, learner_surname, learner_name
        '''
        
        result = self.execute_query(query, tuple(params), fetch_all=True)
        
        if result.success and result.data:
            return [self._row_to_model(row) for row in result.data]
        return []
    
    def find_by_learner(
        self,
        learner_acc_no: str,
        limit: int = 30
    ) -> List[AttendanceRecord]:
        """
        Find recent attendance records for a learner.
        
        Args:
            learner_acc_no: Learner account number
            limit: Maximum records to return
            
        Returns:
            List of attendance records
        """
        query = f'''
            SELECT * FROM {self.table_name}
            WHERE learner_acc_no = ?
            ORDER BY date DESC
            LIMIT ?
        '''
        
        result = self.execute_query(
            query, 
            (learner_acc_no, limit),
            fetch_all=True
        )
        
        if result.success and result.data:
            return [self._row_to_model(row) for row in result.data]
        return []
    
    # ==================== Bulk Operations ====================
    
    def bulk_create(self, records: List[AttendanceRecord]) -> Tuple[int, int]:
        """
        Create multiple attendance records efficiently.
        
        Args:
            records: List of records to create
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        success_count = 0
        failure_count = 0
        
        with self.transaction() as conn:
            cursor = conn.cursor()
            
            for record in records:
                try:
                    data = self._model_to_dict(record)
                    columns = list(data.keys())
                    placeholders = ['?' for _ in columns]
                    
                    query = f'''
                        INSERT OR REPLACE INTO {self.table_name} (
                            {', '.join(columns)}
                        ) VALUES ({', '.join(placeholders)})
                    '''
                    
                    cursor.execute(query, tuple(data.values()))
                    success_count += 1
                except Exception as e:
                    self._logger.error(f"Failed to create record: {e}")
                    failure_count += 1
        
        self._invalidate_cache_pattern(f"{self.table_name}_")
        return success_count, failure_count
    
    def bulk_update_status(
        self,
        attendance_ids: List[int],
        status: AttendanceStatus
    ) -> int:
        """
        Update status for multiple records.
        
        Args:
            attendance_ids: List of record IDs
            status: New status
            
        Returns:
            Number of records updated
        """
        if not attendance_ids:
            return 0
        
        placeholders = ','.join(['?' for _ in attendance_ids])
        query = f'''
            UPDATE {self.table_name}
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE attendance_id IN ({placeholders})
        '''
        
        params = [status.value] + attendance_ids
        result = self.execute_query(query, tuple(params))
        
        if result.success:
            self._invalidate_cache_pattern(f"{self.table_name}_")
            return len(attendance_ids)
        return 0
    
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
            period_start: Start date
            period_end: End date
            
        Returns:
            AttendanceSummary if records exist
        """
        # Get learner info
        learner_query = '''
            SELECT learner_name, learner_surname, grade
            FROM AttendanceRecords
            WHERE learner_acc_no = ?
            LIMIT 1
        '''
        
        learner_result = self.execute_query(
            learner_query,
            (learner_acc_no,),
            fetch_one=True
        )
        
        if not learner_result.success or not learner_result.data:
            return None
        
        learner_info = learner_result.data
        
        # Get statistics
        stats_query = f'''
            SELECT 
                COUNT(*) as total_days,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_days,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent_days,
                SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) as late_days,
                SUM(CASE WHEN status = 'excused' THEN 1 ELSE 0 END) as excused_days
            FROM {self.table_name}
            WHERE learner_acc_no = ? AND date >= ? AND date <= ?
        '''
        
        stats_result = self.execute_query(
            stats_query,
            (learner_acc_no, period_start.isoformat(), period_end.isoformat()),
            fetch_one=True
        )
        
        if not stats_result.success or not stats_result.data:
            return None
        
        stats = stats_result.data
        
        summary = AttendanceSummary(
            learner_acc_no=learner_acc_no,
            learner_name=learner_info[0],
            learner_surname=learner_info[1],
            grade=learner_info[2],
            period_start=period_start,
            period_end=period_end,
            total_days=stats[0] or 0,
            present_days=stats[1] or 0,
            absent_days=stats[2] or 0,
            late_days=stats[3] or 0,
            excused_days=stats[4] or 0
        )
        summary.calculate_attendance_rate()
        
        return summary
    
    def get_grade_summary(
        self,
        grade: int,
        period_start: date,
        period_end: date
    ) -> List[AttendanceSummary]:
        """
        Get attendance summaries for all learners in a grade.
        
        Args:
            grade: Grade number
            period_start: Start date
            period_end: End date
            
        Returns:
            List of AttendanceSummary objects
        """
        # Get unique learners
        learners_query = f'''
            SELECT DISTINCT learner_acc_no, learner_name, learner_surname, grade
            FROM {self.table_name}
            WHERE grade = ? AND date >= ? AND date <= ?
            ORDER BY learner_surname, learner_name
        '''
        
        learners_result = self.execute_query(
            learners_query,
            (grade, period_start.isoformat(), period_end.isoformat()),
            fetch_all=True
        )
        
        if not learners_result.success or not learners_result.data:
            return []
        
        summaries = []
        for learner in learners_result.data:
            summary = self.get_attendance_summary(
                learner[0], period_start, period_end
            )
            if summary:
                summaries.append(summary)
        
        return summaries
    
    # ==================== Payment Integration ====================
    
    def add_payment_feed(self, feed_data: PaymentFeedData) -> int:
        """
        Add a payment to the feed queue.
        
        Args:
            feed_data: Payment feed data
            
        Returns:
            Feed ID
        """
        query = '''
            INSERT INTO AttendancePaymentFeed (
                learner_acc_no, learner_name, learner_surname, amount,
                payment_date, source_document, source_type, reference_number,
                notes, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        '''
        
        params = (
            feed_data.learner_acc_no,
            feed_data.learner_name,
            feed_data.learner_surname,
            feed_data.amount,
            feed_data.payment_date.isoformat() if feed_data.payment_date else None,
            feed_data.source_document,
            feed_data.source_type,
            feed_data.reference_number,
            feed_data.notes
        )
        
        result = self.execute_query(query, params)
        
        if result.success:
            return result.data if result.data else self._get_last_insert_id()
        else:
            raise RuntimeError(f"Failed to add payment feed: {result.error}")
    
    def get_pending_payment_feeds(self) -> List[PaymentFeedData]:
        """
        Get all pending payment feeds.
        
        Returns:
            List of pending PaymentFeedData
        """
        query = '''
            SELECT * FROM AttendancePaymentFeed
            WHERE status = 'pending'
            ORDER BY created_at
        '''
        
        result = self.execute_query(query, fetch_all=True)
        
        if result.success and result.data:
            feeds = []
            for row in result.data:
                if isinstance(row, sqlite3.Row):
                    row = dict(row)
                feeds.append(PaymentFeedData(
                    feed_id=row.get('feed_id'),
                    learner_acc_no=row.get('learner_acc_no', ''),
                    learner_name=row.get('learner_name', ''),
                    learner_surname=row.get('learner_surname', ''),
                    amount=row.get('amount', 0.0),
                    payment_date=date.fromisoformat(row['payment_date']) if row.get('payment_date') else None,
                    source_document=row.get('source_document'),
                    source_type=row.get('source_type', 'attendance_ocr'),
                    reference_number=row.get('reference_number'),
                    notes=row.get('notes'),
                    status=row.get('status', 'pending')
                ))
            return feeds
        return []
    
    def mark_payment_feed_sent(self, feed_id: int) -> bool:
        """Mark a payment feed as sent."""
        query = '''
            UPDATE AttendancePaymentFeed
            SET status = 'sent', processed_at = CURRENT_TIMESTAMP
            WHERE feed_id = ?
        '''
        
        result = self.execute_query(query, (feed_id,))
        return result.success
    
    def mark_payment_feed_failed(self, feed_id: int, error_message: str) -> bool:
        """Mark a payment feed as failed."""
        query = '''
            UPDATE AttendancePaymentFeed
            SET status = 'failed', error_message = ?
            WHERE feed_id = ?
        '''
        
        result = self.execute_query(query, (error_message, feed_id))
        return result.success
    
    # ==================== Cross-System Queries ====================
    
    def get_learners_without_attendance(
        self,
        record_date: date,
        grade: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get learners who don't have attendance recorded for a date.
        
        This queries the Learners table from the payment system.
        
        Args:
            record_date: Date to check
            grade: Optional grade filter
            
        Returns:
            List of learner dictionaries
        """
        if grade:
            query = '''
                SELECT s.acc_no, s.name, s.surname, s.grade
                FROM Learners s
                WHERE s.is_active = 1 AND s.grade = ?
                AND s.acc_no NOT IN (
                    SELECT learner_acc_no FROM AttendanceRecords WHERE date = ?
                )
                ORDER BY s.surname, s.name
            '''
            params = (grade, record_date.isoformat())
        else:
            query = '''
                SELECT s.acc_no, s.name, s.surname, s.grade
                FROM Learners s
                WHERE s.is_active = 1
                AND s.acc_no NOT IN (
                    SELECT learner_acc_no FROM AttendanceRecords WHERE date = ?
                )
                ORDER BY s.grade, s.surname, s.name
            '''
            params = (record_date.isoformat(),)
        
        result = self.execute_query(query, params, fetch_all=True)
        
        if result.success and result.data:
            return [
                {
                    'acc_no': row[0],
                    'name': row[1],
                    'surname': row[2],
                    'grade': row[3]
                }
                for row in result.data
            ]
        return []
    
    def get_attendance_with_payment_info(
        self,
        learner_acc_no: str,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get attendance records with payment information.
        
        Args:
            learner_acc_no: Learner account number
            limit: Maximum records to return
            
        Returns:
            List of attendance records with payment data
        """
        query = f'''
            SELECT 
                ar.*,
                p.amount as payment_amount,
                p.date as payment_date,
                p.notes as payment_notes
            FROM {self.table_name} ar
            LEFT JOIN Payments p ON ar.learner_acc_no = p.learner_id 
                AND ar.date = p.date
            WHERE ar.learner_acc_no = ?
            ORDER BY ar.date DESC
            LIMIT ?
        '''
        
        result = self.execute_query(
            query,
            (learner_acc_no, limit),
            fetch_all=True
        )
        
        if result.success and result.data:
            records = []
            for row in result.data:
                if isinstance(row, sqlite3.Row):
                    row = dict(row)
                record = self._row_to_model(row)
                record_dict = record.to_dict()
                record_dict['payment_amount'] = row.get('payment_amount')
                record_dict['payment_date'] = row.get('payment_date')
                record_dict['payment_notes'] = row.get('payment_notes')
                records.append(record_dict)
            return records
        return []
    
    # ==================== Statistics ====================
    
    def get_daily_statistics(self, record_date: date) -> Dict[str, Any]:
        """
        Get attendance statistics for a specific date.
        
        Args:
            record_date: Date to analyze
            
        Returns:
            Dictionary with statistics
        """
        query = f'''
            SELECT 
                grade,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent,
                SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) as late,
                SUM(CASE WHEN status = 'excused' THEN 1 ELSE 0 END) as excused
            FROM {self.table_name}
            WHERE date = ?
            GROUP BY grade
            ORDER BY grade
        '''
        
        result = self.execute_query(
            query,
            (record_date.isoformat(),),
            fetch_all=True
        )
        
        stats = {
            'date': record_date.isoformat(),
            'by_grade': {},
            'total_records': 0,
            'total_present': 0,
            'total_absent': 0,
            'total_late': 0,
            'total_excused': 0
        }
        
        if result.success and result.data:
            for row in result.data:
                grade = row[0]
                grade_stats = {
                    'total': row[1],
                    'present': row[2],
                    'absent': row[3],
                    'late': row[4],
                    'excused': row[5]
                }
                stats['by_grade'][grade] = grade_stats
                stats['total_records'] += row[1]
                stats['total_present'] += row[2] or 0
                stats['total_absent'] += row[3] or 0
                stats['total_late'] += row[4] or 0
                stats['total_excused'] += row[5] or 0
        
        return stats
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get overall database statistics."""
        stats = {}
        
        # Total records
        result = self.execute_query(
            f"SELECT COUNT(*) FROM {self.table_name}",
            fetch_one=True
        )
        stats['total_records'] = result.data[0] if result.success and result.data else 0
        
        # Records by status
        result = self.execute_query(
            f"SELECT status, COUNT(*) FROM {self.table_name} GROUP BY status",
            fetch_all=True
        )
        stats['by_status'] = {row[0]: row[1] for row in result.data} if result.success and result.data else {}
        
        # Pending payment feeds
        result = self.execute_query(
            "SELECT COUNT(*) FROM AttendancePaymentFeed WHERE status = 'pending'",
            fetch_one=True
        )
        stats['pending_payment_feeds'] = result.data[0] if result.success and result.data else 0
        
        # Date range
        result = self.execute_query(
            f"SELECT MIN(date), MAX(date) FROM {self.table_name}",
            fetch_one=True
        )
        if result.success and result.data:
            stats['date_range'] = {
                'earliest': result.data[0],
                'latest': result.data[1]
            }
        
        return stats