from __future__ import annotations

import logging
import os
import threading
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from core.services.token_service import TokenService
from data.sync.daily_sync_service import DailySyncService


class DailySyncScheduler(QObject):
    syncStarted = Signal()
    syncFinished = Signal(dict)
    syncFailed = Signal(str)

    def __init__(self, main_window, db_manager, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self.enabled = str(os.getenv("SYNC_V2_ENABLED", "true")).lower() in {"1", "true", "yes"}
        self.daily_time = os.getenv("SYNC_DAILY_TIME", "02:00")
        self.client_id = os.getenv("SYNC_CLIENT_ID")

        self.token_service = TokenService()
        self.sync_service = DailySyncService(db_manager, self.token_service, client_id=self.client_id)

        self.timer = QTimer(self)
        self.timer.setInterval(60_000)
        self.timer.timeout.connect(self._check_schedule)
        self._running_thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.enabled:
            self.logger.info("Daily sync scheduler disabled by SYNC_V2_ENABLED")
            return
        self.timer.start()
        self.logger.info("Daily sync scheduler started with target time %s", self.daily_time)
        self._check_schedule()

    def stop(self) -> None:
        self.timer.stop()

    def _parse_daily_time(self) -> tuple[int, int]:
        try:
            hour_str, minute_str = self.daily_time.split(":", 1)
            return int(hour_str), int(minute_str)
        except Exception:
            return 2, 0

    def _last_successful_sync_date(self):
        state = self.sync_service.local_sync_repo.get_client_sync_state(self.sync_service.client_id)
        value = state.get("last_successful_sync_at_utc")
        if not value:
            return None
        if isinstance(value, datetime):
            return value.date()
        try:
            return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").date()
        except Exception:
            return None

    def _is_due_now(self) -> bool:
        now = datetime.now()
        target_hour, target_min = self._parse_daily_time()
        if (now.hour, now.minute) < (target_hour, target_min):
            return False

        last_success_date = self._last_successful_sync_date()
        if last_success_date == now.date():
            return False

        return True

    def _check_schedule(self) -> None:
        if not self.enabled:
            return

        if self._running_thread and self._running_thread.is_alive():
            return

        if not self.main_window or getattr(self.main_window, "current_user_id", None) is None:
            return

        if not self._is_due_now():
            return

        username = getattr(self.main_window, "current_username", None) or "unknown"
        role = getattr(self.main_window, "current_user_role", None) or "user"
        user_id = int(getattr(self.main_window, "current_user_id", 0) or 0)
        if user_id <= 0:
            return

        self.syncStarted.emit()
        self._running_thread = threading.Thread(
            target=self._run_sync_worker,
            args=(username, role, user_id),
            daemon=True,
            name="DailySyncWorker",
        )
        self._running_thread.start()

    def run_now(self) -> None:
        """Manual trigger from UI actions if needed."""
        self._check_schedule()

    def force_run(self) -> None:
        """Manual trigger that bypasses time/date checks."""
        if not self.enabled:
            return

        if self._running_thread and self._running_thread.is_alive():
            return

        if not self.main_window or getattr(self.main_window, "current_user_id", None) is None:
            return

        username = getattr(self.main_window, "current_username", None) or "unknown"
        role = getattr(self.main_window, "current_user_role", None) or "user"
        user_id = int(getattr(self.main_window, "current_user_id", 0) or 0)
        
        self.syncStarted.emit()
        self._running_thread = threading.Thread(
            target=self._run_sync_worker,
            args=(username, role, user_id),
            daemon=True,
            name="ManualSyncWorker",
        )
        self._running_thread.start()

    def _run_sync_worker(self, username: str, role: str, user_id: int) -> None:
        result = self.sync_service.run_daily_sync(username=username, role=role, user_id=user_id)
        if result.get("status") == "success":
            self.syncFinished.emit(result)
            self.logger.info(
                "Daily sync finished | uploaded=%s downloaded=%s conflicts=%s",
                result.get("uploaded_count"),
                result.get("downloaded_count"),
                result.get("conflict_count"),
            )
        else:
            error = str(result.get("error") or "Unknown sync error")
            self.syncFailed.emit(error)
            self.logger.error("Daily sync failed: %s", error)
