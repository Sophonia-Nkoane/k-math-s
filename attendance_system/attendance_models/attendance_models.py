"""
Attendance Models for the Decoupled Attendance System

This module defines the data models for attendance records, separate from
the payment system but designed to integrate seamlessly.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class AttendanceStatus(Enum):
    """Enumeration for attendance status."""
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class PaymentFeedStatus(Enum):
    """Status of payment information feed to payment system."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class AttendanceRecord:
    """
    Represents a single attendance record for a learner.
    
    This is the core data model for the attendance system, designed to be
    independent of the payment system while maintaining compatibility.
    """
    attendance_id: Optional[int] = None
    learner_acc_no: str = ""
    learner_name: str = ""
    learner_surname: str = ""
    grade: int = 1
    date: date = field(default_factory=date.today)
    status: AttendanceStatus = AttendanceStatus.PRESENT
    signature_image: Optional[bytes] = None
    notes: Optional[str] = None
    recorded_by: Optional[str] = None
    recorded_at: datetime = field(default_factory=datetime.now)
    
    # Payment integration fields
    has_payment: bool = False
    payment_amount: Optional[float] = None
    payment_date: Optional[date] = None
    payment_feed_status: PaymentFeedStatus = PaymentFeedStatus.NOT_APPLICABLE
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_synced: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the attendance record to a dictionary."""
        return {
            'attendance_id': self.attendance_id,
            'learner_acc_no': self.learner_acc_no,
            'learner_name': self.learner_name,
            'learner_surname': self.learner_surname,
            'grade': self.grade,
            'date': self.date.isoformat() if self.date else None,
            'status': self.status.value,
            'signature_image': self.signature_image,
            'notes': self.notes,
            'recorded_by': self.recorded_by,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
            'has_payment': self.has_payment,
            'payment_amount': self.payment_amount,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'payment_feed_status': self.payment_feed_status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_synced': self.is_synced
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AttendanceRecord':
        """Create an AttendanceRecord from a dictionary."""
        return cls(
            attendance_id=data.get('attendance_id'),
            learner_acc_no=data.get('learner_acc_no', ''),
            learner_name=data.get('learner_name', ''),
            learner_surname=data.get('learner_surname', ''),
            grade=data.get('grade', 1),
            date=date.fromisoformat(data['date']) if data.get('date') else date.today(),
            status=AttendanceStatus(data.get('status', 'present')),
            signature_image=data.get('signature_image'),
            notes=data.get('notes'),
            recorded_by=data.get('recorded_by'),
            recorded_at=datetime.fromisoformat(data['recorded_at']) if data.get('recorded_at') else datetime.now(),
            has_payment=data.get('has_payment', False),
            payment_amount=data.get('payment_amount'),
            payment_date=date.fromisoformat(data['payment_date']) if data.get('payment_date') else None,
            payment_feed_status=PaymentFeedStatus(data.get('payment_feed_status', 'not_applicable')),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now(),
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.now(),
            is_synced=data.get('is_synced', False)
        )


@dataclass
class AttendanceSummary:
    """
    Summary statistics for attendance over a period.
    """
    learner_acc_no: str
    learner_name: str
    learner_surname: str
    grade: int
    period_start: date
    period_end: date
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
        return self.attendance_rate


@dataclass
class PaymentFeedData:
    """
    Data structure for feeding payment information to the payment system.
    
    This is the integration point between the attendance and payment systems.
    """
    learner_acc_no: str
    learner_name: str
    learner_surname: str
    amount: float
    payment_date: date
    source_document: Optional[str] = None
    source_type: str = "attendance_ocr"  # attendance_ocr, manual, etc.
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls or database storage."""
        return {
            'learner_acc_no': self.learner_acc_no,
            'learner_name': self.learner_name,
            'learner_surname': self.learner_surname,
            'amount': self.amount,
            'payment_date': self.payment_date.isoformat(),
            'source_document': self.source_document,
            'source_type': self.source_type,
            'reference_number': self.reference_number,
            'notes': self.notes,
            'created_at': self.created_at.isoformat()
        }


@dataclass
class OCRResult:
    """
    Result from OCR processing of attendance/payment documents.
    """
    success: bool
    learner_name: str = ""
    learner_surname: str = ""
    learner_acc_no: str = ""
    grade: Optional[int] = None
    date: Optional[date] = None
    is_signed: bool = False
    payment_amount: Optional[float] = None
    confidence_score: float = 0.0
    raw_text: str = ""
    error_message: Optional[str] = None
    
    def to_attendance_record(self) -> AttendanceRecord:
        """Convert OCR result to an attendance record."""
        return AttendanceRecord(
            learner_acc_no=self.learner_acc_no,
            learner_name=self.learner_name,
            learner_surname=self.learner_surname,
            grade=self.grade or 1,
            date=self.date or date.today(),
            status=AttendanceStatus.PRESENT if self.is_signed else AttendanceStatus.ABSENT,
            has_payment=self.payment_amount is not None,
            payment_amount=self.payment_amount,
            payment_date=self.date
        )
    
    def to_payment_feed_data(self) -> Optional[PaymentFeedData]:
        """Convert OCR result to payment feed data if payment was detected."""
        if not self.payment_amount:
            return None
        
        return PaymentFeedData(
            learner_acc_no=self.learner_acc_no,
            learner_name=self.learner_name,
            learner_surname=self.learner_surname,
            amount=self.payment_amount,
            payment_date=self.date or date.today(),
            source_type="attendance_ocr"
        )


@dataclass
class AttendanceFilter:
    """
    Filter criteria for querying attendance records.
    """
    learner_acc_no: Optional[str] = None
    grade: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    status: Optional[AttendanceStatus] = None
    has_payment: Optional[bool] = None
    payment_feed_status: Optional[PaymentFeedStatus] = None
    
    def to_where_clause(self) -> tuple:
        """Generate SQL WHERE clause and parameters from filter."""
        conditions = []
        params = []
        
        if self.learner_acc_no:
            conditions.append("learner_acc_no = ?")
            params.append(self.learner_acc_no)
        
        if self.grade:
            conditions.append("grade = ?")
            params.append(self.grade)
        
        if self.date_from:
            conditions.append("date >= ?")
            params.append(self.date_from.isoformat())
        
        if self.date_to:
            conditions.append("date <= ?")
            params.append(self.date_to.isoformat())
        
        if self.status:
            conditions.append("status = ?")
            params.append(self.status.value)
        
        if self.has_payment is not None:
            conditions.append("has_payment = ?")
            params.append(1 if self.has_payment else 0)
        
        if self.payment_feed_status:
            conditions.append("payment_feed_status = ?")
            params.append(self.payment_feed_status.value)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, tuple(params)