"""
Payment Integration Interface

This module provides the integration layer between the attendance system
and the payment system. It handles feeding payment information detected
during attendance processing to the payment system.
"""

import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
import json
import os
import sys

# Add the src directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from attendance_models.attendance_models import (
    PaymentFeedData, OCRResult, AttendanceRecord, PaymentFeedStatus
)
from attendance_database import AttendanceDatabase


class PaymentIntegrationError(Exception):
    """Custom exception for payment integration errors."""
    pass


@dataclass
class PaymentFeedResult:
    """Result of a payment feed operation."""
    success: bool
    feed_id: int
    learner_acc_no: str
    amount: float
    message: str
    error: Optional[str] = None


class PaymentIntegrationService:
    """
    Service for integrating attendance-detected payments with the payment system.
    
    This service acts as a bridge between the two systems, allowing the attendance
    system to remain independent while still feeding payment information.
    
    Integration Methods:
    1. Database Queue: Payment data is queued in a shared database table
    2. Direct API: Payment data is sent directly to payment system services
    3. Event-based: Payment data triggers events that the payment system listens to
    """
    
    def __init__(
        self, 
        attendance_db: AttendanceDatabase,
        payment_db_manager=None,
        notification_service=None
    ):
        """
        Initialize the payment integration service.
        
        Args:
            attendance_db: The attendance database instance
            payment_db_manager: Optional payment system database manager
            notification_service: Optional notification service for emails
        """
        self.attendance_db = attendance_db
        self.payment_db_manager = payment_db_manager
        self.notification_service = notification_service
        self.logger = logging.getLogger(__name__)
        
        # Callbacks for custom integration
        self._on_payment_feed_callbacks: List[Callable] = []
    
    def register_payment_feed_callback(self, callback: Callable):
        """
        Register a callback to be called when payment data is fed.
        
        Args:
            callback: Function that takes PaymentFeedData as argument
        """
        self._on_payment_feed_callbacks.append(callback)
    
    def process_ocr_result(self, ocr_result: OCRResult) -> Optional[PaymentFeedResult]:
        """
        Process an OCR result and feed payment data if applicable.
        
        This is the main entry point for processing OCR results from
        attendance document scanning.
        
        Args:
            ocr_result: The OCR result to process
            
        Returns:
            PaymentFeedResult if payment was detected, None otherwise
        """
        if not ocr_result.success:
            self.logger.warning(f"OCR result not successful: {ocr_result.error_message}")
            return None
        
        # Check if payment was detected
        if not ocr_result.payment_amount or ocr_result.payment_amount <= 0:
            self.logger.debug(f"No payment detected in OCR result for {ocr_result.learner_name}")
            return None
        
        # Create payment feed data
        payment_data = ocr_result.to_payment_feed_data()
        if not payment_data:
            return None
        
        # Feed the payment data
        return self.feed_payment_data(payment_data)
    
    def feed_payment_data(self, payment_data: PaymentFeedData) -> PaymentFeedResult:
        """
        Feed payment data to the payment system.
        
        This method handles the actual integration, using the configured
        integration method (database queue, direct API, or events).
        
        Args:
            payment_data: The payment data to feed
            
        Returns:
            PaymentFeedResult indicating success or failure
        """
        try:
            # Step 1: Add to the attendance system's payment feed queue
            feed_id = self.attendance_db.add_payment_to_feed_queue(
                learner_acc_no=payment_data.learner_acc_no,
                learner_name=payment_data.learner_name,
                learner_surname=payment_data.learner_surname,
                amount=payment_data.amount,
                payment_date=payment_data.payment_date,
                source_document=payment_data.source_document,
                source_type=payment_data.source_type,
                reference_number=payment_data.reference_number,
                notes=payment_data.notes
            )
            
            self.logger.info(
                f"Payment data queued: R{payment_data.amount:.2f} for "
                f"{payment_data.learner_name} {payment_data.learner_surname}"
            )
            
            # Step 2: Try to directly feed to payment system if available
            direct_feed_result = None
            if self.payment_db_manager:
                direct_feed_result = self._direct_feed_to_payment_system(
                    feed_id, payment_data
                )
            
            # Step 3: Trigger callbacks
            for callback in self._on_payment_feed_callbacks:
                try:
                    callback(payment_data)
                except Exception as e:
                    self.logger.error(f"Callback error: {e}")
            
            # Step 4: Send notification if service available
            if self.notification_service and direct_feed_result:
                self._send_payment_notification(payment_data)
            
            return PaymentFeedResult(
                success=True,
                feed_id=feed_id,
                learner_acc_no=payment_data.learner_acc_no,
                amount=payment_data.amount,
                message="Payment data successfully queued and processed"
            )
            
        except Exception as e:
            error_msg = f"Failed to feed payment data: {e}"
            self.logger.error(error_msg)
            
            return PaymentFeedResult(
                success=False,
                feed_id=0,
                learner_acc_no=payment_data.learner_acc_no,
                amount=payment_data.amount,
                message="Failed to feed payment data",
                error=str(e)
            )
    
    def _direct_feed_to_payment_system(
        self, 
        feed_id: int, 
        payment_data: PaymentFeedData
    ) -> bool:
        """
        Directly feed payment data to the payment system database.
        
        This method writes directly to the payment system's Payments table
        if the payment database manager is available.
        
        Args:
            feed_id: The feed queue ID
            payment_data: The payment data to feed
            
        Returns:
            True if successful, False otherwise
        """
        if not self.payment_db_manager:
            return False
        
        try:
            # Insert into the payment system's Payments table
            query = """
                INSERT INTO Payments (learner_id, date, amount, notes)
                VALUES (?, ?, ?, ?)
            """
            
            notes = f"From attendance OCR - {payment_data.source_type}"
            if payment_data.notes:
                notes += f" - {payment_data.notes}"
            
            self.payment_db_manager.execute_query(
                query,
                (
                    payment_data.learner_acc_no,
                    payment_data.payment_date.isoformat(),
                    payment_data.amount,
                    notes
                ),
                commit=True
            )
            
            # Mark the feed as sent
            self.attendance_db.mark_payment_feed_sent(feed_id)
            
            self.logger.info(
                f"Direct feed successful: R{payment_data.amount:.2f} for "
                f"{payment_data.learner_acc_no}"
            )
            
            return True
            
        except Exception as e:
            error_msg = f"Direct feed failed: {e}"
            self.logger.error(error_msg)
            self.attendance_db.mark_payment_feed_failed(feed_id, str(e))
            return False
    
    def _send_payment_notification(self, payment_data: PaymentFeedData) -> bool:
        """
        Send payment notification email to parents.
        
        Args:
            payment_data: The payment data for notification
            
        Returns:
            True if notification sent successfully
        """
        if not self.notification_service:
            return False
        
        try:
            # Get parent email from payment system
            parent_email = self._get_parent_email(payment_data.learner_acc_no)
            
            if not parent_email:
                self.logger.warning(
                    f"No parent email found for learner {payment_data.learner_acc_no}"
                )
                return False
            
            learner_name = f"{payment_data.learner_name} {payment_data.learner_surname}"
            
            # Send thank you email
            result = self.notification_service.send_payment_thank_you_email(
                parent_email=parent_email,
                learner_name=learner_name,
                amount=payment_data.amount,
                payment_date=payment_data.payment_date.isoformat()
            )
            
            if result:
                self.logger.info(f"Payment notification sent to {parent_email}")
            else:
                self.logger.warning(f"Failed to send notification to {parent_email}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error sending payment notification: {e}")
            return False
    
    def _get_parent_email(self, learner_acc_no: str) -> Optional[str]:
        """
        Get parent email address from the payment system.
        
        Args:
            learner_acc_no: Learner account number
            
        Returns:
            Parent email address or None
        """
        if not self.payment_db_manager:
            return None
        
        try:
            query = """
                SELECT p.email
                FROM Learners s
                LEFT JOIN Parents p ON s.parent_id = p.id
                WHERE s.acc_no = ? AND p.email IS NOT NULL AND p.email != ''
            """
            
            result = self.payment_db_manager.execute_query(
                query, (learner_acc_no,), fetchone=True
            )
            
            if result and result[0]:
                return result[0]
            
            # Try second parent
            query2 = """
                SELECT p.email
                FROM Learners s
                LEFT JOIN Parents p ON s.parent2_id = p.id
                WHERE s.acc_no = ? AND p.email IS NOT NULL AND p.email != ''
            """
            
            result2 = self.payment_db_manager.execute_query(
                query2, (learner_acc_no,), fetchone=True
            )
            
            if result2 and result2[0]:
                return result2[0]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting parent email: {e}")
            return None
    
    def process_pending_feeds(self) -> Dict[str, Any]:
        """
        Process all pending payment feeds.
        
        This method should be called periodically to retry failed feeds
        or process feeds that were queued for later processing.
        
        Returns:
            Dictionary with processing statistics
        """
        pending_feeds = self.attendance_db.get_pending_payment_feeds()
        
        stats = {
            'total_pending': len(pending_feeds),
            'processed': 0,
            'failed': 0,
            'skipped': 0
        }
        
        for feed in pending_feeds:
            try:
                payment_data = PaymentFeedData(
                    learner_acc_no=feed['learner_acc_no'],
                    learner_name=feed['learner_name'],
                    learner_surname=feed['learner_surname'],
                    amount=feed['amount'],
                    payment_date=date.fromisoformat(feed['payment_date']),
                    source_document=feed['source_document'],
                    source_type=feed['source_type'] or 'attendance_ocr',
                    reference_number=feed['reference_number'],
                    notes=feed['notes']
                )
                
                if self.payment_db_manager:
                    result = self._direct_feed_to_payment_system(
                        feed['feed_id'], payment_data
                    )
                    if result:
                        stats['processed'] += 1
                    else:
                        stats['failed'] += 1
                else:
                    stats['skipped'] += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing feed {feed['feed_id']}: {e}")
                stats['failed'] += 1
        
        return stats
    
    def update_attendance_payment_status(
        self, 
        record: AttendanceRecord, 
        feed_result: PaymentFeedResult
    ) -> bool:
        """
        Update an attendance record with payment feed status.
        
        Args:
            record: The attendance record to update
            feed_result: The result of the payment feed operation
            
        Returns:
            True if update successful
        """
        if feed_result.success:
            record.has_payment = True
            record.payment_feed_status = PaymentFeedStatus.SENT
        else:
            record.payment_feed_status = PaymentFeedStatus.FAILED
        
        return self.attendance_db.update_attendance_record(record)


