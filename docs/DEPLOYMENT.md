# CyberScout AI — Production Deployment & Security Runbook

> Authoritative guide for deploying, configuring, and operating CyberScout AI in multi-worker production environments.

---

## 1. Production Architecture Overview

CyberScout AI operates as a decoupled presentation-engine-data architecture designed for containerized cloud deployment (e.g., Render, Railway, AWS ECS, or bare-metal Linux):

```
+---------------------------------------------------------------------------------+
|                       CYBERSCOUT AI PRODUCTION STACK                            |
|                                                                                 |
|  [ Reverse Proxy / Ingress (Nginx / Cloudflare / AWS ALB) ]                     |
|    - Terminates TLS / HTTPS (Port 443)                                          |
|    - Forwards X-Forwarded-Proto, X-Forwarded-For                                |
|                                                                                 |
|  [ WSGI Application Server (Gunicorn / Waitress) ]                              |
|    - Multi-worker processes (e.g. 4 workers)                                    |
|    - Serves Flask application factory via `dashboard.app:create_app()`          |
|    - Serves precompiled static assets (`/static/css/tailwind.css`)              |
|                                                                                 |
|  [ Core Intelligence & Pipeline Engine (src/) ]                                 |
|    - Scanners, Processors, Scoring, Notifier (Brevo REST API)                   |
|                                                                                 |
|  [ PostgreSQL Database (Supabase / RDS / Self-Hosted) ]                         |
|    - Row-Level Security (RLS) enabled on all core tables                        |
|    - Shared ScanJobs state machine with atomic concurrency exclusivity          |
|    - Shared PendingMfa table with atomic OTP attempt counters                   |
|    - Shared ServerSessions table for stateless multi-worker authentication      |
|    - Shared scheduler_webhook_requests replay cache                             |
+---------------------------------------------------------------------------------+
```

### Multi-Worker Concurrency & Session Guarantees
- **Server-Side Session State & Opaque Cookies**: Session state is persisted in the PostgreSQL `"ServerSessions"` table. Client browser cookies (`cyberscout_session`) contain **ONLY** an opaque, cryptographically random token (`secrets.token_urlsafe(32)`). Zero user identity, email, user ID, role, MFA state, or CSRF tokens are exposed client-side.
- **Hashed-at-Rest Session Tokens**: The database stores only `SHA-256(sid)`, ensuring that database dumps cannot be leveraged to forge valid session cookies.
- **Session Rotation & Fixation Resistance**: Sessions automatically rotate on authentication boundaries (login, MFA completion) and old session IDs are revoked server-side immediately.
- **Immediate Server-Side Revocation**: Logout actively deletes/revokes the session record in PostgreSQL; replaying previously issued cookies fails across all workers.
- **Scan Exclusivity**: The PostgreSQL `ScanJobs` table tracks active jobs (`queued`, `running`). Concurrent scan requests from any worker are rejected with HTTP 409 Conflict.
- **Stale Job Recovery**: Crashed or timed-out workers are automatically recovered; running jobs exceeding `STALE_THRESHOLD_MINUTES` (30 mins) are marked failed by `recover_stale_jobs()`.
- **MFA Centralization**: Administrative MFA state resides in `PendingMfa`, allowing login initialization on one worker and OTP completion on another.
- **HMAC Replay Protection**: External scheduler request nonces are tracked in `scheduler_webhook_requests` to prevent replay attacks across worker processes.

---

## 2. Environment Configuration & Secret Management

All production settings are driven by environment variables. Never commit secrets to version control.

### Required Environment Variables

| Variable | Recommended Production Value | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `production` | Enables production mode and security configurations. |
| `SECRET_KEY` | *(64-character random hex string)* | Flask session signing secret. |
| `SESSION_COOKIE_SECURE` | `true` | Enforces HTTPS-only cookies (requires reverse proxy TLS). |
| `DATABASE_URL` | `postgresql://user:pass@host:5432/dbname?sslmode=require` | PostgreSQL database connection URI. |
| `PORT` | `5000` (or cloud-provided) | Port for the WSGI server. |

### Optional / Integration Variables

| Variable | Description |
| :--- | :--- |
| `EMAIL_PROVIDER` | Set to `brevo` for HTTPS delivery (recommended for cloud hosts blocking port 587) or `smtp`. |
| `BREVO_API_KEY` | Brevo v3 API key (`xkeysib-...`) for report delivery. |
| `EMAIL_FROM` | Sender address verified in Brevo / SMTP server. |
| `EMAIL_TO` | Target recipient email address for intelligence digests. |
| `SCHEDULER_SECRET` | Shared secret for external HMAC-SHA256 scheduler webhook triggers. |
| `GITHUB_TOKEN` | Personal Access Token (5,000 req/hr) for GitHub collector. |

---

## 3. Database Migrations

CyberScout AI uses cumulative schema migrations (`src/database/migrations/`). Execute migrations during the deployment build step before starting application workers:

```bash
# Apply all pending PostgreSQL migrations
python -m src.database.migrations.migration_manager
```

