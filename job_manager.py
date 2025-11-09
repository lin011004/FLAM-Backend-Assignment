# job_manager.py
import db
import sqlite3
import json
from datetime import datetime
import time

JOB_STATES = ['pending', 'processing', 'completed', 'failed', 'dead']

# --- Configuration Methods ---

def get_config(key):
    """Retrieves a configuration value."""
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_config(key, value):
    """Sets/updates a configuration value."""
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', 
        (key, str(value))
    )
    conn.commit()
    conn.close()

# --- Job Management Methods ---

def create_job(job_data):
    """Creates a new job in the database."""
    conn = db.get_db_connection()
    now = datetime.now().isoformat()
    max_retries = int(get_config('max_retries') or 3)
    
    # Ensure mandatory fields are present
    if not job_data.get('id') or not job_data.get('command'):
        raise ValueError("Job must have 'id' and 'command'")

    try:
        conn.execute(
            '''INSERT INTO jobs 
            (id, command, state, attempts, max_retries, created_at, updated_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (
                job_data['id'],
                job_data['command'],
                'pending',
                0,
                job_data.get('max_retries', max_retries),
                now,
                now
            )
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        print(f"Error: Job ID '{job_data['id']}' already exists.")
        return False
    finally:
        conn.close()

def update_job_state(job_id, state, attempts=None):
    """Updates a job's state and optionally its attempts."""
    conn = db.get_db_connection()
    now = datetime.now().isoformat()
    
    # Base query
    sql = "UPDATE jobs SET state = ?, updated_at = ?"
    params = [state, now, job_id]
    
    # Add attempts if provided
    if attempts is not None:
        sql += ", attempts = ?"
        params.insert(2, attempts)
    
    sql += " WHERE id = ?"
    
    conn.execute(sql, tuple(params))
    conn.commit()
    conn.close()


def get_dlq_jobs():
    """Retrieves all jobs from the Dead Letter Queue (state='dead')."""
    conn = db.get_db_connection()
    # Make the connection return dictionaries
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE state = 'dead'")
    jobs = cursor.fetchall()
    conn.close()
    # Convert Row objects to standard dicts
    return [dict(job) for job in jobs]

def retry_dlq_job(job_id):
    """Resets a 'dead' job back to 'pending' with 0 attempts."""
    conn = db.get_db_connection()
    now = datetime.now().isoformat()
    try:
        # Update state, reset attempts, and set updated_at to now
        cursor = conn.execute(
            "UPDATE jobs SET state = 'pending', attempts = 0, updated_at = ? WHERE id = ? AND state = 'dead'",
            (now, job_id)
        )
        conn.commit()
        if cursor.rowcount > 0:
            print(f"Job '{job_id}' moved from DLQ back to 'pending'.")
            return True
        else:
            print(f"Error: Job '{job_id}' not found in DLQ (state='dead').")
            return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
    finally:
        conn.close()