# CyberScout AI — Observability & Telemetry Guide (Phase 10)

## 1. Observability Architecture
CyberScout AI Phase 10 implements deep, native observability without external SaaS monitoring dependencies. Observability encompasses:
1. Distributed Request Correlation (`X-Request-ID`).
2. Structured Error & Event Logging with credential scrubbing.
3. Lightweight Liveness and Readiness Probes.
4. Administrative Reliability Telemetry Dashboard (`/admin/reliability`).

---

## 2. Request Correlation Middleware
Every inbound HTTP request is assigned a unique Correlation ID:
- **Header Extraction**: Checks `X-Request-ID`.
- **Sanitization & Bounds**: If provided by client or upstream proxy, sanitized with regex `^[A-Za-z0-9_-]+$` and clamped to 64 characters to eliminate injection attacks.
- **Auto-Generation**: If absent, generates `req-` prefixed UUID4 string.
- **Header Propagation**: Attached to all HTTP responses as `X-Request-ID`.
- **Flask Context**: Stored in `flask.g.request_id`.
- **Error Correlation**: Uncaught 500 errors include the `request_id` in their response and error logs.

---

## 3. Health Probes Specification

### Liveness Probe (`/health/live` & `/api/health/live`)
- **Objective**: Verifies the web worker process is alive and handling requests.
- **Dependencies**: None. Does **not** query PostgreSQL or external services so that transient DB drops do not trigger false container restarts.
- **Status Codes**: Always 200 OK if the process is responsive.
- **Response**:
  ```json
  {
    "status": "ok",
    "alive": true,
    "timestamp": "2026-09-16T08:00:00.000000+00:00"
  }
  ```

### Readiness Probe (`/health/ready` & `/api/health/ready`)
- **Objective**: Verifies the application is ready to accept user traffic (including database responsiveness).
- **Dependencies**: Performs lightweight `db_manager.ping()` (`SELECT 1;`).
- **Status Codes**: 200 OK when database is responsive; 503 Service Unavailable when database is down.
- **Safety**: Never includes database credentials, connection strings, passwords, or internal server paths.
- **Response (Ready)**:
  ```json
  {
    "status": "ready",
    "ready": true,
    "database": "connected",
    "timestamp": "2026-09-16T08:00:00.000000+00:00"
  }
  ```
- **Response (Degraded)**:
  ```json
  {
    "status": "degraded",
    "ready": false,
    "database": "unavailable",
    "timestamp": "2026-09-16T08:00:00.000000+00:00"
  }
  ```

---

## 4. Admin Reliability Dashboard (`/admin/reliability`)
Accessible strictly to authenticated operators with the `Administrator` role:
- **Database Telemetry**: Connection status, pool metrics, query round-trip latency.
- **Active & Recent Scan Jobs**: Current pipeline state, collector progress, and historical executions.
- **Notification Outbox Telemetry**: Real-time counts of `pending`, `processing`, `sent`, and `failed` records.
- **Backup Verification**: List of local backup archives with timestamp, size, and validity status.
- **Source Health Summary**: Live count of healthy vs degraded collectors.
