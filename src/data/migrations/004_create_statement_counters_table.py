import sqlite3

def upgrade(db_manager):
    conn = db_manager.get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS statement_counters (
            learner_id TEXT PRIMARY KEY,
            current_statement_month_year TEXT,
            number_for_current_month INTEGER,
            next_global_sequence_for_learner INTEGER,
            year_count INTEGER,
            last_statement_year INTEGER,
            last_statement_period INTEGER
        )
    ''')
    # conn.commit() # Removed

def downgrade(db_manager):
    conn = db_manager.get_connection()
    c = conn.cursor()
    c.execute('DROP TABLE IF EXISTS statement_counters')
    # conn.commit() # Removed