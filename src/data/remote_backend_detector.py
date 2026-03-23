import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class RemoteBackendSelection:
    backend: str
    config: Dict[str, object]


def _get_first_env(keys, default=None):
    for key in keys:
        value = os.getenv(key)
        if value is not None and value != "":
            return value
    return default


def _get_int_env(keys, default):
    value = _get_first_env(keys, default=str(default))
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_mysql_config_from_env() -> Optional[Dict[str, object]]:
    host = _get_first_env(["MYSQL_HOST", "DB_HOST"])
    user = _get_first_env(["MYSQL_USER", "DB_USER"])
    password = _get_first_env(["MYSQL_PASSWORD", "DB_PASSWORD"])
    database = _get_first_env(["MYSQL_DATABASE", "DB_NAME"])

    if not all([host, user, password, database]):
        return None

    port = _get_int_env(["MYSQL_PORT", "DB_PORT"], default=3306)
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }


def _probe_mysql(config: Dict[str, object], logger: logging.Logger) -> bool:
    try:
        import mysql.connector  # type: ignore
    except Exception as exc:
        logger.debug("MySQL connector not available for probing: %s", exc)
        return False

    conn = None
    try:
        conn = mysql.connector.connect(connect_timeout=3, **config)
        return bool(conn and conn.is_connected())
    except Exception as exc:
        logger.info("MySQL probe failed: %s", exc)
        return False
    finally:
        try:
            if conn and conn.is_connected():
                conn.close()
        except Exception:
            pass


def detect_remote_backend(logger: Optional[logging.Logger] = None) -> Optional[RemoteBackendSelection]:
    """
    Detect MySQL remote backend.
    Returns None when MySQL is not reachable/configured so the app uses SQLite only.
    """
    logger = logger or logging.getLogger(__name__)

    mysql_config = _build_mysql_config_from_env()
    if mysql_config:
        logger.info("Checking MySQL backend availability...")
        if _probe_mysql(mysql_config, logger):
            logger.info("MySQL backend detected and reachable.")
            return RemoteBackendSelection(backend="mysql", config=mysql_config)
        logger.info("MySQL not reachable. Continuing with local SQLite.")

    logger.info("No reachable MySQL backend detected. Using local SQLite.")
    return None
