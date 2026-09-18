# Render Production Deployment Readiness Audit (Phase 11.2)

> **Deployment Readiness Evaluation & Infrastructure Audit for CyberScout AI on Render**  
> **Platform Target**: Render Free-Tier Web Service (Python 3.12, 512 MB RAM, 0.1 vCPU)  
> **Database Target**: Hosted PostgreSQL 17 (e.g., Supabase Free Tier via IPv4 Session/Transaction Pooler)  
> **Final Status**: **CONDITIONALLY READY — DOCUMENTED LIMITATIONS**  

---

## 1. Executive Summary

CyberScout AI has undergone an exhaustive, cross-checked production deployment readiness audit specifically targeting the Render cloud hosting environment. Every component—from WSGI entrypoints, dependency definitions, reverse proxy header processing, database connection pooling, and Row Level Security (RLS) policies, to ephemeral container storage, webhook replay prevention, and background thread survivability—was scrutinized and verified against actual running code.

The evaluation confirms that **CyberScout AI is capable of reliable operation on Render under a free-tier model**, subject to specific, documented architectural limitations inherent to Render's ephemeral filesystem and idle sleep cycles. All 50 Phase 11 security matrix invariants and all 13 production simulation test cases pass with a 100% success rate.

---

## 2. Exact Render Build Command

In the Render Web Service settings (Settings -> Build Command):

```bash
pip install -r requirements.txt && python -m src.database.migrations.migration_manager
```

### Rationale:
1. `pip install -r requirements.txt`: Installs all required runtime, web, database, and reporting dependencies.
2. `python -m src.database.migrations.migration_manager`: Executes sequential, idempotent PostgreSQL migrations before new workers begin taking HTTP traffic.
3. **Precompiled Frontend Assets**: Because `dashboard/static/css/tailwind.css` (~37 KB) is precompiled and committed in the repository, no Node.js or npm installation is required in the build environment, avoiding build bloat on Render's Python native runtime.

---

## 3. Exact Render Start Command

In the Render Web Service settings (Settings -> Start Command):

```bash
gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
```

*(Note: Render automatically detects this from the root `Procfile`: `web: gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`)*

### Rationale:
- **Canonical WSGI Entrypoint**: `wsgi:app` adds the project root to `sys.path` and initializes the application factory via `dashboard.app:create_app()`.
- **Port Binding**: Respects Render's dynamic `$PORT` environment variable (`0.0.0.0:$PORT`).
- **Worker/Thread Concurrency**: 2 workers with 4 threads each provides 8 concurrent request handlers within the 512 MB free-tier memory envelope without risking out-of-memory (OOM) killer terminations.
- **Worker Timeout**: 120 seconds accommodates initial database pool connection handshakes and SSL negotiations during cold boots.

---

## 4. Required Environment Variables

All variables are loaded via standard POSIX environment variables. No secrets are committed in version control or emitted to startup logs.

| Environment Variable | Classification | Example / Recommended Value | Description |
| :--- | :--- | :--- | :--- |
| `CYBERSCOUT_ENV` | Required application configuration | `production` | Enables production security controls, strict cookies, and fail-closed secret validation. |
| `APP_ENV` | Required application configuration | `production` | Secondary environment flag ensuring production mode across CLI and WSGI layers. |
| `SECRET_KEY` | Required security secret | *(64-char random hex)* | Cryptographic session signing key. Must be >= 16 chars and not an insecure default. Fails closed. |
| `DATABASE_URL` | Required database configuration | `postgresql://user:pass@host:6543/postgres?sslmode=require` | PostgreSQL URI. Auto-converts `postgres://` to `postgresql://` and routes Supabase via IPv4 pooler. |
| `CYBERSCOUT_SCHEDULER_SECRET` | Required security secret | *(64-char random hex)* | Shared HMAC-SHA256 secret for validating external scheduler triggers. |
| `SESSION_COOKIE_SECURE` | Required security secret | `true` | Enforces HTTPS-only cookies over Render's TLS-terminated reverse proxy. |
| `PORT` | Required application configuration | `10000` | Automatically injected by Render; bound by Gunicorn. |
| `BREVO_API_KEY` | External integration | `xkeysib-...` | Free-tier transactional email delivery key (300 free emails/day). |
| `EMAIL_PROVIDER` | External integration | `brevo` | Sets email engine to HTTPS REST delivery (bypasses cloud SMTP port 587 blocks). |
| `EMAIL_FROM` | External integration | `reports@yourdomain.com` | Verified sender address in Brevo. |
| `EMAIL_TO` | External integration | `analyst@yourdomain.com` | Target recipient for intelligence digests. |
| `GITHUB_TOKEN` | Optional integration | `ghp_...` | Increases GitHub collector rate limit from 60 to 5,000 requests/hour. |
| `FLASK_DEBUG` | Development-only | `0` | Must be `0` or unset in production. |

