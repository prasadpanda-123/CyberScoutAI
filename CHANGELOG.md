# Changelog

All notable changes to CyberScout AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.1] - 2026-08-04

### Added
- GitHub open-source governance templates (`.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md`).
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) for automated test suite execution and health diagnostics.
- Screenshots gallery documentation (`docs/screenshots/README.md`).
- Open source community documents (`CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`, `ROADMAP.md`, `RELEASE_TEMPLATE.md`).
- Repository Engineering Audit report (`docs/audits/repository_audit.md`).

### Changed
- Complete overhaul of root `README.md` with ASCII architecture diagrams, badges, and CLI/Dashboard operational guides.

---

## [1.1.0] - 2026-08-04

### Added
- Web Dashboard & Control Center presentation layer (`dashboard/`).
- 11 responsive HTML control center pages (Dashboard, Opportunities, Analytics, Collectors, Scheduler, Notifications, Knowledge Base, Configuration, Logs, System Health, System Info).
- 15 REST API endpoints under `/api/*` for health, stats, opportunities, analytics, and control commands.
- Custom dark cybersecurity theme (`#0D1117` background).
- `--dashboard` CLI flag to launch Flask server on port 5000.

---

## [1.0.0] - 2026-08-04

### Added
- End-to-End Validation & Production Hardening suite.
- 112 automated unit, stress, memory leak, security, and resilience tests.
- Master audit documentation (`SYSTEM_AUDIT.md`, `RELEASE_READINESS.md`, `PERFORMANCE_REPORT.md`, `MEMORY_REPORT.md`, `SECURITY_REPORT.md`).

---

## [0.9.0] - 2026-08-03

### Added
- Automation Engine & Scheduler (`src/automation/`).
- `AutomationEngine` and `SchedulerService` background daemon loop.
- Signal handling for `SIGINT` / `SIGTERM` graceful shutdown.
- CLI flags `--run-once`, `--daemon`, `--dry-run`, `--metrics`, `--scheduler-status`.

---

## [0.8.0] - 2026-08-02

### Added
- Notification Engine (`src/notifier/`).
- Jinja2 HTML email digest renderer and plain text fallback.
- SMTP sender with exponential backoff retry decorator.

---

## [0.7.0] - 2026-08-01

### Added
- Knowledge Base & Historical Intelligence (`src/database/knowledge_manager.py`).
- State transition tracking, archive manager, and data retention policies.

---

## [0.6.0] - 2026-07-30

### Added
- Opportunity Intelligence & Priority Ranking Engine (`src/intelligence/ranking_engine.py`).
- Rule-based dynamic scoring system assigning P0, P1, P2, and P3 priorities.

---

## [0.5.0] - 2026-07-28

### Added
- Processing Engine (`src/processors/`).
- Sequential processing pipeline (validation, cleaning, normalization, deduplication, quality check).

---

## [0.4.0] - 2026-07-25

### Added
- Core Collectors (`src/collectors/`).
- RSS/Atom Collector, GitHub Search Collector, YouTube RSS Collector, and CTFtime API Collector.

---

## [0.3.0] - 2026-07-20

### Added
- Universal Collection Framework (`src/collectors/base.py`, `http_client.py`).
- HTTP client with rate limiting, response caching, and `robots.txt` compliance.

---

## [0.2.0] - 2026-07-15

### Added
- Search Intelligence Layer (`src/intelligence/`).
- SearchPlanner, QueryBuilder, QueryValidator, and SearchTemplateEngine.

---

## [0.1.0] - 2026-07-10

### Added
- Initial Foundation milestone.
- Core configuration loader, centralized logging, PostgreSQL DatabaseManager, and CLI parser.
