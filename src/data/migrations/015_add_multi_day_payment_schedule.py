import logging


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return column_name in {row[1] for row in cursor.fetchall()}


def upgrade(db_manager):
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        if not _column_exists(cursor, "LearnerPayments", "due_days_of_month"):
            cursor.execute("ALTER TABLE LearnerPayments ADD COLUMN due_days_of_month TEXT")

        cursor.execute(
            """
            UPDATE LearnerPayments
            SET due_days_of_month = '[' || CAST(COALESCE(due_day_of_month, 1) AS TEXT) || ']'
            WHERE due_days_of_month IS NULL OR TRIM(due_days_of_month) = ''
            """
        )

        logging.info("Migration 015: Added due_days_of_month to LearnerPayments")


def downgrade(db_manager):
    logging.info("Migration 015 downgrade skipped: SQLite does not support dropping columns directly")
