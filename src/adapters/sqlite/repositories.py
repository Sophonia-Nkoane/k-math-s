from __future__ import annotations

import uuid
import calendar
from datetime import datetime, date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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
    primary_due_day,
    serialize_due_days,
    serialize_scheduled_dates,
)


def _to_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    keys = row.keys() if hasattr(row, "keys") else None
    if keys:
        return {k: row[k] for k in keys}
    return dict(row)


def _as_iso_date(value: Any, default: Optional[str] = None) -> str:
    if value is None:
        if default:
            return default
        return date.today().isoformat()
    if isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class SQLiteUserRepository(UserRepoPort):
    def __init__(self, db_manager) -> None:
        self.db_manager = db_manager

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        row = self.db_manager.execute_query(
            "SELECT user_id, username, password, role FROM Users WHERE username = ?",
            (username,),
            fetchone=True,
        )
        return _to_dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = self.db_manager.execute_query(
            "SELECT user_id, username, password, role FROM Users WHERE user_id = ?",
            (user_id,),
            fetchone=True,
        )
        return _to_dict(row) if row else None

    def list_users(self, exclude_username: Optional[str] = None) -> List[Dict[str, Any]]:
        if exclude_username:
            rows = self.db_manager.execute_query(
                "SELECT user_id, username, role FROM Users WHERE username != ? ORDER BY username",
                (exclude_username,),
                fetchall=True,
            )
        else:
            rows = self.db_manager.execute_query(
                "SELECT user_id, username, role FROM Users ORDER BY username",
                fetchall=True,
            )
        return [_to_dict(row) for row in (rows or [])]

    def create_user(self, username: str, password_hash: str, role: str) -> int:
        user_id = self.db_manager.execute_query(
            "INSERT INTO Users (username, password, role) VALUES (?, ?, ?)",
            (username, password_hash, role),
            commit=True,
        )
        return int(user_id)

    def update_user_password(self, username: str, password_hash: str) -> bool:
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Users SET password = ? WHERE username = ?", (password_hash, username))
            conn.commit()
            return cursor.rowcount > 0

    def update_user_role(self, username: str, role: str) -> bool:
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Users SET role = ? WHERE username = ?", (role, username))
            conn.commit()
            return cursor.rowcount > 0

    def delete_user(self, username: str) -> bool:
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Users WHERE username = ?", (username,))
            conn.commit()
            return cursor.rowcount > 0

    def count_admin_users(self) -> int:
        row = self.db_manager.execute_query(
            "SELECT COUNT(*) AS admin_count FROM Users WHERE LOWER(role) = 'admin'",
            fetchone=True,
        )
        if not row:
            return 0
        d = _to_dict(row)
        return int(d.get("admin_count") or list(d.values())[0] or 0)


class SQLiteAuditRepository(AuditRepoPort):
    def __init__(self, db_manager) -> None:
        self.db_manager = db_manager

    def log_action(
        self,
        user_id: Optional[int],
        action_type: str,
        object_type: str,
        object_id: str,
        details: str,
    ) -> None:
        self.db_manager.execute_query(
            """
            INSERT INTO AuditLog (user_id, action_type, object_type, object_id, timestamp, details)
            VALUES (?, ?, ?, ?, STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW'), ?)
            """,
            (user_id, action_type, object_type, object_id, details),
            commit=True,
        )

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
            query += " AND DATE(a.timestamp) >= DATE(?)"
            params.append(start_date)
        if end_date:
            query += " AND DATE(a.timestamp) <= DATE(?)"
            params.append(end_date)
        if action_type:
            query += " AND a.action_type = ?"
            params.append(action_type)
        if username:
            query += " AND COALESCE(u.username, 'System') = ?"
            params.append(username)
        if search:
            like = f"%{search.strip()}%"
            query += """
             AND (
                COALESCE(u.username, 'System') LIKE ?
                OR COALESCE(a.action_type, '') LIKE ?
                OR COALESCE(a.object_type, '') LIKE ?
                OR COALESCE(a.object_id, '') LIKE ?
                OR COALESCE(a.details, '') LIKE ?
             )
            """
            params.extend([like, like, like, like, like])

        query += " ORDER BY a.timestamp DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(int(limit))

        rows = self.db_manager.execute_query(
            query,
            tuple(params),
            fetchall=True,
        )
        return [_to_dict(row) for row in (rows or [])]


