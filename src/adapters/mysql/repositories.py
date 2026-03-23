from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
import calendar
from datetime import date, datetime, timedelta
from typing import Any, Dict, Generator, List, Optional, Tuple

import mysql.connector

from core.ports.repositories import (
    AttendanceRepoPort,
    AuditRepoPort,
    FamilyRepoPort,
    PaymentRepoPort,
    LearnerRepoPort,
    SyncStateRepoPort,
    UserRepoPort,
)
from utils.payment_schedule import (
    normalize_due_days,
    normalize_scheduled_dates,
    next_scheduled_date,
    primary_due_day,
    serialize_due_days,
    serialize_scheduled_dates,
)


logger = logging.getLogger(__name__)
_SCHEMA_COMPAT_CACHE: set[tuple[str, int, str, str]] = set()


def _mysql_config_signature(mysql_config: Dict[str, Any]) -> tuple[str, int, str, str]:
    return (
        str(mysql_config.get("host") or ""),
        int(mysql_config.get("port") or 3306),
        str(mysql_config.get("database") or ""),
        str(mysql_config.get("user") or ""),
    )


def _mysql_table_exists(cursor, database: str, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        LIMIT 1
        """,
        (database, table_name),
    )
    return cursor.fetchone() is not None


def _mysql_column_exists(cursor, database: str, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        LIMIT 1
        """,
        (database, table_name, column_name),
    )
    return cursor.fetchone() is not None


def _rename_mysql_table(cursor, database: str, old_name: str, new_name: str) -> None:
    if not _mysql_table_exists(cursor, database, old_name) or _mysql_table_exists(cursor, database, new_name):
        return
    cursor.execute(f"RENAME TABLE `{old_name}` TO `{new_name}`")


def _rename_mysql_column(
    cursor,
    database: str,
    table_name: str,
    old_name: str,
    new_name: str,
    column_definition: str,
) -> None:
    if not _mysql_table_exists(cursor, database, table_name):
        return
    if not _mysql_column_exists(cursor, database, table_name, old_name):
        return
    if _mysql_column_exists(cursor, database, table_name, new_name):
        return
    cursor.execute(
        f"ALTER TABLE `{table_name}` CHANGE COLUMN `{old_name}` `{new_name}` {column_definition}"
    )


def _replace_mysql_table_name_value(cursor, database: str, table_name: str, old_value: str, new_value: str) -> None:
    if not _mysql_table_exists(cursor, database, table_name):
        return
    if not _mysql_column_exists(cursor, database, table_name, "table_name"):
        return
    cursor.execute(
        f"UPDATE `{table_name}` SET `table_name` = %s WHERE `table_name` = %s",
        (new_value, old_value),
    )


