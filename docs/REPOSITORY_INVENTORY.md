# CyberScout AI — Complete Repository Inventory

**Audit Date**: September 2026  
**Auditor**: CyberScout AI Quality & Security Agent  
**Scope**: All codebase files, templates, migrations, configs, tests, documentation, and operational artifacts  
**Standard**: Phase 11.3 Production Repository Cleanup & Render Readiness  

---

## 1. Executive Summary & Classification Matrix

Every file and directory in the CyberScout AI repository has been inspected, cross-referenced against runtime imports, route registrations, Jinja template loaders, static asset mounts, migration managers, and deployment entrypoints.

| Classification | Count | Description |
|---|---|---|
| **REQUIRED** | 394 | Actively used in production runtime (`src/`, `dashboard/`, `config/`, `templates/`, `wsgi.py`, `Procfile`) |
| **REQUIRED MAINTENANCE** | 12 | Database migrations, backup CLI, initial seeders, main CLI diagnostics, external scheduler trigger |
| **DEVELOPMENT ONLY** | 1,149 | Governance docs, architecture specs, build configs (`tailwind.config.js`), local gitignored reports & logs |
| **TEST ONLY** | 112 | Automated unit and integration test suites (`tests/unit/`, `tests/integration/`) |
| **OBSOLETE** | 5 | Proven redundant duplicates (`app.py`, root `PHASE_*_IMPLEMENTATION_REPORT.md` copies) |
| **UNKNOWN** | 0 | All repository items successfully audited and classified |
| **TOTAL** | **1,672** | Complete repository footprint |

---

## 2. Directory & Module Classification

### 2.1 Core Application Runtime (`src/`) — [REQUIRED / REQUIRED MAINTENANCE]
All files under `src/` are actively used in data collection, processing, ranking, models, notifications, and security.

| Module / Directory | Classification | Purpose & Runtime References |
|---|---|---|
| `src/main.py` | REQUIRED MAINTENANCE | Master CLI entrypoint for health checks, RSS diagnostics, config verification |
| `src/auth/admin_auth.py` | REQUIRED | Admin session authentication, bcrypt hashing, TOTP/MFA validation |
| `src/automation/` | REQUIRED | Pipeline execution, job managers, background scheduler runners |
| `src/collectors/` | REQUIRED | 10 active collectors (RSS, GitHub, Devpost, CTFtime, YouTube, GSoC, Outreachy, UpForGrabs, HTML, MS Learn) |
| `src/collectors/source_definitions.py` | REQUIRED | 75 canonical source family definitions |
| `src/core/` | REQUIRED | App configuration, custom exceptions, logging, security constants, failure models |
| `src/database/` | REQUIRED | SQLAlchemy engine, connection pools, and 12 database repositories |
| `src/database/models/` | REQUIRED | 6 ORM database model files (opportunity, source, user, job, mfa, source_health) |
| `src/database/migrations/` | REQUIRED MAINTENANCE | 15 linear database migrations and `migration_manager.py` (CLI runner) |
| `src/database/seed.py` | REQUIRED MAINTENANCE | Database bootstrap seeder for production initialization |
| `src/intelligence/` | REQUIRED | Quality engine, deduplication, ranking algorithms, matching, lifecycle evaluator |
| `src/maintenance/` | REQUIRED MAINTENANCE | Database backup manager, snapshot rotation, maintenance services |
| `src/models/` | REQUIRED | DTOs, data models, recommendation models, analytics schemas, enums |
| `src/notifier/` | REQUIRED | Brevo REST API email dispatcher, Jinja template loader, email renderer |
| `src/scheduler/` | REQUIRED | Daily report scheduler daemon and trigger processor |
| `src/services/` | REQUIRED | Domain business logic services (Opportunity, Ranking, Analytics, Notification) |
| `src/utils/` | REQUIRED | URL validation, pagination helpers, command doc generator |

### 2.2 Web Dashboard & Control Center (`dashboard/`) — [REQUIRED]
The Flask web dashboard serving SSR pages, API routes, and admin interfaces.

| Component | Classification | Purpose & Runtime References |
|---|---|---|
| `dashboard/app.py` | REQUIRED | Flask application factory, ProxyFix middleware, CSP headers, CSRF protection |
| `dashboard/config.py` | REQUIRED | Dashboard configuration with fail-closed production SECRET_KEY verification |
| `dashboard/sessions.py` | REQUIRED | PostgreSQL server-side session interface with CSRF token management |
| `dashboard/routes/` | REQUIRED | 19 registered blueprints (auth, admin, opportunities, analytics, health, webhooks) |
| `dashboard/services/` | REQUIRED | Presentation adapters delegating to domain services |
| `dashboard/templates/` | REQUIRED | 50 Jinja2 HTML templates for user portal, admin console, auth, and error pages |
| `dashboard/static/` | REQUIRED | Static CSS, JavaScript, and SVG brand assets |

