"""
Combined Reporting Service

Provides integrated reporting capabilities that combine attendance and payment data
from the unified database. This service enables comprehensive reports that show
both attendance patterns and payment history together.
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class LearnerCombinedReport:
    """Combined report data for a learner."""
    learner_acc_no: str
    learner_name: str
    learner_surname: str
    grade: int
    
    # Attendance data
    total_days: int = 0
    present_days: int = 0
    absent_days: int = 0
    late_days: int = 0
    excused_days: int = 0
    attendance_rate: float = 0.0
    
    # Payment data
    total_fees: float = 0.0
    total_paid: float = 0.0
    balance: float = 0.0
    last_payment_date: Optional[str] = None
    last_payment_amount: float = 0.0
    
    # Combined metrics
    payment_attendance_ratio: float = 0.0
    risk_score: int = 0  # 0-10 scale, higher = more risk


class CombinedReportingService:
    """
    Service for generating combined attendance and payment reports.
    
    This service queries both attendance and payment data from the same
    database to provide comprehensive reporting capabilities.
    """
    
    def __init__(self, db_manager):
        """
        Initialize the combined reporting service.
        
        Args:
            db_manager: Database manager instance for the unified database
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    def get_learner_combined_report(
        self,
        learner_acc_no: str,
        period_start: date,
        period_end: date
    ) -> Optional[LearnerCombinedReport]:
        """
        Generate a combined report for a single learner.
        
        Args:
            learner_acc_no: Learner account number
            period_start: Start date for the report
            period_end: End date for the report
            
        Returns:
            LearnerCombinedReport or None if learner not found
        """
        try:
            # Get learner basic info
            learner_query = """
                SELECT acc_no, name, surname, grade
                FROM Learners
                WHERE acc_no = ?
            """
            
            learner_result = self.db_manager.execute_query(
                learner_query,
                (learner_acc_no,),
                fetchone=True
            )
            
            if not learner_result:
                return None
            
            report = LearnerCombinedReport(
                learner_acc_no=learner_result[0],
                learner_name=learner_result[1],
                learner_surname=learner_result[2],
                grade=learner_result[3]
            )
            
            # Get attendance statistics
            attendance_query = """
                SELECT 
                    COUNT(*) as total_days,
                    SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_days,
                    SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent_days,
                    SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) as late_days,
                    SUM(CASE WHEN status = 'excused' THEN 1 ELSE 0 END) as excused_days
                FROM AttendanceRecords
                WHERE learner_acc_no = ? AND date >= ? AND date <= ?
            """
            
            attendance_result = self.db_manager.execute_query(
                attendance_query,
                (learner_acc_no, period_start.isoformat(), period_end.isoformat()),
                fetchone=True
            )
            
            if attendance_result:
                report.total_days = attendance_result[0] or 0
                report.present_days = attendance_result[1] or 0
                report.absent_days = attendance_result[2] or 0
                report.late_days = attendance_result[3] or 0
                report.excused_days = attendance_result[4] or 0
                
                if report.total_days > 0:
                    report.attendance_rate = (report.present_days / report.total_days) * 100
            
            # Get payment statistics
            payment_query = """
                SELECT 
                    COALESCE(SUM(p.amount), 0) as total_paid,
                    MAX(p.date) as last_payment_date
                FROM Payments p
                WHERE p.learner_id = ? AND p.date >= ? AND p.date <= ?
            """
            
            payment_result = self.db_manager.execute_query(
                payment_query,
                (learner_acc_no, period_start.isoformat(), period_end.isoformat()),
                fetchone=True
            )
            
            if payment_result:
                report.total_paid = float(payment_result[0] or 0)
                report.last_payment_date = payment_result[1]
            
            # Get last payment amount
            if report.last_payment_date:
                last_payment_query = """
                    SELECT amount FROM Payments
                    WHERE learner_id = ? AND date = ?
                    ORDER BY id DESC LIMIT 1
                """
                last_payment_result = self.db_manager.execute_query(
                    last_payment_query,
                    (learner_acc_no, report.last_payment_date),
                    fetchone=True
                )
                if last_payment_result:
                    report.last_payment_amount = float(last_payment_result[0] or 0)
            
            # Get balance (from learner's current balance)
            balance_query = """
                SELECT balance FROM Learners WHERE acc_no = ?
            """
            balance_result = self.db_manager.execute_query(
                balance_query,
                (learner_acc_no,),
                fetchone=True
            )
            if balance_result and balance_result[0]:
                report.balance = float(balance_result[0])
            
            # Calculate combined metrics
            if report.total_paid > 0 and report.attendance_rate > 0:
                report.payment_attendance_ratio = (report.attendance_rate / 100) * (report.total_paid / max(report.total_fees, 1))
            
            # Calculate risk score (0-10, higher = more risk)
            report.risk_score = self._calculate_risk_score(report)
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating combined report for {learner_acc_no}: {e}")
            return None
    
    def _calculate_risk_score(self, report: LearnerCombinedReport) -> int:
        """
        Calculate a risk score for a learner based on attendance and payment patterns.
        
        Higher score = higher risk (more attention needed)
        
        Args:
            report: LearnerCombinedReport with calculated metrics
            
        Returns:
            Risk score from 0-10
        """
        score = 0
        
        # Attendance risk (0-4 points)
        if report.attendance_rate < 50:
            score += 4
        elif report.attendance_rate < 70:
            score += 3
        elif report.attendance_rate < 85:
            score += 2
        elif report.attendance_rate < 95:
            score += 1
        
        # Payment risk (0-4 points)
        if report.balance > 0:
            if report.balance > 1000:
                score += 4
            elif report.balance > 500:
                score += 3
            elif report.balance > 200:
                score += 2
            else:
                score += 1
        
        # Combined risk (0-2 points)
        if report.attendance_rate < 70 and report.balance > 0:
            score += 2
        elif report.attendance_rate < 85 and report.balance > 500:
            score += 1
        
        return min(score, 10)
    
    def get_grade_combined_report(
        self,
        grade: int,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Generate a combined report for all learners in a grade.
        
        Args:
            grade: Grade number
            period_start: Start date for the report
            period_end: End date for the report
            
        Returns:
            Dictionary with grade report data
        """
        try:
            # Get all active learners in grade
            learners_query = """
                SELECT acc_no FROM Learners
                WHERE grade = ? AND is_active = 1
                ORDER BY surname, name
            """
            
            learners_result = self.db_manager.execute_query(
                learners_query,
                (grade,),
                fetchall=True
            )
            
            learner_reports = []
            for learner in learners_result or []:
                report = self.get_learner_combined_report(
                    learner[0], period_start, period_end
                )
                if report:
                    learner_reports.append(report)
            
            # Calculate grade-level statistics
            total_learners = len(learner_reports)
            avg_attendance = sum(r.attendance_rate for r in learner_reports) / total_learners if total_learners > 0 else 0
            total_balance = sum(r.balance for r in learner_reports)
            total_payments = sum(r.total_paid for r in learner_reports)
            
            # Risk distribution
            risk_distribution = {
                'low': len([r for r in learner_reports if r.risk_score <= 3]),
                'medium': len([r for r in learner_reports if 4 <= r.risk_score <= 6]),
                'high': len([r for r in learner_reports if r.risk_score >= 7])
            }
            
            return {
                'grade': grade,
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'total_learners': total_learners,
                'average_attendance_rate': round(avg_attendance, 2),
                'total_outstanding_balance': total_balance,
                'total_payments_received': total_payments,
                'risk_distribution': risk_distribution,
                'learners': [asdict(r) for r in learner_reports]
            }
            
        except Exception as e:
            self.logger.error(f"Error generating grade combined report: {e}")
            return {}
    
    def get_school_overview_report(
        self,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Generate a school-wide overview report.
        
        Args:
            period_start: Start date for the report
            period_end: End date for the report
            
        Returns:
            Dictionary with school overview data
        """
        try:
            # Overall statistics
            stats_query = """
                SELECT 
                    (SELECT COUNT(*) FROM Learners WHERE is_active = 1) as total_learners,
                    (SELECT COUNT(*) FROM AttendanceRecords WHERE date >= ? AND date <= ?) as total_attendance_records,
                    (SELECT COALESCE(SUM(amount), 0) FROM Payments WHERE date >= ? AND date <= ?) as total_payments,
                    (SELECT COUNT(DISTINCT learner_acc_no) FROM AttendanceRecords WHERE date >= ? AND date <= ?) as learners_with_attendance
            """
            
            stats_result = self.db_manager.execute_query(
                stats_query,
                (period_start.isoformat(), period_end.isoformat(),
                 period_start.isoformat(), period_end.isoformat(),
                 period_start.isoformat(), period_end.isoformat()),
                fetchone=True
            )
            
            # Grade-by-grade breakdown
            grade_reports = []
            for grade in range(1, 13):
                grade_report = self.get_grade_combined_report(grade, period_start, period_end)
                if grade_report and grade_report.get('total_learners', 0) > 0:
                    grade_reports.append(grade_report)
            
            # Attendance by grade summary
            attendance_by_grade = {}
            for gr in grade_reports:
                attendance_by_grade[gr['grade']] = {
                    'attendance_rate': gr['average_attendance_rate'],
                    'total_learners': gr['total_learners']
                }
            
            return {
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'generated_at': datetime.now().isoformat(),
                'total_learners': stats_result[0] if stats_result else 0,
                'total_attendance_records': stats_result[1] if stats_result else 0,
                'total_payments_received': float(stats_result[2] if stats_result else 0),
                'learners_with_attendance': stats_result[3] if stats_result else 0,
                'attendance_by_grade': attendance_by_grade,
                'grade_reports': grade_reports
            }
            
        except Exception as e:
            self.logger.error(f"Error generating school overview report: {e}")
            return {}
    
    def get_at_risk_learners(
        self,
        min_risk_score: int = 7,
        period_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get list of learners who are at high risk based on attendance and payment patterns.
        
        Args:
            min_risk_score: Minimum risk score to include (default 7)
            period_days: Number of days to analyze (default 30)
            
        Returns:
            List of at-risk learner dictionaries
        """
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=period_days)
            
            # Get all active learners
            learners_query = """
                SELECT acc_no FROM Learners
                WHERE is_active = 1
            """
            
            learners_result = self.db_manager.execute_query(
                learners_query,
                fetchall=True
            )
            
            at_risk = []
            for learner in learners_result or []:
                report = self.get_learner_combined_report(
                    learner[0], start_date, end_date
                )
                if report and report.risk_score >= min_risk_score:
                    at_risk.append({
                        'acc_no': report.learner_acc_no,
                        'name': f"{report.learner_name} {report.learner_surname}",
                        'grade': report.grade,
                        'attendance_rate': round(report.attendance_rate, 1),
                        'balance': report.balance,
                        'last_payment': report.last_payment_date,
                        'risk_score': report.risk_score,
                        'risk_level': 'High' if report.risk_score >= 8 else 'Medium'
                    })
            
            # Sort by risk score (highest first)
            at_risk.sort(key=lambda x: x['risk_score'], reverse=True)
            
            return at_risk
            
        except Exception as e:
            self.logger.error(f"Error getting at-risk learners: {e}")
            return []
    
    def get_payment_attendance_correlation(
        self,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Analyze correlation between payment patterns and attendance.
        
        Args:
            period_start: Start date for analysis
            period_end: End date for analysis
            
        Returns:
            Dictionary with correlation analysis data
        """
        try:
            # Get learners with both attendance and payment data
            query = """
                SELECT 
                    s.acc_no,
                    s.name,
                    s.surname,
                    s.grade,
                    COUNT(DISTINCT ar.date) as attendance_days,
                    SUM(CASE WHEN ar.status = 'present' THEN 1 ELSE 0 END) as present_days,
                    COALESCE(SUM(p.amount), 0) as total_payments
                FROM Learners s
                LEFT JOIN AttendanceRecords ar ON s.acc_no = ar.learner_acc_no
                    AND ar.date >= ? AND ar.date <= ?
                LEFT JOIN Payments p ON s.acc_no = p.learner_id
                    AND p.date >= ? AND p.date <= ?
                WHERE s.is_active = 1
                GROUP BY s.acc_no
                HAVING attendance_days > 0
            """
            
            result = self.db_manager.execute_query(
                query,
                (period_start.isoformat(), period_end.isoformat(),
                 period_start.isoformat(), period_end.isoformat()),
                fetchall=True
            )
            
            # Analyze correlation
            learners_data = []
            for row in result or []:
                attendance_days = row[4] or 0
                present_days = row[5] or 0
                attendance_rate = (present_days / attendance_days * 100) if attendance_days > 0 else 0
                
                learners_data.append({
                    'acc_no': row[0],
                    'name': f"{row[1]} {row[2]}",
                    'grade': row[3],
                    'attendance_rate': round(attendance_rate, 1),
                    'total_payments': float(row[6] or 0)
                })
            
            # Group by payment status
            paid_learners = [s for s in learners_data if s['total_payments'] > 0]
            unpaid_learners = [s for s in learners_data if s['total_payments'] == 0]
            
            avg_attendance_paid = sum(s['attendance_rate'] for s in paid_learners) / len(paid_learners) if paid_learners else 0
            avg_attendance_unpaid = sum(s['attendance_rate'] for s in unpaid_learners) / len(unpaid_learners) if unpaid_learners else 0

            return {
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'total_learners_analyzed': len(learners_data),
                'paid_learners_count': len(paid_learners),
                'unpaid_learners_count': len(unpaid_learners),
                'avg_attendance_paid': round(avg_attendance_paid, 2),
                'avg_attendance_unpaid': round(avg_attendance_unpaid, 2),
                'attendance_gap': round(avg_attendance_paid - avg_attendance_unpaid, 2),
                'learner_samples': learners_data[:50]
            }

        except Exception as e:
            self.logger.error(f"Error analyzing payment-attendance correlation: {e}")
            return {}