def _ensure_mysql_app_settings_table(cursor, database: str) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS `AppSettings` (
            `setting_key` VARCHAR(120) PRIMARY KEY,
            `setting_value` LONGTEXT,
            `uuid` VARCHAR(64) UNIQUE DEFAULT (UUID()),
            `last_modified_timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            `is_dirty` TINYINT DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )

    if _mysql_column_exists(cursor, database, "AppSettings", "setting_value"):
        cursor.execute("ALTER TABLE `AppSettings` MODIFY COLUMN `setting_value` LONGTEXT")

    if not _mysql_column_exists(cursor, database, "AppSettings", "uuid"):
        cursor.execute("ALTER TABLE `AppSettings` ADD COLUMN `uuid` VARCHAR(64) UNIQUE NULL DEFAULT (UUID())")
    if not _mysql_column_exists(cursor, database, "AppSettings", "last_modified_timestamp"):
        cursor.execute(
            """
            ALTER TABLE `AppSettings`
            ADD COLUMN `last_modified_timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            """
        )
    if not _mysql_column_exists(cursor, database, "AppSettings", "is_dirty"):
        cursor.execute("ALTER TABLE `AppSettings` ADD COLUMN `is_dirty` TINYINT DEFAULT 0")

    cursor.execute(
        """
        UPDATE `AppSettings`
        SET
            `uuid` = COALESCE(NULLIF(`uuid`, ''), UUID()),
            `last_modified_timestamp` = COALESCE(`last_modified_timestamp`, UTC_TIMESTAMP()),
            `is_dirty` = COALESCE(`is_dirty`, 0)
        """
    )


def ensure_mysql_learner_schema(mysql_config: Dict[str, Any]) -> None:
    signature = _mysql_config_signature(mysql_config)
    if signature in _SCHEMA_COMPAT_CACHE:
        return

    conn = mysql.connector.connect(**mysql_config)
    try:
        database = str(mysql_config.get("database") or "")
        cursor = conn.cursor()

        _rename_mysql_table(cursor, database, "Students", "Learners")
        _rename_mysql_table(cursor, database, "StudentPayments", "LearnerPayments")

        _rename_mysql_column(cursor, database, "Learners", "is_new_student", "is_new_learner", "TINYINT NOT NULL DEFAULT 1")
        _rename_mysql_column(cursor, database, "Payments", "student_id", "learner_id", "VARCHAR(64)")
        _rename_mysql_column(cursor, database, "LearnerPayments", "student_id", "learner_id", "VARCHAR(64) NOT NULL")
        _rename_mysql_column(cursor, database, "Archive", "student_acc_no", "learner_acc_no", "VARCHAR(64) NOT NULL")
        _rename_mysql_column(cursor, database, "AttendanceRecords", "student_acc_no", "learner_acc_no", "VARCHAR(64) NOT NULL")
        _rename_mysql_column(cursor, database, "AttendanceRecords", "student_name", "learner_name", "VARCHAR(120) NOT NULL")
        _rename_mysql_column(cursor, database, "AttendanceRecords", "student_surname", "learner_surname", "VARCHAR(120) NOT NULL")
        _rename_mysql_column(cursor, database, "AttendanceSummary", "student_acc_no", "learner_acc_no", "VARCHAR(64) NOT NULL")
        _rename_mysql_column(cursor, database, "AttendancePaymentFeed", "student_acc_no", "learner_acc_no", "VARCHAR(64) NOT NULL")
        _rename_mysql_column(cursor, database, "AttendancePaymentFeed", "student_name", "learner_name", "VARCHAR(120) NOT NULL")
        _rename_mysql_column(cursor, database, "AttendancePaymentFeed", "student_surname", "learner_surname", "VARCHAR(120) NOT NULL")
        _rename_mysql_column(cursor, database, "statement_counters", "student_id", "learner_id", "VARCHAR(64) NOT NULL")

        _replace_mysql_table_name_value(cursor, database, "SyncDeletedRecords", "Students", "Learners")
        _replace_mysql_table_name_value(cursor, database, "SyncDeletedRecords", "StudentPayments", "LearnerPayments")
        _replace_mysql_table_name_value(cursor, database, "SyncConflicts", "Students", "Learners")
        _replace_mysql_table_name_value(cursor, database, "SyncConflicts", "StudentPayments", "LearnerPayments")
        _ensure_mysql_app_settings_table(cursor, database)
        if _mysql_table_exists(cursor, database, "LearnerPayments") and not _mysql_column_exists(
            cursor, database, "LearnerPayments", "due_days_of_month"
        ):
            cursor.execute("ALTER TABLE `LearnerPayments` ADD COLUMN `due_days_of_month` LONGTEXT NULL")
            cursor.execute(
                """
                UPDATE `LearnerPayments`
                SET `due_days_of_month` = CONCAT('[', COALESCE(`due_day_of_month`, 1), ']')
                WHERE `due_days_of_month` IS NULL OR TRIM(`due_days_of_month`) = ''
                """
            )
        if _mysql_table_exists(cursor, database, "LearnerPayments") and not _mysql_column_exists(
            cursor, database, "LearnerPayments", "scheduled_payment_dates"
        ):
            cursor.execute("ALTER TABLE `LearnerPayments` ADD COLUMN `scheduled_payment_dates` LONGTEXT NULL")

        conn.commit()
        _SCHEMA_COMPAT_CACHE.add(signature)
    except Exception:
        logger.exception("MySQL learner schema compatibility upgrade failed")
        raise
    finally:
        conn.close()


def _as_iso_date(value: Any, default: Optional[str] = None) -> str:
    if value is None:
        return default or date.today().isoformat()
    if isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class MySQLConnectionMixin:
    def __init__(self, mysql_config: Dict[str, Any]) -> None:
        self.mysql_config = mysql_config
        ensure_mysql_learner_schema(mysql_config)

    @contextmanager
    def _connection(self) -> Generator[mysql.connector.MySQLConnection, None, None]:
        conn = mysql.connector.connect(**self.mysql_config)
        try:
            yield conn
        finally:
            conn.close()


class MySQLUserRepository(MySQLConnectionMixin, UserRepoPort):
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT user_id, username, password, role FROM Users WHERE username = %s",
                (username,),
            )
            return cursor.fetchone()

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT user_id, username, password, role FROM Users WHERE user_id = %s",
                (user_id,),
            )
            return cursor.fetchone()

    def list_users(self, exclude_username: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            if exclude_username:
                cursor.execute(
                    "SELECT user_id, username, role FROM Users WHERE username != %s ORDER BY username",
                    (exclude_username,),
                )
            else:
                cursor.execute("SELECT user_id, username, role FROM Users ORDER BY username")
            return cursor.fetchall() or []

    def create_user(self, username: str, password_hash: str, role: str) -> int:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Users (username, password, role) VALUES (%s, %s, %s)",
                (username, password_hash, role),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def update_user_password(self, username: str, password_hash: str) -> bool:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Users SET password = %s WHERE username = %s", (password_hash, username))
            conn.commit()
            return cursor.rowcount > 0

    def update_user_role(self, username: str, role: str) -> bool:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Users SET role = %s WHERE username = %s", (role, username))
            conn.commit()
            return cursor.rowcount > 0

    def delete_user(self, username: str) -> bool:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Users WHERE username = %s", (username,))
            conn.commit()
            return cursor.rowcount > 0

    def count_admin_users(self) -> int:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Users WHERE LOWER(role) = 'admin'")
            row = cursor.fetchone()
            return int((row[0] if row else 0) or 0)


class MySQLAuditRepository(MySQLConnectionMixin, AuditRepoPort):
    def log_action(
        self,
        user_id: Optional[int],
        action_type: str,
        object_type: str,
        object_id: str,
        details: str,
    ) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO AuditLog (user_id, action_type, object_type, object_id, timestamp, details)
                VALUES (%s, %s, %s, %s, UTC_TIMESTAMP(), %s)
                """,
                (user_id, action_type, object_type, object_id, details),
            )
            conn.commit()

    def list_audit(
        self,
        limit: Optional[int] = 200,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        action_type: Optional[str] = None,
        username: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT
                a.log_id,
                a.user_id,
                COALESCE(u.username, 'System') AS username,
                a.action_type,
                a.object_type,
                a.object_id,
                a.timestamp,
                a.details
            FROM AuditLog a
            LEFT JOIN Users u ON a.user_id = u.user_id
            WHERE 1 = 1
        """
        params: List[Any] = []

        if start_date:
            query += " AND DATE(a.timestamp) >= DATE(%s)"
            params.append(start_date)
        if end_date:
            query += " AND DATE(a.timestamp) <= DATE(%s)"
            params.append(end_date)
        if action_type:
            query += " AND a.action_type = %s"
            params.append(action_type)
        if username:
            query += " AND COALESCE(u.username, 'System') = %s"
            params.append(username)
        if search:
            like = f"%{search.strip()}%"
            query += """
             AND (
                COALESCE(u.username, 'System') LIKE %s
                OR COALESCE(a.action_type, '') LIKE %s
                OR COALESCE(a.object_type, '') LIKE %s
                OR COALESCE(a.object_id, '') LIKE %s
                OR COALESCE(a.details, '') LIKE %s
             )
            """
            params.extend([like, like, like, like, like])

        query += " ORDER BY a.timestamp DESC"
        if limit is not None:
            query += " LIMIT %s"
            params.append(int(limit))

        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, tuple(params))
            return cursor.fetchall() or []


class MySQLFamilyRepository(MySQLConnectionMixin, FamilyRepoPort):
    def list_families(self) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT family_id, family_name, family_account_no, payment_mode, discount_percentage
                FROM Families
                ORDER BY family_name
                """
            )
            return cursor.fetchall() or []

    def get_family(self, family_id: int) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT family_id, family_name, family_account_no, payment_mode, discount_percentage
                FROM Families
                WHERE family_id = %s
                """,
                (family_id,),
            )
            return cursor.fetchone()

    def get_family_and_learner_details_for_statement(self, family_id: int) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT family_account_no, payment_mode
                FROM Families
                WHERE family_id = %s
                """,
                (family_id,),
            )
            family_row = cursor.fetchone()
            if not family_row:
                return None

            family_details: Dict[str, Any] = {
                "account_no": family_row.get("family_account_no") or f"FAM-{family_id}",
                "payment_mode": family_row.get("payment_mode") or "individual_discount",
            }

            cursor.execute(
                """
                SELECT
                    p1.title AS p1_title, p1.name AS p1_name, p1.surname AS p1_surname,
                    p2.title AS p2_title, p2.name AS p2_name, p2.surname AS p2_surname,
                    g.title AS g_title, g.name AS g_name, g.surname AS g_surname
                FROM Learners s
                LEFT JOIN Parents p1 ON s.parent_id = p1.id
                LEFT JOIN Parents p2 ON s.parent2_id = p2.id
                LEFT JOIN Parents g ON s.guardian_id = g.id
                WHERE s.family_id = %s
                ORDER BY s.acc_no
                LIMIT 1
                """,
                (family_id,),
            )
            parent_row = cursor.fetchone() or {}
            family_details.update(
                {
                    "p1_title": parent_row.get("p1_title"),
                    "p1_name": parent_row.get("p1_name", "N/A"),
                    "p1_surname": parent_row.get("p1_surname", ""),
                    "p2_title": parent_row.get("p2_title"),
                    "p2_name": parent_row.get("p2_name"),
                    "p2_surname": parent_row.get("p2_surname"),
                    "g_title": parent_row.get("g_title"),
                    "g_name": parent_row.get("g_name"),
                    "g_surname": parent_row.get("g_surname"),
                }
            )

            cursor.execute(
                """
                SELECT acc_no, name, surname, COALESCE(grade, 1) AS grade
                FROM Learners
                WHERE family_id = %s
                ORDER BY grade, surname, name
                """,
                (family_id,),
            )
            family_details["learners"] = cursor.fetchall() or []
            return family_details

    def get_payment_history_for_family(self, family_id: int) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT p.date, p.amount
                FROM Payments p
                JOIN Learners s ON p.learner_id = s.acc_no
                WHERE s.family_id = %s
                UNION ALL
                SELECT p.date, p.amount
                FROM Payments p
                WHERE p.family_id = %s
                ORDER BY date ASC
                """,
                (family_id, family_id),
            )
            rows = cursor.fetchall() or []
            return [
                {
                    "date": _as_iso_date(row.get("date")),
                    "amount": row.get("amount"),
                    "type": "payment",
                }
                for row in rows
            ]

    def get_family_due_day(self, family_id: int) -> int:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT lp.due_day_of_month, lp.scheduled_payment_dates
                FROM LearnerPayments lp
                JOIN Learners s ON s.acc_no = lp.learner_id
                WHERE s.family_id = %s
                  AND (lp.end_date IS NULL OR lp.end_date >= CURDATE())
                  AND lp.start_date <= CURDATE()
                ORDER BY lp.start_date DESC, lp.learner_id ASC
                LIMIT 1
                """,
                (family_id,),
            )
            row = cursor.fetchone()
            scheduled_date = next_scheduled_date((row or {}).get("scheduled_payment_dates"), reference_date=date.today())
            if scheduled_date:
                return scheduled_date.day
            return int((row or {}).get("due_day_of_month") or 1)

    def get_family_next_scheduled_payment_date(self, family_id: int, reference_date=None) -> Optional[date]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT lp.scheduled_payment_dates
                FROM LearnerPayments lp
                JOIN Learners s ON s.acc_no = lp.learner_id
                WHERE s.family_id = %s
                  AND (lp.end_date IS NULL OR lp.end_date >= CURDATE())
                  AND lp.start_date <= CURDATE()
                """,
                (family_id,),
            )
            rows = cursor.fetchall() or []
            combined_dates: List[str] = []
            for row in rows:
                combined_dates.extend(normalize_scheduled_dates((row or {}).get("scheduled_payment_dates")))
            return next_scheduled_date(combined_dates, reference_date=reference_date)

    def create_family(self, payload: Dict[str, Any]) -> int:
        account_no = payload.get("family_account_no") or f"FAM-{uuid.uuid4().hex[:8].upper()}"
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO Families (family_name, family_account_no, payment_mode, discount_percentage)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    payload.get("family_name"),
                    account_no,
                    payload.get("payment_mode") or "individual_discount",
                    float(payload.get("discount_percentage") or 0),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def update_family(self, family_id: int, payload: Dict[str, Any]) -> bool:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE Families
                SET family_name = %s, family_account_no = %s, payment_mode = %s, discount_percentage = %s
                WHERE family_id = %s
                """,
                (
                    payload.get("family_name"),
                    payload.get("family_account_no"),
                    payload.get("payment_mode") or "individual_discount",
                    float(payload.get("discount_percentage") or 0),
                    family_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_family(self, family_id: int) -> bool:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) AS c FROM Learners WHERE family_id = %s", (family_id,))
            in_use = int((cursor.fetchone() or {}).get("c") or 0)
            if in_use > 0:
                return False
            write_cursor = conn.cursor()
            write_cursor.execute("DELETE FROM Families WHERE family_id = %s", (family_id,))
            conn.commit()
            return write_cursor.rowcount > 0


