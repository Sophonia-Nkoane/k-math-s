"""
Attendance System Main Module

This is the main entry point for the decoupled attendance system.
It provides a unified interface for attendance management while
maintaining integration with the payment system.
"""

import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional
import os
import sys

# Add src to path for payment system integration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from attendance_models.attendance_models import (
    AttendanceRecord, AttendanceSummary, AttendanceFilter,
    OCRResult, PaymentFeedData, AttendanceStatus, PaymentFeedStatus
)
from attendance_database import AttendanceDatabase
from attendance_ocr_processor import AttendanceOCRProcessor, create_ocr_processor_from_payment_db
from payment_integration import PaymentIntegrationService, PaymentFeedResult


class AttendanceSystem:
    """
    Main attendance system class.
    
    This class provides a unified interface for all attendance operations,
    acting as a facade for the underlying components.
    
    Features:
    - Attendance recording and management
    - OCR document processing
    - Payment data integration with payment system
    - Reporting and summaries
    """
    
    def __init__(
        self,
        attendance_db_path: str = "attendance_system/attendance.db",
        payment_db_manager=None,
        notification_service=None
    ):
        """
        Initialize the attendance system.
        
        Args:
            attendance_db_path: Path to the attendance database
            payment_db_manager: Optional payment system database manager for integration
            notification_service: Optional notification service for payment emails
        """
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.db = AttendanceDatabase(db_path=attendance_db_path)
        self.payment_db_manager = payment_db_manager
        self.notification_service = notification_service
        
        # Initialize OCR processor
        if payment_db_manager:
            self.ocr_processor = create_ocr_processor_from_payment_db(payment_db_manager)
        else:
            self.ocr_processor = AttendanceOCRProcessor()
        
        # Initialize payment integration
        self.payment_integration = PaymentIntegrationService(
            attendance_db=self.db,
            payment_db_manager=payment_db_manager,
            notification_service=notification_service
        )
        
        self.logger.info("Attendance system initialized")
    
    # ==================== Attendance Recording ====================
    
    def record_attendance(
        self,
        learner_acc_no: str,
        learner_name: str,
        learner_surname: str,
        grade: int,
        record_date: date,
        status: AttendanceStatus = AttendanceStatus.PRESENT,
        signature_image: bytes = None,
        notes: str = None,
        recorded_by: str = None
    ) -> int:
        """
        Record attendance for a learner.
        
        Args:
            learner_acc_no: Learner account number
            learner_name: Learner first name
            learner_surname: Learner surname
            grade: Learner grade
            record_date: Date of attendance
            status: Attendance status (present, absent, late, excused)
            signature_image: Optional signature image bytes
            notes: Optional notes
            recorded_by: Username of person recording
            
        Returns:
            ID of the created attendance record
        """
        record = AttendanceRecord(
            learner_acc_no=learner_acc_no,
            learner_name=learner_name,
            learner_surname=learner_surname,
            grade=grade,
            date=record_date,
            status=status,
            signature_image=signature_image,
            notes=notes,
            recorded_by=recorded_by
        )
        
        return self.db.create_attendance_record(record)
    
    def record_bulk_attendance(
        self,
        records: List[Dict[str, Any]]
    ) -> tuple:
        """
        Record attendance for multiple learners.
        
        Args:
            records: List of attendance record dictionaries
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        attendance_records = []
        
        for r in records:
            record = AttendanceRecord(
                learner_acc_no=r.get('learner_acc_no', ''),
                learner_name=r.get('learner_name', ''),
                learner_surname=r.get('learner_surname', ''),
                grade=r.get('grade', 1),
                date=r.get('date', date.today()),
                status=AttendanceStatus(r.get('status', 'present')),
                signature_image=r.get('signature_image'),
                notes=r.get('notes'),
                recorded_by=r.get('recorded_by')
            )
            attendance_records.append(record)
        
        return self.db.bulk_create_attendance_records(attendance_records)
    
    def update_attendance(
        self,
        attendance_id: int,
        status: AttendanceStatus = None,
        notes: str = None
    ) -> bool:
        """
        Update an existing attendance record.
        
        Args:
            attendance_id: ID of the attendance record
            status: New status (optional)
            notes: New notes (optional)
            
        Returns:
            True if update successful
        """
        record = self.db.get_attendance_record(attendance_id)
        if not record:
            return False
        
        if status:
            record.status = status
        if notes:
            record.notes = notes
        
        return self.db.update_attendance_record(record)
    
    def get_attendance(
        self,
        learner_acc_no: str = None,
        grade: int = None,
        date_from: date = None,
        date_to: date = None,
        status: AttendanceStatus = None
    ) -> List[AttendanceRecord]:
        """
        Get attendance records with optional filtering.
        
        Args:
            learner_acc_no: Filter by learner account number
            grade: Filter by grade
            date_from: Filter from date
            date_to: Filter to date
            status: Filter by status
            
        Returns:
            List of matching attendance records
        """
        filter_criteria = AttendanceFilter(
            learner_acc_no=learner_acc_no,
            grade=grade,
            date_from=date_from,
            date_to=date_to,
            status=status
        )
        
        return self.db.query_attendance_records(filter_criteria=filter_criteria)
    
    def get_attendance_for_date(
        self,
        record_date: date,
        grade: int = None
    ) -> List[AttendanceRecord]:
        """
        Get all attendance records for a specific date.
        
        Args:
            record_date: The date to get attendance for
            grade: Optional grade filter
            
        Returns:
            List of attendance records
        """
        return self.get_attendance(
            date_from=record_date,
            date_to=record_date,
            grade=grade
        )
    
    # ==================== OCR Processing ====================
    
    def process_attendance_document(
        self,
        file_path: str,
        extract_payments: bool = True,
        auto_record: bool = True
    ) -> Dict[str, Any]:
        """
        Process an attendance document (PDF or image) using OCR.
        
        Args:
            file_path: Path to the document
            extract_payments: Whether to extract payment data
            auto_record: Whether to automatically record attendance
            
        Returns:
            Dictionary with processing results
        """
        result = {
            'success': False,
            'ocr_results': [],
            'attendance_recorded': 0,
            'payments_detected': 0,
            'payments_fed': 0,
            'errors': []
        }
        
        try:
            # Process document with OCR
            ocr_results = self.ocr_processor.process_document(
                file_path, extract_payments
            )
            
            result['ocr_results'] = [r.to_dict() for r in ocr_results]
            
            if auto_record:
                # Convert OCR results to attendance records
                records = [r.to_attendance_record() for r in ocr_results if r.success]
                
                if records:
                    success_count, failure_count = self.db.bulk_create_attendance_records(records)
                    result['attendance_recorded'] = success_count
                    
                    if failure_count > 0:
                        result['errors'].append(f"Failed to record {failure_count} attendance records")
            
            # Process payments if detected
            if extract_payments:
                for ocr_result in ocr_results:
                    if ocr_result.payment_amount and ocr_result.payment_amount > 0:
                        result['payments_detected'] += 1
                        
                        feed_result = self.payment_integration.process_ocr_result(ocr_result)
                        if feed_result and feed_result.success:
                            result['payments_fed'] += 1
            
            result['success'] = True
            
        except Exception as e:
            result['errors'].append(str(e))
            self.logger.error(f"Error processing attendance document: {e}")
        
        return result
    
    def update_learner_list(self, learner_list: List[Dict[str, Any]]):
        """
        Update the learner list used for OCR matching.
        
        Args:
            learner_list: List of learner dictionaries with acc_no, name, surname, grade
        """
        self.ocr_processor.update_learner_list(learner_list)
    
    def refresh_learner_list_from_payment_db(self):
        """Refresh the learner list from the payment system database."""
        if self.payment_db_manager:
            self.ocr_processor = create_ocr_processor_from_payment_db(self.payment_db_manager)
            self.logger.info("Learner list refreshed from payment database")
    
    # ==================== Reporting ====================
    
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
            AttendanceSummary or None
        """
        return self.db.get_attendance_summary(learner_acc_no, period_start, period_end)
    
    def get_grade_attendance_report(
        self,
        grade: int,
        date_from: date,
        date_to: date
    ) -> Dict[str, Any]:
        """
        Generate an attendance report for a grade.
        
        Args:
            grade: Grade number
            date_from: Start date
            date_to: End date
            
        Returns:
            Dictionary with report data
        """
        records = self.get_attendance(
            grade=grade,
            date_from=date_from,
            date_to=date_to
        )
        
        # Group by learner
        learner_summaries = {}
        for record in records:
            acc_no = record.learner_acc_no
            if acc_no not in learner_summaries:
                learner_summaries[acc_no] = {
                    'learner_acc_no': acc_no,
                    'learner_name': record.learner_name,
                    'learner_surname': record.learner_surname,
                    'grade': record.grade,
                    'total_days': 0,
                    'present_days': 0,
                    'absent_days': 0,
                    'late_days': 0,
                    'excused_days': 0
                }
            
            summary = learner_summaries[acc_no]
            summary['total_days'] += 1
            
            if record.status == AttendanceStatus.PRESENT:
                summary['present_days'] += 1
            elif record.status == AttendanceStatus.ABSENT:
                summary['absent_days'] += 1
            elif record.status == AttendanceStatus.LATE:
                summary['late_days'] += 1
            elif record.status == AttendanceStatus.EXCUSED:
                summary['excused_days'] += 1
        
        # Calculate attendance rates
        for summary in learner_summaries.values():
            if summary['total_days'] > 0:
                summary['attendance_rate'] = (summary['present_days'] / summary['total_days']) * 100
            else:
                summary['attendance_rate'] = 0
        
        return {
            'grade': grade,
            'period_start': date_from.isoformat(),
            'period_end': date_to.isoformat(),
            'total_records': len(records),
            'unique_learners': len(learner_summaries),
            'learners': list(learner_summaries.values())
        }
    
    def get_daily_attendance_report(self, report_date: date) -> Dict[str, Any]:
        """
        Generate a daily attendance report.
        
        Args:
            report_date: Date to generate report for
            
        Returns:
            Dictionary with daily report data
        """
        records = self.get_attendance_for_date(report_date)
        
        # Group by grade
        by_grade = {}
        for record in records:
            grade = record.grade
            if grade not in by_grade:
                by_grade[grade] = {
                    'grade': grade,
                    'total': 0,
                    'present': 0,
                    'absent': 0,
                    'late': 0,
                    'excused': 0
                }
            
            by_grade[grade]['total'] += 1
            by_grade[grade][record.status.value] += 1
        
        return {
            'date': report_date.isoformat(),
            'total_records': len(records),
            'by_grade': by_grade,
            'records': [r.to_dict() for r in records]
        }
    
    # ==================== Payment Integration ====================
    
    def get_pending_payment_feeds(self) -> List[Dict[str, Any]]:
        """Get all pending payment feeds waiting to be processed."""
        return self.db.get_pending_payment_feeds()
    
    def process_pending_payment_feeds(self) -> Dict[str, Any]:
        """Process all pending payment feeds."""
        return self.payment_integration.process_pending_feeds()
    
    def get_payment_feed_stats(self) -> Dict[str, Any]:
        """Get statistics about payment feeds."""
        stats = self.db.get_database_stats()
        return {
            'pending_payment_feeds': stats.get('pending_payment_feeds', 0)
        }
    
    # ==================== System Operations ====================
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get overall system statistics."""
        return self.db.get_database_stats()
    
    def sync_with_payment_system(self) -> Dict[str, Any]:
        """
        Synchronize data with the payment system.
        
        This method:
        1. Refreshes the learner list from payment DB
        2. Processes any pending payment feeds
        
        Returns:
            Dictionary with sync results
        """
        result = {
            'learners_refreshed': False,
            'payment_feeds_processed': None
        }
        
        # Refresh learner list
        try:
            self.refresh_learner_list_from_payment_db()
            result['learners_refreshed'] = True
        except Exception as e:
            self.logger.error(f"Error refreshing learners: {e}")
        
        # Process pending payment feeds
        result['payment_feeds_processed'] = self.process_pending_payment_feeds()
        
        return result


# ==================== Factory Functions ====================

def create_attendance_system(
    payment_db_manager=None,
    notification_service=None,
    attendance_db_path: str = "attendance_system/attendance.db"
) -> AttendanceSystem:
    """
    Create and configure an attendance system instance.
    
    Args:
        payment_db_manager: Optional payment system database manager
        notification_service: Optional notification service
        attendance_db_path: Path to attendance database
        
    Returns:
        Configured AttendanceSystem instance
    """
    return AttendanceSystem(
        attendance_db_path=attendance_db_path,
        payment_db_manager=payment_db_manager,
        notification_service=notification_service
    )


def create_standalone_attendance_system(
    attendance_db_path: str = "attendance_system/attendance.db"
) -> AttendanceSystem:
    """
    Create a standalone attendance system without payment integration.
    
    Args:
        attendance_db_path: Path to attendance database
        
    Returns:
        Standalone AttendanceSystem instance
    """
    return AttendanceSystem(attendance_db_path=attendance_db_path)


# ==================== CLI Entry Point ====================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Attendance System")
    parser.add_argument('--stats', action='store_true', help='Show system statistics')
    parser.add_argument('--process-feeds', action='store_true', help='Process pending payment feeds')
    parser.add_argument('--process-document', type=str, help='Process an attendance document')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create standalone system
    system = create_standalone_attendance_system()
    
    if args.stats:
        stats = system.get_system_stats()
        print("\n=== Attendance System Statistics ===")
        for key, value in stats.items():
            print(f"{key}: {value}")
    
    if args.process_feeds:
        result = system.process_pending_payment_feeds()
        print("\n=== Payment Feed Processing ===")
        print(f"Total pending: {result['total_pending']}")
        print(f"Processed: {result['processed']}")
        print(f"Failed: {result['failed']}")
    
    if args.process_document:
        result = system.process_attendance_document(args.process_document)
        print("\n=== Document Processing Result ===")
        print(f"Success: {result['success']}")
        print(f"Attendance recorded: {result['attendance_recorded']}")
        print(f"Payments detected: {result['payments_detected']}")
        print(f"Payments fed: {result['payments_fed']}")
        if result['errors']:
            print(f"Errors: {result['errors']}")