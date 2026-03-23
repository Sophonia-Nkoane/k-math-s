import bcrypt

def upgrade(db_manager):
    """Creates the initial database schema."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    _create_users_table(cursor)
    _create_parents_table(cursor)
    _create_families_table(cursor)
    _create_learners_table(cursor)
    _create_payment_options_table(cursor)
    _create_payment_terms_table(cursor)
    _create_payments_table(cursor)
    _create_audit_log_table(cursor)
    _create_learner_payments_table(cursor)
    _create_archive_table(cursor)
    _create_system_settings_table(cursor)
    _create_triggers(cursor)
    _create_indexes(cursor)
    _ensure_admin_user_exists(cursor)

    # conn.commit() # Removed

def _create_users_table(cursor):
    """Creates the Users table if it doesn't exist."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'user')) DEFAULT 'user',
            last_modified_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_dirty INTEGER DEFAULT 0
        )
    ''')

def _create_parents_table(cursor):
    """Creates the Parents table if it doesn't exist."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Parents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            title TEXT,
            name TEXT,
            surname TEXT,
            country_code TEXT,
            contact_number TEXT,
            email TEXT,
            last_modified_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_dirty INTEGER DEFAULT 0,
            UNIQUE(contact_number)
        )
    ''')

def _create_families_table(cursor):
    """Creates the Families table if it doesn't exist."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Families (
            family_id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            family_name TEXT,
            family_account_no TEXT UNIQUE,
            payment_mode TEXT DEFAULT 'individual_discount' CHECK(payment_mode IN ('single_coverage', 'individual_discount')),
            discount_percentage REAL DEFAULT 0.0 CHECK (discount_percentage >= 0 AND discount_percentage <= 100),
            last_modified_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_dirty INTEGER DEFAULT 0
        )
    ''')

def _create_learners_table(cursor):
    """Creates the Learners table if it doesn't exist."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Learners (
            acc_no TEXT PRIMARY KEY,
            uuid TEXT UNIQUE,
            name TEXT NOT NULL,
            surname TEXT NOT NULL,
            date_of_birth TEXT,
            gender TEXT,
            country_code TEXT,
            contact_number TEXT,
            email TEXT,
            grade INTEGER NOT NULL,
            subjects_count INTEGER NOT NULL,
            payment_option TEXT,
            total_payment REAL DEFAULT 0,
            parent_id INTEGER NOT NULL,
            is_new_learner INTEGER NOT NULL DEFAULT 1,
            apply_admission_fee INTEGER NOT NULL DEFAULT 1,
            family_id INTEGER,
            parent2_id INTEGER,
            guardian_id INTEGER,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_modified_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_dirty INTEGER DEFAULT 0,
            FOREIGN KEY (parent_id) REFERENCES Parents (id) ON DELETE RESTRICT,
            FOREIGN KEY (parent2_id) REFERENCES Parents (id) ON DELETE SET NULL,
            FOREIGN KEY (guardian_id) REFERENCES Parents (id) ON DELETE SET NULL,
            FOREIGN KEY (family_id) REFERENCES Families (family_id) ON DELETE RESTRICT
        )
    ''')

def _create_payment_options_table(cursor):
    """Creates the PaymentOptions table if it doesn't exist."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS PaymentOptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            option_name TEXT NOT NULL,
            subjects_count INTEGER NOT NULL,
            grade INTEGER NOT NULL,
            adm_reg_fee REAL DEFAULT 0.0,
            monthly_fee REAL DEFAULT 0.0,
            last_modified_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_dirty INTEGER DEFAULT 0,
            UNIQUE(option_name, subjects_count, grade)
        )
    ''')

def _create_payment_terms_table(cursor):
    """Creates the PaymentTerms table if it doesn't exist."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS PaymentTerms (
            term_id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            term_name TEXT NOT NULL UNIQUE,
            description TEXT,
            discount_percentage REAL DEFAULT 0.0 CHECK (discount_percentage >= 0 AND discount_percentage <= 100),
            last_modified_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_dirty INTEGER DEFAULT 0
        )
    ''')

    # Create default payment terms if they don't exist
    default_terms = [
        ('Monthly', 'Standard monthly payment', 0.0),
        ('Quarterly', 'Quarterly payment with discount', 5.0),
        ('Annually', 'Annual payment with discount', 10.0)
    ]

    for term_name, description, discount in default_terms:
        cursor.execute('''
            INSERT OR IGNORE INTO PaymentTerms (term_name, description, discount_percentage)
            VALUES (?, ?, ?)
        ''', (term_name, description, discount))

def _create_payments_table(cursor):
    """Creates the Payments table if it doesn't exist."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            learner_id TEXT,
            family_id INTEGER,
            amount REAL NOT NULL CHECK (amount >= 0),
            date TEXT NOT NULL,
            payment_type TEXT NOT NULL DEFAULT 'tuition' CHECK(payment_type IN ('tuition', 'admission', 'other')),
            month_year TEXT,
            description TEXT,
            recorded_by_user_id INTEGER,
            last_modified_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_dirty INTEGER DEFAULT 0,
            FOREIGN KEY (learner_id) REFERENCES Learners (acc_no) ON DELETE CASCADE,
            FOREIGN KEY (family_id) REFERENCES Families (family_id) ON DELETE CASCADE,
            FOREIGN KEY (recorded_by_user_id) REFERENCES Users (user_id) ON DELETE SET NULL,
            CHECK (
                (learner_id IS NOT NULL AND family_id IS NULL) OR
                (learner_id IS NULL AND family_id IS NOT NULL) OR
                (learner_id IS NULL AND family_id IS NULL AND payment_type = 'other')
            ),
            CHECK (payment_type != 'tuition' OR month_year IS NOT NULL)
        )
    ''')

def _create_audit_log_table(cursor):
    """Creates the AuditLog table if it doesn't exist."""
    cursor.execute('''
       CREATE TABLE IF NOT EXISTS AuditLog (
           log_id INTEGER PRIMARY KEY AUTOINCREMENT,
           uuid TEXT UNIQUE,
           user_id INTEGER,
           action_type TEXT NOT NULL,
           object_type TEXT,
           object_id TEXT,
           timestamp TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW')),
           details TEXT,
           last_modified_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
           is_dirty INTEGER DEFAULT 0,
           FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE SET NULL
        )
    ''')

def _create_learner_payments_table(cursor):
    """Creates the LearnerPayments table if it doesn't exist."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS LearnerPayments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            learner_id TEXT NOT NULL,
            term_id INTEGER NOT NULL,
            payment_option_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            due_day_of_month INTEGER DEFAULT 1 CHECK(due_day_of_month BETWEEN 1 AND 31),
            due_days_of_month TEXT,
            scheduled_payment_dates TEXT,
            last_modified_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_dirty INTEGER DEFAULT 0,
            FOREIGN KEY (learner_id) REFERENCES Learners (acc_no) ON DELETE CASCADE,
            FOREIGN KEY (term_id) REFERENCES PaymentTerms (term_id) ON DELETE RESTRICT,
            FOREIGN KEY (payment_option_id) REFERENCES PaymentOptions (id) ON DELETE RESTRICT,
            UNIQUE (learner_id, end_date)
        )
    ''')