class SQLiteFamilyRepository(FamilyRepoPort):
    def __init__(self, db_manager) -> None:
        self.db_manager = db_manager

    def list_families(self) -> List[Dict[str, Any]]:
        rows = self.db_manager.execute_query(
            """
            SELECT family_id, family_name, family_account_no, payment_mode, discount_percentage
            FROM Families
            ORDER BY family_name
            """,
            fetchall=True,
        )
        return [_to_dict(row) for row in (rows or [])]

    def get_family(self, family_id: int) -> Optional[Dict[str, Any]]:
        row = self.db_manager.execute_query(
            """
            SELECT family_id, family_name, family_account_no, payment_mode, discount_percentage
            FROM Families
            WHERE family_id = ?
            """,
            (family_id,),
            fetchone=True,
        )
        if not row:
            return None
        return _to_dict(row)

    def create_family(self, payload: Dict[str, Any]) -> int:
        family_account_no = payload.get("family_account_no") or f"FAM-{uuid.uuid4().hex[:8].upper()}"
        family_id = self.db_manager.execute_query(
            """
            INSERT INTO Families (family_name, family_account_no, payment_mode, discount_percentage)
            VALUES (?, ?, ?, ?)
            """,
            (
                payload.get("family_name"),
                family_account_no,
                payload.get("payment_mode") or "individual_discount",
                float(payload.get("discount_percentage") or 0),
            ),
            commit=True,
        )
        return int(family_id)

    def update_family(self, family_id: int, payload: Dict[str, Any]) -> bool:
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE Families
                SET family_name = ?, family_account_no = ?, payment_mode = ?, discount_percentage = ?
                WHERE family_id = ?
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
        # Keep behavior safe: do not delete a family that still has linked learners.
        linked = self.db_manager.execute_query(
            "SELECT COUNT(*) AS c FROM Learners WHERE family_id = ?",
            (family_id,),
            fetchone=True,
        )
        linked_count = int((_to_dict(linked).get("c") if linked else 0) or 0)
        if linked_count > 0:
            return False
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Families WHERE family_id = ?", (family_id,))
            conn.commit()
            return cursor.rowcount > 0