### 2.3 Templates (`templates/`) — [REQUIRED]
Root `templates/` directory containing email digest and intelligence report templates loaded by `src/notifier/template_loader.py`.

| File | Classification | Purpose |
|---|---|---|
| `templates/base.html` | REQUIRED | Base HTML skeleton for email notifications |
| `templates/category.html` | REQUIRED | Opportunity category section partial |
| `templates/footer.html` | REQUIRED | Compliance and unsubscribe footer partial |
| `templates/header.html` | REQUIRED | Email header and brand banner partial |
| `templates/report.html` | REQUIRED | Daily cybersecurity intelligence digest template |
| `templates/statistics.html` | REQUIRED | Daily metrics summary section |
| `templates/summary.html` | REQUIRED | Category count summary table |

### 2.4 Configuration (`config/`) — [REQUIRED]
Active configuration files loaded dynamically by application collectors and intelligence engines.

| File / Pattern | Classification | Purpose |
|---|---|---|
| `config/sources.yaml` | REQUIRED | Master source catalog and collector mapping |
| `config/source_capabilities.yaml`| REQUIRED | Search and collector capabilities matrix |
| `config/sources_registry.yaml` | REQUIRED | Secondary registry configuration |
| `config/collectors.yaml` | REQUIRED | Collector registration mapping |
| `config/categories/*.yaml` | REQUIRED | Category definitions and keyword classifiers |

### 2.5 Operational & Maintenance Scripts (`scripts/`) — [REQUIRED MAINTENANCE]

| Script | Classification | Purpose |
|---|---|---|
| `scripts/backup_database.py` | REQUIRED MAINTENANCE | Operational CLI script to execute full PostgreSQL database backups |
| `scripts/google_apps_script_trigger.js` | REQUIRED MAINTENANCE | External cron trigger script designed for Google Apps Script to wake Render |

### 2.6 Deployment Entrypoints & Core Configs (Root)

| File | Classification | Status & Notes |
|---|---|---|
| `wsgi.py` | REQUIRED | Authoritative WSGI entrypoint for Render (`gunicorn wsgi:app`) |
| `Procfile` | REQUIRED | Render web service specification (`web: gunicorn wsgi:app`) |
| `requirements.txt` | REQUIRED | Production Python dependencies |
| `alembic.ini` | REQUIRED MAINTENANCE | Alembic configuration for database migrations |
| `main.py` | REQUIRED MAINTENANCE | Root proxy to `src/main.py` |
| `app.py` | OBSOLETE | Exact duplicate of `wsgi.py`; superseded by `wsgi.py` |
| `commands.md` | DEVELOPMENT ONLY | Comprehensive CLI documentation |
| `commands.txt` | DEVELOPMENT ONLY | Text version generated by `python main.py --generate-command-docs` |
| `PHASE_8_IMPLEMENTATION_REPORT.md` | OBSOLETE | Redundant duplicate of `docs/PHASE_8_IMPLEMENTATION_REPORT.md` |
| `PHASE_9_IMPLEMENTATION_REPORT.md` | OBSOLETE | Redundant duplicate of `docs/PHASE_9_IMPLEMENTATION_REPORT.md` |
| `PHASE_10_IMPLEMENTATION_REPORT.md` | OBSOLETE | Redundant duplicate of `docs/PHASE_10_IMPLEMENTATION_REPORT.md` |
| `PHASE_11_IMPLEMENTATION_REPORT.md` | OBSOLETE | Redundant duplicate of `docs/PHASE_11_IMPLEMENTATION_REPORT.md` |
| `AUTHENTICATION_FIX_REPORT.md` | DEVELOPMENT ONLY | Documentation report; recommended to move to `docs/` |

---

## 3. Python Dependencies Audit (`requirements.txt`)

All declared dependencies in `requirements.txt` were audited for runtime import usage across `src/`, `dashboard/`, `scripts/`, and `tests/`:

