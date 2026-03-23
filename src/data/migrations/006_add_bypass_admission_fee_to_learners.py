import logging


def upgrade(db_manager):
    """Add bypass_admission_fee column to Learners table."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE Learners ADD COLUMN bypass_admission_fee INTEGER DEFAULT 0")
        logging.info("Migration 006: Added bypass_admission_fee column to Learners table.")
    except Exception as e:
        logging.error(f"Error in migration 006: {e}")
        conn.rollback()

def downgrade(db_manager):
    """Remove bypass_admission_fee column from Learners table."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE Learners DROP COLUMN bypass_admission_fee")
        logging.info("Migration 006: Removed bypass_admission_fee column from Learners table.")
    except Exception as e:
        logging.error(f"Error in migration 006 downgrade: {e}")
        conn.rollback()
