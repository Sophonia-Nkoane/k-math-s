import logging


def upgrade(db_manager):
    """Add theme column to Users table."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if column exists before adding
        cursor.execute("PRAGMA table_info(Users)")
        columns = [col[1] for col in cursor.fetchall()]
        if "theme" not in columns:
            cursor.execute("ALTER TABLE Users ADD COLUMN theme TEXT DEFAULT 'system' CHECK(theme IN ('light', 'dark', 'system'))")
            logging.info("Migration 012: Added theme column to Users.")
        else:
            logging.info("Migration 012: Column theme already exists in Users. Skipping.")
    except Exception as e:
        logging.error(f"Error adding theme to Users: {e}")


def downgrade(db_manager):
    """Remove theme column from Users table (SQLite limitation - not supported)."""
    logging.warning("Downgrade for migration 012 not supported in SQLite.")