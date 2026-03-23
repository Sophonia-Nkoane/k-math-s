from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.ports.repositories import SyncStateRepoPort


SYNC_TABLES_DEFAULT = [
    "AppSettings",
    "Users",
    "Parents",
    "Families",
    "Learners",
    "PaymentOptions",
    "PaymentTerms",
    "Payments",
    "LearnerPayments",
    "AuditLog",
    "AttendanceRecords",
    "AttendanceSummary",
    "AttendancePaymentFeed",
    "AttendanceConfig",
]


@dataclass
class SyncUploadResult:
    run_id: int
    uploaded_count: int
    conflict_count: int
    upload_cursor: str


@dataclass
class SyncDownloadResult:
    downloaded_count: int
    download_cursor: str
    changes: Dict[str, List[Dict[str, Any]]]
    tombstones: List[Dict[str, Any]]


class SyncUseCase:
    def __init__(self, repo: SyncStateRepoPort, sync_tables: Optional[List[str]] = None) -> None:
        self.repo = repo
        self.sync_tables = sync_tables or list(SYNC_TABLES_DEFAULT)

    @staticmethod
    def _utc_now_str() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def start_run(self, user_id: Optional[int]) -> int:
        return self.repo.start_sync_run(user_id)

    def upload(
        self,
        user_id: Optional[int],
        run_id: int,
        changes_by_table: Dict[str, List[Dict[str, Any]]],
        tombstones: List[Dict[str, Any]],
    ) -> SyncUploadResult:
        uploaded_count, _downloaded_count_unused, conflict_count = self.repo.apply_remote_changes(
            changes_by_table=changes_by_table,
            tombstones=tombstones,
        )

        return SyncUploadResult(
            run_id=run_id,
            uploaded_count=uploaded_count,
            conflict_count=conflict_count,
            upload_cursor=self._utc_now_str(),
        )

    def download(self, cursor_utc: str) -> SyncDownloadResult:
        changes = self.repo.get_changes_since(cursor_utc=cursor_utc, tables=self.sync_tables)
        tombstones = self.repo.get_deleted_records(cursor_utc=cursor_utc)
        downloaded_count = sum(len(rows) for rows in changes.values()) + len(tombstones)
        return SyncDownloadResult(
            downloaded_count=downloaded_count,
            download_cursor=self._utc_now_str(),
            changes=changes,
            tombstones=tombstones,
        )

    def commit(
        self,
        client_id: str,
        run_id: int,
        last_upload_cursor: str,
        last_download_cursor: str,
        uploaded_count: int,
        downloaded_count: int,
        conflict_count: int,
        error_text: Optional[str] = None,
    ) -> None:
        status = "SUCCESS" if not error_text else "FAILED"
        self.repo.upsert_client_sync_state(
            client_id=client_id,
            last_upload_cursor=last_upload_cursor,
            last_download_cursor=last_download_cursor,
            successful=error_text is None,
        )
        self.repo.finish_sync_run(
            run_id=run_id,
            status=status,
            uploaded_count=uploaded_count,
            downloaded_count=downloaded_count,
            conflict_count=conflict_count,
            error_text=error_text,
        )
