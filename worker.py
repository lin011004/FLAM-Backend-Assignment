# worker.py
import db
import job_manager
import subprocess
import time
from datetime import datetime, timedelta
import math
import multiprocessing

# --- Worker Functions ---

def calculate_next_retry_time(attempts, base_backoff):
    """Calculates the time the job is eligible for the next retry (Exponential Backoff)."""
    # delay = base_backoff ^ attempts seconds
    delay = math.pow(base_backoff, attempts)
    return datetime.now() + timedelta(seconds=delay)

def worker_main(worker_id):
    """The main loop for a single worker process."""
    print(f"Worker {worker_id} started.")
    
    # Get config once per worker to minimize DB calls
    try:
        base_backoff = int(job_manager.get_config('backoff_base'))
    except TypeError:
        base_backoff = 2
        print(f"Warning: Backoff base config not found, using default {base_backoff}.")

    while True:
        job = None
        conn = db.get_db_connection()
        
        try:
            # 1. ATOMICALLY SELECT & LOCK (set to processing)
            # Find a 'pending' job whose retry time has passed (updated_at)
            now_iso = datetime.now().isoformat()
            
            # Use a transaction to ensure no other worker grabs this job
            with conn: 
                cursor = conn.execute(
                    '''SELECT * FROM jobs 
                       WHERE state = 'pending' AND updated_at <= ? 
                       ORDER BY updated_at ASC LIMIT 1''',
                    (now_iso,)
                )
                job_row = cursor.fetchone()

                if job_row:
                    job_data = dict(zip([col[0] for col in cursor.description], job_row))
                    job_id = job_data['id']
                    
                    # Lock the job by moving it to 'processing'
                    conn.execute(
                        "UPDATE jobs SET state = 'processing', updated_at = ? WHERE id = ?",
                        (datetime.now().isoformat(), job_id)
                    )
                    job = job_data
            
            if not job:
                # No job found, wait a bit
                time.sleep(1)
                continue

            # 2. EXECUTE COMMAND
            print(f"Worker {worker_id}: Processing job '{job_id}'...")
            result = subprocess.run(
                job['command'], 
                shell=True, 
                capture_output=True, 
                text=True,
                timeout=300 # Basic timeout guard
            )
            exit_code = result.returncode

            # 3. HANDLE OUTCOME (Retry / Complete / DLQ)
            if exit_code == 0:
                print(f"Worker {worker_id}: Job '{job_id}' completed successfully.")
                job_manager.update_job_state(job_id, 'completed')
            else:
                attempts = job['attempts'] + 1
                
                if attempts < job['max_retries']:
                    retry_time = calculate_next_retry_time(attempts, base_backoff)
                    print(f"Worker {worker_id}: Job '{job_id}' failed (Attempt {attempts}). Retrying at {retry_time.strftime('%H:%M:%S')}.")
                    
                    # Update state to 'pending', increment attempts, and set future retry time
                    conn = db.get_db_connection()
                    conn.execute(
                        "UPDATE jobs SET state = 'pending', attempts = ?, updated_at = ? WHERE id = ?",
                        (attempts, retry_time.isoformat(), job_id)
                    )
                    conn.commit()
                    conn.close()

                else:
                    print(f"Worker {worker_id}: Job '{job_id}' failed all retries. Moved to DLQ.")
                    job_manager.update_job_state(job_id, 'dead', attempts)

        except subprocess.TimeoutExpired:
            print(f"Worker {worker_id}: Job '{job_id}' timed out.")
            # Treat timeout as failure for retry logic
            # ... (add logic to handle timeout as a failure, triggering retry/DLQ)
            
        except Exception as e:
            print(f"Worker {worker_id}: An unexpected error occurred: {e}")
            # If a job was being processed, move it back to pending/failed to avoid being stuck
            if job:
                job_manager.update_job_state(job['id'], 'failed')

        finally:
            conn.close()

# --- Integration for queuectl.py ---
def start_workers(count):
    """Starts multiple worker processes."""
    processes = []
    for i in range(count):
        p = multiprocessing.Process(target=worker_main, args=(i + 1,))
        processes.append(p)
        p.start()
    
    # Simple way to keep main process alive (for a real system, you'd daemonize or use signals)
    print(f"Started {count} workers. Press Ctrl+C to stop.")
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\nAttempting graceful worker shutdown...")
        for p in processes:
            p.terminate() # Simple stop for this example
        print("Workers stopped.")

# --- Update queuectl.py to use start_workers ---
# In queuectl.py, update the worker handler:
'''
    elif args.command == 'worker':
        if args.action == 'start':
            worker.start_workers(args.count)
        elif args.action == 'stop':
            # This requires more complex IPC, for now, we rely on Ctrl+C termination
            print("To stop workers, use Ctrl+C in the terminal where they were started.")
'''