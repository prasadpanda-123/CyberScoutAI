# CyberScout AI — Project Roadmap

This document outlines completed engineering milestones and future architectural goals for CyberScout AI.

---

## 🟢 Completed Milestones (v1.0.0 – v1.1.1)

- [x] **Phase 0 — Research & Architecture Specification**: Requirements gathering, zero-cost constraints.
- [x] **Phase 1 — Core Foundation**: Bootstrap pipeline, logging engine, SQLite connection manager.
- [x] **Phase 2 — Search Intelligence**: Keyword engine, query builder, validation, search planner.
- [x] **Phase 3.1 — Universal Collection Framework**: BaseCollector, HTTP client, rate limiter, cache, robots.txt.
- [x] **Phase 3.2 — Core Collectors**: RSS/Atom collector, GitHub API collector, YouTube RSS, CTFtime API.
- [x] **Phase 4 — Processing Engine**: Validation, HTML cleaning, normalization, deduplication, quality check.
- [x] **Phase 5 — Opportunity Intelligence**: Dynamic scoring rules, P0-P3 priority ranking engine.
- [x] **Phase 6 — Knowledge Base**: Opportunity state transitions, archive manager, trend retention.
- [x] **Phase 7 — Notification Engine**: Jinja2 HTML email digest renderer, SMTP sender with backoff retry.
- [x] **Phase 9 — Automation Engine**: Background daemon thread, YAML scheduler, signal handling.
- [x] **Phase 10 — Production Hardening**: 112 automated unit tests, memory leak audit, release v1.0.0.
- [x] **Phase 11 — Web Dashboard & Control Center**: Flask presentation layer, 11 HTML pages, REST API.
- [x] **v1.1.1 — Repository Professionalization**: Open-source governance, CI workflows, docs.

---

## 🔮 Future Vision (v1.2+ Roadmap)

### Phase 12 — Plugin Extension Framework
- Extensible Python plugin interface allowing community-submitted collectors without modifying core source.

### Phase 13 — Containerized Docker Deployment
- Multi-stage `Dockerfile` and `docker-compose.yml` for isolated containerized daemon execution.

### Phase 14 — Multi-User & RBAC Authorization
- User accounts, custom notification preferences per user, and API authentication tokens.

### Phase 15 — Mobile App & Cloud Sync
- Mobile-responsive PWA (Progressive Web App) and optional self-hosted cloud sync relay.
