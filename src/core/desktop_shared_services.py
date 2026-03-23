from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from adapters.sqlite.repositories import (
    SQLiteAttendanceRepository,
    SQLiteAuditRepository,
    SQLiteFamilyRepository,
    SQLiteLearnerRepository,
    SQLitePaymentRepository,
    SQLiteUserRepository,
)
from core.services.token_service import TokenService
from core.use_cases.admin_use_case import AdminUseCase
from core.use_cases.attendance_use_case import AttendanceUseCase
from core.use_cases.audit_use_case import AuditUseCase
from core.use_cases.auth_use_case import AuthUseCase
from core.use_cases.family_use_case import FamilyUseCase
from core.use_cases.learner_use_case import LearnerUseCase
from core.use_cases.payment_catalog_use_case import PaymentCatalogUseCase
from core.use_cases.payment_use_case import PaymentUseCase
from core.use_cases.settings_use_case import SettingsUseCase


def _iso(value: date | str) -> str:
    return value if isinstance(value, str) else value.isoformat()


class DesktopAttendanceFacade:
    """Desktop bridge that keeps the dialog working while using shared adapters/use cases."""

    def __init__(
        self,
        learner_use_case: LearnerUseCase,
        attendance_use_case: AttendanceUseCase,
    ) -> None:
        self.learner_use_case = learner_use_case
        self.attendance_use_case = attendance_use_case

    def list_daily(self, record_date: date, grade: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.attendance_use_case.list_daily(_iso(record_date), grade=grade)

    def record_bulk(self, records: List[Dict[str, Any]], user_id: Optional[int] = None) -> tuple[int, int]:
        success_count = 0
        failure_count = 0
        for payload in records:
            normalized = dict(payload)
            normalized["date"] = _iso(payload.get("date") or date.today())
            attendance_id, error = self.attendance_use_case.record(normalized, user_id=user_id)
            if attendance_id and not error:
                success_count += 1
            else:
                failure_count += 1
        return success_count, failure_count

    def history(
        self,
        start_date: date,
        end_date: date,
        learner_acc_no: Optional[str] = None,
        grade: Optional[int] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        return self.attendance_use_case.history(
            start_date=_iso(start_date),
            end_date=_iso(end_date),
            learner_acc_no=learner_acc_no,
            grade=grade,
            limit=limit,
        )

    def summary(self, start_date: date, end_date: date, grade: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.attendance_use_case.summary(_iso(start_date), _iso(end_date), grade=grade)

    def grade_report(self, grade: int, start_date: date, end_date: date) -> Dict[str, Any]:
        learners = self.summary(start_date, end_date, grade=grade)
        normalized = [
            {
                "learner_acc_no": row.get("learner_acc_no"),
                "learner_name": row.get("learner_name"),
                "learner_surname": row.get("learner_surname"),
                "grade": row.get("grade"),
                "total_days": int(row.get("total_days") or 0),
                "present_days": int(row.get("present_days") or 0),
                "absent_days": int(row.get("absent_days") or 0),
                "late_days": int(row.get("late_days") or 0),
                "excused_days": int(row.get("excused_days") or 0),
                "attendance_rate": float(row.get("attendance_rate") or 0.0),
            }
            for row in learners
        ]
        total_days = sum(item["total_days"] for item in normalized)
        total_present = sum(item["present_days"] for item in normalized)
        overall_rate = round((total_present / total_days) * 100, 2) if total_days else 0.0
        return {"learners": normalized, "overall_attendance_rate": overall_rate}

    def daily_report(self, record_date: date, grade: Optional[int] = None) -> Dict[str, Any]:
        rows = self.list_daily(record_date, grade=grade)
        by_grade: Dict[int, Dict[str, int]] = {}
        totals = {"present": 0, "absent": 0, "late": 0, "excused": 0, "half_day": 0}

        for row in rows:
            learner_grade = int(row.get("grade") or 0)
            bucket = by_grade.setdefault(
                learner_grade,
                {"total": 0, "present": 0, "absent": 0, "late": 0, "excused": 0, "half_day": 0},
            )
            status = str(row.get("status") or "present").lower()
            bucket["total"] += 1
            bucket[status] = bucket.get(status, 0) + 1
            totals[status] = totals.get(status, 0) + 1

        expected = (
            self.learner_use_case.list_learners(grade=grade, is_active=True)
            if grade is not None
            else self.learner_use_case.list_learners(is_active=True)
        )
        missing_count = max(0, len(expected) - len(rows))

        return {
            "date": _iso(record_date),
            "total_records": len(rows),
            "total_present": totals.get("present", 0),
            "total_absent": totals.get("absent", 0),
            "total_late": totals.get("late", 0),
            "total_excused": totals.get("excused", 0),
            "missing_count": missing_count,
            "by_grade": dict(sorted(by_grade.items(), key=lambda item: item[0])),
        }

    def monthly_report(self, year: int, month: int, grade: Optional[int] = None) -> Dict[str, Any]:
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        rows = self.history(start_date, end_date, grade=grade, limit=10_000)
        daily_statistics: Dict[int, Dict[str, int]] = {}
        for row in rows:
            row_date = str(row.get("date") or "")
            day = int(row_date[-2:]) if row_date else 0
            if day <= 0:
                continue
            bucket = daily_statistics.setdefault(day, {"present": 0, "absent": 0, "late": 0, "excused": 0})
            status = str(row.get("status") or "present").lower()
            if status in bucket:
                bucket[status] += 1

        return {
            "start_date": _iso(start_date),
            "end_date": _iso(end_date),
            "grade": grade if grade is not None else "All Grades",
            "total_records": len(rows),
            "daily_statistics": daily_statistics,
        }

    def attendance_trends(self, days: int = 30, grade: Optional[int] = None) -> Dict[str, Any]:
        end_date = date.today()
        start_date = end_date - timedelta(days=max(1, days) - 1)
        rows = self.history(start_date, end_date, grade=grade, limit=50_000)

        daily_data: Dict[str, Dict[str, int]] = {}
        total_present = 0
        for row in rows:
            row_date = str(row.get("date") or "")
            if not row_date:
                continue
            bucket = daily_data.setdefault(row_date, {"present": 0, "absent": 0, "late": 0, "total": 0})
            status = str(row.get("status") or "present").lower()
            if status in {"present", "absent", "late"}:
                bucket[status] += 1
            bucket["total"] += 1
            if status == "present":
                total_present += 1

        average_attendance_rate = round((total_present / len(rows)) * 100, 2) if rows else 0.0
        return {
            "period_start": _iso(start_date),
            "period_end": _iso(end_date),
            "grade": grade if grade is not None else "All Grades",
            "total_records": len(rows),
            "average_attendance_rate": average_attendance_rate,
            "daily_data": daily_data,
        }


@dataclass(frozen=True)
class DesktopSharedServices:
    user_repo: SQLiteUserRepository
    audit_repo: SQLiteAuditRepository
    learner_repo: SQLiteLearnerRepository
    family_repo: SQLiteFamilyRepository
    payment_repo: SQLitePaymentRepository
    attendance_repo: SQLiteAttendanceRepository
    auth_use_case: AuthUseCase
    admin_use_case: AdminUseCase
    learner_use_case: LearnerUseCase
    family_use_case: FamilyUseCase
    payment_use_case: PaymentUseCase
    payment_catalog_use_case: PaymentCatalogUseCase
    attendance_use_case: AttendanceUseCase
    attendance_facade: DesktopAttendanceFacade
    audit_use_case: AuditUseCase
    settings_use_case: SettingsUseCase


def get_desktop_shared_services(db_manager: Any) -> DesktopSharedServices:
    existing = getattr(db_manager, "_desktop_shared_services", None)
    if existing is not None:
        return existing

    user_repo = SQLiteUserRepository(db_manager)
    audit_repo = SQLiteAuditRepository(db_manager)
    learner_repo = SQLiteLearnerRepository(db_manager)
    family_repo = SQLiteFamilyRepository(db_manager)
    payment_repo = SQLitePaymentRepository(db_manager)
    attendance_repo = SQLiteAttendanceRepository(db_manager)

    auth_use_case = AuthUseCase(user_repo, TokenService(), audit_repo)
    services = DesktopSharedServices(
        user_repo=user_repo,
        audit_repo=audit_repo,
        learner_repo=learner_repo,
        family_repo=family_repo,
        payment_repo=payment_repo,
        attendance_repo=attendance_repo,
        auth_use_case=auth_use_case,
        admin_use_case=AdminUseCase(user_repo, audit_repo),
        learner_use_case=LearnerUseCase(learner_repo, audit_repo),
        family_use_case=FamilyUseCase(family_repo, audit_repo),
        payment_use_case=PaymentUseCase(payment_repo, audit_repo),
        payment_catalog_use_case=PaymentCatalogUseCase(payment_repo, audit_repo),
        attendance_use_case=AttendanceUseCase(attendance_repo, audit_repo),
        attendance_facade=DesktopAttendanceFacade(
            learner_use_case=LearnerUseCase(learner_repo, audit_repo),
            attendance_use_case=AttendanceUseCase(attendance_repo, audit_repo),
        ),
        audit_use_case=AuditUseCase(audit_repo),
        settings_use_case=SettingsUseCase(auth_use_case),
    )
    setattr(db_manager, "_desktop_shared_services", services)
    return services