class SQLiteLearnerRepository(LearnerRepoPort):
    def __init__(self, db_manager) -> None:
        self.db_manager = db_manager

    @staticmethod
    def _table_exists(cursor, table_name: str) -> bool:
        cursor.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            LIMIT 1
            """,
            (table_name,),
        )
        return cursor.fetchone() is not None

    def _delete_child_rows(self, cursor, table_name: str, column_name: str, acc_no: str) -> None:
        if not self._table_exists(cursor, table_name):
            return
        cursor.execute(f'DELETE FROM "{table_name}" WHERE "{column_name}" = ?', (acc_no,))

    @staticmethod
    def _cleanup_orphan_parents(cursor, parent_ids: List[int]) -> None:
        if not parent_ids:
            return
        for parent_id in sorted(set(parent_ids)):
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM Learners
                WHERE parent_id = ? OR parent2_id = ? OR guardian_id = ?
                """,
                (parent_id, parent_id, parent_id),
            )
            remaining = cursor.fetchone()
            if remaining and int(remaining[0] or 0) == 0:
                cursor.execute("DELETE FROM Parents WHERE id = ?", (parent_id,))

    def _generate_acc_no(self) -> str:
        return f"KM{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

    def _find_or_create_parent(self, payload: Dict[str, Any]) -> int:
        contact = payload.get("contact_number") or "0000000000"
        code = payload.get("country_code") or "+27"
        existing = self.db_manager.execute_query(
            "SELECT id FROM Parents WHERE country_code = ? AND contact_number = ?",
            (code, contact),
            fetchone=True,
        )
        if existing:
            existing_dict = _to_dict(existing)
            return int(existing_dict.get("id") or existing[0])

        parent_id = self.db_manager.execute_query(
            """
            INSERT INTO Parents (title, name, surname, country_code, contact_number, email)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("title") or "",
                payload.get("name") or "Unknown",
                payload.get("surname") or "Parent",
                code,
                contact,
                payload.get("email"),
            ),
            commit=True,
        )
        return int(parent_id)

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
        row = self.db_manager.execute_query(
            """
            SELECT id FROM PaymentOptions
            WHERE option_name = ? AND grade = ? AND subjects_count = ?
            """,
            (option_name, grade, subjects_count),
            fetchone=True,
        )
        if row:
            row_dict = _to_dict(row)
            return int(row_dict.get("id") or row[0])

        option_id = self.db_manager.execute_query(
            """
            INSERT INTO PaymentOptions (option_name, subjects_count, grade, adm_reg_fee, monthly_fee)
            VALUES (?, ?, ?, ?, ?)
            """,
            (option_name, subjects_count, grade, float(0), float(monthly_fee)),
            commit=True,
        )
        return int(option_id)

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
            query += " AND (LOWER(name) LIKE ? OR LOWER(surname) LIKE ? OR LOWER(acc_no) LIKE ?)"
            like = f"%{search.lower()}%"
            params.extend([like, like, like])

        if grade is not None:
            query += " AND grade = ?"
            params.append(int(grade))

        if is_active is not None:
            query += " AND is_active = ?"
            params.append(1 if is_active else 0)

        query += " ORDER BY surname, name"
        rows = self.db_manager.execute_query(query, tuple(params), fetchall=True)
        return [_to_dict(row) for row in (rows or [])]

    def get_learner(self, acc_no: str) -> Optional[Dict[str, Any]]:
        row = self.db_manager.execute_query(
            """
            SELECT l.*,
                   lp.term_id, lp.due_day_of_month, lp.due_days_of_month, lp.scheduled_payment_dates, lp.start_date
            FROM Learners l
            LEFT JOIN (
                SELECT *
                FROM LearnerPayments
                WHERE learner_id = ?
                ORDER BY start_date DESC
                LIMIT 1
            ) lp ON l.acc_no = lp.learner_id
            WHERE l.acc_no = ?
            """,
            (acc_no, acc_no),
            fetchone=True,
        )
        if not row:
            return None
        
        learner = _to_dict(row)
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
        row = self.db_manager.execute_query(
            "SELECT * FROM Parents WHERE id = ?",
            (parent_id,),
            fetchone=True,
        )
        return _to_dict(row) if row else None

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

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO Learners (
                    acc_no, name, surname, date_of_birth, gender, country_code, contact_number,
                    email, grade, subjects_count, payment_option, parent_id, parent2_id,
                    guardian_id, family_id, is_new_learner, apply_admission_fee, is_active,
                    skip_initial_fee, custom_admission_amount_enabled, custom_admission_amount,
                    progress_percentage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                VALUES (?, ?, ?, ?, ?, ?, ?)
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

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE Learners
                SET name = ?, surname = ?, date_of_birth = ?, gender = ?, country_code = ?,
                    contact_number = ?, email = ?, grade = ?, subjects_count = ?,
                    payment_option = ?, family_id = ?, is_active = ?,
                    parent_id = ?, parent2_id = ?, guardian_id = ?,
                    skip_initial_fee = ?, custom_admission_amount_enabled = ?, custom_admission_amount = ?,
                    progress_percentage = ?
                WHERE acc_no = ?
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
                SET term_id = ?, due_day_of_month = ?, due_days_of_month = ?, scheduled_payment_dates = ?, start_date = ?
                WHERE learner_id = ?
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
        self.db_manager.execute_query(
            """
            UPDATE Parents
            SET title = ?, name = ?, surname = ?, country_code = ?,
                contact_number = ?, email = ?
            WHERE id = ?
            """,
            (
                payload.get("title"),
                payload.get("name"),
                payload.get("surname"),
                payload.get("country_code"),
                payload.get("contact_number"),
                payload.get("email"),
                parent_id,
            ),
            commit=True,
        )

    def list_learners_for_family(self, family_id: int) -> List[Dict[str, Any]]:
        rows = self.db_manager.execute_query(
            """
            SELECT acc_no, name, surname, grade, subjects_count, payment_option
            FROM Learners
            WHERE family_id = ?
            ORDER BY surname, name
            """,
            (family_id,),
            fetchall=True,
        )
        return [_to_dict(row) for row in (rows or [])]

    def list_learners_by_grade(self, grade: int) -> List[Dict[str, Any]]:
        rows = self.db_manager.execute_query(
            """
            SELECT acc_no, name, surname, grade, subjects_count, payment_option
            FROM Learners
            WHERE grade = ? AND is_active = 1
            ORDER BY surname, name
            """,
            (grade,),
            fetchall=True,
        )
        return [_to_dict(row) for row in (rows or [])]

    def set_learner_active(self, acc_no: str, is_active: bool, reason: Optional[str] = None) -> bool:
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Learners SET is_active = ? WHERE acc_no = ?", (1 if is_active else 0, acc_no))
                if cursor.rowcount <= 0:
                    conn.commit()
                    return False
                if not is_active and reason:
                    cursor.execute(
                        """
                        INSERT INTO Archive (learner_acc_no, archive_date, reason, reactivation_date)
                        VALUES (?, datetime('now'), ?, NULL)
                        """,
                        (acc_no, reason),
                    )
                if is_active:
                    cursor.execute(
                        """
                        UPDATE Archive
                        SET reactivation_date = datetime('now')
                        WHERE learner_acc_no = ? AND reactivation_date IS NULL
                        """,
                        (acc_no,),
                    )
                conn.commit()
            return True
        except Exception:
            return False

    def delete_learner(self, acc_no: str) -> bool:
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute(
                "SELECT parent_id, parent2_id, guardian_id FROM Learners WHERE acc_no = ?",
                (acc_no,),
            )
            learner = cursor.fetchone()
            if not learner:
                return False

            parent_ids = [int(parent_id) for parent_id in learner if parent_id is not None]
            for table_name, column_name in (
                ("AttendancePaymentFeed", "learner_acc_no"),
                ("AttendanceSummary", "learner_acc_no"),
                ("AttendanceRecords", "learner_acc_no"),
                ("Archive", "learner_acc_no"),
                ("Payments", "learner_id"),
                ("LearnerPayments", "learner_id"),
                ("statement_counters", "learner_id"),
            ):
                self._delete_child_rows(cursor, table_name, column_name, acc_no)

            cursor.execute("DELETE FROM Learners WHERE acc_no = ?", (acc_no,))
            deleted = cursor.rowcount > 0
            if not deleted:
                conn.commit()
                return False

            if self._table_exists(cursor, "Parents"):
                self._cleanup_orphan_parents(cursor, parent_ids)
            conn.commit()
            return True

    def get_grade_payment_rule(self, grade: int) -> Optional[Dict[str, Any]]:
        row = self.db_manager.execute_query(
            """
            SELECT grade, min_progress_percentage, change_interval_months, progress_validity_months, is_active
            FROM GradePaymentRules
            WHERE grade = ? AND is_active = 1
            """,
            (grade,),
            fetchone=True,
        )
        return _to_dict(row) if row else None

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
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE Learners
                SET progress_percentage = ?, progress_updated_date = ?, progress_eligible_until = ?
                WHERE acc_no = ?
                """,
                (float(progress_percentage), now.strftime("%Y-%m-%d %H:%M:%S"), eligible_until, acc_no),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_learner_progress_status(self, acc_no: str) -> Optional[Dict[str, Any]]:
        row = self.db_manager.execute_query(
            """
            SELECT acc_no, grade, progress_percentage, last_payment_change_date, progress_eligible_until, progress_updated_date
            FROM Learners
            WHERE acc_no = ?
            """,
            (acc_no,),
            fetchone=True,
        )
        if not row:
            return None
        data = _to_dict(row)
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
            try:
                eligible_until = datetime.strptime(str(eligible_until_raw), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                eligible_until = datetime.max
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
            try:
                last_change = datetime.strptime(str(last_change_raw), "%Y-%m-%d %H:%M:%S")
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
            except ValueError:
                pass

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
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE Learners SET last_payment_change_date = ? WHERE acc_no = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), acc_no),
            )
            conn.commit()
            return cursor.rowcount > 0


