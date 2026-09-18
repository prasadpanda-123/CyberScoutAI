# CyberScout AI — Production Reliability Guide (Phase 10)

## 1. Overview & Architectural Philosophy
CyberScout AI operates in diverse production deployment environments, from single-node web instances to multi-worker containerized setups (e.g. Render, Docker, or bare-metal Linux). In Phase 10, production reliability has been established not by introducing expensive third-party SaaS dependencies, but by making the system resilient from first principles.

The core reliability philosophy is:
- **Fail Closed for Security, Fail Graceful for Availability**: Database disconnections return HTTP 503 Service Unavailable without claiming invalid credentials or locking users out.
- **Transactional Atomicity**: All database mutations execute inside context-managed transactions (`with db_manager.transaction() as cur:`).
- **Concurrency Locking**: Jobs and outbox records enforce atomic state locks in PostgreSQL.
- **Safe Recovery**: Worker restarts and container redeployments automatically reconcile stale or interrupted tasks.

---

## 2. Deterministic Failure Classification Model
All system exceptions, HTTP status codes, and database errors are classified through `src/core/failure_model.py`:

| Category | Typical Causes | Retryable? | Suggested Action |
|---|---|---|---|
| `TRANSIENT` | Network timeouts, peer disconnections, deadlocks, HTTP 429/502/503/504 | Yes | Exponential backoff retry |
| `PERMANENT` | HTTP 404, invalid endpoint, unsupported protocol | No | Log and quarantine item |
| `DATA` | Schema constraint violations, foreign key issues, malformed JSON | No | Quarantine record for administrative inspection |
| `AUTHENTICATION`| Invalid credentials, expired session, bad OTP | No | Prompt user / challenge MFA |
| `AUTHORIZATION` | Insufficient RBAC role, RLS violation | No | Access denied / 403 Forbidden |
| `CONFIGURATION`| Missing environment variables, invalid DSN | No | Halt startup, notify admin |
| `PROGRAMMING`  | NameError, AttributeError, syntax bugs | No | Immediate patch & deployment |

---

## 3. Database Connection Resilience & Pooling
CyberScout AI utilizes `DatabaseManager` backed by `psycopg2` with SQLAlchemy connection pooling:
- **Ping Protocol**: Liveness probe does not touch the DB; Readiness probe verifies database connectivity via `db_manager.ping()`.
- **Automatic Pool Reset**: Pool corruption triggers `db_manager.reset_pool()` and restores connectivity.
- **Context Manager Support**: `PgCursorAdapter` supports both standard database iteration and context manager semantics (`with conn.cursor() as cur:`).
- **Safe Transaction Rollback**: Any unhandled exception during database writes rolls back the transaction cleanly.

---

## 4. ScanJob Invariants & Concurrency Locks
Harvesting jobs are tracked in the `"ScanJobs"` PostgreSQL table with strict concurrency guarantees:
- **Single Active Scan Enforcement**: Only one job can be in `queued`, `running`, `collecting`, `processing`, or `saving` state at any time via a partial unique index `uq_active_scan_job`.
- **Concurrency Exception**: Concurrent attempts to spawn a scan raise `ScanInProgressError`.
- **Stuck Worker Recovery**: `recover_stuck_jobs(timeout_seconds)` scans for jobs that exceeded maximum execution limits and transitions them safely to `failed` without leaving locks stranded.

---

## 5. Notification Outbox Survivability
Alerting and email deliveries are decoupled using an outbox pattern in `"NotificationOutbox"`:
- **Crash Survivability**: When notifications are enqueued, they remain `pending` until worker pickup.
- **Interrupted Task Recovery**: If a worker crashes while processing notifications, `recover_stuck_processing(timeout_seconds)` reverts in-flight `processing` records to `pending` with incremented attempt counts.
- **Bounded Exponential Backoff**: Delivery failures increment `attempt_count` up to `max_attempts`. Once exhausted, the record transitions to `failed` without infinite retries.

---

## 6. Zero Paid Resource Constraints
All Phase 10 reliability and observability capabilities are implemented natively:
- No CloudWatch, Datadog, Sentry, or paid APM services.
- No external message broker (RabbitMQ/Kafka) required; PostgreSQL provides ACID queuing.