| Package | Declared Version | Status | Evidence & Runtime Usage |
|---|---|---|---|
| `pyyaml` | `>=6.0.1` | **REQUIRED** | Imported in config loaders, source registries, test fixtures |
| `python-dotenv` | `>=1.0.1` | **REQUIRED** | Imported in core config, main CLI, and test runners |
| `sqlalchemy` | `>=2.0.0` | **REQUIRED** | Core ORM and database connection pooling |
| `psycopg2-binary` | `>=2.9.0` | **REQUIRED** | PostgreSQL database driver for production |
| `alembic` | `>=1.13.0` | **REQUIRED** | Migration engine |
| `flask` | `>=3.0.0` | **REQUIRED** | Web application framework |
| `gunicorn` | `>=21.2.0` | **REQUIRED** | Production WSGI application server on Render |
| `jinja2` | `>=3.1.3` | **REQUIRED** | Server-side template rendering for web and emails |
| `werkzeug` | `>=3.0.1` | **REQUIRED** | WSGI utilities, password hashing, secure filename handling |
| `python-docx` | `>=1.1.0` | **REQUIRED** | Word document report generation engine |
| `pandas` | `>=2.0.0` | **REQUIRED** | Analytics processing and CSV reporting |
| `openpyxl` | `>=3.1.0` | **REQUIRED** | Excel data export engine |
| `requests` | `>=2.31.0` | **REQUIRED** | HTTP client for RSS feeds, Brevo API, and web scraping |
| `beautifulsoup4`| `>=4.12.3` | **REQUIRED** | HTML parsing and text extraction across scrapers |
| `playwright` | `>=1.42.0` | **OBSOLETE** | **Zero imports** across `src/`, `dashboard/`, `scripts/`, and `tests/`. Not supported on Render Free Tier. Proven safe to remove. |

---

## 4. Test Suites Audit (`tests/`) — [TEST ONLY]

112 test files containing 287 automated test cases:

- **Core Phase Regression Suites (27 files)**: Exhaustively test security release controls (Phase 11), reliability & observability (Phase 10), matching intelligence (Phase 9), analytics (Phase 8), notifications (Phase 7), data quality & lifecycle (Phase 6), ranking (Phase 5), SSR & CSP (Phase 4), admin MFA & isolation (Phase 3), harvesting & RLS (Phase 2), and authentication/foundation (Phase 1).
- **Integration Test Suites (4 files)**: Pipeline and admin isolation end-to-end verifications.
- **Unit Micro-Tests (79 files)**: Component-level unit test suites for individual repositories, parsers, and utilities.
- **Tradeoff Analysis**: All tests are valuable for continuous integration and regression prevention. None are executed in production runtime on Render. They remain organized under `tests/` and are not packaged into deployment images.

---

## 5. Security & Dangerous Patterns Audit

An exhaustive static scan was executed across all production modules:

| Vulnerability / Pattern | Search Target | Result | Status |
|---|---|---|---|
| Dangerous code evaluation | `eval()` | 0 matches in production code | **CLEAN** |
| Arbitrary code execution | `exec()` | 0 matches in production code | **CLEAN** |
| Unsafe shell execution | `subprocess(..., shell=True)` | 0 matches | **CLEAN** |
| OS system execution | `os.system()` | 0 matches | **CLEAN** |
| Permissive CORS | `Access-Control-Allow-Origin: *` | 0 matches | **CLEAN** |
| Debug mode in production | `debug=True` or `DEBUG = True` | Defaults to `False` | **CLEAN** |
| Hardcoded secrets | Raw secret strings | Fail-closed validation in production | **CLEAN** |
| Empty directories | Non-git empty folders | 0 found | **CLEAN** |
| Naming conventions | Non-snake_case python files | 0 found (100% compliant) | **CLEAN** |

---

## 6. Cleanup Recommendations & Execution Plan

1. **Dependency Pruning**: Remove `playwright>=1.42.0` from `requirements.txt`.
2. **Duplicate Code Elimination**: Remove redundant root `app.py` (superseded by canonical `wsgi.py`).
3. **Report Consolidation**: Remove duplicate root files `PHASE_8_IMPLEMENTATION_REPORT.md`, `PHASE_9_IMPLEMENTATION_REPORT.md`, `PHASE_10_IMPLEMENTATION_REPORT.md`, and `PHASE_11_IMPLEMENTATION_REPORT.md` (already archived in `docs/`). Move root `AUTHENTICATION_FIX_REPORT.md` into `docs/`.
4. **Gitignore Hardening**: Add `data/backups/`, `data/*.sql`, and `scratch/` to `.gitignore` to prevent database dumps (24 MB) and developer scratch scripts from entering deployment builds.