class SQLitePaymentRepository(PaymentRepoPort):
    def __init__(self, db_manager) -> None:
        self.db_manager = db_manager

    def list_payments(
        self,
        learner_acc_no: Optional[str] = None,
        family_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT payment_id, learner_id, family_id, amount, date, payment_type, month_year, description
            FROM Payments
            WHERE 1 = 1
        """
        params: List[Any] = []

        if learner_acc_no:
            query += " AND learner_id = ?"
            params.append(learner_acc_no)

        if family_id is not None:
            query += " AND family_id = ?"
            params.append(family_id)

        query += " ORDER BY date DESC, payment_id DESC LIMIT ?"
        params.append(limit)

        rows = self.db_manager.execute_query(query, tuple(params), fetchall=True)
        return [_to_dict(row) for row in (rows or [])]

    def create_payment(self, payload: Dict[str, Any]) -> int:
        amount = float(payload.get("amount") or 0)
        payment_id = self.db_manager.execute_query(
            """
            INSERT INTO Payments (learner_id, family_id, amount, date, payment_type, month_year, description, recorded_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            commit=True,
        )
        return int(payment_id)

    def delete_payment(self, payment_id: int) -> bool:
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Payments WHERE payment_id = ?", (payment_id,))
            conn.commit()
            return cursor.rowcount > 0

    def _learner_monthly_fee(self, acc_no: str) -> float:
        row = self.db_manager.execute_query(
            """
            SELECT po.monthly_fee
            FROM Learners s
            LEFT JOIN PaymentOptions po
              ON po.option_name = s.payment_option
             AND po.grade = s.grade
             AND po.subjects_count = s.subjects_count
            WHERE s.acc_no = ?
            """,
            (acc_no,),
            fetchone=True,
        )
        if not row:
            return 0.0
        row_dict = _to_dict(row)
        value = row_dict.get("monthly_fee")
        if value is None:
            return 0.0
        return float(value)

    def _learner_start_date(self, acc_no: str) -> Optional[date]:
        row = self.db_manager.execute_query(
            """
            SELECT start_date FROM LearnerPayments
            WHERE learner_id = ?
            ORDER BY start_date ASC
            LIMIT 1
            """,
            (acc_no,),
            fetchone=True,
        )
        if not row:
            return None
        value = _to_dict(row).get("start_date")
        if not value:
            return None
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                return None
        if hasattr(value, "date"):
            return value.date()
        return None

    def get_balance_for_learner(self, acc_no: str) -> float:
        payments_row = self.db_manager.execute_query(
            "SELECT COALESCE(SUM(amount), 0) AS total_paid FROM Payments WHERE learner_id = ?",
            (acc_no,),
            fetchone=True,
        )
        total_paid = float((_to_dict(payments_row).get("total_paid") if payments_row else 0) or 0)

        monthly_fee = self._learner_monthly_fee(acc_no)
        start = self._learner_start_date(acc_no)
        if not start:
            return -total_paid

        today = date.today()
        months = max(1, (today.year - start.year) * 12 + (today.month - start.month) + 1)
        estimated_charges = monthly_fee * months
        return estimated_charges - total_paid

    def get_balance_for_family(self, family_id: int) -> float:
        rows = self.db_manager.execute_query(
            "SELECT acc_no FROM Learners WHERE family_id = ?",
            (family_id,),
            fetchall=True,
        )
        total = 0.0
        for row in rows or []:
            acc_no = _to_dict(row).get("acc_no")
            if acc_no:
                total += self.get_balance_for_learner(str(acc_no))
        return total

    def list_payment_options(self) -> List[Dict[str, Any]]:
        rows = self.db_manager.execute_query(
            """
            SELECT id, option_name, subjects_count, grade, adm_reg_fee, monthly_fee
            FROM PaymentOptions
            WHERE option_name != 'MANUAL'
            ORDER BY grade, subjects_count, option_name
            """,
            fetchall=True,
        )
        return [_to_dict(row) for row in (rows or [])]

    def create_payment_option(self, payload: Dict[str, Any]) -> int:
        option_id = self.db_manager.execute_query(
            """
            INSERT INTO PaymentOptions (option_name, subjects_count, grade, adm_reg_fee, monthly_fee)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.get("option_name"),
                int(payload.get("subjects_count") or 1),
                int(payload.get("grade") or 1),
                float(payload.get("adm_reg_fee") or 0),
                float(payload.get("monthly_fee") or 0),
            ),
            commit=True,
        )
        return int(option_id)

    def update_payment_option(self, option_id: int, payload: Dict[str, Any]) -> bool:
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE PaymentOptions
                SET option_name = ?, subjects_count = ?, grade = ?, adm_reg_fee = ?, monthly_fee = ?
                WHERE id = ?
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
        in_use = self.db_manager.execute_query(
            "SELECT COUNT(*) AS c FROM LearnerPayments WHERE payment_option_id = ?",
            (option_id,),
            fetchone=True,
        )
        if int((_to_dict(in_use).get("c") if in_use else 0) or 0) > 0:
            return False
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PaymentOptions WHERE id = ?", (option_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_payment_terms(self) -> List[Dict[str, Any]]:
        rows = self.db_manager.execute_query(
            """
            SELECT term_id, term_name, description, discount_percentage
            FROM PaymentTerms
            ORDER BY term_name
            """,
            fetchall=True,
        )
        return [_to_dict(row) for row in (rows or [])]

    def create_payment_term(self, payload: Dict[str, Any]) -> int:
        term_id = self.db_manager.execute_query(
            """
            INSERT INTO PaymentTerms (term_name, description, discount_percentage)
            VALUES (?, ?, ?)
            """,
            (
                payload.get("term_name"),
                payload.get("description"),
                float(payload.get("discount_percentage") or 0),
            ),
            commit=True,
        )
        return int(term_id)

    def update_payment_term(self, term_id: int, payload: Dict[str, Any]) -> bool:
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE PaymentTerms
                SET term_name = ?, description = ?, discount_percentage = ?
                WHERE term_id = ?
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
        in_use = self.db_manager.execute_query(
            "SELECT COUNT(*) AS c FROM LearnerPayments WHERE term_id = ?",
            (term_id,),
            fetchone=True,
        )
        if int((_to_dict(in_use).get("c") if in_use else 0) or 0) > 0:
            return False
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PaymentTerms WHERE term_id = ?", (term_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_payment_statistics(
        self,
        month_year: str,
        include_on_track: bool = True,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        learner_rows = self.db_manager.execute_query(
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
            """,
            fetchall=True,
        ) or []

        payment_rows = self.db_manager.execute_query(
            """
            SELECT learner_id, COALESCE(SUM(amount), 0) AS paid
            FROM Payments
            WHERE payment_type = 'tuition' AND strftime('%Y-%m', date) = ?
            GROUP BY learner_id
            """,
            (month_year,),
            fetchall=True,
        ) or []
        paid_map = {str(_to_dict(row).get("learner_id")): float(_to_dict(row).get("paid") or 0) for row in payment_rows}

        search_term = (search or "").strip().lower()
        rows: List[Dict[str, Any]] = []
        total_due = 0.0
        total_paid = 0.0
        for raw in learner_rows:
            learner = _to_dict(raw)
            acc_no = str(learner.get("acc_no") or "")
            full_name = f"{learner.get('name', '')} {learner.get('surname', '')}".strip()
            if search_term and search_term not in full_name.lower() and search_term not in acc_no.lower():
                continue

            due = float(learner.get("monthly_fee") or 0.0)
            paid = float(paid_map.get(acc_no, 0.0))
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

        rows.sort(key=lambda r: (str(r.get("surname") or "").lower(), str(r.get("name") or "").lower()))
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
            total_row = self.db_manager.execute_query(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM Payments
                WHERE payment_type = 'tuition' AND strftime('%Y-%m', date) = ?
                """,
                (month_key,),
                fetchone=True,
            )
            total = float((_to_dict(total_row).get("total") if total_row else 0.0) or 0.0)
            out.append(
                {
                    "month_year": month_key,
                    "label": f"{calendar.month_name[int(month_key[5:7])]} {month_key[:4]}",
                    "total_collected": total,
                }
            )
        return out


class SQLiteAttendanceRepository(AttendanceRepoPort):
    def __init__(self, db_manager) -> None:
        self.db_manager = db_manager

    def list_attendance_for_date(self, iso_date: str, grade: Optional[int] = None) -> List[Dict[str, Any]]:
        query = """
            SELECT attendance_id, learner_acc_no, learner_name, learner_surname, grade, date, status,
                   check_in_time, check_out_time, notes, recorded_by, has_payment, payment_amount,
                   payment_date, payment_reference, payment_feed_status
            FROM AttendanceRecords
            WHERE date = ?
        """
        params: List[Any] = [iso_date]
        if grade is not None:
            query += " AND grade = ?"
            params.append(grade)
        query += " ORDER BY learner_surname, learner_name"

        rows = self.db_manager.execute_query(query, tuple(params), fetchall=True)
        return [_to_dict(row) for row in (rows or [])]

    def record_attendance(self, payload: Dict[str, Any]) -> int:
        existing = self.db_manager.execute_query(
            "SELECT attendance_id FROM AttendanceRecords WHERE learner_acc_no = ? AND date = ?",
            (payload.get("learner_acc_no"), payload.get("date")),
            fetchone=True,
        )
        if existing:
            attendance_id = int(_to_dict(existing).get("attendance_id") or existing[0])
            self.db_manager.execute_query(
                """
                UPDATE AttendanceRecords
                SET status = ?, check_in_time = ?, check_out_time = ?, notes = ?,
                    recorded_by = ?, has_payment = ?, payment_amount = ?, payment_date = ?,
                    payment_reference = ?, payment_feed_status = ?
                WHERE attendance_id = ?
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
                commit=True,
            )
            return attendance_id

        learner = self.db_manager.execute_query(
            "SELECT name, surname, grade FROM Learners WHERE acc_no = ?",
            (payload.get("learner_acc_no"),),
            fetchone=True,
        )
        if not learner:
            raise ValueError("Learner not found for attendance record")

        learner_dict = _to_dict(learner)
        attendance_id = self.db_manager.execute_query(
            """
            INSERT INTO AttendanceRecords (
                learner_acc_no, learner_name, learner_surname, grade, date, status,
                check_in_time, check_out_time, notes, recorded_by, has_payment,
                payment_amount, payment_date, payment_reference, payment_feed_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("learner_acc_no"),
                learner_dict.get("name"),
                learner_dict.get("surname"),
                learner_dict.get("grade") or 1,
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
            commit=True,
        )
        return int(attendance_id)

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
            WHERE date BETWEEN ? AND ?
        """
        params: List[Any] = [start_date, end_date]

        if learner_acc_no:
            query += " AND learner_acc_no = ?"
            params.append(learner_acc_no)

        if grade is not None:
            query += " AND grade = ?"
            params.append(grade)

        query += " ORDER BY date DESC, learner_surname ASC LIMIT ?"
        params.append(limit)

        rows = self.db_manager.execute_query(query, tuple(params), fetchall=True)
        return [_to_dict(row) for row in (rows or [])]

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
            WHERE date BETWEEN ? AND ?
        """
        params: List[Any] = [start_date, end_date]

        if grade is not None:
            query += " AND grade = ?"
            params.append(grade)

        query += " GROUP BY learner_acc_no, learner_name, learner_surname, grade ORDER BY learner_surname, learner_name"
        rows = self.db_manager.execute_query(query, tuple(params), fetchall=True)

        result: List[Dict[str, Any]] = []
        for row in rows or []:
            d = _to_dict(row)
            total = int(d.get("total_days") or 0)
            present = int(d.get("present_days") or 0)
            rate = round((present / total) * 100, 2) if total else 0.0
            d["attendance_rate"] = rate
            result.append(d)

        return result


class SQLiteSyncStateRepository(SyncStateRepoPort):
    def __init__(self, db_manager) -> None:
        self.db_manager = db_manager
        self._table_columns_cache: Dict[str, List[str]] = {}

    def _columns(self, table_name: str) -> List[str]:
        if table_name not in self._table_columns_cache:
            rows = self.db_manager.execute_query(f"PRAGMA table_info({table_name})", fetchall=True) or []
            cols: List[str] = []
            for row in rows:
                d = _to_dict(row)
                if "name" in d:
                    cols.append(str(d["name"]))
                elif len(row) > 1:
                    cols.append(str(row[1]))
            self._table_columns_cache[table_name] = cols
        return self._table_columns_cache[table_name]

    def _now_utc(self) -> str:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    def start_sync_run(self, user_id: Optional[int]) -> int:
        run_id = self.db_manager.execute_query(
            """
            INSERT INTO SyncRuns (user_id, started_at_utc, status, uploaded_count, downloaded_count, conflict_count)
            VALUES (?, ?, 'RUNNING', 0, 0, 0)
            """,
            (user_id, self._now_utc()),
            commit=True,
        )
        return int(run_id)

    def finish_sync_run(
        self,
        run_id: int,
        status: str,
        uploaded_count: int,
        downloaded_count: int,
        conflict_count: int,
        error_text: Optional[str] = None,
    ) -> None:
        self.db_manager.execute_query(
            """
            UPDATE SyncRuns
            SET finished_at_utc = ?, status = ?, uploaded_count = ?, downloaded_count = ?,
                conflict_count = ?, error_text = ?
            WHERE run_id = ?
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
            commit=True,
        )

    def get_client_sync_state(self, client_id: str) -> Dict[str, Any]:
        row = self.db_manager.execute_query(
            """
            SELECT client_id, last_upload_cursor, last_download_cursor,
                   last_successful_sync_at_utc, last_attempt_at_utc
            FROM SyncState WHERE client_id = ?
            """,
            (client_id,),
            fetchone=True,
        )
        if not row:
            return {
                "client_id": client_id,
                "last_upload_cursor": "1970-01-01 00:00:00",
                "last_download_cursor": "1970-01-01 00:00:00",
                "last_successful_sync_at_utc": None,
                "last_attempt_at_utc": None,
            }
        return _to_dict(row)

    def upsert_client_sync_state(
        self,
        client_id: str,
        last_upload_cursor: str,
        last_download_cursor: str,
        successful: bool,
    ) -> None:
        now = self._now_utc()
        success_time = now if successful else None

        self.db_manager.execute_query(
            """
            INSERT INTO SyncState (
                client_id, last_upload_cursor, last_download_cursor,
                last_successful_sync_at_utc, last_attempt_at_utc
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(client_id) DO UPDATE SET
                last_upload_cursor = excluded.last_upload_cursor,
                last_download_cursor = excluded.last_download_cursor,
                last_successful_sync_at_utc = CASE
                    WHEN excluded.last_successful_sync_at_utc IS NOT NULL
                    THEN excluded.last_successful_sync_at_utc
                    ELSE SyncState.last_successful_sync_at_utc
                END,
                last_attempt_at_utc = excluded.last_attempt_at_utc
            """,
            (client_id, last_upload_cursor, last_download_cursor, success_time, now),
            commit=True,
        )

    def get_dirty_rows(self, tables: List[str], limit_per_table: int = 500) -> Dict[str, List[Dict[str, Any]]]:
        result: Dict[str, List[Dict[str, Any]]] = {}
        for table in tables:
            cols = self._columns(table)
            if "is_dirty" not in cols:
                result[table] = []
                continue
            rows = self.db_manager.execute_query(
                f"SELECT * FROM {table} WHERE is_dirty = 1 ORDER BY last_modified_timestamp ASC LIMIT ?",
                (limit_per_table,),
                fetchall=True,
            )
            result[table] = [_to_dict(row) for row in (rows or [])]
        return result

    def mark_rows_clean(self, table_name: str, uuids: List[str]) -> None:
        if not uuids:
            return
        placeholders = ",".join(["?"] * len(uuids))
        self.db_manager.execute_query(
            f"UPDATE {table_name} SET is_dirty = 0 WHERE uuid IN ({placeholders})",
            tuple(uuids),
            commit=True,
        )

    def get_changes_since(
        self,
        cursor_utc: str,
        tables: List[str],
        limit_per_table: int = 500,
    ) -> Dict[str, List[Dict[str, Any]]]:
        result: Dict[str, List[Dict[str, Any]]] = {}
        for table in tables:
            cols = self._columns(table)
            if "last_modified_timestamp" not in cols:
                result[table] = []
                continue
            rows = self.db_manager.execute_query(
                f"""
                SELECT * FROM {table}
                WHERE last_modified_timestamp > ?
                ORDER BY last_modified_timestamp ASC
                LIMIT ?
                """,
                (cursor_utc, limit_per_table),
                fetchall=True,
            )
            result[table] = [_to_dict(row) for row in (rows or [])]
        return result

    def get_deleted_records(self, cursor_utc: str, limit: int = 1000) -> List[Dict[str, Any]]:
        rows = self.db_manager.execute_query(
            """
            SELECT delete_id, table_name, record_uuid, deleted_at_utc, source
            FROM SyncDeletedRecords
            WHERE deleted_at_utc > ?
            ORDER BY deleted_at_utc ASC
            LIMIT ?
            """,
            (cursor_utc, limit),
            fetchall=True,
        )
        return [_to_dict(row) for row in (rows or [])]

    def apply_remote_changes(
        self,
        changes_by_table: Dict[str, List[Dict[str, Any]]],
        tombstones: List[Dict[str, Any]],
    ) -> Tuple[int, int, int]:
        uploaded_count = 0
        downloaded_count = 0
        conflict_count = 0

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            for table_name, rows in changes_by_table.items():
                cols = self._columns(table_name)
                if not cols:
                    continue

                for remote_row in rows:
                    record_uuid = remote_row.get("uuid")
                    if not record_uuid:
                        continue

                    local = cursor.execute(
                        f"SELECT is_dirty, last_modified_timestamp FROM {table_name} WHERE uuid = ?",
                        (record_uuid,),
                    ).fetchone()

                    if local:
                        local_dirty = int(local[0] or 0)
                        local_ts = str(local[1] or "1970-01-01 00:00:00")
                        remote_ts = str(remote_row.get("last_modified_timestamp") or "1970-01-01 00:00:00")
                        if local_dirty == 1 and local_ts > remote_ts:
                            conflict_count += 1
                            cursor.execute(
                                """
                                INSERT INTO SyncConflicts (
                                    table_name, record_uuid, local_ts, remote_ts, winner, resolved_at_utc, user_id
                                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (table_name, str(record_uuid), local_ts, remote_ts, "local", self._now_utc(), None),
                            )
                            continue

                    payload = {k: v for k, v in remote_row.items() if k in cols}
                    payload["is_dirty"] = 0
                    cols_to_use = list(payload.keys())
                    placeholders = ",".join(["?"] * len(cols_to_use))
                    quoted_cols = ",".join(cols_to_use)
                    cursor.execute(
                        f"INSERT OR REPLACE INTO {table_name} ({quoted_cols}) VALUES ({placeholders})",
                        tuple(payload[c] for c in cols_to_use),
                    )
                    downloaded_count += 1

            for tombstone in tombstones:
                table_name = tombstone.get("table_name")
                record_uuid = tombstone.get("record_uuid")
                if not table_name or not record_uuid:
                    continue
                if "uuid" not in self._columns(str(table_name)):
                    continue
                cursor.execute(f"DELETE FROM {table_name} WHERE uuid = ?", (record_uuid,))
                downloaded_count += cursor.rowcount

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
        self.db_manager.execute_query(
            """
            INSERT INTO SyncConflicts (
                table_name, record_uuid, local_ts, remote_ts, winner, resolved_at_utc, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (table_name, record_uuid, local_ts, remote_ts, winner, self._now_utc(), user_id),
            commit=True,
        )