def _create_archive_table(cursor):
    """Creates the Archive table for logging paused billing events."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Archive (
            archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
            learner_acc_no TEXT NOT NULL,
            archive_date TEXT NOT NULL,
            reason TEXT,
            expected_return_date TEXT,
            archived_by_user_id INTEGER,
            notes TEXT,
            reactivation_date TEXT,
            reactivated_by_user_id INTEGER,
            FOREIGN KEY (learner_acc_no) REFERENCES Learners (acc_no) ON DELETE CASCADE,
            FOREIGN KEY (archived_by_user_id) REFERENCES Users (user_id) ON DELETE SET NULL,
            FOREIGN KEY (reactivated_by_user_id) REFERENCES Users (user_id) ON DELETE SET NULL
        )
    ''')

def _create_system_settings_table(cursor):
    """Creates the SystemSettings table if it doesn't exist."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS SystemSettings (
            setting_name TEXT PRIMARY KEY,
            setting_value TEXT
        )
    """)
    default_settings = [
        ('billing_start_day', '1'),
        ('fee_calc_mode', 'Standard'),
        ('adm_fee_new_only', 'true'),
        ('adm_fee_mode', 'One-time'),
        ('last_sync_timestamp', '1970-01-01 00:00:00')
    ]
    for setting_name, default_value in default_settings:
        cursor.execute("""
            INSERT OR IGNORE INTO SystemSettings (setting_name, setting_value) 
            VALUES (?, ?)
        """, (setting_name, default_value))

def _create_indexes(cursor):
    """Creates optimized indexes for production performance."""
    index_definitions = [
        ("idx_learners_family_id", "Learners(family_id)"),
        ("idx_learners_parent_id", "Learners(parent_id)"),
        ("idx_learners_is_active", "Learners(is_active)"),
        ("idx_payments_learner_id", "Payments(learner_id)"),
        ("idx_payments_family_id", "Payments(family_id)"),
        ("idx_payments_month_year", "Payments(month_year)"),
        ("idx_payments_date", "Payments(date)"),
        ("idx_auditlog_timestamp", "AuditLog(timestamp)"),
        ("idx_auditlog_object", "AuditLog(object_type, object_id)"),
        ("idx_learnerpayments_learner_id", "LearnerPayments(learner_id)")
    ]
    for index_name, index_def in index_definitions:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_def}")

def _create_triggers(cursor):
    """Creates triggers to automatically update last_modified_timestamp and is_dirty flag."""
    tables = ['Users', 'Parents', 'Families', 'Learners', 'PaymentOptions', 'PaymentTerms', 'Payments', 'LearnerPayments']
    for table in tables:
        cursor.execute(f'''
            CREATE TRIGGER IF NOT EXISTS {table}_insert_trigger
            AFTER INSERT ON {table}
            FOR EACH ROW
            BEGIN
                UPDATE {table}
                SET last_modified_timestamp = CURRENT_TIMESTAMP,
                    is_dirty = 1,
                    uuid = (select lower(hex(randomblob(16))))
                WHERE rowid = NEW.rowid;
            END;
        ''')
        cursor.execute(f'''
            CREATE TRIGGER IF NOT EXISTS {table}_update_trigger
            AFTER UPDATE ON {table}
            FOR EACH ROW
            BEGIN
                UPDATE {table}
                SET last_modified_timestamp = CURRENT_TIMESTAMP,
                    is_dirty = 1
                WHERE rowid = NEW.rowid;
            END;
        ''')

def _ensure_admin_user_exists(cursor):
    """Ensures system has an admin user with secure password handling."""
    cursor.execute("SELECT COUNT(*) FROM Users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        hashed_password = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt())
        cursor.execute(
            "INSERT INTO Users (username, password, role) VALUES (?, ?, ?)",
            (hashed_password.decode('utf-8'), 'admin', 'admin')
        )