class MySQLLearnerRepository(MySQLConnectionMixin, LearnerRepoPort):
    def _table_exists(self, cursor, table_name: str) -> bool:
        database = str(self.mysql_config.get("database") or "")
        return _mysql_table_exists(cursor, database, table_name)

    def _delete_child_rows(self, cursor, table_name: str, column_name: str, acc_no: str) -> None:
        if not self._table_exists(cursor, table_name):
            return
        cursor.execute(f"DELETE FROM `{table_name}` WHERE `{column_name}` = %s", (acc_no,))

    def _cleanup_orphan_parents(self, conn, parent_ids: List[int]) -> None:
        if not parent_ids:
            return

        schema_cursor = conn.cursor()
        try:
            if not self._table_exists(schema_cursor, "Parents"):
                return
        finally:
            schema_cursor.close()

        read_cursor = conn.cursor(dictionary=True)
        write_cursor = conn.cursor()
        for parent_id in sorted(set(parent_ids)):
            read_cursor.execute(
                """
                SELECT COUNT(*) AS c
                FROM Learners
                WHERE parent_id = %s OR parent2_id = %s OR guardian_id = %s
                """,
                (parent_id, parent_id, parent_id),
            )
            remaining = int((read_cursor.fetchone() or {}).get("c") or 0)
            if remaining == 0:
                write_cursor.execute("DELETE FROM Parents WHERE id = %s", (parent_id,))

    def _generate_acc_no(self) -> str:
        return f"KM{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

    def _find_or_create_parent(self, payload: Dict[str, Any]) -> int:
        code = payload.get("country_code") or "+27"
        contact = payload.get("contact_number") or "0000000000"

        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT id FROM Parents WHERE country_code = %s AND contact_number = %s",
                (code, contact),
            )
            existing = cursor.fetchone()
            if existing:
                return int(existing["id"])

            write_cursor = conn.cursor()
            write_cursor.execute(
                """
                INSERT INTO Parents (title, name, surname, country_code, contact_number, email)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    payload.get("title") or "",
                    payload.get("name") or "Unknown",
                    payload.get("surname") or "Parent",
                    code,
                    contact,
                    payload.get("email"),
                ),
            )
            conn.commit()
            return int(write_cursor.lastrowid)

    def _has_contact_payload(self, payload: Optional[Dict[str, Any]]) -> bool:
        if not payload:
            return False
        return any(str(payload.get(key) or "").strip() for key in ("name", "surname", "contact_number", "email"))

    def _resolve_contact_ids(self, payload: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        parent_id = payload.get("parent_id")
        parent2_id = payload.get("parent2_id")
        guardian_id = payload.get("guardian_id")

        primary_payload = payload.get("parent") or {
            "relationship_type": payload.get("parent_relationship_type"),
            "title": payload.get("parent_title"),
            "name": payload.get("parent_name"),
            "surname": payload.get("parent_surname"),
            "country_code": payload.get("parent_country_code") or "+27",
            "contact_number": payload.get("parent_contact_number"),
            "email": payload.get("parent_email"),
        }
        if not (parent_id or guardian_id) and self._has_contact_payload(primary_payload):
            primary_contact_id = int(self._find_or_create_parent(primary_payload))
            relationship = str(primary_payload.get("relationship_type") or "Parent").strip().lower()
            if relationship == "guardian":
                guardian_id = primary_contact_id
            else:
                parent_id = primary_contact_id

        second_parent_payload = payload.get("second_parent")
        if not parent2_id and self._has_contact_payload(second_parent_payload):
            parent2_id = int(self._find_or_create_parent(second_parent_payload))

        return (
            int(parent_id) if parent_id is not None else None,
            int(parent2_id) if parent2_id is not None else None,
            int(guardian_id) if guardian_id is not None else None,
        )

    def _get_or_create_payment_option(self, option_name: str, grade: int, subjects_count: int, monthly_fee: float) -> int:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id FROM PaymentOptions
                WHERE option_name = %s AND grade = %s AND subjects_count = %s
                """,
                (option_name, grade, subjects_count),
            )
            row = cursor.fetchone()
            if row:
                return int(row["id"])

            write_cursor = conn.cursor()
            write_cursor.execute(
                """
                INSERT INTO PaymentOptions (option_name, subjects_count, grade, adm_reg_fee, monthly_fee)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (option_name, subjects_count, grade, float(0), float(monthly_fee)),
            )
            conn.commit()
            return int(write_cursor.lastrowid)

    def list_learners(
        self,
        search: Optional[str] = None,
        grade: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            "SELECT acc_no, name, surname, grade, subjects_count, gender, contact_number, "
            "is_active, family_id, payment_option FROM Learners WHERE 1=1"
        )
        params: List[Any] = []

        if search:
            query += " AND (LOWER(name) LIKE %s OR LOWER(surname) LIKE %s OR LOWER(acc_no) LIKE %s)"
            like = f"%{search.lower()}%"
            params.extend([like, like, like])

        if grade is not None:
            query += " AND grade = %s"
            params.append(int(grade))

        if is_active is not None:
            query += " AND is_active = %s"
            params.append(1 if is_active else 0)

        query += " ORDER BY surname, name"

        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, tuple(params))
            return cursor.fetchall() or []

    def get_learner(self, acc_no: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT l.*,
                       lp.term_id, lp.due_day_of_month, lp.due_days_of_month, lp.scheduled_payment_dates, lp.start_date
                FROM Learners l
                LEFT JOIN (
                    SELECT *
                    FROM LearnerPayments
                    WHERE learner_id = %s
                    ORDER BY start_date DESC
                    LIMIT 1
                ) lp ON l.acc_no = lp.learner_id
                WHERE l.acc_no = %s
                """,
                (acc_no, acc_no),
            )
            learner = cursor.fetchone()
            if not learner:
                return None
            learner["scheduled_payment_dates"] = normalize_scheduled_dates(learner.get("scheduled_payment_dates"))
            learner["due_days_of_month"] = normalize_due_days(
                learner.get("due_days_of_month"),
                learner.get("due_day_of_month"),
            )
            learner["due_day_of_month"] = primary_due_day(
                learner.get("due_days_of_month"),
                learner.get("due_day_of_month"),
            )

            # Fetch parent details
            if learner.get("parent_id"):
                learner["parent"] = self._get_parent(learner["parent_id"])
                if learner["parent"]:
                    learner["parent"]["relationship_type"] = "Parent"
            
            if learner.get("parent2_id"):
                learner["second_parent"] = self._get_parent(learner["parent2_id"])
            
            if learner.get("guardian_id") and not learner.get("parent"):
                learner["parent"] = self._get_parent(learner["guardian_id"])
                if learner["parent"]:
                    learner["parent"]["relationship_type"] = "Guardian"

            return learner

    def _get_parent(self, parent_id: int) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM Parents WHERE id = %s", (parent_id,))
            return cursor.fetchone()

    def get_learner_details_for_statement(self, acc_no: str) -> Optional[Tuple[Any, ...]]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.acc_no, s.name, s.surname, COALESCE(s.grade, 1) AS grade,
                       s.is_new_learner, s.apply_admission_fee, s.payment_option,
                       p1.title AS p1_title, p1.name AS p1_name, p1.surname AS p1_surname,
                       p2.title AS p2_title, p2.name AS p2_name, p2.surname AS p2_surname,
                       g.title AS g_title, g.name AS g_name, g.surname AS g_surname,
                       po.adm_reg_fee, s.skip_initial_fee, s.custom_admission_amount_enabled, s.custom_admission_amount
                FROM Learners s
                LEFT JOIN Parents p1 ON s.parent_id = p1.id
                LEFT JOIN Parents p2 ON s.parent2_id = p2.id
                LEFT JOIN Parents g ON s.guardian_id = g.id
                LEFT JOIN PaymentOptions po
                  ON s.payment_option = po.option_name
                 AND s.subjects_count = po.subjects_count
                 AND s.grade = po.grade
                WHERE s.acc_no = %s
                """,
                (acc_no,),
            )
            return cursor.fetchone()


    def get_learner_payment_history(self, acc_no: str) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT
                    sp.start_date,
                    sp.end_date,
                    po.option_name,
                    po.monthly_fee,
                    po.adm_reg_fee,
                    s.is_new_learner,
                    s.apply_admission_fee,
                    s.skip_initial_fee,
                    s.custom_admission_amount_enabled,
                    s.custom_admission_amount
                FROM LearnerPayments sp
                JOIN PaymentOptions po ON sp.payment_option_id = po.id
                JOIN Learners s ON sp.learner_id = s.acc_no
                WHERE sp.learner_id = %s
                ORDER BY sp.start_date
                """,
                (acc_no,),
            )
            return cursor.fetchall() or []

    def create_learner(self, payload: Dict[str, Any]) -> str:
        acc_no = payload.get("acc_no") or self._generate_acc_no()
        grade = int(payload.get("grade") or 1)
        subjects_count = int(payload.get("subjects_count") or 1)
        option_name = str(payload.get("payment_option") or "STANDARD")
        monthly_fee = float(payload.get("monthly_fee") or 0)
        if payload.get("manual_amount_enabled") and payload.get("manual_amount") is not None:
            option_name = "MANUAL"
            monthly_fee = float(payload.get("manual_amount") or 0)

        parent_id, parent2_id, guardian_id = self._resolve_contact_ids(payload)
        payment_option_id = self._get_or_create_payment_option(option_name, grade, subjects_count, monthly_fee)
        due_days = normalize_due_days(payload.get("due_days_of_month"), payload.get("due_day_of_month"))
        scheduled_dates = normalize_scheduled_dates(payload.get("scheduled_payment_dates"))
        primary_schedule_day = int(scheduled_dates[0][-2:]) if scheduled_dates else primary_due_day(due_days)
        if scheduled_dates and not payload.get("due_days_of_month"):
            due_days = [primary_schedule_day]

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO Learners (
                    acc_no, name, surname, date_of_birth, gender, country_code, contact_number,
                    email, grade, subjects_count, payment_option, parent_id, parent2_id,
                    guardian_id, family_id, is_new_learner, apply_admission_fee, is_active,
                    skip_initial_fee, custom_admission_amount_enabled, custom_admission_amount,
                    progress_percentage
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    acc_no,
                    payload.get("name"),
                    payload.get("surname"),
                    _as_iso_date(payload.get("date_of_birth"), "2000-01-01"),
                    payload.get("gender") or "Unknown",
                    payload.get("country_code") or "+27",
                    payload.get("contact_number") or "",
                    payload.get("email"),
                    grade,
                    subjects_count,
                    option_name,
                    parent_id,
                    parent2_id,
                    guardian_id,
                    payload.get("family_id"),
                    1 if payload.get("is_new_learner", True) else 0,
                    1 if payload.get("apply_admission_fee", True) else 0,
                    1 if payload.get("is_active", True) else 0,
                    1 if payload.get("skip_initial_fee", False) else 0,
                    1 if payload.get("custom_admission_amount_enabled", False) else 0,
                    payload.get("custom_admission_amount"),
                    float(payload.get("progress_percentage") or 0),
                ),
            )
            cursor.execute(
                """
                INSERT INTO LearnerPayments (
                    learner_id,
                    term_id,
                    payment_option_id,
                    start_date,
                    due_day_of_month,
                    due_days_of_month,
                    scheduled_payment_dates
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    acc_no,
                    int(payload.get("term_id") or 1),
                    payment_option_id,
                    _as_iso_date(payload.get("start_date") or payload.get("billing_start_date"), date.today().isoformat()),
                    primary_schedule_day,
                    serialize_due_days(due_days),
                    serialize_scheduled_dates(scheduled_dates),
                ),
            )
            conn.commit()

        return acc_no

    def update_learner(self, acc_no: str, payload: Dict[str, Any]) -> bool:
        current = self.get_learner(acc_no)
        if not current:
            return False

        # Handle parent updates if provided
        if "parent" in payload:
            parent_id = current.get("parent_id") or current.get("guardian_id")
            if parent_id:
                self._update_parent_details(parent_id, payload["parent"])
        
        if "second_parent" in payload:
            parent2_id = current.get("parent2_id")
            if parent2_id:
                self._update_parent_details(parent2_id, payload["second_parent"])

        merged = dict(current)
        merged.update(payload)

        # Resolve IDs again
        res_p, res_p2, res_g = self._resolve_contact_ids(payload)

        # Determine final IDs: use resolved if payload touched the relevant fields, else keep current
        has_primary = "parent" in payload or "parent_id" in payload or "guardian_id" in payload
        if has_primary:
            parent_id = res_p
            guardian_id = res_g
        else:
            parent_id = current.get("parent_id")
            guardian_id = current.get("guardian_id")

        has_secondary = "second_parent" in payload or "parent2_id" in payload
        if has_secondary:
            parent2_id = res_p2
        else:
            parent2_id = current.get("parent2_id")
        due_days = normalize_due_days(
            payload.get("due_days_of_month"),
            payload.get("due_day_of_month")
            or merged.get("due_days_of_month")
            or merged.get("due_day_of_month"),
        )
        scheduled_dates = normalize_scheduled_dates(
            payload.get("scheduled_payment_dates")
            or merged.get("scheduled_payment_dates")
        )
        primary_schedule_day = int(scheduled_dates[0][-2:]) if scheduled_dates else primary_due_day(due_days)
        if "scheduled_payment_dates" in payload and not payload.get("due_days_of_month") and "due_day_of_month" not in payload:
            due_days = [primary_schedule_day]

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE Learners
                SET name = %s, surname = %s, date_of_birth = %s, gender = %s, country_code = %s,
                    contact_number = %s, email = %s, grade = %s, subjects_count = %s,
                    payment_option = %s, family_id = %s, is_active = %s,
                    parent_id = %s, parent2_id = %s, guardian_id = %s,
                    skip_initial_fee = %s, custom_admission_amount_enabled = %s, custom_admission_amount = %s,
                    progress_percentage = %s
                WHERE acc_no = %s
                """,
                (
                    merged.get("name"),
                    merged.get("surname"),
                    _as_iso_date(merged.get("date_of_birth"), "2000-01-01"),
                    merged.get("gender") or "Unknown",
                    merged.get("country_code") or "+27",
                    merged.get("contact_number") or "",
                    merged.get("email"),
                    int(merged.get("grade") or 1),
                    int(merged.get("subjects_count") or 1),
                    merged.get("payment_option") or "STANDARD",
                    merged.get("family_id"),
                    1 if merged.get("is_active", True) else 0,
                    parent_id,
                    parent2_id,
                    guardian_id,
                    1 if merged.get("skip_initial_fee", False) else 0,
                    1 if merged.get("custom_admission_amount_enabled", False) else 0,
                    merged.get("custom_admission_amount"),
                    float(merged.get("progress_percentage") or 0),
                    acc_no,
                ),
            )
            
            # Also update LearnerPayments
            cursor.execute(
                """
                UPDATE LearnerPayments
                SET term_id = %s, due_day_of_month = %s, due_days_of_month = %s, scheduled_payment_dates = %s, start_date = %s
                WHERE learner_id = %s
                """,
                (
                    int(payload.get("term_id") or merged.get("term_id") or 1),
                    primary_schedule_day,
                    serialize_due_days(due_days),
                    serialize_scheduled_dates(scheduled_dates),
                    _as_iso_date(
                        payload.get("start_date")
                        or payload.get("billing_start_date")
                        or merged.get("start_date")
                        or merged.get("billing_start_date"),
                        date.today().isoformat(),
                    ),
                    acc_no,
                )
            )
            conn.commit()
        return True

    def _update_parent_details(self, parent_id: int, payload: Dict[str, Any]):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE Parents
                SET title = %s, name = %s, surname = %s, country_code = %s,
                    contact_number = %s, email = %s
                WHERE id = %s
                """,
                (
                    payload.get("title"),
                    payload.get("name"),
                    payload.get("surname"),
                    payload.get("country_code"),
                    payload.get("contact_number"),
                    payload.get("email"),
                    parent_id,
                )
            )
            conn.commit()

    def list_learners_for_family(self, family_id: int) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT acc_no, name, surname, grade, subjects_count, payment_option
                FROM Learners
                WHERE family_id = %s
                ORDER BY surname, name
                """,
                (family_id,),
            )
            return cursor.fetchall() or []

    def list_learners_by_grade(self, grade: int) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT acc_no, name, surname, grade, subjects_count, payment_option
                FROM Learners
                WHERE grade = %s AND is_active = 1
                ORDER BY surname, name
                """,
                (grade,),
            )
            return cursor.fetchall() or []

    def set_learner_active(self, acc_no: str, is_active: bool, reason: Optional[str] = None) -> bool:
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE Learners SET is_active = %s WHERE acc_no = %s",
                    (1 if is_active else 0, acc_no),
                )
                if cursor.rowcount <= 0:
                    conn.commit()
                    return False
                if not is_active and reason:
                    cursor.execute(
                        """
                        INSERT INTO Archive (learner_acc_no, archive_date, reason, reactivation_date)
                        VALUES (%s, NOW(), %s, NULL)
                        """,
                        (acc_no, reason),
                    )
                if is_active:
                    cursor.execute(
                        """
                        UPDATE Archive
                        SET reactivation_date = NOW()
                        WHERE learner_acc_no = %s AND reactivation_date IS NULL
                        """,
                        (acc_no,),
                    )
                conn.commit()
            return True
        except Exception:
            return False

    def delete_learner(self, acc_no: str) -> bool:
        with self._connection() as conn:
            read_cursor = conn.cursor(dictionary=True)
            read_cursor.execute(
                "SELECT parent_id, parent2_id, guardian_id FROM Learners WHERE acc_no = %s",
                (acc_no,),
            )
            learner = read_cursor.fetchone()
            if not learner:
                return False

            parent_ids = [
                int(parent_id)
                for parent_id in (
                    learner.get("parent_id"),
                    learner.get("parent2_id"),
                    learner.get("guardian_id"),
                )
                if parent_id is not None
            ]

            write_cursor = conn.cursor()
            for table_name, column_name in (
                ("AttendancePaymentFeed", "learner_acc_no"),
                ("AttendanceSummary", "learner_acc_no"),
                ("AttendanceRecords", "learner_acc_no"),
                ("Archive", "learner_acc_no"),
                ("Payments", "learner_id"),
                ("LearnerPayments", "learner_id"),
                ("statement_counters", "learner_id"),
            ):
                self._delete_child_rows(write_cursor, table_name, column_name, acc_no)

            write_cursor.execute("DELETE FROM Learners WHERE acc_no = %s", (acc_no,))
            deleted = write_cursor.rowcount > 0
            if not deleted:
                conn.commit()
                return False

            self._cleanup_orphan_parents(conn, parent_ids)
            conn.commit()
            return True

    def get_grade_payment_rule(self, grade: int) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT grade, min_progress_percentage, change_interval_months, progress_validity_months, is_active
                FROM GradePaymentRules
                WHERE grade = %s AND is_active = 1
                """,
                (grade,),
            )
            return cursor.fetchone()

    def set_learner_progress(self, acc_no: str, progress_percentage: float) -> bool:
        learner = self.get_learner(acc_no)
        if not learner:
            return False
        grade = int(learner.get("grade") or 0)
        now = datetime.now()
        eligible_until = None
        rule = self.get_grade_payment_rule(grade) if grade in range(1, 8) else None
        if rule:
            validity_months = int(rule.get("progress_validity_months") or 12)
            eligible_until = (now + timedelta(days=validity_months * 30)).strftime("%Y-%m-%d %H:%M:%S")
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE Learners
                SET progress_percentage = %s, progress_updated_date = %s, progress_eligible_until = %s
                WHERE acc_no = %s
                """,
                (float(progress_percentage), now.strftime("%Y-%m-%d %H:%M:%S"), eligible_until, acc_no),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_learner_progress_status(self, acc_no: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT acc_no, grade, progress_percentage, last_payment_change_date, progress_eligible_until, progress_updated_date
                FROM Learners
                WHERE acc_no = %s
                """,
                (acc_no,),
            )
            data = cursor.fetchone()
        if not data:
            return None

        grade = int(data.get("grade") or 0)
        progress = float(data.get("progress_percentage") or 0)
        data["progress_percentage"] = progress
        rule = self.get_grade_payment_rule(grade) if grade in range(1, 8) else None
        if not rule:
            data.update(
                {
                    "allowed": True,
                    "reason": "No restrictions for this grade",
                    "min_progress_required": 0.0,
                    "change_interval_months": 0,
                }
            )
            return data

        min_progress = float(rule.get("min_progress_percentage") or 0)
        if progress < min_progress:
            data.update(
                {
                    "allowed": False,
                    "reason": f"Progress {progress:.1f}% below minimum {min_progress:.1f}%",
                    "min_progress_required": min_progress,
                }
            )
            return data

        eligible_until_raw = data.get("progress_eligible_until")
        if eligible_until_raw:
            eligible_until = eligible_until_raw if isinstance(eligible_until_raw, datetime) else datetime.strptime(
                str(eligible_until_raw),
                "%Y-%m-%d %H:%M:%S",
            )
            if datetime.now() > eligible_until:
                data.update(
                    {
                        "allowed": False,
                        "reason": "Progress eligibility has expired",
                        "min_progress_required": min_progress,
                        "change_interval_months": int(rule.get("change_interval_months") or 0),
                    }
                )
                return data

        last_change_raw = data.get("last_payment_change_date")
        if last_change_raw:
            last_change = last_change_raw if isinstance(last_change_raw, datetime) else datetime.strptime(
                str(last_change_raw),
                "%Y-%m-%d %H:%M:%S",
            )
            months_since = (datetime.now() - last_change).days / 30.0
            interval = float(rule.get("change_interval_months") or 0)
            if months_since < interval:
                remaining = max(0.0, interval - months_since)
                data.update(
                    {
                        "allowed": False,
                        "reason": f"Payment change blocked for another {remaining:.1f} months",
                        "min_progress_required": min_progress,
                        "change_interval_months": int(interval),
                    }
                )
                return data

        data.update(
            {
                "allowed": True,
                "reason": "Payment change allowed",
                "min_progress_required": min_progress,
                "change_interval_months": int(rule.get("change_interval_months") or 0),
            }
        )
        return data

    def record_payment_change(self, acc_no: str, change_description: str) -> bool:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE Learners SET last_payment_change_date = %s WHERE acc_no = %s",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), acc_no),
            )
            conn.commit()
            return cursor.rowcount > 0


