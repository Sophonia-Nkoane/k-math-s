"""
Migration: Create statement generation log table
Created: 2026-02-25
Purpose: Track automatic statement generation history for auditing and monitoring
"""

import logging


def upgrade(db_manager):
    """Create the statement_generation_log table."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS statement_generation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            statements_generated INTEGER NOT NULL DEFAULT 0,
            emails_sent INTEGER NOT NULL DEFAULT 0,
            errors_count INTEGER NOT NULL DEFAULT 0,
            duration_seconds INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'PENDING',
            error_message TEXT,
            error_details TEXT,
            triggered_by TEXT DEFAULT 'AUTOMATIC',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create index for faster queries on generation_date
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_generation_log_date 
        ON statement_generation_log(generation_date)
    ''')
    
    # Create index for status queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_generation_log_status 
        ON statement_generation_log(status)
    ''')
    
    logging.info("Migration 009: Created statement_generation_log table")


def downgrade(db_manager):
    """Drop the statement_generation_log table."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DROP INDEX IF EXISTS idx_generation_log_status')
    cursor.execute('DROP INDEX IF EXISTS idx_generation_log_date')
    cursor.execute('DROP TABLE IF EXISTS statement_generation_log')
    
    logging.info("Migration 009: Dropped statement_generation_log table")
