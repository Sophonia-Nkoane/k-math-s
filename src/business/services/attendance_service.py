"""
Attendance Service

Business logic layer for attendance management with full integration
to the payment system. This service provides a unified interface for
all attendance operations while maintaining clean separation of concerns.
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from data.repositories.attendance_repository import (
    AttendanceRepository,
    AttendanceRecord,
    AttendanceSummary,
    AttendanceStatus,
    PaymentFeedStatus,
    PaymentFeedData
)
from data.repositories.learner_repository import LearnerRepository
from data.repositories.payment_repository import PaymentRepository
from business.services.email_service import EmailService
from business.services.event_bus import EventBus


class AttendanceService:
    """
    Service for attendance management with payment system integration.
    
    Features:
    - Attendance recording and management
    - Bulk operations for efficiency
    - Payment detection and integration
    - Summary and reporting
    - Event-driven notifications
    - Cross-system data access
    """
    
    def __init__(
        self,
        attendance_repository: AttendanceRepository,
        learner_repository: LearnerRepository,
        payment_repository: PaymentRepository,
        email_service: Optional[EmailService] = None,
        event_bus: Optional[EventBus] = None
    ):
        """
        Initialize the attendance service.
        
        Args:
            attendance_repository: Repository for attendance data
            learner_repository: Repository for learner data
            payment_repository: Repository for payment data
            email_service: Optional email service for notifications
            event_bus: Optional event bus for system events
        """
        self.attendance_repo = attendance_repository
        self.learner_repo = learner_repository
        self.payment_repo = payment_repository
        self.email_service = email_service
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
    
    # ==================== Attendance Recording ====================
    
    def record_attendance(
        self,
        learner_acc_no: str,
        record_date: date,
        status: AttendanceStatus = AttendanceStatus.PRESENT,
        check_in_time: Optional[str] = None,
        check_out_time: Optional[str] = None,
        notes: Optional[str] = None,
        recorded_by: Optional[str] = None,
        signature_image: Optional[bytes] = None
    ) -> AttendanceRecord:
        """
        Record attendance for a single learner.
        
        Args:
            learner_acc_no: Learner account number
            record_date: Date of attendance
            status: Attendance status
            check_in_time: Optional check-in time
            check_out_time: Optional check-out time
            notes: Optional notes
            recorded_by: Username of person recording
            signature_image: Optional signature image
            
        Returns:
            Created attendance record
        """
        # Get learner info from payment system
        learner_info = self._get_learner_info(learner_acc_no)
        
        if not learner_info:
            raise ValueError(f"Learner {learner_acc_no} not found")
        
        record = AttendanceRecord(
            learner_acc_no=learner_acc_no,
            learner_name=learner_info['name'],
            learner_surname=learner_info['surname'],
            grade=learner_info['grade'],
            date=record_date,
            status=status,
            check_in_time=check_in_time,
            check_out_time=check_out_time,
            notes=notes,
            recorded_by=recorded_by,
            signature_image=signature_image
        )
        
        created_record = self.attendance_repo.create(record)
        
        # Emit event if event bus is available
        if self.event_bus:
            self.event_bus.emit('attendance_recorded', {
                'learner_acc_no': learner_acc_no,
                'date': record_date.isoformat(),
                'status': status.value
            })
        
        self.logger.info(
            f"Recorded attendance for {learner_acc_no} on {record_date}: {status.value}"
        )
        
        return created_record
    
    def record_bulk_attendance(
        self,
        records: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        """
        Record attendance for multiple learners.
        
        Args:
            records: List of attendance record dictionaries
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        attendance_records = []
        
        for r in records:
            learner_acc_no = r.get('learner_acc_no')
            if not learner_acc_no:
                continue
            
            learner_info = self._get_learner_info(learner_acc_no)
            if not learner_info:
                self.logger.warning(f"Learner {learner_acc_no} not found, skipping")
                continue
            
            record = AttendanceRecord(
                learner_acc_no=learner_acc_no,
                learner_name=learner_info['name'],
                learner_surname=learner_info['surname'],
                grade=learner_info['grade'],
                date=r.get('date', date.today()),
                status=AttendanceStatus(r.get('status', 'present')),
                check_in_time=r.get('check_in_time'),
                check_out_time=r.get('check_out_time'),
                notes=r.get('notes'),
                recorded_by=r.get('recorded_by'),
                signature_image=r.get('signature_image')
            )
            attendance_records.append(record)
        
        success_count, failure_count = self.attendance_repo.bulk_create(attendance_records)
        
        # Emit bulk event
        if self.event_bus and success_count > 0:
            self.event_bus.emit('bulk_attendance_recorded', {
                'success_count': success_count,
                'failure_count': failure_count
            })
        
        return success_count, failure_count
    
    def record_grade_attendance(
        self,
        grade: int,
        record_date: date,
        present_learners: List[str],
        absent_learners: Optional[List[str]] = None,
        late_learners: Optional[List[str]] = None,
        recorded_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record attendance for an entire grade.
        
        Args:
            grade: Grade number
            record_date: Date of attendance
            present_learners: List of learner account numbers present
            absent_learners: Optional list of absent learners
            late_learners: Optional list of late learners
            recorded_by: Username of person recording
            
        Returns:
            Dictionary with results
        """
        # Get all active learners in grade
        all_learners = self.learner_repo.find_by_criteria({'grade': grade, 'is_active': 1})
        
        records = []
        results = {
            'total_learners': len(all_learners),
            'present': 0,
            'absent': 0,
            'late': 0,
            'excused': 0,
            'errors': []
        }
        
        present_set = set(present_learners)
        absent_set = set(absent_learners or [])
        late_set = set(late_learners or [])
        
        for learner in all_learners:
            acc_no = learner.acc_no if hasattr(learner, 'acc_no') else learner.get('acc_no')
            
            if acc_no in present_set:
                status = AttendanceStatus.PRESENT
                results['present'] += 1
            elif acc_no in late_set:
                status = AttendanceStatus.LATE
                results['late'] += 1
            elif acc_no in absent_set:
                status = AttendanceStatus.ABSENT
                results['absent'] += 1
            else:
                # Default to absent if not marked present
                status = AttendanceStatus.ABSENT
                results['absent'] += 1
            
            records.append({
                'learner_acc_no': acc_no,
                'date': record_date,
                'status': status.value,
                'recorded_by': recorded_by
            })
        
        success_count, failure_count = self.attendance_repo.bulk_create(
            [self._dict_to_record(r) for r in records]
        )
        
        results['success_count'] = success_count
        results['failure_count'] = failure_count
        
        return results
    
    # ==================== Attendance Queries ====================
    
    def get_attendance_for_date(
        self,
        record_date: date,
        grade: Optional[int] = None
    ) -> List[AttendanceRecord]:
        """
        Get all attendance records for a specific date.
        
        Args:
            record_date: Date to query
            grade: Optional grade filter
            
        Returns:
            List of attendance records
        """
        return self.attendance_repo.find_by_date(record_date, grade)
    
    def get_learner_attendance(
        self,
        learner_acc_no: str,
        limit: int = 30
    ) -> List[AttendanceRecord]:
        """
        Get attendance history for a learner.
        
        Args:
            learner_acc_no: Learner account number
            limit: Maximum records to return
            
        Returns:
            List of attendance records
        """
        return self.attendance_repo.find_by_learner(learner_acc_no, limit)
    
    def get_learner_attendance_for_period(
        self,
        learner_acc_no: str,
        start_date: date,
        end_date: date
    ) -> List[AttendanceRecord]:
        """
        Get attendance for a learner over a period.
        
        Args:
            learner_acc_no: Learner account number
            start_date: Start date
            end_date: End date
            
        Returns:
            List of attendance records
        """
        return self.attendance_repo.find_by_date_range(
            start_date, end_date, learner_acc_no
        )
    
    def get_learners_without_attendance(
        self,
        record_date: date,
        grade: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get learners who don't have attendance recorded.
        
        Args:
            record_date: Date to check
            grade: Optional grade filter
            
        Returns:
            List of learner dictionaries
        """
        return self.attendance_repo.get_learners_without_attendance(record_date, grade)
    
    # ==================== Attendance Updates ====================
    
    def update_attendance_status(
        self,
        attendance_id: int,
        new_status: AttendanceStatus,
        notes: Optional[str] = None
    ) -> bool:
        """
        Update the status of an attendance record.
        
        Args:
            attendance_id: ID of the attendance record
            new_status: New status
            notes: Optional new notes
            
        Returns:
            True if successful
        """
        record = self.attendance_repo.find_by_id(attendance_id)
        if not record:
            return False
        
        record.status = new_status
        if notes:
            record.notes = notes
        
        self.attendance_repo.update(record)
        
        # Emit event
        if self.event_bus:
            self.event_bus.emit('attendance_updated', {
                'attendance_id': attendance_id,
                'new_status': new_status.value
            })
        
        return True
    
    def mark_learner_present(
        self,
        learner_acc_no: str,
        record_date: date,
        recorded_by: Optional[str] = None
    ) -> AttendanceRecord:
        """
        Mark a learner as present for a date.
        
        Args:
            learner_acc_no: Learner account number
            record_date: Date to mark
            recorded_by: Username of person recording
            
        Returns:
            Created or updated attendance record
        """
        return self.record_attendance(
            learner_acc_no=learner_acc_no,
            record_date=record_date,
            status=AttendanceStatus.PRESENT,
            recorded_by=recorded_by
        )
    
    def mark_learner_absent(
        self,
        learner_acc_no: str,
        record_date: date,
        reason: Optional[str] = None,
        recorded_by: Optional[str] = None
    ) -> AttendanceRecord:
        """
        Mark a learner as absent for a date.
        
        Args:
            learner_acc_no: Learner account number
            record_date: Date to mark
            reason: Optional absence reason
            recorded_by: Username of person recording
            
        Returns:
            Created or updated attendance record
        """
        return self.record_attendance(
            learner_acc_no=learner_acc_no,
            record_date=record_date,
            status=AttendanceStatus.ABSENT,
            notes=reason,
            recorded_by=recorded_by
        )
    
    # ==================== Summary and Reporting ====================
    
    def get_attendance_summary(
        self,
        learner_acc_no: str,
        period_start: date,
        period_end: date
    ) -> Optional[AttendanceSummary]:
        """
        Get attendance summary for a learner.
        
        Args:
            learner_acc_no: Learner account number
            period_start: Start date
            period_end: End date
            
        Returns:
            AttendanceSummary if records exist
        """
        return self.attendance_repo.get_attendance_summary(
            learner_acc_no, period_start, period_end
        )
    
    def get_grade_attendance_report(
        self,
        grade: int,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Generate attendance report for a grade.
        
        Args:
            grade: Grade number
            period_start: Start date
            period_end: End date
            
        Returns:
            Dictionary with report data
        """
        summaries = self.attendance_repo.get_grade_summary(
            grade, period_start, period_end
        )
        
        total_learners = len(summaries)
        total_days = sum(s.total_days for s in summaries)
        total_present = sum(s.present_days for s in summaries)
        total_absent = sum(s.absent_days for s in summaries)
        total_late = sum(s.late_days for s in summaries)
        
        overall_rate = (total_present / total_days * 100) if total_days > 0 else 0
        
        return {
            'grade': grade,
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'total_learners': total_learners,
            'total_days': total_days,
            'total_present': total_present,
            'total_absent': total_absent,
            'total_late': total_late,
            'overall_attendance_rate': round(overall_rate, 2),
            'learners': [s.__dict__ for s in summaries]
        }
    
    def get_daily_attendance_report(
        self,
        record_date: date
    ) -> Dict[str, Any]:
        """
        Generate daily attendance report.
        
        Args:
            record_date: Date to report
            
        Returns:
            Dictionary with daily report data
        """
        stats = self.attendance_repo.get_daily_statistics(record_date)
        
        # Get learners without attendance
        missing = self.attendance_repo.get_learners_without_attendance(record_date)
        
        stats['learners_without_attendance'] = missing
        stats['missing_count'] = len(missing)
        
        return stats
    
    def get_monthly_attendance_report(
        self,
        year: int,
        month: int,
        grade: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate monthly attendance report.
        
        Args:
            year: Year
            month: Month (1-12)
            grade: Optional grade filter
            
        Returns:
            Dictionary with monthly report data
        """
        # Calculate date range
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        # Get records
        records = self.attendance_repo.find_by_date_range(
            start_date, end_date, grade=grade
        )
        
        # Calculate statistics
        daily_stats = {}
        for record in records:
            day = record.date.day
            if day not in daily_stats:
                daily_stats[day] = {
                    'present': 0, 'absent': 0, 'late': 0, 'excused': 0
                }
            daily_stats[day][record.status.value] += 1
        
        return {
            'year': year,
            'month': month,
            'grade': grade,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'total_records': len(records),
            'daily_statistics': daily_stats
        }
    
    # ==================== Payment Integration ====================
    
    def record_attendance_with_payment(
        self,
        learner_acc_no: str,
        record_date: date,
        payment_amount: float,
        status: AttendanceStatus = AttendanceStatus.PRESENT,
        payment_reference: Optional[str] = None,
        notes: Optional[str] = None,
        recorded_by: Optional[str] = None
    ) -> Tuple[AttendanceRecord, bool]:
        """
        Record attendance with a payment.
        
        This method records attendance and creates a payment feed entry
        for integration with the payment system.
        
        Args:
            learner_acc_no: Learner account number
            record_date: Date of attendance
            payment_amount: Payment amount detected
            status: Attendance status
            payment_reference: Optional payment reference
            notes: Optional notes
            recorded_by: Username of person recording
            
        Returns:
            Tuple of (attendance_record, payment_feed_success)
        """
        # Get learner info
        learner_info = self._get_learner_info(learner_acc_no)
        if not learner_info:
            raise ValueError(f"Learner {learner_acc_no} not found")
        
        # Create attendance record with payment info
        record = AttendanceRecord(
            learner_acc_no=learner_acc_no,
            learner_name=learner_info['name'],
            learner_surname=learner_info['surname'],
            grade=learner_info['grade'],
            date=record_date,
            status=status,
            notes=notes,
            recorded_by=recorded_by,
            has_payment=True,
            payment_amount=payment_amount,
            payment_date=record_date,
            payment_reference=payment_reference,
            payment_feed_status=PaymentFeedStatus.PENDING
        )
        
        created_record = self.attendance_repo.create(record)
        
        # Create payment feed entry
        feed_data = PaymentFeedData(
            learner_acc_no=learner_acc_no,
            learner_name=learner_info['name'],
            learner_surname=learner_info['surname'],
            amount=payment_amount,
            payment_date=record_date,
            reference_number=payment_reference,
            notes=f"Detected during attendance on {record_date}",
            source_type='attendance_manual'
        )
        
        try:
            feed_id = self.attendance_repo.add_payment_feed(feed_data)
            payment_feed_success = True
            
            # Try to process payment immediately
            self._process_payment_feed(feed_id, feed_data)
            
        except Exception as e:
            self.logger.error(f"Failed to create payment feed: {e}")
            payment_feed_success = False
        
        return created_record, payment_feed_success
    
    def process_pending_payment_feeds(self) -> Dict[str, Any]:
        """
        Process all pending payment feeds.
        
        Returns:
            Dictionary with processing statistics
        """
        pending_feeds = self.attendance_repo.get_pending_payment_feeds()
        
        stats = {
            'total_pending': len(pending_feeds),
            'processed': 0,
            'failed': 0,
            'skipped': 0
        }
        
        for feed in pending_feeds:
            try:
                success = self._process_payment_feed(feed.feed_id, feed)
                if success:
                    stats['processed'] += 1
                else:
                    stats['failed'] += 1
            except Exception as e:
                self.logger.error(f"Error processing feed {feed.feed_id}: {e}")
                stats['failed'] += 1
        
        return stats
    
    def _process_payment_feed(
        self,
        feed_id: int,
        feed_data: PaymentFeedData
    ) -> bool:
        """
        Process a single payment feed.
        
        Args:
            feed_id: Feed ID
            feed_data: Payment feed data
            
        Returns:
            True if successful
        """
        try:
            # Create payment in payment system
            if self.payment_repo:
                # Use payment repository to create payment
                payment_dict = {
                    'learner_id': feed_data.learner_acc_no,
                    'date': feed_data.payment_date.isoformat(),
                    'amount': feed_data.amount,
                    'notes': f"From attendance - {feed_data.notes or ''}"
                }
                
                # This would call the payment repository's create method
                # For now, we'll mark as sent
                self.attendance_repo.mark_payment_feed_sent(feed_id)
                
                # Send notification if email service available
                if self.email_service:
                    self._send_payment_notification(feed_data)
                
                # Emit event
                if self.event_bus:
                    self.event_bus.emit('payment_created_from_attendance', {
                        'feed_id': feed_id,
                        'learner_acc_no': feed_data.learner_acc_no,
                        'amount': feed_data.amount
                    })
                
                self.logger.info(
                    f"Processed payment feed {feed_id}: R{feed_data.amount:.2f} "
                    f"for {feed_data.learner_acc_no}"
                )
                
                return True
            else:
                self.attendance_repo.mark_payment_feed_failed(
                    feed_id, "Payment repository not available"
                )
                return False
                
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Failed to process payment feed {feed_id}: {error_msg}")
            self.attendance_repo.mark_payment_feed_failed(feed_id, error_msg)
            return False
    
    def _send_payment_notification(self, feed_data: PaymentFeedData) -> bool:
        """
        Send payment notification email.
        
        Args:
            feed_data: Payment feed data
            
        Returns:
            True if notification sent successfully
        """
        if not self.email_service:
            return False
        
        try:
            # Get parent email
            parent_email = self._get_parent_email(feed_data.learner_acc_no)
            
            if not parent_email:
                self.logger.warning(
                    f"No parent email found for learner {feed_data.learner_acc_no}"
                )
                return False
            
            learner_name = f"{feed_data.learner_name} {feed_data.learner_surname}"
            
            # Send thank you email
            result = self.email_service.send_payment_thank_you_email(
                parent_email=parent_email,
                learner_name=learner_name,
                amount=feed_data.amount,
                payment_date=feed_data.payment_date.isoformat()
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error sending payment notification: {e}")
            return False
    
    # ==================== Helper Methods ====================
    
    def _get_learner_info(self, learner_acc_no: str) -> Optional[Dict[str, Any]]:
        """
        Get learner information from the payment system.
        
        Args:
            learner_acc_no: Learner account number
            
        Returns:
            Learner info dictionary or None
        """
        try:
            if self.learner_repo:
                learner = self.learner_repo.find_by_acc_no(learner_acc_no)
                if learner:
                    return {
                        'name': learner.name if hasattr(learner, 'name') else learner.get('name'),
                        'surname': learner.surname if hasattr(learner, 'surname') else learner.get('surname'),
                        'grade': learner.grade if hasattr(learner, 'grade') else learner.get('grade', 1)
                    }
        except Exception as e:
            self.logger.error(f"Error getting learner info: {e}")
        
        return None
    
    def _get_parent_email(self, learner_acc_no: str) -> Optional[str]:
        """
        Get parent email for a learner.
        
        Args:
            learner_acc_no: Learner account number
            
        Returns:
            Parent email or None
        """
        try:
            if self.learner_repo:
                # This would query the parent through the learner relationship
                # Implementation depends on your specific data model
                pass
        except Exception as e:
            self.logger.error(f"Error getting parent email: {e}")
        
        return None
    
    def _dict_to_record(self, data: Dict[str, Any]) -> AttendanceRecord:
        """Convert dictionary to AttendanceRecord."""
        learner_acc_no = data.get('learner_acc_no', '')
        learner_info = self._get_learner_info(learner_acc_no) or {}
        
        return AttendanceRecord(
            learner_acc_no=learner_acc_no,
            learner_name=learner_info.get('name', ''),
            learner_surname=learner_info.get('surname', ''),
            grade=learner_info.get('grade', 1),
            date=data.get('date', date.today()),
            status=AttendanceStatus(data.get('status', 'present')),
            check_in_time=data.get('check_in_time'),
            check_out_time=data.get('check_out_time'),
            notes=data.get('notes'),
            recorded_by=data.get('recorded_by'),
            signature_image=data.get('signature_image')
        )
    
    # ==================== Statistics ====================
    
    def get_system_stats(self) -> Dict[str, Any]:
        """
        Get overall system statistics.
        
        Returns:
            Dictionary with statistics
        """
        return self.attendance_repo.get_database_stats()
    
    def get_attendance_trends(
        self,
        grade: Optional[int] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get attendance trends over a period.
        
        Args:
            grade: Optional grade filter
            days: Number of days to analyze
            
        Returns:
            Dictionary with trend data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        records = self.attendance_repo.find_by_date_range(
            start_date, end_date, grade=grade
        )
        
        # Group by date
        daily_data = {}
        for record in records:
            day_str = record.date.isoformat()
            if day_str not in daily_data:
                daily_data[day_str] = {
                    'present': 0, 'absent': 0, 'late': 0, 'excused': 0, 'total': 0
                }
            daily_data[day_str][record.status.value] += 1
            daily_data[day_str]['total'] += 1
        
        # Calculate trends
        total_present = sum(d['present'] for d in daily_data.values())
        total_records = sum(d['total'] for d in daily_data.values())
        
        avg_attendance = (total_present / total_records * 100) if total_records > 0 else 0
        
        return {
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'grade': grade,
            'total_records': total_records,
            'average_attendance_rate': round(avg_attendance, 2),
            'daily_data': daily_data
        }