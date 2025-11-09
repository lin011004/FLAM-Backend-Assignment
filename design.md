# `queuectl` - Design Document

This document outlines the architecture, design patterns, and core components of the `queuectl` job queue system.

## 1. Objective

The goal is to create a minimal, production-grade, CLI-based job queue system. It must support persistent jobs, parallel workers, automatic retries with exponential backoff, and a Dead Letter Queue (DLQ).

## 2. Core Components & Modular Design

The system is built in Python 3 and divided into four main modules to ensure a clear separation of concerns:

1.  **`queuectl.py` (CLI Interface)**
    * **Responsibility:** The user-facing entry point.
    * **Technology:** Uses Python's `argparse` module.
    * **Function:** Parses all CLI commands (`enqueue`, `worker`, `status`, `dlq`) and delegates the logic to the `job_manager` or `worker` modules. It handles user input and formats the final output.

2.  **`db.py` (Persistence Layer)**
    * **Responsibility:** Handles all direct database interactions.
    * **Technology:** Uses Python's built-in `sqlite3` module.
    * **Function:** Initializes the database (`queuectl.db`) and tables. Provides a simple `get_db_connection()` function for other modules to use.

3.  **`job_manager.py` (Business Logic Layer)**
    * **Responsibility:** Manages the state and logic of jobs and configuration.
    * **Function:** Contains all business logic for creating jobs, updating job states, handling DLQ operations (`list`, `retry`), and managing configuration. It acts as the primary interface to the database, abstracting the raw SQL queries.

4.  **`worker.py` (Execution Layer)**
    * **Responsibility:** Executes the jobs.
    * **Technology:** Uses `multiprocessing` for parallel execution and `subprocess` to run job commands.
    * **Function:** Contains the core worker loop that fetches, locks, and executes jobs. It also implements the retry/backoff and DLQ logic upon job failure or success.

## 3. Persistence: SQLite Database

* **Technology:** SQLite was chosen because it's a file-based, embedded, and transactional database that requires no separate server process. This perfectly matches the "minimal" and "persistent" requirements.
* **Concurrency:** SQLite handles file-level locking, which is sufficient for multiple processes on a single machine. Our atomic "select-and-lock" operation (see Concurrency Model) relies on SQLite's transactional guarantees.

### Database Schema

1.  **`jobs` Table:** The primary table for all job data.
    * `id` (TEXT, PK): The unique job identifier.
    * `command` (TEXT): The shell command to be executed.
    * `state` (TEXT): The current state of the job (`pending`, `processing`, `completed`, `failed`, `dead`).
    * `attempts` (INTEGER): Counter for retry attempts.
    * `max_retries` (INTEGER): Max attempts before moving to DLQ.
    * `created_at` (TEXT): ISO 8601 timestamp.
    * `updated_at` (TEXT): ISO 8601 timestamp. Used for backoff delay calculation.

2.  **`config` Table:** Stores system-wide configuration.
    * `key` (TEXT, PK): The config key (e.g., `max_retries`).
    * `value` (TEXT): The config value.

## 4. Job Lifecycle (State Machine)

A job moves through a well-defined set of states:

1.  **`pending`:** The initial state. A job is created and waits for a worker.
2.  **`processing`:** A worker has locked the job and is actively executing its command.
3.  **`completed`:** The job's command finished with a `0` exit code. This is a final state.
4.  **`failed`:** The command finished with a non-zero exit code, but `attempts < max_retries`. The job will be moved back to `pending` after a backoff delay.
5.  **`dead`:** The command failed and `attempts >= max_retries`. The job is moved to the Dead Letter Queue (DLQ) for manual review. This is a final state unless manually retried via `dlq retry`.

## 5. Concurrency Model & Locking

* **Technology:** We use the **`multiprocessing`** module, not `threading`.
    * **Reason:** Job execution involves running external commands via `subprocess`. These are I/O-bound operations that wait for another process. `multiprocessing` avoids Python's Global Interpreter Lock (GIL) and allows for true parallel execution, making it ideal for managing multiple `subprocess` calls.

* **Preventing Race Conditions (Job Locking):**
    To prevent two workers from grabbing the same job, we use an atomic database transaction. The worker loop does the following:
    1.  `BEGIN TRANSACTION`
    2.  `SELECT` the oldest `pending` job whose `updated_at` (retry time) is in the past.
    3.  If a job is found, immediately `UPDATE` its state to `processing` and update its `updated_at` timestamp.
    4.  `COMMIT TRANSACTION`
    5.  Only *after* the commit is successful does the worker begin executing the job's command.

    Because this entire block is transactional, no other worker can select that same job.

## 6. Error Handling: Retry & DLQ

* **Retry Logic:** If a job fails, the `worker` increments the `attempts` counter.
* **Exponential Backoff:** The worker calculates the delay using $delay = base^{attempts}$ seconds (where `base` is from the `config` table). It then sets the job's state back to `pending` but updates the `updated_at` timestamp to `CurrentTime + delay`.
* **Job Selection:** The worker's `SELECT` query is modified to only pick up jobs where `state = 'pending'` AND `updated_at <= CurrentTime`. This ensures the backoff delay is respected.
* **DLQ:** If `attempts` reaches `max_retries`, the worker sets the state to `dead`. The `dlq list` and `dlq retry` commands provide the manual interface to manage these failed jobs.
