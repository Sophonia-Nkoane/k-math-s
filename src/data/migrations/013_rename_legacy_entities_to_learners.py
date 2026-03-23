import logging


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,))
    return cursor.fetchone() is not None


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    if not _table_exists(cursor, table_name):
        return False
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in (cursor.fetchall() or []))


def _rename_table(cursor, old_name: str, new_name: str) -> None:
    if not _table_exists(cursor, old_name) or _table_exists(cursor, new_name):
        return
    cursor.execute(f"ALTER TABLE {old_name} RENAME TO {new_name}")


def _rename_column(cursor, table_name: str, old_name: str, new_name: str) -> None:
    if not _column_exists(cursor, table_name, old_name) or _column_exists(cursor, table_name, new_name):
        return
    cursor.execute(f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name}")


def _update_sync_metadata(cursor, table_name: str, old_value: str, new_value: str) -> None:
    if not _table_exists(cursor, table_name) or not _column_exists(cursor, table_name, "table_name"):
        return
    cursor.execute(
        f"UPDATE {table_name} SET table_name = ? WHERE table_name = ?",
        (new_value, old_value),
    )


def upgrade(db_manager):
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        _rename_table(cursor, "Students", "Learners")
        _rename_table(cursor, "StudentPayments", "LearnerPayments")

        _rename_column(cursor, "Learners", "is_new_student", "is_new_learner")
        _rename_column(cursor, "Payments", "student_id", "learner_id")
        _rename_column(cursor, "LearnerPayments", "student_id", "learner_id")
        _rename_column(cursor, "Archive", "student_acc_no", "learner_acc_no")
        _rename_column(cursor, "AttendanceRecords", "student_acc_no", "learner_acc_no")
        _rename_column(cursor, "AttendanceRecords", "student_name", "learner_name")
        _rename_column(cursor, "AttendanceRecords", "student_surname", "learner_surname")
        _rename_column(cursor, "AttendanceSummary", "student_acc_no", "learner_acc_no")
        _rename_column(cursor, "AttendancePaymentFeed", "student_acc_no", "learner_acc_no")
        _rename_column(cursor, "AttendancePaymentFeed", "student_name", "learner_name")
        _rename_column(cursor, "AttendancePaymentFeed", "student_surname", "learner_surname")
        _rename_column(cursor, "statement_counters", "student_id", "learner_id")

        _update_sync_metadata(cursor, "SyncDeletedRecords", "Students", "Learners")
        _update_sync_metadata(cursor, "SyncDeletedRecords", "StudentPayments", "LearnerPayments")
        _update_sync_metadata(cursor, "SyncConflicts", "Students", "Learners")
        _update_sync_metadata(cursor, "SyncConflicts", "StudentPayments", "LearnerPayments")

        logging.info("Migration 013: legacy student schema renamed to learner schema")


def downgrade(db_manager):
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        _rename_column(cursor, "statement_counters", "learner_id", "student_id")
        _rename_column(cursor, "AttendancePaymentFeed", "learner_surname", "student_surname")
        _rename_column(cursor, "AttendancePaymentFeed", "learner_name", "student_name")
        _rename_column(cursor, "AttendancePaymentFeed", "learner_acc_no", "student_acc_no")
        _rename_column(cursor, "AttendanceSummary", "learner_acc_no", "student_acc_no")
        _rename_column(cursor, "AttendanceRecords", "learner_surname", "student_surname")
        _rename_column(cursor, "AttendanceRecords", "learner_name", "student_name")
        _rename_column(cursor, "AttendanceRecords", "learner_acc_no", "student_acc_no")
        _rename_column(cursor, "Archive", "learner_acc_no", "student_acc_no")
        _rename_column(cursor, "LearnerPayments", "learner_id", "student_id")
        _rename_column(cursor, "Payments", "learner_id", "student_id")
        _rename_column(cursor, "Learners", "is_new_learner", "is_new_student")

        _rename_table(cursor, "LearnerPayments", "StudentPayments")
        _rename_table(cursor, "Learners", "Students")

        _update_sync_metadata(cursor, "SyncDeletedRecords", "Learners", "Students")
        _update_sync_metadata(cursor, "SyncDeletedRecords", "LearnerPayments", "StudentPayments")
        _update_sync_metadata(cursor, "SyncConflicts", "Learners", "Students")
        _update_sync_metadata(cursor, "SyncConflicts", "LearnerPayments", "StudentPayments")

        logging.info("Migration 013: learner schema downgraded to legacy student schema")
