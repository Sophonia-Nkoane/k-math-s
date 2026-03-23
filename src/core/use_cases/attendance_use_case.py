from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.ports.repositories import AttendanceRepoPort, AuditRepoPort


class AttendanceUseCase:
    def __init__(
        self,
        attendance_repo: AttendanceRepoPort,
        audit_repo: Optional[AuditRepoPort] = None,
    ) -> None:
        self.attendance_repo = attendance_repo
        self.audit_repo = audit_repo

    def list_daily(self, iso_date: str, grade: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.attendance_repo.list_attendance_for_date(iso_date=iso_date, grade=grade)

    def record(self, payload: Dict[str, Any], user_id: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
        required = ["learner_acc_no", "date", "status"]
        missing = [field for field in required if not payload.get(field)]
        if missing:
            return None, f"Missing required fields: {', '.join(missing)}"

        attendance_id = self.attendance_repo.record_attendance(payload)

        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="RECORD_ATTENDANCE",
                object_type="Attendance",
                object_id=str(payload.get("learner_acc_no")),
                details=f"Recorded attendance status={payload.get('status')}",
            )

        return attendance_id, None

    def history(
        self,
        start_date: str,
        end_date: str,
        learner_acc_no: Optional[str] = None,
        grade: Optional[int] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        return self.attendance_repo.list_attendance_history(
            start_date=start_date,
            end_date=end_date,
            learner_acc_no=learner_acc_no,
            grade=grade,
            limit=limit,
        )

    def summary(self, start_date: str, end_date: str, grade: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.attendance_repo.get_attendance_summary(
            start_date=start_date,
            end_date=end_date,
            grade=grade,
        )
