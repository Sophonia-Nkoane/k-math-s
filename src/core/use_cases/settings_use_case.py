from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.use_cases.auth_use_case import AuthUseCase
from utils.settings_manager import SettingsManager


class SettingsUseCase:
    def __init__(self, auth_use_case: AuthUseCase) -> None:
        self.auth_use_case = auth_use_case
        self.settings_manager = SettingsManager()

    def get_system_settings(self) -> Dict[str, Any]:
        keys = [
            "billing_cycle_day",
            "grace_period_days",
            "ocr_model_path",
            "auto_generate_enabled",
            "auto_generate_day",
            "auto_generate_hour",
            "auto_generate_minute",
            "auto_generate_recipients",
        ]
        return {key: self.settings_manager.get_system_setting(key) for key in keys}

    def save_system_settings(self, payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        for key, value in payload.items():
            self.settings_manager.set_system_setting(key, value)
        return True, None

    def get_statement_settings(self) -> Dict[str, Any]:
        return self.settings_manager.load_statement_settings()

    def save_statement_settings(
        self,
        payload: Dict[str, Any],
        logo_file_path: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        try:
            self.settings_manager.save_statement_settings(payload, logo_file_path)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def get_email_settings(self) -> Dict[str, Any]:
        return self.settings_manager.load_email_settings()

    def save_email_settings(
        self,
        payload: Dict[str, Any],
        admin_password: str,
        actor_user_id: Optional[int],
        actor_role: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        if str(actor_role or "").lower() != "admin":
            return False, "Admin role required"
        if not actor_user_id:
            return False, "Missing actor user id"
        if not self.auth_use_case.verify_user_password(int(actor_user_id), admin_password):
            return False, "Admin password verification failed"
        try:
            current_settings = self.settings_manager.load_email_settings()
            current_settings.update(payload)
            self.settings_manager.save_email_settings_payload(current_settings)
            return True, None
        except Exception as exc:
            return False, str(exc)
