import logging


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,))
    return cursor.fetchone() is not None


def upgrade(db_manager):
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS AppSettings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT,
                uuid TEXT UNIQUE,
                last_modified_timestamp DATETIME,
                is_dirty INTEGER DEFAULT 0
            )
            """
        )
        cursor.execute(
            """
            UPDATE AppSettings
            SET uuid = lower(hex(randomblob(16)))
            WHERE uuid IS NULL OR uuid = ''
            """
        )
        cursor.execute(
            """
            UPDATE AppSettings
            SET last_modified_timestamp = COALESCE(last_modified_timestamp, CURRENT_TIMESTAMP)
            WHERE last_modified_timestamp IS NULL OR last_modified_timestamp = ''
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS AppSettings_syncv2_insert_trigger
            AFTER INSERT ON AppSettings
            FOR EACH ROW
            BEGIN
                UPDATE AppSettings
                SET
                    uuid = COALESCE(NULLIF(uuid, ''), lower(hex(randomblob(16)))),
                    last_modified_timestamp = CURRENT_TIMESTAMP,
                    is_dirty = 1
                WHERE rowid = NEW.rowid;
            END;
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS AppSettings_syncv2_update_trigger
            AFTER UPDATE ON AppSettings
            FOR EACH ROW
            BEGIN
                UPDATE AppSettings
                SET
                    last_modified_timestamp = CURRENT_TIMESTAMP,
                    is_dirty = 1
                WHERE rowid = NEW.rowid;
            END;
            """
        )
        if _table_exists(cursor, "SyncDeletedRecords"):
            cursor.execute(
                """
                CREATE TRIGGER IF NOT EXISTS AppSettings_syncv2_delete_trigger
                AFTER DELETE ON AppSettings
                FOR EACH ROW
                BEGIN
                    INSERT INTO SyncDeletedRecords (table_name, record_uuid, deleted_at_utc, source)
                    VALUES ('AppSettings', OLD.uuid, STRFTIME('%Y-%m-%d %H:%M:%S', 'NOW'), 'sqlite');
                END;
                """
            )

        logging.info("Migration 014: AppSettings table created successfully")


def downgrade(db_manager):
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TRIGGER IF EXISTS AppSettings_syncv2_delete_trigger")
        cursor.execute("DROP TRIGGER IF EXISTS AppSettings_syncv2_update_trigger")
        cursor.execute("DROP TRIGGER IF EXISTS AppSettings_syncv2_insert_trigger")
        cursor.execute("DROP TABLE IF EXISTS AppSettings")
        logging.info("Migration 014: AppSettings table removed")
