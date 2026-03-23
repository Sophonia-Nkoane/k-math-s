from __future__ import annotations

import base64
import logging
import os
import socket
import threading
from datetime import datetime
from typing import Any, Dict, List

from adapters.sqlite.repositories import SQLiteSyncStateRepository
from core.use_cases.sync_use_case import SYNC_TABLES_DEFAULT
from data.sync.api_client import SyncAPIClient


class DailySyncService:
    def __init__(self, db_manager, token_service, client_id: str | None = None) -> None:
        self.db_manager = db_manager
        self.token_service = token_service
        self.client_id = client_id or f"desktop-{socket.gethostname()}"
        self.logger = logging.getLogger(self.__class__.__name__)
        self.local_sync_repo = SQLiteSyncStateRepository(db_manager)
        self.sync_tables = list(SYNC_TABLES_DEFAULT)
        self._lock = threading.Lock()

        base_url = os.getenv("SYNC_API_BASE_URL", "http://127.0.0.1:8000")
        self.api_client = SyncAPIClient(base_url=base_url)

    def _go_live_timestamp(self) -> str:
        env_value = os.getenv("SYNC_GO_LIVE_TIMESTAMP")
        if env_value:
            return env_value
        try:
            row = self.db_manager.execute_query(
                "SELECT setting_value FROM SystemSettings WHERE setting_name = 'go_live_timestamp'",
                fetchone=True,
            )
            if row:
                if isinstance(row, dict):
                    return str(row.get("setting_value") or "1970-01-01 00:00:00")
                if hasattr(row, "keys"):
                    return str(row["setting_value"])
                return str(row[0])
        except Exception:
            pass
        return "1970-01-01 00:00:00"

    @staticmethod
    def _is_after_go_live(value: Any, go_live: str) -> bool:
        if value is None:
            return False
        value_str = str(value)
        return value_str >= go_live

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, bytes):
            return {"__b64__": base64.b64encode(value).decode("ascii")}
        if isinstance(value, dict):
            return {k: DailySyncService._json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [DailySyncService._json_safe(v) for v in value]
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        return str(value)

    def run_daily_sync(self, username: str, role: str, user_id: int) -> Dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            return {"status": "skipped", "reason": "sync already running"}

        run_id = self.local_sync_repo.start_sync_run(user_id)
        uploaded_count = 0
        downloaded_count = 0
        conflict_count = 0

        try:
            claims = {
                "scope": "desktop-sync",
                "client_id": self.client_id,
            }
            token = self.token_service.issue_access_token(
                subject=username,
                role=role,
                user_id=user_id,
                minutes=90,
                extra_claims=claims,
            )

            state = self.local_sync_repo.get_client_sync_state(self.client_id)
            last_upload_cursor = str(state.get("last_upload_cursor") or "1970-01-01 00:00:00")
            last_download_cursor = str(state.get("last_download_cursor") or "1970-01-01 00:00:00")
            go_live_ts = self._go_live_timestamp()

            dirty = self.local_sync_repo.get_dirty_rows(self.sync_tables, limit_per_table=2000)
            upload_uuids: Dict[str, List[str]] = {}
            changes_by_table: Dict[str, List[Dict[str, Any]]] = {}
            for table, rows in dirty.items():
                serialized_rows = []
                uuids: List[str] = []
                for row in rows:
                    if not self._is_after_go_live(row.get("last_modified_timestamp"), go_live_ts):
                        continue
                    row_safe = self._json_safe(row)
                    serialized_rows.append(row_safe)
                    row_uuid = row.get("uuid")
                    if row_uuid:
                        uuids.append(str(row_uuid))
                changes_by_table[table] = serialized_rows
                upload_uuids[table] = uuids

            tombstones_all = self.local_sync_repo.get_deleted_records(last_upload_cursor, limit=5000)
            tombstones = [
                t for t in tombstones_all
                if str(t.get("source") or "sqlite") != "remote"
                and self._is_after_go_live(t.get("deleted_at_utc"), go_live_ts)
            ]

            upload_response = self.api_client.upload(
                token,
                {
                    "client_id": self.client_id,
                    "run_id": None,
                    "changes_by_table": changes_by_table,
                    "tombstones": tombstones,
                },
            )

            remote_run_id = int(upload_response.get("run_id") or run_id)
            uploaded_count = int(upload_response.get("uploaded_count") or 0)
            conflict_count = int(upload_response.get("conflict_count") or 0)
            upload_cursor = str(upload_response.get("upload_cursor") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

            for table, uuids in upload_uuids.items():
                if uuids:
                    self.local_sync_repo.mark_rows_clean(table, uuids)

            download_response = self.api_client.download(token, last_download_cursor)
            changes_remote = download_response.get("changes_by_table") or {}
            tombstones_remote = download_response.get("tombstones") or []
            downloaded_count = int(download_response.get("downloaded_count") or 0)
            download_cursor = str(download_response.get("download_cursor") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

            _up, local_downloaded, local_conflicts = self.local_sync_repo.apply_remote_changes(
                changes_by_table=changes_remote,
                tombstones=tombstones_remote,
            )
            downloaded_count = max(downloaded_count, local_downloaded)
            conflict_count += local_conflicts

            for tombstone in tombstones_remote:
                table_name = tombstone.get("table_name")
                record_uuid = tombstone.get("record_uuid")
                if not table_name or not record_uuid:
                    continue
                self.db_manager.execute_query(
                    """
                    UPDATE SyncDeletedRecords
                    SET source = 'remote'
                    WHERE delete_id = (
                        SELECT delete_id
                        FROM SyncDeletedRecords
                        WHERE table_name = ? AND record_uuid = ?
                        ORDER BY delete_id DESC
                        LIMIT 1
                    )
                    """,
                    (table_name, record_uuid),
                    commit=True,
                )

            self.api_client.commit(
                token,
                {
                    "client_id": self.client_id,
                    "run_id": remote_run_id,
                    "last_upload_cursor": upload_cursor,
                    "last_download_cursor": download_cursor,
                    "uploaded_count": uploaded_count,
                    "downloaded_count": downloaded_count,
                    "conflict_count": conflict_count,
                    "error_text": None,
                },
            )

            self.local_sync_repo.upsert_client_sync_state(
                client_id=self.client_id,
                last_upload_cursor=upload_cursor,
                last_download_cursor=download_cursor,
                successful=True,
            )

            self.local_sync_repo.finish_sync_run(
                run_id=run_id,
                status="SUCCESS",
                uploaded_count=uploaded_count,
                downloaded_count=downloaded_count,
                conflict_count=conflict_count,
                error_text=None,
            )

            return {
                "status": "success",
                "run_id": run_id,
                "uploaded_count": uploaded_count,
                "downloaded_count": downloaded_count,
                "conflict_count": conflict_count,
            }
        except Exception as exc:
            self.logger.exception("Daily sync run failed")
            current_state = self.local_sync_repo.get_client_sync_state(self.client_id)
            self.local_sync_repo.upsert_client_sync_state(
                client_id=self.client_id,
                last_upload_cursor=str(current_state.get("last_upload_cursor") or "1970-01-01 00:00:00"),
                last_download_cursor=str(current_state.get("last_download_cursor") or "1970-01-01 00:00:00"),
                successful=False,
            )
            self.local_sync_repo.finish_sync_run(
                run_id=run_id,
                status="FAILED",
                uploaded_count=uploaded_count,
                downloaded_count=downloaded_count,
                conflict_count=conflict_count,
                error_text=str(exc),
            )
            return {"status": "error", "error": str(exc), "run_id": run_id}
        finally:
            self._lock.release()
