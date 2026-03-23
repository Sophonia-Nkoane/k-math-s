import logging


def upgrade(db_manager):
    """Add skip_initial_fee column to Learners table."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE Learners ADD COLUMN skip_initial_fee INTEGER DEFAULT 0")
        logging.info("Migration 005: Added skip_initial_fee column to Learners table.")
    except Exception as e:
        logging.error(f"Error in migration 005: {e}")
        conn.rollback()

def downgrade(db_manager):
    """Remove skip_initial_fee column from Learners table."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE Learners DROP COLUMN skip_initial_fee")
        logging.info("Migration 005: Removed skip_initial_fee column from Learners table.")
    except Exception as e:
        logging.error(f"Error in migration 005 downgrade: {e}")
        conn.rollback()
