import logging


def upgrade(db_manager):
    """Add is_dirty column to various tables."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    tables = [
        "Users", "Parents", "Families", "Learners",
        "PaymentOptions", "PaymentTerms", "Payments", "LearnerPayments"
    ]
    
    for table in tables:
        try:
            # Check if column exists before adding
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            if "is_dirty" not in columns:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN is_dirty INTEGER NOT NULL DEFAULT 0")
                logging.info(f"Migration 003: Added is_dirty column to {table}.")
            else:
                logging.info(f"Migration 003: Column is_dirty already exists in {table}. Skipping.")
        except Exception as e:
            logging.error(f"Error adding is_dirty to {table}: {e}")
            # Continue even if one fails, as some tables might already have it
    # conn.commit() # Removed

def downgrade(db_manager):
    """Remove is_dirty column from various tables (SQLite limitation)."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    tables = [
        "Users", "Parents", "Families", "Learners",
        "PaymentOptions", "PaymentTerms", "Payments", "LearnerPayments"
    ]
    
    logging.info("Migration 003: Downgrade - Attempting to remove is_dirty column.")
    logging.info("Note: SQLite does not directly support DROP COLUMN. This operation might fail or require manual intervention.")
    
    for table in tables:
        try:
            # This will likely fail on SQLite unless it's a fresh table
            cursor.execute(f"ALTER TABLE {table} DROP COLUMN is_dirty")
            logging.info(f"Migration 003: Removed is_dirty column from {table}.")
        except Exception as e:
            logging.error(f"Error removing is_dirty from {table}: {e}")
    # conn.commit() # Removed
