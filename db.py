# db.py
import sqlite3
import os

DB_FILE = 'queuectl.db'

def get_db_connection():
    """Returns a connection object to the database."""
    return sqlite3.connect(DB_FILE)

def initialize_db(default_max_retries=3, default_backoff_base=2):
    """Initializes the database and creates tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- Jobs Table ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            command TEXT NOT NULL,
            state TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            max_retries INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    # --- Config Table ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Initialize default config values
    config_data = {
        'max_retries': str(default_max_retries),
        'backoff_base': str(default_backoff_base),
    }
    for key, value in config_data.items():
        # Insert if not exists, or update
        cursor.execute(
            'INSERT OR IGNORE INTO config VALUES (?, ?)', 
            (key, value)
        )

    conn.commit()
    conn.close()
    print(f"Database '{DB_FILE}' initialized.")

# Call this once at the start of the application
# initialize_db()