class MySQLPaymentRepository(MySQLConnectionMixin, PaymentRepoPort):
    def list_payments(
        self,
        learner_acc_no: Optional[str] = None,
        family_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT payment_id, learner_id, family_id, amount,
                   date,
                   payment_type,
                   month_year, description
            FROM Payments
            WHERE 1 = 1
        """
        params: List[Any] = []

        if learner_acc_no:
            query += " AND learner_id = %s"
            params.append(learner_acc_no)

        if family_id is not None:
            query += " AND family_id = %s"
            params.append(family_id)

        query += " ORDER BY date DESC, payment_id DESC LIMIT %s"
        params.append(limit)

        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, tuple(params))
            return cursor.fetchall() or []

    def create_payment(self, payload: Dict[str, Any]) -> int:
        amount = float(payload.get("amount") or 0)
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO Payments (learner_id, family_id, amount, date, payment_type, month_year, description, recorded_by_user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    payload.get("learner_id"),
                    payload.get("family_id"),
                    amount,
                    _as_iso_date(payload.get("date"), date.today().isoformat()),
                    payload.get("payment_type") or "tuition",
                    payload.get("month_year"),
                    payload.get("description") or "",
                    payload.get("recorded_by_user_id"),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def delete_payment(self, payment_id: int) -> bool:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Payments WHERE payment_id = %s", (payment_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_payment_history_for_learner(self, acc_no: str) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT date, amount FROM Payments WHERE learner_id = %s ORDER BY date ASC",
                (acc_no,),
            )
            rows = cursor.fetchall() or []
            return [{"date": _as_iso_date(row.get("date")), "amount": row.get("amount")} for row in rows]

    def get_payment_history_for_family(self, family_id: int) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT p.date, p.amount
                FROM Payments p
                JOIN Learners s ON p.learner_id = s.acc_no
                WHERE s.family_id = %s
                UNION ALL
                SELECT p.date, p.amount
                FROM Payments p
                WHERE p.family_id = %s
                ORDER BY date ASC
                """,
                (family_id, family_id),
            )
            rows = cursor.fetchall() or []
            return [
                {
                    "date": _as_iso_date(row.get("date")),
                    "amount": row.get("amount"),
                    "type": "payment",
                }
                for row in rows
            ]

    def get_monthly_fee_for_statement(self, acc_no: str) -> float:
        return self._learner_monthly_fee(acc_no)


    def _learner_monthly_fee(self, acc_no: str) -> float:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT po.monthly_fee
                FROM Learners s
                LEFT JOIN PaymentOptions po
                  ON po.option_name = s.payment_option
                 AND po.grade = s.grade
                 AND po.subjects_count = s.subjects_count
                WHERE s.acc_no = %s
                """,
                (acc_no,),
            )
            row = cursor.fetchone()
            return float((row or {}).get("monthly_fee") or 0)

    def _learner_start_date(self, acc_no: str) -> Optional[date]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT start_date FROM LearnerPayments
                WHERE learner_id = %s
                ORDER BY start_date ASC
                LIMIT 1
                """,
                (acc_no,),
            )
            row = cursor.fetchone()
            value = (row or {}).get("start_date")
            if not value:
                return None
            if isinstance(value, str):
                try:
                    return datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    return None
            if hasattr(value, "date"):
                return value.date()
            return value

    def get_due_day_for_learner(self, acc_no: str) -> int:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT due_day_of_month, scheduled_payment_dates
                FROM LearnerPayments
                WHERE learner_id = %s
                  AND (end_date IS NULL OR end_date >= CURDATE())
                  AND start_date <= CURDATE()
                ORDER BY start_date DESC
                LIMIT 1
                """,
                (acc_no,),
            )
            row = cursor.fetchone()
            scheduled_date = next_scheduled_date((row or {}).get("scheduled_payment_dates"), reference_date=date.today())
            if scheduled_date:
                return scheduled_date.day
            return int((row or {}).get("due_day_of_month") or 1)

    def get_next_scheduled_payment_date_for_learner(self, acc_no: str, reference_date=None) -> Optional[date]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT scheduled_payment_dates
                FROM LearnerPayments
                WHERE learner_id = %s
                  AND (end_date IS NULL OR end_date >= CURDATE())
                  AND start_date <= CURDATE()
                ORDER BY start_date DESC
                LIMIT 1
                """,
                (acc_no,),
            )
            row = cursor.fetchone()
            return next_scheduled_date((row or {}).get("scheduled_payment_dates"), reference_date=reference_date)

    def get_balance_for_learner(self, acc_no: str) -> float:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COALESCE(SUM(amount), 0) AS total_paid FROM Payments WHERE learner_id = %s", (acc_no,))
            total_paid = float((cursor.fetchone() or {}).get("total_paid") or 0)

        monthly_fee = self._learner_monthly_fee(acc_no)
        start = self._learner_start_date(acc_no)
        if not start:
            return -total_paid

        today = date.today()
        months = max(1, (today.year - start.year) * 12 + (today.month - start.month) + 1)
        estimated_charges = monthly_fee * months
        return estimated_charges - total_paid

    def get_balance_for_family(self, family_id: int) -> float:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT acc_no FROM Learners WHERE family_id = %s", (family_id,))
            learners = cursor.fetchall() or []

        total = 0.0
        for learner in learners:
            acc_no = learner.get("acc_no")
            if acc_no:
                total += self.get_balance_for_learner(str(acc_no))
        return total

    def get_active_term_for_learner(self, acc_no: str) -> Optional[int]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT term_id
                FROM LearnerPayments
                WHERE learner_id = %s
                  AND (end_date IS NULL OR end_date >= CURDATE())
                  AND start_date <= CURDATE()
                ORDER BY start_date DESC
                LIMIT 1
                """,
                (acc_no,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            value = row.get("term_id")
            return int(value) if value is not None else None

    def get_term_name_by_id(self, term_id: int) -> Optional[str]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT term_name FROM PaymentTerms WHERE term_id = %s",
                (term_id,),
            )
            row = cursor.fetchone()
            return str(row.get("term_name")) if row and row.get("term_name") is not None else None

    def list_payment_options(self) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, option_name, subjects_count, grade, adm_reg_fee, monthly_fee
                FROM PaymentOptions
                WHERE option_name != 'MANUAL'
                ORDER BY grade, subjects_count, option_name
                """
            )
            return cursor.fetchall() or []

    def create_payment_option(self, payload: Dict[str, Any]) -> int:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO PaymentOptions (option_name, subjects_count, grade, adm_reg_fee, monthly_fee)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    payload.get("option_name"),
                    int(payload.get("subjects_count") or 1),
                    int(payload.get("grade") or 1),
                    float(payload.get("adm_reg_fee") or 0),
                    float(payload.get("monthly_fee") or 0),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def update_payment_option(self, option_id: int, payload: Dict[str, Any]) -> bool:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE PaymentOptions
                SET option_name = %s, subjects_count = %s, grade = %s, adm_reg_fee = %s, monthly_fee = %s
                WHERE id = %s
                """,
                (
                    payload.get("option_name"),
                    int(payload.get("subjects_count") or 1),
                    int(payload.get("grade") or 1),
                    float(payload.get("adm_reg_fee") or 0),
                    float(payload.get("monthly_fee") or 0),
                    option_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_payment_option(self, option_id: int) -> bool:
        with self._connection() as conn:
            read_cursor = conn.cursor(dictionary=True)
            read_cursor.execute("SELECT COUNT(*) AS c FROM LearnerPayments WHERE payment_option_id = %s", (option_id,))
            in_use = int((read_cursor.fetchone() or {}).get("c") or 0)
            if in_use > 0:
                return False
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PaymentOptions WHERE id = %s", (option_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_payment_terms(self) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT term_id, term_name, description, discount_percentage
                FROM PaymentTerms
                ORDER BY term_name
                """
            )
            return cursor.fetchall() or []

    def create_payment_term(self, payload: Dict[str, Any]) -> int:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO PaymentTerms (term_name, description, discount_percentage)
                VALUES (%s, %s, %s)
                """,
                (
                    payload.get("term_name"),
                    payload.get("description"),
                    float(payload.get("discount_percentage") or 0),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def update_payment_term(self, term_id: int, payload: Dict[str, Any]) -> bool:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE PaymentTerms
                SET term_name = %s, description = %s, discount_percentage = %s
                WHERE term_id = %s
                """,
                (
                    payload.get("term_name"),
                    payload.get("description"),
                    float(payload.get("discount_percentage") or 0),
                    term_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_payment_term(self, term_id: int) -> bool:
        with self._connection() as conn:
            read_cursor = conn.cursor(dictionary=True)
            read_cursor.execute("SELECT COUNT(*) AS c FROM LearnerPayments WHERE term_id = %s", (term_id,))
            in_use = int((read_cursor.fetchone() or {}).get("c") or 0)
            if in_use > 0:
                return False
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PaymentTerms WHERE term_id = %s", (term_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_payment_statistics(
        self,
        month_year: str,
        include_on_track: bool = True,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT s.acc_no, s.name, s.surname, s.grade,
                       COALESCE(po.monthly_fee, 0) AS monthly_fee
                FROM Learners s
                LEFT JOIN PaymentOptions po
                  ON po.option_name = s.payment_option
                 AND po.subjects_count = s.subjects_count
                 AND po.grade = s.grade
                WHERE s.is_active = 1
                ORDER BY s.surname, s.name
                """
            )
            learners = cursor.fetchall() or []
            cursor.execute(
                """
                SELECT learner_id, COALESCE(SUM(amount), 0) AS paid
                FROM Payments
                WHERE payment_type = 'tuition' AND DATE_FORMAT(date, '%Y-%m') = %s
                GROUP BY learner_id
                """,
                (month_year,),
            )
            paid_rows = cursor.fetchall() or []

        paid_map = {str(row.get("learner_id")): float(row.get("paid") or 0) for row in paid_rows}
        search_term = (search or "").strip().lower()
        rows: List[Dict[str, Any]] = []
        total_due = 0.0
        total_paid = 0.0
        for learner in learners:
            acc_no = str(learner.get("acc_no") or "")
            full_name = f"{learner.get('name', '')} {learner.get('surname', '')}".strip()
            if search_term and search_term not in full_name.lower() and search_term not in acc_no.lower():
                continue
            due = float(learner.get("monthly_fee") or 0)
            paid = float(paid_map.get(acc_no, 0))
            outstanding = max(0.0, due - paid)
            on_track = paid >= due if due > 0 else paid > 0
            if not include_on_track and on_track:
                continue
            rows.append(
                {
                    "acc_no": acc_no,
                    "name": learner.get("name"),
                    "surname": learner.get("surname"),
                    "grade": learner.get("grade"),
                    "due_amount": due,
                    "paid_amount": paid,
                    "outstanding_amount": outstanding,
                    "on_track": on_track,
                }
            )
            total_due += due
            total_paid += paid

        missed_count = sum(1 for row in rows if not row.get("on_track"))
        return {
            "rows": rows,
            "summary": {
                "total_learners": len(rows),
                "on_track_count": len(rows) - missed_count,
                "missed_count": missed_count,
                "total_due": total_due,
                "total_paid": total_paid,
                "total_outstanding": max(0.0, total_due - total_paid),
            },
        }

    def get_payment_trends(self, months: int = 12) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        today = date.today().replace(day=1)
        for i in range(max(1, months) - 1, -1, -1):
            month_start = (today - timedelta(days=i * 30)).replace(day=1)
            month_key = month_start.strftime("%Y-%m")
            with self._connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(amount), 0) AS total
                    FROM Payments
                    WHERE payment_type = 'tuition' AND DATE_FORMAT(date, '%Y-%m') = %s
                    """,
                    (month_key,),
                )
                row = cursor.fetchone()
            out.append(
                {
                    "month_year": month_key,
                    "label": f"{calendar.month_name[int(month_key[5:7])]} {month_key[:4]}",
                    "total_collected": float((row or {}).get("total") or 0.0),
                }
            )
        return out