### Verified Schema Tables
- `Users` & `Admins` (Isolated authentication domains)
- `Opportunities` (Aggregated cybersecurity intelligence)
- `AuditLogs` & `AppLogs` (System audit trail and diagnostics)
- `ScanJobs` (Cross-worker job state machine)
- `PendingMfa` (MFA tokens with atomic attempt counters)
- `scheduler_webhook_requests` (HMAC webhook replay protection)

---

## 4. Frontend Asset Generation

Tailwind CSS must be precompiled prior to WSGI startup. The runtime relies entirely on static CSS and requires no Node.js runtime in production:

```bash
# Install Node dev dependencies (during build only)
npm ci

# Compile minified production stylesheet
npm run build:css
```

Verified static output: `dashboard/static/css/tailwind.css` (~37 KB).

---

## 5. WSGI Server Execution

Launch the application using a production-grade WSGI server such as Gunicorn:

```bash
# Launch with 4 worker processes
gunicorn -w 4 -b 0.0.0.0:5000 "dashboard.app:create_app()"
```

Or run via the repository WSGI entrypoint:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

On Railway / Render, the root `Procfile` is preconfigured:
```
web: gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
```

---

## 6. Security Posture & Attack Surface Reference

CyberScout AI routes are segmented into four distinct operational tiers:

### Tier 1: Standard User Surface (`dashboard_bp`, `auth_bp`, etc.)
- `/` — Public landing & intelligence overview.
- `/login`, `/register`, `/logout` — User authentication.
- `/dashboard`, `/opportunities`, `/analytics`, `/profile` — Authenticated user workflows.
- Enforces `@login_required` / `@roles_required`.

### Tier 2: Administrative Control Center (`admin_bp`, `admin_api_bp`)
- `/admin/login`, `/admin/verify-otp`, `/admin/logout` — Admin authentication & MFA.
- `/admin/dashboard`, `/admin/scheduler`, `/admin/email`, `/admin/logs` — Operations UI.
- `/admin/api/*` — Authoritative operational endpoints (scan trigger, digest dispatch, logs).
- Enforces `@admin_required` + constant-time CSRF verification on all state-changing verbs (`POST`, `PUT`, `PATCH`, `DELETE`).

### Tier 3: External Machine Webhook (`external_trigger_bp`)
- `POST /api/scheduler/trigger` & `POST /api/external/scheduler/trigger` — External cron scheduler triggers.
- Requires:
  - `X-CyberScout-Signature`: Valid HMAC-SHA256 (`sha256=<hash>` or `<hash>`) of the canonical string `f"{timestamp}.{nonce}.{raw_body}"` using `CYBERSCOUT_SCHEDULER_SECRET`.
  - `X-CyberScout-Timestamp`: UNIX timestamp within `MAX_WEBHOOK_AGE_SECONDS` (300 seconds).
  - `X-CyberScout-Nonce` (or `request_id` in JSON body): Unique UUID checked against `scheduler_webhook_requests` for replay protection (replays rejected with HTTP 409 Conflict).

### Tier 4: Health Probes & Telemetry (`health_bp`)
- `GET /health/live` & `GET /api/health/live` — Process Liveness probe (HTTP 200, no database required, recommended for Render Health Check Path).
- `GET /health/ready` & `GET /api/health/ready` — Service Readiness probe (HTTP 200 connected, HTTP 503 degraded, checks PostgreSQL).
- `GET /health` — SSR visual telemetry dashboard (or JSON metrics if `Accept: application/json`).
- `GET /api/health` & `GET /api/health/database` — JSON health metrics payloads.

### Content Security Policy (CSP)
Strict nonce-based policy enforced on all HTML responses:
```
default-src 'self';
script-src 'self' 'nonce-<RANDOM_TOKEN>';
style-src 'self' https://fonts.googleapis.com;
font-src 'self' https://fonts.gstatic.com;
img-src 'self' data: https:;
connect-src 'self';
object-src 'none';
base-uri 'self';
form-action 'self';
frame-ancestors 'none';
```
- No `'unsafe-inline'` or `'unsafe-eval'` in `script-src`.
- No `'unsafe-inline'` in `style-src`.
- Zero CDN dependencies.

---

## 7. Production Deployment Checklist

Before exposing CyberScout AI to public traffic:

- [ ] **1. Static Assets**: Verify `dashboard/static/css/tailwind.css` exists.
- [ ] **2. Environment Secrets**: Set random 64-character `SECRET_KEY`.
- [ ] **3. TLS Reverse Proxy**: Verify Nginx / Cloudflare terminates HTTPS and forwards `X-Forwarded-Proto: https`.
- [ ] **4. Cookie Security**: Set `APP_ENV=production` and `SESSION_COOKIE_SECURE=true`.
- [ ] **5. Database**: Set `DATABASE_URL` with SSL enabled (`sslmode=require`).
- [ ] **6. Schema Migrations**: Run `python -m src.database.migrations.migration_manager`.
- [ ] **7. Admin Seeding**: Seed initial administrator account with a high-entropy password.
- [ ] **8. Email Delivery**: Configure `EMAIL_PROVIDER=brevo` and set `BREVO_API_KEY`.
- [ ] **9. External Scheduler**: If using external cron, set `SCHEDULER_SECRET` in both the scheduler client and server environment.
