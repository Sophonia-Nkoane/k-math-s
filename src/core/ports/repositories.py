from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple


class UserRepoPort(Protocol):
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        ...

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        ...

    def list_users(self, exclude_username: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    def create_user(self, username: str, password_hash: str, role: str) -> int:
        ...

    def update_user_password(self, username: str, password_hash: str) -> bool:
        ...

    def update_user_role(self, username: str, role: str) -> bool:
        ...

    def delete_user(self, username: str) -> bool:
        ...

    def count_admin_users(self) -> int:
        ...

    def list_users_paged(
        self,
        exclude_username: Optional[str],
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
    ) -> Tuple[List[Dict[str, Any]], int]:
        ...


class LearnerRepoPort(Protocol):
    def list_learners(
        self,
        search: Optional[str] = None,
        grade: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        ...

    def get_learner(self, acc_no: str) -> Optional[Dict[str, Any]]:
        ...

    def create_learner(self, payload: Dict[str, Any]) -> str:
        ...

    def update_learner(self, acc_no: str, payload: Dict[str, Any]) -> bool:
        ...

    def list_learners_for_family(self, family_id: int) -> List[Dict[str, Any]]:
        ...

    def list_learners_by_grade(self, grade: int) -> List[Dict[str, Any]]:
        ...

    def set_learner_active(self, acc_no: str, is_active: bool, reason: Optional[str] = None) -> bool:
        ...

    def delete_learner(self, acc_no: str) -> bool:
        ...

    def get_grade_payment_rule(self, grade: int) -> Optional[Dict[str, Any]]:
        ...

    def set_learner_progress(self, acc_no: str, progress_percentage: float) -> bool:
        ...

    def get_learner_progress_status(self, acc_no: str) -> Optional[Dict[str, Any]]:
        ...

    def record_payment_change(self, acc_no: str, change_description: str) -> bool:
        ...

    def list_learners_paged(
        self,
        search: Optional[str],
        grade: Optional[int],
        is_active: Optional[bool],
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
    ) -> Tuple[List[Dict[str, Any]], int]:
        ...


class FamilyRepoPort(Protocol):
    def list_families(self) -> List[Dict[str, Any]]:
        ...

    def get_family(self, family_id: int) -> Optional[Dict[str, Any]]:
        ...

    def create_family(self, payload: Dict[str, Any]) -> int:
        ...

    def update_family(self, family_id: int, payload: Dict[str, Any]) -> bool:
        ...

    def delete_family(self, family_id: int) -> bool:
        ...

    def list_families_paged(
        self,
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
    ) -> Tuple[List[Dict[str, Any]], int]:
        ...


class PaymentRepoPort(Protocol):
    def list_payments(
        self,
        learner_acc_no: Optional[str] = None,
        family_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        ...

    def create_payment(self, payload: Dict[str, Any]) -> int:
        ...

    def delete_payment(self, payment_id: int) -> bool:
        ...

    def get_balance_for_learner(self, acc_no: str) -> float:
        ...

    def get_balance_for_family(self, family_id: int) -> float:
        ...

    def list_payment_options(self) -> List[Dict[str, Any]]:
        ...

    def create_payment_option(self, payload: Dict[str, Any]) -> int:
        ...

    def update_payment_option(self, option_id: int, payload: Dict[str, Any]) -> bool:
        ...

    def delete_payment_option(self, option_id: int) -> bool:
        ...

    def list_payment_terms(self) -> List[Dict[str, Any]]:
        ...

    def create_payment_term(self, payload: Dict[str, Any]) -> int:
        ...

    def update_payment_term(self, term_id: int, payload: Dict[str, Any]) -> bool:
        ...

    def delete_payment_term(self, term_id: int) -> bool:
        ...

    def get_payment_statistics(
        self,
        month_year: str,
        include_on_track: bool = True,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        ...

    def get_payment_trends(self, months: int = 12) -> List[Dict[str, Any]]:
        ...

    def list_payments_paged(
        self,
        learner_acc_no: Optional[str],
        family_id: Optional[int],
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
    ) -> Tuple[List[Dict[str, Any]], int]:
        ...

    def list_payment_options_paged(
        self,
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
    ) -> Tuple[List[Dict[str, Any]], int]:
        ...

    def list_payment_terms_paged(
        self,
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
    ) -> Tuple[List[Dict[str, Any]], int]:
        ...


class AttendanceRepoPort(Protocol):
    def list_attendance_for_date(
        self,
        iso_date: str,
        grade: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        ...

    def record_attendance(self, payload: Dict[str, Any]) -> int:
        ...

    def list_attendance_history(
        self,
        start_date: str,
        end_date: str,
        learner_acc_no: Optional[str] = None,
        grade: Optional[int] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        ...

    def get_attendance_summary(
        self,
        start_date: str,
        end_date: str,
        grade: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        ...


class AuditRepoPort(Protocol):
    def log_action(
        self,
        user_id: Optional[int],
        action_type: str,
        object_type: str,
        object_id: str,
        details: str,
    ) -> None:
        ...

    def list_audit(
        self,
        limit: Optional[int] = 200,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        action_type: Optional[str] = None,
        username: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ...


class SyncStateRepoPort(Protocol):
    def start_sync_run(self, user_id: Optional[int]) -> int:
        ...

    def finish_sync_run(
        self,
        run_id: int,
        status: str,
        uploaded_count: int,
        downloaded_count: int,
        conflict_count: int,
        error_text: Optional[str] = None,
    ) -> None:
        ...

    def get_client_sync_state(self, client_id: str) -> Dict[str, Any]:
        ...

    def upsert_client_sync_state(
        self,
        client_id: str,
        last_upload_cursor: str,
        last_download_cursor: str,
        successful: bool,
    ) -> None:
        ...

    def get_dirty_rows(
        self,
        tables: List[str],
        limit_per_table: int = 500,
    ) -> Dict[str, List[Dict[str, Any]]]:
        ...

    def mark_rows_clean(self, table_name: str, uuids: List[str]) -> None:
        ...

    def get_changes_since(
        self,
        cursor_utc: str,
        tables: List[str],
        limit_per_table: int = 500,
    ) -> Dict[str, List[Dict[str, Any]]]:
        ...

    def get_deleted_records(
        self,
        cursor_utc: str,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        ...

    def apply_remote_changes(
        self,
        changes_by_table: Dict[str, List[Dict[str, Any]]],
        tombstones: List[Dict[str, Any]],
    ) -> Tuple[int, int, int]:
        ...

    def log_conflict(
        self,
        table_name: str,
        record_uuid: str,
        local_ts: str,
        remote_ts: str,
        winner: str,
        user_id: Optional[int],
    ) -> None:
        ...
