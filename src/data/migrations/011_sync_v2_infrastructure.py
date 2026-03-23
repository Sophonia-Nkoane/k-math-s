"""
Migration 011: Sync V2 Infrastructure

Adds tables and triggers required for daily two-way desktop/web synchronization.
"""

import logging


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table_name})")
    cols = [row[1] for row in cursor.fetchall()]
    return column_name in cols


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table_name,))
    return cursor.fetchone() is not None


def _safe_add_column(cursor, table_name: str, sql: str, column_name: str) -> None:
    if not _table_exists(cursor, table_name):
        return
    if _column_exists(cursor, table_name, column_name):
        return
    cursor.execute(sql)


def _create_sync_tables(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS SyncDeletedRecords (
            delete_id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            record_uuid TEXT NOT NULL,
            deleted_at_utc TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%S', 'NOW')),
            source TEXT,
            UNIQUE(table_name, record_uuid, deleted_at_utc)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS SyncState (
            client_id TEXT PRIMARY KEY,
            last_upload_cursor TEXT NOT NULL DEFAULT '1970-01-01 00:00:00',
            last_download_cursor TEXT NOT NULL DEFAULT '1970-01-01 00:00:00',
            last_successful_sync_at_utc TEXT,
            last_attempt_at_utc TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS SyncConflicts (
            conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            record_uuid TEXT NOT NULL,
            local_ts TEXT NOT NULL,
            remote_ts TEXT NOT NULL,
            winner TEXT NOT NULL,
            resolved_at_utc TEXT NOT NULL,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS SyncRuns (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            started_at_utc TEXT NOT NULL,
            finished_at_utc TEXT,
            status TEXT NOT NULL,
            uploaded_count INTEGER NOT NULL DEFAULT 0,
            downloaded_count INTEGER NOT NULL DEFAULT 0,
            conflict_count INTEGER NOT NULL DEFAULT 0,
            error_text TEXT,
            FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_deleted_time ON SyncDeletedRecords(deleted_at_utc)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_conflicts_time ON SyncConflicts(resolved_at_utc)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_runs_started ON SyncRuns(started_at_utc)")


def _ensure_sync_columns(cursor) -> None:
    synced_tables = [
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

    for table in synced_tables:
        if not _table_exists(cursor, table):
            continue

        _safe_add_column(
            cursor,
            table,
            f"ALTER TABLE {table} ADD COLUMN uuid TEXT",
            "uuid",
        )
        _safe_add_column(
            cursor,
            table,
            # SQLite does not allow non-constant defaults (e.g. CURRENT_TIMESTAMP)
            # when adding a column via ALTER TABLE on existing tables.
            f"ALTER TABLE {table} ADD COLUMN last_modified_timestamp DATETIME",
            "last_modified_timestamp",
        )
        _safe_add_column(
            cursor,
            table,
            f"ALTER TABLE {table} ADD COLUMN is_dirty INTEGER DEFAULT 0",
            "is_dirty",
        )

        cursor.execute(f"UPDATE {table} SET uuid = lower(hex(randomblob(16))) WHERE uuid IS NULL OR uuid = ''")
        cursor.execute(
            f"""
            UPDATE {table}
            SET last_modified_timestamp = COALESCE(last_modified_timestamp, CURRENT_TIMESTAMP)
            WHERE last_modified_timestamp IS NULL OR last_modified_timestamp = ''
            """
        )


def _create_data_change_triggers(cursor) -> None:
    tables = [
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

    for table in tables:
        if not _table_exists(cursor, table):
            continue

        cursor.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS {table}_syncv2_insert_trigger
            AFTER INSERT ON {table}
            FOR EACH ROW
            BEGIN
                UPDATE {table}
                SET
                    uuid = COALESCE(NULLIF(uuid, ''), lower(hex(randomblob(16)))),
                    last_modified_timestamp = CURRENT_TIMESTAMP,
                    is_dirty = 1
                WHERE rowid = NEW.rowid;
            END;
            """
        )

        cursor.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS {table}_syncv2_update_trigger
            AFTER UPDATE ON {table}
            FOR EACH ROW
            BEGIN
                UPDATE {table}
                SET
                    last_modified_timestamp = CURRENT_TIMESTAMP,
                    is_dirty = 1
                WHERE rowid = NEW.rowid;
            END;
            """
        )

        cursor.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS {table}_syncv2_delete_trigger
            AFTER DELETE ON {table}
            FOR EACH ROW
            BEGIN
                INSERT INTO SyncDeletedRecords (table_name, record_uuid, deleted_at_utc, source)
                VALUES ('{table}', OLD.uuid, STRFTIME('%Y-%m-%d %H:%M:%S', 'NOW'), 'sqlite');
            END;
            """
        )


def upgrade(db_manager):
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    _create_sync_tables(cursor)
    _ensure_sync_columns(cursor)
    _create_data_change_triggers(cursor)

    cursor.execute(
        """
        INSERT OR IGNORE INTO SystemSettings (setting_name, setting_value)
        VALUES ('sync_v2_enabled', 'true')
        """
    )
    cursor.execute(
        """
        INSERT OR IGNORE INTO SystemSettings (setting_name, setting_value)
        VALUES ('sync_daily_time', '02:00')
        """
    )
    cursor.execute(
        """
        INSERT OR IGNORE INTO SystemSettings (setting_name, setting_value)
        VALUES ('go_live_timestamp', STRFTIME('%Y-%m-%d %H:%M:%S', 'NOW'))
        """
    )

    logging.info("Migration 011: Sync V2 infrastructure created successfully")


def downgrade(db_manager):
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS SyncRuns")
    cursor.execute("DROP TABLE IF EXISTS SyncConflicts")
    cursor.execute("DROP TABLE IF EXISTS SyncState")
    cursor.execute("DROP TABLE IF EXISTS SyncDeletedRecords")

    logging.info("Migration 011: Sync V2 infrastructure removed")