class PaymentFeedWorker:
    """
    Background worker for processing payment feeds.
    
    This worker can be run in a separate thread to periodically
    process pending payment feeds.
    """
    
    def __init__(
        self, 
        integration_service: PaymentIntegrationService,
        interval_seconds: int = 60
    ):
        """
        Initialize the payment feed worker.
        
        Args:
            integration_service: The payment integration service
            interval_seconds: Interval between processing runs
        """
        self.integration_service = integration_service
        self.interval_seconds = interval_seconds
        self.logger = logging.getLogger(__name__)
        self._running = False
    
    def start(self):
        """Start the worker."""
        import threading
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.logger.info("Payment feed worker started")
    
    def stop(self):
        """Stop the worker."""
        self._running = False
        self.logger.info("Payment feed worker stopped")
    
    def _run_loop(self):
        """Main worker loop."""
        import time
        
        while self._running:
            try:
                stats = self.integration_service.process_pending_feeds()
                if stats['total_pending'] > 0:
                    self.logger.info(f"Processed pending feeds: {stats}")
            except Exception as e:
                self.logger.error(f"Error in feed worker: {e}")
            
            time.sleep(self.interval_seconds)


# Convenience function for quick integration
def create_payment_integration(
    attendance_db_path: str = "attendance_system/attendance.db",
    payment_db_manager=None,
    notification_service=None
) -> PaymentIntegrationService:
    """
    Create a payment integration service with default configuration.
    
    Args:
        attendance_db_path: Path to the attendance database
        payment_db_manager: Optional payment system database manager
        notification_service: Optional notification service
        
    Returns:
        Configured PaymentIntegrationService instance
    """
    attendance_db = AttendanceDatabase(db_path=attendance_db_path)
    return PaymentIntegrationService(
        attendance_db=attendance_db,
        payment_db_manager=payment_db_manager,
        notification_service=notification_service
    )