# queuectl: A CLI-Based Job Queue System

`queuectl` is a minimal, production-grade background job queue system built in Python. It supports enqueuing jobs, parallel worker processing, automatic retries with exponential backoff, and a Dead Letter Queue (DLQ) for permanently failed jobs.

All operations are managed via a command-line interface, and job data is persisted across restarts using an embedded SQLite database.

## 🚀 Core Features

* **Persistent Job Queue:** Jobs are stored in an SQLite database (`queuectl.db`), so no data is lost on restart.
* **Parallel Workers:** Supports running multiple worker processes using Python's `multiprocessing` module for true parallel execution.
* **Job Retries:** Failed jobs (non-zero exit code) are automatically retried.
* **Exponential Backoff:** The delay between retries increases exponentially ($delay = base^{attempts}$) to avoid overwhelming failing services.
* **Dead Letter Queue (DLQ):** After exhausting all retry attempts, jobs are moved to a DLQ for manual inspection.
* **Full CLI Control:** All functions (enqueue, start workers, check status, manage DLQ) are handled through the `queuectl.py` CLI.

## 🛠️ Architecture & Tech Stack

* **Language:** Python 3
* **Persistence:** SQLite (using the built-in `sqlite3` module). The database file `queuectl.db` is created automatically.
* **Concurrency:** `multiprocessing` module. Each worker runs in its own process, avoiding the Global Interpreter Lock (GIL) and allowing CPU-bound or external-process jobs to run in true parallel.
* **CLI:** `argparse` (built-in) for parsing commands and arguments.

---

## 1. Setup Instructions

This project uses only the Python 3 standard library, so **no external packages need to be installed**.

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/lin011004/FLAM-Backend-Assignment
    cd FLAM-Backend-Assignment
    ```

2.  **Prerequisite:** Ensure you have **Python 3** installed and accessible in your command line.

3.  **Initialize Database:** The database (`queuectl.db`) and its tables are **created automatically** the first time you run any `queuectl` command.

---

## 2. Usage Examples

All commands are run from the Command Prompt (cmd.exe).

### 1. Enqueueing Jobs

The `enqueue` command takes a single JSON string. In `cmd.exe`, internal double quotes must be escaped with a backslash (`\"`).

**Enqueue a job that succeeds:**
```cmd
py queuectl.py enqueue "{\"id\": \"success_job\", \"command\": \"echo Hello world\"}"
```

**Enqueue a job that will fail (for DLQ testing):**
```cmd
py queuectl.py enqueue "{\"id\": \"fail_retry\", \"command\": \"false\"}"
```

**Enqueue a delayed job (using Windows `timeout` command):**
Special characters like `&` must be escaped with a caret (`^`).
```cmd
py queuectl.py enqueue "{\"id\": \"delayed_job\", \"command\": \"timeout /t 2 /nobreak > NUL ^&^& echo Done\"}"
```

### 2. Checking Job Status

Get a summary of all jobs in the system.
```cmd
py queuectl.py status
```
**Example Output:**
```
--- Job Status Summary ---
  Pending   : 3
  Processing: 0
  Completed : 0
  Failed    : 0
  Dead      : 0
--------------------------
```

### 3. Running Workers

Start worker processes to execute pending jobs. This command will take over the current terminal to log worker activity.

```cmd
py queuectl.py worker start --count 3
```
**Example Output (in the worker terminal):**
```
Started 3 workers. Press Ctrl+C to stop.
Worker 2 started.
Worker 3 started.
Worker 1 started.
Worker 2: Processing job 'success_job'...
Worker 1: Processing job 'fail_retry'...
Worker 3: Processing job 'delayed_job'...
Worker 1: Job 'fail_retry' failed (Attempt 1). Retrying at ...
Worker 2: Job 'success_job' completed successfully.
...
```

### 4. Managing the Dead Letter Queue (DLQ)

**List all jobs in the DLQ:**
```cmd
py queuectl.py dlq list
```
**Example Output:**
```
--- Dead Letter Queue (DLQ) Jobs ---
  ID: fail_retry, Command: false, Attempts: 3
--------------------------------------
```

**Retry a job from the DLQ:**
This moves a job from `dead` back to `pending` and resets its attempts.
```cmd
py queuectl.py dlq retry fail_retry
```
**Example Output:**
```
Job 'fail_retry' moved from DLQ back to 'pending'.
```

---

## 3. Assumptions & Trade-offs

* **Operating System:** The job commands (`false`, `timeout`) are specific to the **Windows Command Prompt (cmd.exe)**. The core logic is OS-agnostic, but the example job commands are not.
* **Persistence:** **SQLite** was chosen for simplicity and to meet the "embedded DB" requirement. It handles locking for multiple processes on a single machine well. It would not be suitable for a multi-machine, distributed-worker setup (which would require a system like RabbitMQ or a centralized DB server).
* **Concurrency:** **`multiprocessing`** was used instead of `threading` because job execution involves running external shell commands (`subprocess`). This makes each job an external process, so `multiprocessing` is the most efficient way to manage them in parallel.
* **Worker Shutdown:** Workers are stopped with `Ctrl+C`. This uses a basic `KeyboardInterrupt` handler. A more complex system would use a dedicated `queuectl worker stop` command with IPC (e.g., a sentinel file or signal) for a more graceful shutdown.

---

## 4. Testing & Verification

To verify all functionality is working:

1.  **Open two `cmd` terminals** in the project directory.
2.  **Terminal 1:** Enqueue the three example jobs (success, fail, delay) from the "Usage" section.
3.  **Terminal 1:** Run `py queuectl.py status` and see 3 `Pending` jobs.
4.  **Terminal 2:** Run the workers: `py queuectl.py worker start --count 3`.
5.  **Terminal 1:** Wait 15-20 seconds and run `py queuectl.py status` again. You should see 2 `Completed` and 1 `Dead`.
6.  **Terminal 1:** Run `py queuectl.py dlq list`. You should see the `fail_retry` job listed.
7.  **Terminal 1:** Run `py queuectl.py dlq retry fail_retry`.
8.  **Terminal 1:** Run `py queuectl.py status`. You will see 1 `Pending` job.
9.  **Terminal 2:** The workers will automatically pick up the retried job and process it again, eventually moving it back to the DLQ.

---

## 5. 🎬 CLI Demo

[**<< INSERT YOUR DEMO VIDEO LINK HERE >>**](https://www.example.com)
