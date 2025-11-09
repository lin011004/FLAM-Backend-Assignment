# queuectl.py
import argparse
import json
import db
import job_manager
import worker 

def setup_db_and_config():
    """Ensure DB is initialized before running any command."""
    db.initialize_db()

def handle_config(args):
    """Handles the 'queuectl config' commands."""
    if args.action == 'set':
        if args.key and args.value:
            job_manager.set_config(args.key, args.value)
            print(f"Config '{args.key}' set to '{args.value}'.")
        else:
            print("Error: 'set' requires a key and a value.")

def handle_enqueue(args):
    """Handles the 'queuectl enqueue' command."""
    try:
 
        job_string = " ".join(args.job_json)

        job_string = job_string.strip().strip("'").strip('"') # Clean it up
        
        job_data = json.loads(job_string) # Parse the re-assembled string


        if job_manager.create_job(job_data):
            print(f"Job '{job_data['id']}' enqueued successfully.")
            
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format for job data. Details: {e}")
        print(f"Received string: {args.job_json}") # Show what Python actually received
        
    except ValueError as e:
        print(f"Error: {e}")

def handle_status(args):
    """Handles the 'queuectl status' command."""
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT state, COUNT(*) FROM jobs GROUP BY state")
    status = dict(cursor.fetchall())
    conn.close()
    
    print("\n--- Job Status Summary ---")
    for state in job_manager.JOB_STATES:
        count = status.get(state, 0)
        print(f"  {state.capitalize().ljust(10)}: {count}")
    print("--------------------------\n")


def handle_dlq(args):
    """Handles the 'queuectl dlq' commands."""
    if args.action == 'list':
        jobs = job_manager.get_dlq_jobs()
        if not jobs:
            print("Dead Letter Queue is empty.")
            return
        
        print("\n--- Dead Letter Queue (DLQ) Jobs ---")
        for job in jobs:
            print(f"  ID: {job['id']}, Command: {job['command']}, Attempts: {job['attempts']}")
        print("--------------------------------------\n")

    elif args.action == 'retry':
        job_manager.retry_dlq_job(args.job_id)

def main():
    setup_db_and_config()
    parser = argparse.ArgumentParser(description="CLI-based background job queue system (queuectl).")
    subparsers = parser.add_subparsers(dest='command')

    # --- Config Command ---
    config_parser = subparsers.add_parser('config', help='Manage configuration.')
    config_subparsers = config_parser.add_subparsers(dest='action')
    set_parser = config_subparsers.add_parser('set', help='Set a configuration value.')
    set_parser.add_argument('key', type=str, help='Configuration key (e.g., max_retries).')
    set_parser.add_argument('value', type=str, help='Configuration value.')

    # --- Enqueue Command ---
    enqueue_parser = subparsers.add_parser('enqueue', help='Add a new job to the queue.')
    enqueue_parser.add_argument('job_json', nargs='*', help='JSON string (can be split by shell).')
    
    # --- Status Command ---
    subparsers.add_parser('status', help='Show summary of all job states.')

    # --- Worker Command (Stub) ---
    worker_parser = subparsers.add_parser('worker', help='Manage worker processes.')
    worker_subparsers = worker_parser.add_subparsers(dest='action')
    start_parser = worker_subparsers.add_parser('start', help='Start one or more workers.')
    start_parser.add_argument('--count', type=int, default=1, help='Number of workers to start.')
    stop_parser = worker_subparsers.add_parser('stop', help='Stop running workers gracefully.')

   # --- DLQ Command ---
    dlq_parser = subparsers.add_parser('dlq', help='Manage the Dead Letter Queue.')
    dlq_subparsers = dlq_parser.add_subparsers(dest='action', required=True)
    
    # 'dlq list' command
    dlq_list_parser = dlq_subparsers.add_parser('list', help='List all jobs in the DLQ.')
    
    # 'dlq retry' command
    dlq_retry_parser = dlq_subparsers.add_parser('retry', help='Retry a specific job from the DLQ.')
    dlq_retry_parser.add_argument('job_id', type=str, help='The ID of the job to retry.')

    
    # --- Execute Command Logic ---
    args = parser.parse_args()

    if args.command == 'config':
        handle_config(args)
    elif args.command == 'enqueue':
        handle_enqueue(args)
    elif args.command == 'status':
        handle_status(args)
    elif args.command == 'worker':
        if args.action == 'start':
            worker.start_workers(args.count)
        elif args.action == 'stop':
            print("To stop workers, use Ctrl+C in the terminal where they were started.")
    elif args.command == 'dlq':
        handle_dlq(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()