---

## 5. Database Requirements (PostgreSQL / Supabase)

1. **Engine Compatibility**:
   - CyberScout AI is strictly coupled to PostgreSQL 15+ (PostgreSQL 17 recommended). SQLite is explicitly rejected on boot by `src/database/engine.py`.
2. **Supabase IPv4 Pooler Compatibility**:
   - Render free tier instances lack native IPv6 outbound connectivity. Direct Supabase connections (`db.<ref>.supabase.co:5432`) fail due to IPv6 routing.
   - CyberScout AI's `src/database/engine.py` automatically rewrites direct Supabase URIs and port 5432 to the IPv4-compatible transaction pooler (`pooler.supabase.com:6543`).
3. **Connection Pooling Invariants**:
   - `create_db_engine()` is configured with:
     - `pool_size = 3`, `max_overflow = 5` (max 8 connections per worker; 16 connections total across 2 Gunicorn workers).
     - `pool_pre_ping = True` (tests connections before checkout; eliminates stale connection exceptions).
     - `pool_recycle = 45` (recycles idle connections every 45s, well beneath Supabase's 60-second idle connection timeout).
     - TCP Keepalives: `keepalives_idle = 30`, `keepalives_interval = 10`, `keepalives_count = 3`.
4. **Transaction Integrity**:
   - All repositories use context-managed cursors (`with conn.cursor() as cur:`) with atomic commits and explicit rollbacks on exceptions, preventing connection leaks in the pool.

---

## 6. Migration Procedure

CyberScout AI utilizes a cumulative, sequential schema migration framework (`src/database/migrations/migration_manager.py`).

### Safe Production Migration Steps:
1. **Pre-Deployment Execution (Build Command)**:
   ```bash
   python -m src.database.migrations.migration_manager
   ```
2. **Idempotency Guarantee**:
   - All DDL statements use `IF NOT EXISTS` syntax (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`).
   - The `schema_version` table uses `ON CONFLICT (version) DO NOTHING;` to guarantee safety against repeated executions.
3. **Online Non-Destructive Invariants**:
   - Migrations do not issue `DROP TABLE` or `DROP COLUMN`.
   - Existing production records (users, admins, opportunities, preferences) survive migration runs without data loss.
4. **Runtime Fallback**:
   - `dashboard/app.py` independently verifies database connectivity on startup (`db_mgr.initialize_database()`), ensuring schema integrity even if the build step migration was bypassed.

---

## 7. Health-Check Configuration

Render supports an automated HTTP health check path to determine service readiness and conduct zero-downtime rolling deploys.

### Health Endpoints Audited:
- **`GET /health/live`** (Process Liveness Probe):
  - Returns `{"alive": true, "service": "CyberScout AI", "status": "ok"}, 200`.
  - Zero database dependency. Fast response (< 1ms).
  - Sanitized: Zero secrets, DSNs, or host credentials emitted.
- **`GET /health/ready`** (Service Readiness Probe):
  - Executes `db_mgr.ping()`.
  - Returns `{"ready": true, "database": "connected", "status": "ok"}, 200` if database is reachable.
  - Returns `{"ready": false, "database": "unavailable", "status": "degraded"}, 503` if database is down.

### Render Configuration Recommendation:
- **Health Check Path**: `/health/live`
- *Reasoning*: On free-tier platforms, hosted databases (e.g. Supabase) may occasionally exhibit transient cold-start latency (1–3 seconds). Using `/health/live` prevents Render from prematurely failing deployments or entering crash loops while the database connection warms up.

---

## 8. Security & Reverse Proxy Configuration

### 1. Reverse Proxy Header Handling (`ProxyFix`)
- Render terminates TLS at its edge ingress and proxies traffic internally over HTTP with `X-Forwarded-Proto: https` and `X-Forwarded-For: <client-ip>`.
- `dashboard/app.py` applies Werkzeug's `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)`.
- This ensures:
  - `request.is_secure` accurately evaluates to `True`.
  - External URL generation (`url_for(..., _external=True)`) generates `https://` URLs.
  - Client IP rate-limiting (`AdminSecurityManager`) tracks the true client IP rather than the Render internal router IP.

### 2. Cookie & Session Security
- `SESSION_COOKIE_NAME = "cyberscout_session"`
- `SESSION_COOKIE_HTTPONLY = True` (JavaScript cannot read cookie).
- `SESSION_COOKIE_SAMESITE = "Lax"` (Protects against CSRF in cross-origin navigations).
- `SESSION_COOKIE_SECURE = True` (Browser sends cookie strictly over HTTPS).
- **Server-Side Session Store**: All session dictionaries reside in PostgreSQL `"ServerSessions"`. The client cookie contains only an opaque, cryptographically random token (`secrets.token_urlsafe(32)`). Tokens are stored hashed-at-rest (`SHA-256(token)`).

### 3. Content Security Policy (CSP) & Headers
- Strict per-request nonce (`g.csp_nonce`) applied to all scripts.
- No `'unsafe-inline'` or `'unsafe-eval'` in `script-src`.
- No CDN script dependencies; all JS is self-hosted.
- Anti-clickjacking (`X-Frame-Options: DENY`), MIME sniffing prevention (`X-Content-Type-Options: nosniff`), and HSTS (`Strict-Transport-Security: max-age=31536000`).

---

## 9. Filesystem / Ephemeral Storage Requirements

> [!WARNING]
> **Ephemeral Storage Limitation on Render**  
> Render containers possess an ephemeral filesystem. Files written to local disk are discarded when the service restarts, deploys a new commit, or spins down due to inactivity.

### Application Impact Analysis:
1. **Database Backups (`data/backups/`)**:
   - `BackupManager` writes `.sql` backups locally. On Render, these local files are **ephemeral** and will be lost on container restart.
   - *Mitigation*: For production disaster recovery, operators must rely on PostgreSQL hosted provider snapshots (e.g. Supabase automated daily backups) rather than local container backups.
2. **Generated Reports (`reports/csv/`, `reports/docx/`)**:
   - Downloadable reports generated via `/admin/reports/download/<filename>` remain available only for the lifetime of the active container.
   - *Mitigation*: Intelligence is permanently stored in PostgreSQL `Opportunities` and `AuditLogs` tables; reports can be re-generated on demand.
3. **Application Logs (`logs/`)**:
   - Local files in `logs/*.log` are ephemeral.
   - *Mitigation*: `DatabaseLogHandler` persists all structured application logs to PostgreSQL table `AppLogs`. Standard console logs stream to Render's persistent log dashboard.
4. **User Uploads**:
   - Zero dependency. CyberScout AI has no user file upload endpoints.

---

## 10. Webhook & Scheduler Behavior

Render Free-Tier web services spin down to sleep after 15 minutes of inactivity. CyberScout AI's architecture is fully decoupled from long-running local cron daemons.

### Webhook Operation Invariants:
1. **External Trigger Endpoint**: `POST /api/scheduler/trigger` (and `/api/external/scheduler-trigger`).
2. **Cold-Start Wakeup**: When an external scheduler (e.g. Google Apps Script, GitHub Actions workflow, or cron-job.org) issues an HTTP request, Render spins up the container within 30–50 seconds.
3. **HMAC-SHA256 Verification**:
   - Headers: `X-CyberScout-Signature`, `X-CyberScout-Timestamp`, `X-CyberScout-Nonce`.
   - Bounded clock skew (±300 seconds).
   - Replay protection: Nonces are checked and recorded in PostgreSQL table `scheduler_webhook_requests`.
4. **Asynchronous Execution**:
   - Webhook returns HTTP `202 Accepted` within 25ms, avoiding Gunicorn worker timeout.
   - Scan pipeline runs in a background thread while the container remains active during Render's 15-minute post-request wake window.
   - Concurrency lock: `ScanJobRepository` enforces single active scan execution via `uq_active_scan_job`. Concurrent triggers return HTTP `409 Conflict`.

---

## 11. Background Job Considerations

- **Crash Resistance**: If Render terminates a container during a scan, Phase 10's `recover_stuck_jobs(timeout_seconds=1800)` automatically transitions orphaned jobs from `running` to `failed` on the subsequent boot.
- **Outbox Processing**: Interrupted email notifications in `processing` status are safely returned to `pending` by `recover_stuck_processing(timeout_seconds=300)`.
- **Zero In-Memory Queues**: No Celery, Redis, or RabbitMQ is required; all job and outbox state machines are transactional in PostgreSQL.

---

## 12. Free-Tier Compliance Audit

| Requirement | Free Tier Solution | Cost |
| :--- | :--- | :--- |
| Compute / Web Hosting | Render Free Web Service (512 MB, 0.1 CPU, 750 free hrs/mo) | $0.00 |
| Relational Database | Supabase Free Tier (500 MB PostgreSQL 17, IPv4 Pooler) | $0.00 |
| Transactional Email | Brevo Free Plan (300 emails/day via HTTPS REST API) | $0.00 |
| Observability / APM | Built-in `/health/*` routes + `/admin/reliability` dashboard | $0.00 |
| External Scheduling | GitHub Actions Cron / Google Apps Script Webhook | $0.00 |
| Asset Delivery | Local Flask static serving + Precompiled Tailwind CSS | $0.00 |
| **Total Monthly Spend** | | **$0.00** |

---

## 13. Tests Actually Executed

1. **Render Deployment Simulation Suite** (`scratch/test_render_readiness_simulation.py`):
   - 13 comprehensive end-to-end test cases under simulated production environment (`CYBERSCOUT_ENV=production`, `SECRET_KEY`, `CYBERSCOUT_SCHEDULER_SECRET`).
   - **Result**: **13/13 PASSED (OK)** in 18.385s.
2. **Phase 11 Production Security Matrix** (`tests/unit/test_phase11_security_release.py`):
   - 50 security criteria (RBAC, CSRF, IDOR, SQL injection, XSS escaping, HMAC, RLS).
   - **Result**: **50/50 PASSED (OK)** in 105.316s.
3. **Phase 9 Matching Intelligence Regression** (`tests/unit/test_phase9_matching_intelligence.py`):
   - 51 criteria (Explainable match analysis, skill normalizer, similarity engine).
   - **Result**: **51/51 PASSED (OK)** in 69.895s.
4. **CLI Migration Manager Test**:
   - `python -m src.database.migrations.migration_manager`
   - **Result**: Exit code 0; applied pending migrations; reported current version 15.
5. **PostgreSQL RLS Catalog Test**:
   - `DatabaseManager.verify_rls_policies()`
   - **Result**: `is_configured: True`, `missing_tables: []`, `unprotected_tables: []`.

---

## 14. Tests Unavailable During Audit

- **Live Render Cloud Deployment**: An active Render Web Service deployment was not performed from this local session because live Render API keys and a remote deployment hook were not provided.
- **Production Hosted PostgreSQL Catalog**: While verified on the local/test PostgreSQL instance, live production catalog verification on a remote Supabase instance is marked:
  `NOT VERIFIED — PRODUCTION DATABASE ACCESS REQUIRED` (must be verified upon initial deployment).

---

## 15. Findings

### Finding 1: Reverse Proxy Headers (`ProxyFix`) — *Resolved*
- *Issue*: `create_app()` previously lacked Werkzeug's `ProxyFix`, causing `request.is_secure` to be `False` behind Render's TLS termination and attributing all incoming traffic to Render's internal proxy IP.
- *Resolution*: Wrapped `app.wsgi_app` with `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)` in `dashboard/app.py`.

### Finding 2: Missing Migration Manager CLI Runner — *Resolved*
- *Issue*: `DEPLOYMENT.md` documented running `python -m src.database.migrations.migration_manager`, but `migration_manager.py` had no `if __name__ == "__main__":` block.
- *Resolution*: Added the CLI execution block to `src/database/migrations/migration_manager.py`.

### Finding 3: Procfile Command Discrepancy in Documentation — *Resolved*
- *Issue*: `DEPLOYMENT.md` listed `web: python main.py`, which is the CLI scanner rather than the WSGI server.
- *Resolution*: Updated `DEPLOYMENT.md` to match the actual root `Procfile` (`web: gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`).

### Finding 4: Unused Playwright Dependency in `requirements.txt` — *Noted*
- *Issue*: `playwright>=1.42.0` is present in `requirements.txt`, but all collectors in `src/collectors/` use `requests` and `BeautifulSoup`.
- *Impact*: Non-blocking. Increases build time slightly on Render, but does not impact runtime since browsers are neither installed nor requested.

---

## 16. Blocking Issues
**Zero Blocking Issues**. All requirements for WSGI startup, database pooling, secret validation, and endpoint routing are satisfied.

---

## 17. Non-Blocking Issues & Limitations
1. **Ephemeral Local Storage**: Local database backups (`data/backups/`) and generated reports (`reports/`) do not survive Render container restarts. Production disaster recovery must use hosted database provider snapshots.
2. **Cold-Start Latency on Free Tier**: Render free-tier containers spin down after 15 minutes of inactivity; initial requests after idle take ~30–50 seconds to respond. External scheduler callers must configure timeouts >= 60 seconds.
3. **Playwright Wheel Overhead**: Removing `playwright` from `requirements.txt` in a future cleanup will save ~50 MB of build download bandwidth.

---

## 18. Production Deployment Checklist for Render

Before opening public traffic on Render:

- [ ] **1. Create Render Web Service**:
  - Runtime: `Python 3`
  - Build Command: `pip install -r requirements.txt && python -m src.database.migrations.migration_manager`
  - Start Command: `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
- [ ] **2. Configure Environment Variables**:
  - `CYBERSCOUT_ENV=production`
  - `APP_ENV=production`
  - `SECRET_KEY=<generate-64-char-random-hex>`
  - `DATABASE_URL=<your-hosted-postgresql-pooler-url>`
  - `CYBERSCOUT_SCHEDULER_SECRET=<generate-64-char-random-hex>`
  - `SESSION_COOKIE_SECURE=true`
  - `EMAIL_PROVIDER=brevo`
  - `BREVO_API_KEY=<your-brevo-api-key>`
  - `EMAIL_FROM=<your-verified-sender>`
  - `EMAIL_TO=<your-analyst-recipient>`
- [ ] **3. Configure Health Check**:
  - Set Health Check Path in Render settings to `/health/live`.
- [ ] **4. Post-Deployment Verification**:
  - Verify `/health/live` returns HTTP 200.
  - Verify `/health/ready` returns HTTP 200 (verifies database connectivity).
  - Access `/setup` to initialize the primary Administrator account.
  - Verify admin login and MFA at `/admin/login`.
- [ ] **5. External Scheduler Trigger Setup**:
  - Set up Google Apps Script or GitHub Actions scheduled workflow to issue HMAC-signed POST requests to `https://<your-service>.onrender.com/api/scheduler/trigger`.

---

### Final Render Readiness Status:
**CONDITIONALLY READY — DOCUMENTED LIMITATIONS**  
*(Approved for controlled deployment in accordance with the documented ephemeral storage runbooks and health check configurations).*
