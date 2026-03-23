def upgrade(db_manager):
    """Creates the Attendance table."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            learner_acc_no TEXT NOT NULL,
            date TEXT NOT NULL,
            present INTEGER NOT NULL DEFAULT 0,
            signature_image BLOB,
            FOREIGN KEY(learner_acc_no) REFERENCES Learners(acc_no) ON DELETE CASCADE,
            UNIQUE(learner_acc_no, date)
        )
    ''')

    # conn.commit() # Removed