class MySQLAttendanceRepository(MySQLConnectionMixin, AttendanceRepoPort):
    def list_attendance_for_date(self, iso_date: str, grade: Optional[int] = None) -> List[Dict[str, Any]]:
        query = """
            SELECT attendance_id, learner_acc_no, learner_name, learner_surname, grade, date, status,
                   check_in_time, check_out_time, notes, recorded_by, has_payment, payment_amount,
                   payment_date, payment_reference, payment_feed_status
            FROM AttendanceRecords
            WHERE date = %s
        """
        params: List[Any] = [iso_date]
        if grade is not None:
            query += " AND grade = %s"
            params.append(grade)
        query += " ORDER BY learner_surname, learner_name"

        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, tuple(params))
            return cursor.fetchall() or []

    def record_attendance(self, payload: Dict[str, Any]) -> int:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT attendance_id FROM AttendanceRecords WHERE learner_acc_no = %s AND date = %s",
                (payload.get("learner_acc_no"), payload.get("date")),
            )
            existing = cursor.fetchone()

            if existing:
                attendance_id = int(existing["attendance_id"])
                write_cursor = conn.cursor()
                write_cursor.execute(
                    """
                    UPDATE AttendanceRecords
                    SET status = %s, check_in_time = %s, check_out_time = %s, notes = %s,
                        recorded_by = %s, has_payment = %s, payment_amount = %s, payment_date = %s,
                        payment_reference = %s, payment_feed_status = %s
                    WHERE attendance_id = %s
                    """,
                    (
                        payload.get("status"),
                        payload.get("check_in_time"),
                        payload.get("check_out_time"),
                        payload.get("notes"),
                        payload.get("recorded_by"),
                        1 if payload.get("has_payment") else 0,
                        payload.get("payment_amount"),
                        payload.get("payment_date"),
                        payload.get("payment_reference"),
                        payload.get("payment_feed_status") or "not_applicable",
                        attendance_id,
                    ),
                )
                conn.commit()
                return attendance_id

            cursor.execute(
                "SELECT name, surname, grade FROM Learners WHERE acc_no = %s",
                (payload.get("learner_acc_no"),),
            )
            learner = cursor.fetchone()
            if not learner:
                raise ValueError("Learner not found for attendance record")

            write_cursor = conn.cursor()
            write_cursor.execute(
                """
                INSERT INTO AttendanceRecords (
                    learner_acc_no, learner_name, learner_surname, grade, date, status,
                    check_in_time, check_out_time, notes, recorded_by, has_payment,
                    payment_amount, payment_date, payment_reference, payment_feed_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    payload.get("learner_acc_no"),
                    learner.get("name"),
                    learner.get("surname"),
                    learner.get("grade") or 1,
                    payload.get("date"),
                    payload.get("status"),
                    payload.get("check_in_time"),
                    payload.get("check_out_time"),
                    payload.get("notes"),
                    payload.get("recorded_by"),
                    1 if payload.get("has_payment") else 0,
                    payload.get("payment_amount"),
                    payload.get("payment_date"),
                    payload.get("payment_reference"),
                    payload.get("payment_feed_status") or "not_applicable",
                ),
            )
            conn.commit()
            return int(write_cursor.lastrowid)

    def list_attendance_history(
        self,
        start_date: str,
        end_date: str,
        learner_acc_no: Optional[str] = None,
        grade: Optional[int] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT attendance_id, learner_acc_no, learner_name, learner_surname, grade, date, status,
                   check_in_time, check_out_time, notes, recorded_by
            FROM AttendanceRecords
            WHERE date BETWEEN %s AND %s
        """
        params: List[Any] = [start_date, end_date]

        if learner_acc_no:
            query += " AND learner_acc_no = %s"
            params.append(learner_acc_no)

        if grade is not None:
            query += " AND grade = %s"
            params.append(grade)

        query += " ORDER BY date DESC, learner_surname ASC LIMIT %s"
        params.append(limit)

        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, tuple(params))
            return cursor.fetchall() or []

    def get_attendance_summary(self, start_date: str, end_date: str, grade: Optional[int] = None) -> List[Dict[str, Any]]:
        query = """
            SELECT
                learner_acc_no,
                learner_name,
                learner_surname,
                grade,
                COUNT(*) AS total_days,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) AS present_days,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) AS absent_days,
                SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) AS late_days,
                SUM(CASE WHEN status = 'excused' THEN 1 ELSE 0 END) AS excused_days
            FROM AttendanceRecords
            WHERE date BETWEEN %s AND %s
        """
        params: List[Any] = [start_date, end_date]

        if grade is not None:
            query += " AND grade = %s"
            params.append(grade)

        query += " GROUP BY learner_acc_no, learner_name, learner_surname, grade ORDER BY learner_surname, learner_name"

        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall() or []

        result: List[Dict[str, Any]] = []
        for row in rows:
            total = int(row.get("total_days") or 0)
            present = int(row.get("present_days") or 0)
            row["attendance_rate"] = round((present / total) * 100, 2) if total else 0.0
            result.append(row)
        return result


