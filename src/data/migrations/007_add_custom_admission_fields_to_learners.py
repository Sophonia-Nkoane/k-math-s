import logging


def upgrade(db_manager):
    """Add custom_admission_amount_enabled and custom_admission_amount columns to Learners table."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    try:
        # Add custom_admission_amount_enabled
        cursor.execute("PRAGMA table_info(Learners)")
        columns = [col[1] for col in cursor.fetchall()]
        if "custom_admission_amount_enabled" not in columns:
            cursor.execute("ALTER TABLE Learners ADD COLUMN custom_admission_amount_enabled INTEGER DEFAULT 0")
            logging.info("Migration 007: Added custom_admission_amount_enabled column to Learners table.")
        else:
            logging.info("Migration 007: Column custom_admission_amount_enabled already exists. Skipping.")

        # Add custom_admission_amount
        cursor.execute("PRAGMA table_info(Learners)")
        columns = [col[1] for col in cursor.fetchall()]
        if "custom_admission_amount" not in columns:
            cursor.execute("ALTER TABLE Learners ADD COLUMN custom_admission_amount REAL")
            logging.info("Migration 007: Added custom_admission_amount column to Learners table.")
        else:
            logging.info("Migration 007: Column custom_admission_amount already exists. Skipping.")

        # Attempt to drop bypass_admission_fee if it exists (from previous migration)
        cursor.execute("PRAGMA table_info(Learners)")
        columns = [col[1] for col in cursor.fetchall()]
        if "bypass_admission_fee" in columns:
            try:
                cursor.execute("ALTER TABLE Learners DROP COLUMN bypass_admission_fee")
                logging.info("Migration 007: Removed bypass_admission_fee column from Learners table.")
            except Exception as e:
                logging.warning(f"Migration 007: Could not drop bypass_admission_fee column (SQLite limitation?): {e}")
        
    except Exception as e:
        logging.error(f"Error in migration 007: {e}")
        conn.rollback()

def downgrade(db_manager):
    """Remove custom_admission_amount_enabled and custom_admission_amount columns from Learners table."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    try:
        # Remove custom_admission_amount
        cursor.execute("PRAGMA table_info(Learners)")
        columns = [col[1] for col in cursor.fetchall()]
        if "custom_admission_amount" in columns:
            try:
                cursor.execute("ALTER TABLE Learners DROP COLUMN custom_admission_amount")
                logging.info("Migration 007: Removed custom_admission_amount column from Learners table.")
            except Exception as e:
                logging.warning(f"Migration 007: Could not drop custom_admission_amount column (SQLite limitation?): {e}")

        # Remove custom_admission_amount_enabled
        cursor.execute("PRAGMA table_info(Learners)")
        columns = [col[1] for col in cursor.fetchall()]
        if "custom_admission_amount_enabled" in columns:
            try:
                cursor.execute("ALTER TABLE Learners DROP COLUMN custom_admission_amount_enabled")
                logging.info("Migration 007: Removed custom_admission_amount_enabled column from Learners table.")
            except Exception as e:
                logging.warning(f"Migration 007: Could not drop custom_admission_amount_enabled column (SQLite limitation?): {e}")

    except Exception as e:
        logging.error(f"Error in migration 007 downgrade: {e}")
        conn.rollback()
