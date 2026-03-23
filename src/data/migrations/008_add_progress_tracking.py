def _column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall() or [])


def upgrade(db_manager):
    """Adds progress tracking fields for grade 1-7 payment restrictions (idempotent)."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    # Add progress tracking fields to Learners table only when missing.
    if not _column_exists(cursor, "Learners", "progress_percentage"):
        cursor.execute(
            """
            ALTER TABLE Learners
            ADD COLUMN progress_percentage REAL DEFAULT 0.0
            CHECK (progress_percentage >= 0 AND progress_percentage <= 100)
            """
        )
    if not _column_exists(cursor, "Learners", "last_payment_change_date"):
        cursor.execute("ALTER TABLE Learners ADD COLUMN last_payment_change_date TEXT")
    if not _column_exists(cursor, "Learners", "progress_eligible_until"):
        cursor.execute("ALTER TABLE Learners ADD COLUMN progress_eligible_until TEXT")
    if not _column_exists(cursor, "Learners", "progress_updated_date"):
        cursor.execute("ALTER TABLE Learners ADD COLUMN progress_updated_date TEXT")

    # Create table for grade 1-7 payment rules.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS GradePaymentRules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            grade INTEGER NOT NULL CHECK (grade >= 1 AND grade <= 7),
            min_progress_percentage REAL NOT NULL DEFAULT 60.0 CHECK (min_progress_percentage >= 0 AND min_progress_percentage <= 100),
            change_interval_months INTEGER NOT NULL DEFAULT 6 CHECK (change_interval_months > 0),
            progress_validity_months INTEGER NOT NULL DEFAULT 12 CHECK (progress_validity_months > 0),
            is_active INTEGER NOT NULL DEFAULT 1,
            last_modified_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_dirty INTEGER DEFAULT 0,
            UNIQUE(grade)
        )
        """
    )

    # Insert default rules for grades 1-7.
    default_rules = []
    for grade in range(1, 8):
        if grade <= 3:
            min_progress = 50.0
            interval_months = 3
        else:
            min_progress = 60.0
            interval_months = 6
        default_rules.append((grade, min_progress, interval_months, 12))

    for grade, min_progress, interval, validity in default_rules:
        cursor.execute(
            """
            INSERT OR IGNORE INTO GradePaymentRules (grade, min_progress_percentage, change_interval_months, progress_validity_months)
            VALUES (?, ?, ?, ?)
            """,
            (grade, min_progress, interval, validity),
        )

    # Keep sync fields populated for this table.
    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS GradePaymentRules_insert_trigger
        AFTER INSERT ON GradePaymentRules
        FOR EACH ROW
        BEGIN
            UPDATE GradePaymentRules
            SET last_modified_timestamp = CURRENT_TIMESTAMP,
                is_dirty = 1,
                uuid = (select lower(hex(randomblob(16))))
            WHERE rowid = NEW.rowid;
        END;
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS GradePaymentRules_update_trigger
        AFTER UPDATE ON GradePaymentRules
        FOR EACH ROW
        BEGIN
            UPDATE GradePaymentRules
            SET last_modified_timestamp = CURRENT_TIMESTAMP,
                is_dirty = 1
            WHERE rowid = NEW.rowid;
        END;
        """
    )

    conn.commit()
