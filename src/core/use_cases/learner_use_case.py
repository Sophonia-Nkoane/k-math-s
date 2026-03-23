from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.ports.repositories import AuditRepoPort, LearnerRepoPort
from core.use_cases.pagination import sort_and_paginate


class LearnerUseCase:
    def __init__(self, learner_repo: LearnerRepoPort, audit_repo: Optional[AuditRepoPort] = None) -> None:
        self.learner_repo = learner_repo
        self.audit_repo = audit_repo

    def list_learners(
        self,
        search: Optional[str] = None,
        grade: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        return self.learner_repo.list_learners(search=search, grade=grade, is_active=is_active)

    def list_learners_paged(
        self,
        search: Optional[str] = None,
        grade: Optional[int] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "surname",
        sort_dir: str = "asc",
    ) -> Tuple[List[Dict[str, Any]], int, int, int, int]:
        rows = self.list_learners(search=search, grade=grade, is_active=is_active)
        return sort_and_paginate(rows, sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size)

    def get_learner(self, acc_no: str) -> Optional[Dict[str, Any]]:
        return self.learner_repo.get_learner(acc_no)

    def list_learners_for_family(self, family_id: int) -> List[Dict[str, Any]]:
        return self.learner_repo.list_learners_for_family(family_id)

    def create_learner(self, payload: Dict[str, Any], user_id: Optional[int] = None) -> Tuple[Optional[str], Optional[str]]:
        required = ["name", "surname", "grade", "subjects_count", "gender"]
        missing = [field for field in required if payload.get(field) in (None, "")]
        if missing:
            return None, f"Missing required fields: {', '.join(missing)}"

        acc_no = self.learner_repo.create_learner(payload)
        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="CREATE_LEARNER",
                object_type="Learner",
                object_id=acc_no,
                details=f"Created learner {payload.get('name')} {payload.get('surname')}",
            )
        return acc_no, None

    def update_learner(self, acc_no: str, payload: Dict[str, Any], user_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        try:
            current = self.learner_repo.get_learner(acc_no)
        except Exception as exc:
            return False, str(exc)
        if not current:
            return False, "Learner not found"

        # Enforce grade 1-7 payment-option change restrictions.
        old_option = (current.get("payment_option") or "").strip().upper()
        new_option = str(payload.get("payment_option") or old_option).strip().upper()
        grade = int(current.get("grade") or payload.get("grade") or 0)
        if grade in range(1, 8) and new_option != old_option:
            try:
                progress_status = self.learner_repo.get_learner_progress_status(acc_no)
            except Exception as exc:
                return False, str(exc)
            if not progress_status:
                return False, "Progress status unavailable. Update progress first."
            if not bool(progress_status.get("allowed", False)):
                reason = str(progress_status.get("reason") or "Payment change not allowed")
                return False, reason

        try:
            ok = self.learner_repo.update_learner(acc_no, payload)
        except Exception as exc:
            return False, str(exc)
        if not ok:
            return False, "Learner update failed"

        if grade in range(1, 8) and new_option != old_option:
            try:
                self.learner_repo.record_payment_change(acc_no, f"Payment option changed {old_option} -> {new_option}")
            except Exception:
                pass

        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="UPDATE_LEARNER",
                object_type="Learner",
                object_id=acc_no,
                details="Updated learner record",
            )
        return True, None

    def set_learner_active(
        self,
        acc_no: str,
        is_active: bool,
        reason: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        try:
            ok = self.learner_repo.set_learner_active(acc_no, is_active=is_active, reason=reason)
        except Exception as exc:
            return False, str(exc)
        if not ok:
            return False, "Failed to update learner billing status"

        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="RESUME_LEARNER_BILLING" if is_active else "PAUSE_LEARNER_BILLING",
                object_type="Learner",
                object_id=acc_no,
                details=reason or ("Resumed billing" if is_active else "Paused billing"),
            )
        return True, None

    def delete_learner(self, acc_no: str, user_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        try:
            current = self.learner_repo.get_learner(acc_no)
        except Exception as exc:
            return False, str(exc)
        if not current:
            return False, "Learner not found"

        try:
            ok = self.learner_repo.delete_learner(acc_no)
        except Exception as exc:
            return False, str(exc)
        if not ok:
            return False, "Failed to delete learner"

        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="DELETE_LEARNER",
                object_type="Learner",
                object_id=acc_no,
                details=f"Deleted learner {current.get('name', '')} {current.get('surname', '')}".strip(),
            )
        return True, None

    def update_progress(
        self,
        acc_no: str,
        progress_percentage: float,
        user_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        if progress_percentage < 0 or progress_percentage > 100:
            return False, "progress_percentage must be between 0 and 100"

        try:
            ok = self.learner_repo.set_learner_progress(acc_no, progress_percentage)
        except Exception as exc:
            return False, str(exc)
        if not ok:
            return False, "Failed to update progress"

        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="UPDATE_PROGRESS",
                object_type="Learner",
                object_id=acc_no,
                details=f"Progress updated to {progress_percentage:.2f}%",
            )
        return True, None

    def get_progress_status(self, acc_no: str) -> Optional[Dict[str, Any]]:
        try:
            return self.learner_repo.get_learner_progress_status(acc_no)
        except Exception:
            return None
