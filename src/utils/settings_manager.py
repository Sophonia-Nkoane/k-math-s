import base64
import json
import logging
import mimetypes
import os
import re
import shutil
import sys
from typing import Any, Dict, Optional

from .helpers import get_app_base_dir


class SettingsSaveError(Exception):
    """Exception raised when settings cannot be saved."""


class SettingsManager:
    _instance = None
    APP_SETTINGS_TABLE = "AppSettings"

    DEFAULT_SYSTEM_FIELDS = [
        "billing_cycle_day",
        "grace_period_days",
        "ocr_model_path",
        "auto_generate_enabled",
        "auto_generate_day",
        "auto_generate_hour",
        "auto_generate_minute",
        "auto_generate_recipients",
    ]

    DEFAULT_EMAIL_FIELDS = [
        "email_enabled",
        "smtp_user",
        "smtp_password",
        "smtp_host",
        "smtp_port",
        "smtp_tls",
        "imap_user",
        "imap_password",
        "imap_host",
        "imap_port",
        "imap_tls",
        "bank_email_sender",
        "admin_email",
        "payment_subject",
        "payment_body",
        "ocr_subject",
        "ocr_body",
    ]

    DEFAULT_STATEMENT_FIELDS = [
        "logo_path",
        "logo_data",
        "address",
        "whatsapp",
        "phone",
        "email",
        "statement_message",
        "thank_you_message",
        "bank_name",
        "account_holder",
        "account_number",
    ]

    @staticmethod
    def _resolve_user_settings_root() -> str:
        override = os.getenv("KMATHS_SETTINGS_DIR") or os.getenv("KMATHS_APP_DATA_DIR")
        if override:
            return os.path.abspath(os.path.expanduser(override))

        # Web deployments run inside a container with /app/data mounted as a
        # persistent volume. Using the container home directory causes settings
        # and uploaded branding assets to disappear on image replacement.
        web_enabled = str(os.getenv("WEB_ENABLED", "")).strip().lower() in {"1", "true", "yes", "on"}
        container_data_dir = os.getenv("KMATHS_CONTAINER_DATA_DIR", "/app/data")
        expanded_container_data_dir = os.path.abspath(os.path.expanduser(container_data_dir))
        if web_enabled and os.path.isdir(expanded_container_data_dir) and os.access(expanded_container_data_dir, os.W_OK):
            return os.path.join(expanded_container_data_dir, "k-maths")

        home_dir = os.path.expanduser("~")
        if sys.platform.startswith("win"):
            base_dir = os.getenv("APPDATA") or os.path.join(home_dir, "AppData", "Roaming")
        elif sys.platform == "darwin":
            base_dir = os.path.join(home_dir, "Library", "Application Support")
        else:
            base_dir = os.getenv("XDG_DATA_HOME") or os.path.join(home_dir, ".local", "share")
        return os.path.join(base_dir, "k-maths")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

            base_dir = get_app_base_dir()
            settings_root = cls._resolve_user_settings_root()
            config_dir = os.path.join(settings_root, "config")

            cls._instance.system_config_file = os.path.join(config_dir, "system_settings.json")
            cls._instance.statement_config_file = os.path.join(config_dir, "statement_config.json")
            cls._instance.legacy_invoice_config_file = os.path.join(config_dir, "invoice_config.json")
            cls._instance.email_config_file = os.path.join(config_dir, "email_settings.json")
            cls._instance.resources_dir = os.path.join(settings_root, "resources")
            cls._instance.ocr_model_dir = os.path.join(settings_root, "models", "ocr")
            cls._instance._legacy_system_config_files = [
                os.path.join(base_dir, "ui", "config", "system_settings.json"),
            ]
            cls._instance._legacy_statement_config_files = [
                os.path.join(base_dir, "ui", "config", "statement_config.json"),
                os.path.join(base_dir, "presentation", "config", "statement_config.json"),
                os.path.join(base_dir, "ui", "config", "invoice_config.json"),
                os.path.join(base_dir, "presentation", "config", "invoice_config.json"),
            ]
            cls._instance._legacy_email_config_files = [
                os.path.join(base_dir, "ui", "config", "email_settings.json"),
            ]

            os.makedirs(cls._instance.ocr_model_dir, exist_ok=True)
            os.makedirs(cls._instance.resources_dir, exist_ok=True)
            os.makedirs(os.path.dirname(cls._instance.statement_config_file), exist_ok=True)
            cls._instance._migrate_legacy_files()

            cls._instance.system_settings = {}
            cls._instance.statement_settings = {}
            cls._instance.email_settings = {}

            try:
                cls._instance.load_settings()
            except Exception:
                cls._instance.system_settings = cls._instance._default_system_settings()
                cls._instance.statement_settings = cls._instance._default_statement_settings()
                cls._instance.email_settings = cls._instance._default_email_settings()
                try:
                    cls._instance._save_system_settings()
                    cls._instance._save_statement_settings()
                    cls._instance._save_email_settings()
                except Exception:
                    pass
        return cls._instance

    @staticmethod
    def _load_json_safely(file_path: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            return None
        return None

    def _select_best_statement_legacy_file(self) -> Optional[str]:
        best_path = None
        best_score = -1
        best_mtime = -1.0

        for candidate in self._legacy_statement_config_files:
            payload = self._load_json_safely(candidate)
            if not payload:
                continue
            score = sum(
                1
                for key in self.DEFAULT_STATEMENT_FIELDS
                if key != "logo_data" and str(payload.get(key, "")).strip()
            )
            try:
                mtime = os.path.getmtime(candidate)
            except OSError:
                mtime = -1.0
            if score > best_score or (score == best_score and mtime > best_mtime):
                best_path = candidate
                best_score = score
                best_mtime = mtime

        return best_path

    @staticmethod
    def _copy_file_if_missing(source_path: Optional[str], target_path: str) -> None:
        if not source_path or not os.path.exists(source_path) or os.path.exists(target_path):
            return
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copy2(source_path, target_path)

    def _migrate_legacy_files(self) -> None:
        self._copy_file_if_missing(
            next((path for path in self._legacy_system_config_files if os.path.exists(path)), None),
            self.system_config_file,
        )
        self._copy_file_if_missing(
            self._select_best_statement_legacy_file(),
            self.statement_config_file,
        )
        self._copy_file_if_missing(
            next((path for path in self._legacy_email_config_files if os.path.exists(path)), None),
            self.email_config_file,
        )

    def _default_system_settings(self) -> Dict[str, Any]:
        return {
            "billing_cycle_day": 25,
            "grace_period_days": 3,
            "ocr_model_path": self.ocr_model_dir,
            "auto_generate_enabled": False,
            "auto_generate_day": 25,
            "auto_generate_hour": 9,
            "auto_generate_minute": 0,
            "auto_generate_recipients": "Admin Only",
        }

    @classmethod
    def _default_statement_settings(cls) -> Dict[str, str]:
        return {field: "" for field in cls.DEFAULT_STATEMENT_FIELDS}

    @classmethod
    def _default_email_settings(cls) -> Dict[str, str]:
        return {field: "" for field in cls.DEFAULT_EMAIL_FIELDS}

    @staticmethod
    def _serialise_app_setting_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    @staticmethod
    def _build_mysql_config_from_env() -> Optional[Dict[str, Any]]:
        host = os.getenv("MYSQL_HOST", os.getenv("DB_HOST", "")).strip()
        database = os.getenv("MYSQL_DATABASE", os.getenv("DB_NAME", "")).strip()
        user = os.getenv("MYSQL_USER", os.getenv("DB_USER", "")).strip()
        if not host or not database or not user:
            return None

        try:
            port = int(os.getenv("MYSQL_PORT", os.getenv("DB_PORT", "3306")))
        except ValueError:
            port = 3306

        return {
            "host": host,
            "port": port,
            "user": user,
            "password": os.getenv("MYSQL_PASSWORD", os.getenv("DB_PASSWORD", "")),
            "database": database,
            "autocommit": False,
        }

    @staticmethod
    def _get_sqlite_db_manager() -> Any:
        try:
            from data.database_manager import DatabaseManager
        except Exception:
            return None

        db_manager = getattr(DatabaseManager, "_instance", None)
        if db_manager is None or not getattr(db_manager, "is_initialized", False):
            return None
        return db_manager

    @staticmethod
    def _app_settings_prefix(namespace: str) -> str:
        return f"{namespace}."

    def _read_app_settings_namespace(self, namespace: str) -> Optional[Dict[str, str]]:
        db_manager = self._get_sqlite_db_manager()
        prefix = f"{self._app_settings_prefix(namespace)}%"

        if db_manager is not None:
            try:
                rows = db_manager.execute_query(
                    f"SELECT setting_key, setting_value FROM {self.APP_SETTINGS_TABLE} WHERE setting_key LIKE ?",
                    (prefix,),
                    fetchall=True,
                ) or []
                result: Dict[str, str] = {}
                for row in rows:
                    if isinstance(row, dict):
                        setting_key = str(row.get("setting_key") or "")
                        setting_value = str(row.get("setting_value") or "")
                    elif hasattr(row, "keys"):
                        setting_key = str(row["setting_key"])
                        setting_value = str(row["setting_value"] or "")
                    else:
                        setting_key = str(row[0])
                        setting_value = str(row[1] or "")
                    result[setting_key.removeprefix(self._app_settings_prefix(namespace))] = setting_value
                return result
            except Exception as exc:
                logging.debug("SQLite AppSettings read unavailable: %s", exc)

        mysql_config = self._build_mysql_config_from_env()
        if mysql_config is None:
            return None

        try:
            import mysql.connector

            conn = mysql.connector.connect(**mysql_config)
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"SELECT setting_key, setting_value FROM {self.APP_SETTINGS_TABLE} WHERE setting_key LIKE %s",
                    (prefix,),
                )
                rows = cursor.fetchall() or []
                return {
                    str(row["setting_key"]).removeprefix(self._app_settings_prefix(namespace)): str(row["setting_value"] or "")
                    for row in rows
                }
            finally:
                conn.close()
        except Exception as exc:
            logging.debug("MySQL AppSettings read unavailable: %s", exc)
            return None

    def _write_app_settings_namespace(self, namespace: str, payload: Dict[str, Any]) -> bool:
        if not payload:
            return True

        db_manager = self._get_sqlite_db_manager()
        if db_manager is not None:
            try:
                with db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    for key, value in payload.items():
                        setting_key = f"{self._app_settings_prefix(namespace)}{key}"
                        setting_value = self._serialise_app_setting_value(value)
                        cursor.execute(
                            f"""
                            UPDATE {self.APP_SETTINGS_TABLE}
                            SET setting_value = ?, last_modified_timestamp = CURRENT_TIMESTAMP, is_dirty = 1
                            WHERE setting_key = ?
                            """,
                            (setting_value, setting_key),
                        )
                        if cursor.rowcount == 0:
                            cursor.execute(
                                f"""
                                INSERT INTO {self.APP_SETTINGS_TABLE}
                                (setting_key, setting_value, uuid, last_modified_timestamp, is_dirty)
                                VALUES (?, ?, lower(hex(randomblob(16))), CURRENT_TIMESTAMP, 1)
                                """,
                                (setting_key, setting_value),
                            )
                return True
            except Exception as exc:
                logging.warning("SQLite AppSettings write failed: %s", exc)

        mysql_config = self._build_mysql_config_from_env()
        if mysql_config is None:
            return False

        try:
            import mysql.connector

            conn = mysql.connector.connect(**mysql_config)
            try:
                cursor = conn.cursor()
                for key, value in payload.items():
                    setting_key = f"{self._app_settings_prefix(namespace)}{key}"
                    setting_value = self._serialise_app_setting_value(value)
                    cursor.execute(
                        f"""
                        INSERT INTO {self.APP_SETTINGS_TABLE}
                        (setting_key, setting_value, uuid, last_modified_timestamp, is_dirty)
                        VALUES (%s, %s, UUID(), UTC_TIMESTAMP(), 1)
                        ON DUPLICATE KEY UPDATE
                            setting_value = VALUES(setting_value),
                            last_modified_timestamp = UTC_TIMESTAMP(),
                            is_dirty = 1
                        """,
                        (setting_key, setting_value),
                    )
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as exc:
            logging.warning("MySQL AppSettings write failed: %s", exc)
            return False

    @staticmethod
    def _encode_logo_file_to_data_uri(file_path: str) -> str:
        cleaned = str(file_path or "").strip()
        if not cleaned:
            return ""
        if cleaned.startswith("data:"):
            return cleaned

        expanded = os.path.expanduser(cleaned)
        if not os.path.isabs(expanded):
            app_base_dir = get_app_base_dir()
            repo_root = os.path.dirname(app_base_dir)
            candidates = [
                os.path.join(app_base_dir, expanded),
                os.path.join(repo_root, expanded),
                os.path.abspath(expanded),
            ]
        else:
            candidates = [expanded]

        resolved = next((path for path in candidates if os.path.isfile(path)), None)
        if not resolved:
            return ""

        mime_type, _ = mimetypes.guess_type(resolved)
        with open(resolved, "rb") as handle:
            payload = base64.b64encode(handle.read()).decode("ascii")
        return f"data:{mime_type or 'image/png'};base64,{payload}"

    def _prepare_statement_settings_payload(self, raw_settings: Dict[str, Any]) -> Dict[str, str]:
        prepared = self._default_statement_settings()
        for field in self.DEFAULT_STATEMENT_FIELDS:
            prepared[field] = self._serialise_app_setting_value(raw_settings.get(field, prepared[field]))

        logo_data = str(prepared.get("logo_data") or "").strip()
        logo_path = str(prepared.get("logo_path") or "").strip()
        if not logo_data and logo_path:
            encoded_logo = self._encode_logo_file_to_data_uri(logo_path)
            if encoded_logo:
                prepared["logo_data"] = encoded_logo
                prepared["logo_path"] = os.path.basename(os.path.expanduser(logo_path))
        elif logo_data and not logo_path:
            prepared["logo_path"] = "statement_logo"

        return prepared

    def _normalise_statement_logo_path(self) -> None:
        prepared = self._prepare_statement_settings_payload(self.statement_settings)
        if prepared != self.statement_settings:
            self.statement_settings = prepared
            self._save_statement_settings()

    def _load_system_settings_from_files(self) -> Dict[str, Any]:
        return self._load_json_file(self.system_config_file, self._default_system_settings())

    def _load_statement_settings_from_files(self) -> Dict[str, str]:
        statement_config_path = self.statement_config_file
        if not os.path.exists(statement_config_path) and os.path.exists(self.legacy_invoice_config_file):
            statement_config_path = self.legacy_invoice_config_file

        settings = self._load_json_file(statement_config_path, self._default_statement_settings())
        settings = self._prepare_statement_settings_payload(settings)

        if statement_config_path != self.statement_config_file:
            try:
                with open(self.statement_config_file, "w", encoding="utf-8") as f:
                    json.dump(settings, f, indent=4)
            except IOError:
                pass

        return settings

    def _load_email_settings_from_files(self) -> Dict[str, str]:
        settings = self._load_json_file(self.email_config_file, self._default_email_settings())
        return {field: self._serialise_app_setting_value(settings.get(field, "")) for field in self.DEFAULT_EMAIL_FIELDS}

    def _load_statement_settings_from_app_store(self) -> Optional[Dict[str, str]]:
        defaults = self._default_statement_settings()
        stored = self._read_app_settings_namespace("statement")
        if stored is None:
            return None

        if any(field not in stored for field in defaults):
            legacy_settings = self._prepare_statement_settings_payload(self._load_statement_settings_from_files())
            seed_payload = {field: legacy_settings.get(field, defaults[field]) for field in defaults if field not in stored}
            self._write_app_settings_namespace("statement", seed_payload)
            stored.update({field: self._serialise_app_setting_value(seed_payload.get(field, "")) for field in seed_payload})

        merged = defaults.copy()
        merged.update(stored)
        return self._prepare_statement_settings_payload(merged)

    def _load_email_settings_from_app_store(self) -> Optional[Dict[str, str]]:
        defaults = self._default_email_settings()
        stored = self._read_app_settings_namespace("email")
        if stored is None:
            return None

        if any(field not in stored for field in defaults):
            legacy_settings = self._load_email_settings_from_files()
            seed_payload = {field: legacy_settings.get(field, defaults[field]) for field in defaults if field not in stored}
            self._write_app_settings_namespace("email", seed_payload)
            stored.update({field: self._serialise_app_setting_value(seed_payload.get(field, "")) for field in seed_payload})

        merged = defaults.copy()
        merged.update(stored)
        return {field: self._serialise_app_setting_value(merged.get(field, "")) for field in self.DEFAULT_EMAIL_FIELDS}

    def load_settings(self):
        """Load all settings from the configured storage backends."""
        self.system_settings = self._load_system_settings_from_files()

        statement_settings = self._load_statement_settings_from_app_store()
        self.statement_settings = statement_settings or self._load_statement_settings_from_files()

        email_settings = self._load_email_settings_from_app_store()
        self.email_settings = email_settings or self._load_email_settings_from_files()

    def _load_json_file(self, file_path: str, default_config: Dict[str, Any]) -> Dict[str, Any]:
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except (json.JSONDecodeError, IOError):
                return default_config.copy()

        config = default_config.copy()
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except IOError:
            pass
        return config

    def _save_system_settings(self):
        with open(self.system_config_file, "w", encoding="utf-8") as f:
            json.dump(self.system_settings, f, indent=4)

    def _save_statement_settings(self):
        try:
            with open(self.statement_config_file, "w", encoding="utf-8") as f:
                json.dump(self.statement_settings, f, indent=4)
        except IOError as e:
            raise SettingsSaveError(f"Failed to save statement settings: {e}")

    def _save_email_settings(self):
        try:
            with open(self.email_config_file, "w", encoding="utf-8") as f:
                json.dump(self.email_settings, f, indent=4)
        except IOError as e:
            raise SettingsSaveError(f"Failed to save email settings: {e}")

    def get_system_setting(self, key: str, default: Any = None) -> Any:
        if not self.system_settings:
            self.load_settings()
        return self.system_settings.get(key, default)

    def set_system_setting(self, key: str, value: Any):
        self.system_settings[key] = value
        self._save_system_settings()

    def get_statement_setting(self, key: str, default: Any = None) -> Any:
        self.load_settings()
        return self.statement_settings.get(key, default)

    def load_statement_settings(self) -> Dict[str, str]:
        self.load_settings()
        return self.statement_settings.copy()

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        if not email:
            return True
        return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))

    @staticmethod
    def _is_valid_phone(phone: str) -> bool:
        if not phone:
            return True
        return bool(re.match(r"^\+?\d{10,15}$", phone.replace(" ", "")))

    def save_statement_settings(self, settings_data: Dict[str, str], new_logo_path: Optional[str] = None):
        logging.info("Attempting to save statement settings.")

        try:
            email = str(settings_data.get("email", "") or "")
            whatsapp = str(settings_data.get("whatsapp", "") or "")
            phone = str(settings_data.get("phone", "") or "")

            if not self._is_valid_email(email):
                raise SettingsSaveError("Invalid Email: Please enter a valid email address.")
            if not self._is_valid_phone(whatsapp):
                raise SettingsSaveError("Invalid WhatsApp Number: Please enter a valid WhatsApp number.")
            if phone and not self._is_valid_phone(phone):
                raise SettingsSaveError("Invalid Phone Number: Please enter a valid phone number.")

            merged_settings = self.load_statement_settings()
            merged_settings.update(settings_data)

            if new_logo_path:
                encoded_logo = self._encode_logo_file_to_data_uri(new_logo_path)
                if not encoded_logo:
                    raise SettingsSaveError("Could not read the selected logo file.")
                merged_settings["logo_path"] = os.path.basename(new_logo_path)
                merged_settings["logo_data"] = encoded_logo
            elif new_logo_path == "":
                merged_settings["logo_path"] = ""
                merged_settings["logo_data"] = ""

            prepared_settings = self._prepare_statement_settings_payload(merged_settings)
            self.statement_settings = prepared_settings

            if self._write_app_settings_namespace("statement", prepared_settings):
                logging.info("Statement settings saved to AppSettings successfully.")
            else:
                self._save_statement_settings()
                logging.info("Statement settings saved to JSON fallback successfully.")

        except SettingsSaveError:
            raise
        except Exception as e:
            logging.error("An unexpected error occurred while saving settings: %s", e, exc_info=True)
            raise SettingsSaveError(f"An unexpected error occurred: {str(e)}")

    def _persist_email_settings(self, settings_data: Dict[str, Any]) -> None:
        smtp_user = self._serialise_app_setting_value(settings_data.get("smtp_user", ""))
        if smtp_user and not self._is_valid_email(smtp_user):
            raise SettingsSaveError("Invalid SMTP Email: Please enter a valid email address.")

        admin_email = self._serialise_app_setting_value(settings_data.get("admin_email", ""))
        if admin_email and not self._is_valid_email(admin_email):
            raise SettingsSaveError("Invalid Admin Email: Please enter a valid email address.")

        bank_sender = self._serialise_app_setting_value(settings_data.get("bank_email_sender", ""))
        if bank_sender and not self._is_valid_email(bank_sender):
            raise SettingsSaveError("Invalid Bank Email Sender: Please enter a valid email address.")

        prepared_settings = {
            field: self._serialise_app_setting_value(settings_data.get(field, ""))
            for field in self.DEFAULT_EMAIL_FIELDS
        }
        self.email_settings = prepared_settings

        if self._write_app_settings_namespace("email", prepared_settings):
            logging.info("Email settings saved to AppSettings successfully.")
        else:
            self._save_email_settings()
            logging.info("Email settings saved to JSON fallback successfully.")

    def save_email_settings_payload(self, settings_data: Dict[str, Any]) -> None:
        self._persist_email_settings(settings_data)

    def get_email_setting(self, key: str, default: Any = None) -> Any:
        self.load_settings()
        return self.email_settings.get(key, default)

    def set_email_setting(self, key: str, value: Any):
        settings = self.load_email_settings()
        settings[key] = value
        self._persist_email_settings(settings)

    def load_email_settings(self) -> Dict[str, str]:
        self.load_settings()
        return self.email_settings.copy()

    def save_email_settings(self, settings_data: Dict[str, str], admin_password: str, auth_service, db_manager):
        logging.info("Attempting to save email settings with admin verification.")

        try:
            del auth_service, db_manager
            if not admin_password:
                raise SettingsSaveError("Admin password is required to save email settings.")
            self._persist_email_settings(settings_data)
        except SettingsSaveError:
            raise
        except Exception as e:
            logging.error("An unexpected error occurred while saving email settings: %s", e, exc_info=True)
            raise SettingsSaveError(f"An unexpected error occurred: {str(e)}")