class MySQLSyncStateRepository(MySQLConnectionMixin, SyncStateRepoPort):
    def __init__(self, mysql_config: Dict[str, Any]) -> None:
        super().__init__(mysql_config)
        self._table_columns_cache: Dict[str, List[str]] = {}

    def _columns(self, table_name: str) -> List[str]:
        if table_name in self._table_columns_cache:
            return self._table_columns_cache[table_name]

        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
                """,
                (table_name,),
            )
            rows = cursor.fetchall() or []
        cols = [str(row["COLUMN_NAME"]) for row in rows]
        self._table_columns_cache[table_name] = cols
        return cols

    def _now_utc(self) -> str:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    def start_sync_run(self, user_id: Optional[int]) -> int:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO SyncRuns (user_id, started_at_utc, status, uploaded_count, downloaded_count, conflict_count)
                VALUES (%s, %s, 'RUNNING', 0, 0, 0)
                """,
                (user_id, self._now_utc()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def finish_sync_run(
        self,
        run_id: int,
        status: str,
        uploaded_count: int,
        downloaded_count: int,
        conflict_count: int,
        error_text: Optional[str] = None,
    ) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE SyncRuns
                SET finished_at_utc = %s, status = %s, uploaded_count = %s, downloaded_count = %s,
                    conflict_count = %s, error_text = %s
                WHERE run_id = %s
                """,
                (
                    self._now_utc(),
                    status,
                    uploaded_count,
                    downloaded_count,
                    conflict_count,
                    error_text,
                    run_id,
                ),
            )
            conn.commit()

    def get_client_sync_state(self, client_id: str) -> Dict[str, Any]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT client_id, last_upload_cursor, last_download_cursor,
                       last_successful_sync_at_utc, last_attempt_at_utc
                FROM SyncState
                WHERE client_id = %s
                """,
                (client_id,),
            )
            row = cursor.fetchone()

        if not row:
            return {
                "client_id": client_id,
                "last_upload_cursor": "1970-01-01 00:00:00",
                "last_download_cursor": "1970-01-01 00:00:00",
                "last_successful_sync_at_utc": None,
                "last_attempt_at_utc": None,
            }
        return row

    def upsert_client_sync_state(
        self,
        client_id: str,
        last_upload_cursor: str,
        last_download_cursor: str,
        successful: bool,
    ) -> None:
        now = self._now_utc()
        success_value = now if successful else None
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO SyncState (
                    client_id, last_upload_cursor, last_download_cursor,
                    last_successful_sync_at_utc, last_attempt_at_utc
                ) VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    last_upload_cursor = VALUES(last_upload_cursor),
                    last_download_cursor = VALUES(last_download_cursor),
                    last_successful_sync_at_utc = COALESCE(VALUES(last_successful_sync_at_utc), last_successful_sync_at_utc),
                    last_attempt_at_utc = VALUES(last_attempt_at_utc)
                """,
                (client_id, last_upload_cursor, last_download_cursor, success_value, now),
            )
            conn.commit()

    def get_dirty_rows(self, tables: List[str], limit_per_table: int = 500) -> Dict[str, List[Dict[str, Any]]]:
        result: Dict[str, List[Dict[str, Any]]] = {}
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            for table in tables:
                cols = self._columns(table)
                if "is_dirty" not in cols:
                    result[table] = []
                    continue
                cursor.execute(
                    f"SELECT * FROM {table} WHERE is_dirty = 1 ORDER BY last_modified_timestamp ASC LIMIT %s",
                    (limit_per_table,),
                )
                result[table] = cursor.fetchall() or []
        return result

    def mark_rows_clean(self, table_name: str, uuids: List[str]) -> None:
        if not uuids:
            return
        placeholders = ",".join(["%s"] * len(uuids))
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE {table_name} SET is_dirty = 0 WHERE uuid IN ({placeholders})",
                tuple(uuids),
            )
            conn.commit()

    def get_changes_since(
        self,
        cursor_utc: str,
        tables: List[str],
        limit_per_table: int = 500,
    ) -> Dict[str, List[Dict[str, Any]]]:
        result: Dict[str, List[Dict[str, Any]]] = {}
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            for table in tables:
                cols = self._columns(table)
                if "last_modified_timestamp" not in cols:
                    result[table] = []
                    continue
                cursor.execute(
                    f"""
                    SELECT * FROM {table}
                    WHERE last_modified_timestamp > %s
                    ORDER BY last_modified_timestamp ASC
                    LIMIT %s
                    """,
                    (cursor_utc, limit_per_table),
                )
                result[table] = cursor.fetchall() or []
        return result

    def get_deleted_records(self, cursor_utc: str, limit: int = 1000) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT delete_id, table_name, record_uuid, deleted_at_utc, source
                FROM SyncDeletedRecords
                WHERE deleted_at_utc > %s
                ORDER BY deleted_at_utc ASC
                LIMIT %s
                """,
                (cursor_utc, limit),
            )
            return cursor.fetchall() or []

    def apply_remote_changes(
        self,
        changes_by_table: Dict[str, List[Dict[str, Any]]],
        tombstones: List[Dict[str, Any]],
    ) -> Tuple[int, int, int]:
        uploaded_count = 0
        downloaded_count = 0
        conflict_count = 0

        with self._connection() as conn:
            read_cursor = conn.cursor(dictionary=True)
            write_cursor = conn.cursor()

            for table_name, rows in changes_by_table.items():
                cols = self._columns(table_name)
                if not cols:
                    continue

                for remote_row in rows:
                    record_uuid = remote_row.get("uuid")
                    if not record_uuid:
                        continue

                    read_cursor.execute(
                        f"SELECT is_dirty, last_modified_timestamp FROM {table_name} WHERE uuid = %s",
                        (record_uuid,),
                    )
                    local = read_cursor.fetchone()

                    if local:
                        local_dirty = int(local.get("is_dirty") or 0)
                        local_ts = str(local.get("last_modified_timestamp") or "1970-01-01 00:00:00")
                        remote_ts = str(remote_row.get("last_modified_timestamp") or "1970-01-01 00:00:00")
                        if local_dirty == 1 and local_ts > remote_ts:
                            conflict_count += 1
                            write_cursor.execute(
                                """
                                INSERT INTO SyncConflicts (
                                    table_name, record_uuid, local_ts, remote_ts, winner, resolved_at_utc, user_id
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """,
                                (table_name, str(record_uuid), local_ts, remote_ts, "local", self._now_utc(), None),
                            )
                            continue

                    payload = {k: v for k, v in remote_row.items() if k in cols}
                    payload["is_dirty"] = 0
                    cols_to_use = list(payload.keys())
                    col_sql = ", ".join(cols_to_use)
                    placeholder_sql = ", ".join(["%s"] * len(cols_to_use))
                    update_sql = ", ".join([f"{c}=VALUES({c})" for c in cols_to_use if c != "uuid"])
                    write_cursor.execute(
                        f"INSERT INTO {table_name} ({col_sql}) VALUES ({placeholder_sql}) ON DUPLICATE KEY UPDATE {update_sql}",
                        tuple(payload[c] for c in cols_to_use),
                    )
                    uploaded_count += 1

            for tombstone in tombstones:
                table_name = tombstone.get("table_name")
                record_uuid = tombstone.get("record_uuid")
                if not table_name or not record_uuid:
                    continue
                if "uuid" not in self._columns(str(table_name)):
                    continue
                write_cursor.execute(
                    f"DELETE FROM {table_name} WHERE uuid = %s",
                    (record_uuid,),
                )
                uploaded_count += write_cursor.rowcount

            conn.commit()

        return uploaded_count, downloaded_count, conflict_count

    def log_conflict(
        self,
        table_name: str,
        record_uuid: str,
        local_ts: str,
        remote_ts: str,
        winner: str,
        user_id: Optional[int],
    ) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO SyncConflicts (
                    table_name, record_uuid, local_ts, remote_ts, winner, resolved_at_utc, user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (table_name, record_uuid, local_ts, remote_ts, winner, self._now_utc(), user_id),
            )
            conn.commit()
