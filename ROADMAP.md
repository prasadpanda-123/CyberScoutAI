# CyberScout AI — Project Roadmap

This document outlines completed engineering milestones and future architectural goals for CyberScout AI.

---

## 🟢 Completed Milestones (v1.0.0 – v1.2.0)

- [x] **Phase 0 — Research & Architecture Specification**: Zero-cost constraints, threat modeling, schema specification.
- [x] **Phase 1 — Core Foundation & PostgreSQL Hardening**: PostgreSQL connection pooling, migrations, RLS policies, audit logging.
- [x] **Phase 2 — Universal Collection Framework**: Rate limiting, exponential backoff, circuit breaking, source definitions.
- [x] **Phase 3 — Administrative Security & Multi-Factor Auth**: Admin/User table isolation, TOTP MFA, brute-force rate-limiting.
- [x] **Phase 4 — SSR Search Portal & Deduplication Engine**: Server-rendered search, faceted filtering, SHA-256 canonical deduplication.
- [x] **Phase 5 — Opportunity Intelligence & Matching**: Dynamic priority ranking, rule weights, skill extraction, eligibility criteria.
- [x] **Phase 6 — Data Quality & Lifecycle Engine**: Quarantine state transitions, automated validation rules, decay management.
- [x] **Phase 7 — Notifications & Outbox Survivability**: Transactional outbox pattern, quiet hours evaluator, responsive HTML digest renderer.
- [x] **Phase 8 — Observability, Analytics & Source Health**: Diagnostic dashboards, health telemetry, source anomaly detection.
- [x] **Phase 9 — Explainable Matching Intelligence**: Deterministic similarity engine, skill normalizer, audit-ready reasoning.
- [x] **Phase 10 — Production Reliability & Disaster Recovery**: Context-managed pooling, transactional SQL backups, restore drills, liveness/readiness probes.
- [x] **Phase 11 — Final Security Audit & Production Release**: 50-point security matrix (CSRF, IDOR, XSS, HMAC webhooks, RLS enforcement, session rotation).

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
