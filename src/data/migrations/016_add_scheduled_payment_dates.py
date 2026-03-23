import logging


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return column_name in {row[1] for row in cursor.fetchall()}


def upgrade(db_manager):
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        if not _column_exists(cursor, "LearnerPayments", "scheduled_payment_dates"):
            cursor.execute("ALTER TABLE LearnerPayments ADD COLUMN scheduled_payment_dates TEXT")

        logging.info("Migration 016: Added scheduled_payment_dates to LearnerPayments")


def downgrade(db_manager):
    logging.info("Migration 016 downgrade skipped: SQLite does not support dropping columns directly")
