# Preflight Audit Report — Phase 12.2

**Date & Time (UTC):** 2026-09-18T15:45:00Z  
**Phase:** 12.2 — Controlled Fresh Database Reset, Integrity Repair & Verification  
**Auditor:** CyberScout AI Security & Database Operations Agent  
**Status:** COMPLETE (Pre-Reset Baseline Established)

---

## 1. Database Identity & Connection Verification

| Parameter | Value / Status | Note |
|---|---|---|
| **Target Host** | `aws-0-ap-northeast-2.pooler.supabase.com:6543` | Supabase Pooler (Transaction mode) |
| **Database Name** | `postgres` | Confirmed disposable development DB |
| **Connected PostgreSQL Role** | `postgres` | Administrative pooler role |
| **rolsuper** | `False` | Managed cloud PostgreSQL instance |
| **rolbypassrls** | `True` | Used for administration/migrations only |
| **PostgreSQL Version** | `PostgreSQL 17.6 on x86_64-pc-linux-gnu` | Linux Debian clang 19.1.7 |
| **Application Environment** | `APP_ENV=development` | Verified from `.env` and runtime |
| **Application Role (`cyberscout_app`)** | `rolsuper=False, rolbypassrls=False, canlogin=True` | Dedicated least-privileged role for authentic RLS validation |
| **Connection Type** | Supabase Pooler port 6543 | SSL mode `require`, pooled transactions |

> [!IMPORTANT]
> Target environment is confirmed as `development` (`APP_ENV=development`). The database is confirmed disposable and all schema definitions, migrations, and seed scripts exist in the repository to deterministically recreate the state.

---

## 2. Schema and Migration State

### Current Migration Version
* **Schema Version:** `v16` (`Phase 12 Canonical User ID UUID Migration`)
* **Applied Migrations:**
  1. `v1`: Initial baseline schema creation
  2. `v2`: Knowledge Base & Historical Intelligence Schema v2
  3. `v3`: Phase 11.5 Quality Intelligence Schema Extension
  4. `v4`: Phase 12 Production Data Intelligence Schema Extension
  5. `v5`: Phase 12.3 Scheduler State Table Creation
  6. `v6`: External Scheduler Webhook Request Idempotency & Tracking Table
  7. `v7`: Phase 2 ScanJobs Operational Job State & Concurrency Table
  8. `v8`: Phase 3 Pending MFA & OTP State Centralization Table
  9. `v9`: Server-Side Sessions & Opaque Cookie Minimization Table
  10. `v10`: Phase 2 Source Registry, Health & Granular Opportunity Pricing Schema Extension
  11. `v11`: Phase 2.1 Idempotent Harvesting & Layered Identity Hardening
  12. `v12`: Phase 4 SSR-First Discovery, PostgreSQL Full-Text Search & Saved Opportunities
  13. `v13`: Phase 5 Intelligent Opportunity Ranking, Personalization & User Preferences
  14. `v14`: Phase 6 Industrial Data Quality, Opportunity Lifecycle, Quarantine & Freshness Intelligence
  15. `v15`: Phase 7 Intelligent Alerting, Change Detection & User Notification Engine
  16. `v16`: Phase 12 Canonical User ID UUID Migration

---

## 3. Public Schema Inventory (25 Tables) & Pre-Reset Row Counts

| # | Table Name | Row Count | Primary Key | PK Type | RLS Enabled | FORCE RLS | Owner |
|---|---|---:|---|---|:---:|:---:|---|
| 1 | `Admins` | 10 | `id` | `integer` | YES | YES | `postgres` |
| 2 | `AppLogs` | 1,344 | `id` | `integer` | NO | YES | `postgres` |
| 3 | `AuditLogs` | 1,863 | `id` | `integer` | YES | YES | `postgres` |
| 4 | `EmailHistory` | 41 | `id` | `varchar` | NO | YES | `postgres` |
| 5 | `Keywords` | 6 | `id` | `varchar` | NO | YES | `postgres` |
| 6 | `LoginAttempts` | 107 | `id` | `integer` | YES | YES | `postgres` |
| 7 | `NotificationOutbox` | 6 | `id` | `varchar` | YES | YES | `postgres` |
| 8 | `Opportunities` | 890 | `id` | `varchar` | YES | YES | `postgres` |
| 9 | `OpportunityDuplicatesArchive` | 0 | `id` | `varchar` | NO | NO | `postgres` |
| 10 | `PendingMfa` | 69 | `token` | `varchar` | YES | YES | `postgres` |
| 11 | `Preferences` | 4 | `id` | `varchar` | NO | YES | `postgres` |
| 12 | `SavedOpportunities` | 11 | `id` | `varchar` | YES | YES | `postgres` |
| 13 | `ScanJobs` | 77 | `job_id` | `varchar` | YES | YES | `postgres` |
| 14 | `SearchHistory` | 106 | `run_id` | `varchar` | YES | YES | `postgres` |
| 15 | `ServerSessions` | 2,018 | `session_hash` | `varchar` | YES | YES | `postgres` |
| 16 | `SourceHealth` | 2 | `source_id` | `varchar` | YES | YES | `postgres` |
| 17 | `Sources` | 197 | `id` | `varchar` | YES | YES | `postgres` |
| 18 | `Statistics` | 0 | `id` | `varchar` | NO | YES | `postgres` |
| 19 | `UserPreferences` | 53 | `id` | `varchar` | YES | YES | `postgres` |
| 20 | `UserSearchHistory` | 32 | `id` | `varchar` | YES | YES | `postgres` |
| 21 | `Users` | 480 | `id` | `uuid` | YES | YES | `postgres` |
| 22 | `alembic_version` | 1 | `version_num` | `varchar` | NO | NO | `postgres` |
| 23 | `scheduler_state` | 1 | `id` | `integer` | NO | YES | `postgres` |
| 24 | `scheduler_webhook_requests` | 198 | `id` | `integer` | NO | NO | `postgres` |
| 25 | `schema_version` | 11 | `version` | `integer` | NO | NO | `postgres` |

---

## 4. Foreign Key Constraints Dependency Graph

All foreign key constraints discovered from `information_schema.table_constraints`:

1. **`Users(id)` References (UUID Canonical Identity):**
   * `AuditLogs.user_id` (`uuid`) $\to$ `Users.id` [`ON DELETE SET NULL`]
   * `SavedOpportunities.user_id` (`uuid`) $\to$ `Users.id` [`ON DELETE CASCADE`]
   * `UserPreferences.user_id` (`uuid`) $\to$ `Users.id` [`ON DELETE CASCADE`]
   * `UserSearchHistory.user_id` (`uuid`) $\to$ `Users.id` [`ON DELETE CASCADE`]
   * `NotificationOutbox.user_id` (`uuid`) $\to$ `Users.id` [`ON DELETE CASCADE`]

2. **`Opportunities(id)` References:**
   * `SavedOpportunities.opportunity_id` (`varchar`) $\to$ `Opportunities.id` [`ON DELETE CASCADE`]
   * `NotificationOutbox.opportunity_id` (`varchar`) $\to$ `Opportunities.id` [`ON DELETE CASCADE`]
   * `EmailHistory.opportunity_id` (`varchar`) $\to$ `Opportunities.id` [`ON DELETE NO ACTION`]
   * `Opportunities.duplicate_of_id` (`varchar`) $\to$ `Opportunities.id` [`ON DELETE NO ACTION`]

3. **`Sources(id)` References:**
   * `Opportunities.source_id` (`varchar`) $\to$ `Sources.id` [`ON DELETE NO ACTION`]
   * `Statistics.source_id` (`varchar`) $\to$ `Sources.id` [`ON DELETE NO ACTION`]

4. **`SearchHistory(run_id)` References:**
   * `Opportunities.run_id` (`varchar`) $\to$ `SearchHistory.run_id` [`ON DELETE NO ACTION`]

5. **Self References:**
   * `Keywords.synonym_of` (`varchar`) $\to$ `Keywords.id` [`ON DELETE NO ACTION`]

---

## 5. Row-Level Security (RLS) Policy Catalog

Total 25 policies cataloged in `public` schema across tables:
* Core tables (`Admins`, `Users`, `Opportunities`, `AuditLogs`, `ScanJobs`, `PendingMfa`, `ServerSessions`, `SourceHealth`, `Sources`, `SearchHistory`, `LoginAttempts`, `SavedOpportunities`, `UserPreferences`, `UserSearchHistory`, `NotificationOutbox`) have `RLS=True` and `FORCE_RLS=True`.
* Append-only protection on `AuditLogs`: `audit_no_delete` (`USING: false`), `audit_no_update` (`USING: false`), `audit_append_only` (`WITH CHECK: true`).
* Role isolation and user-specific tenant filtering policies are audited in Step 5 using application role `cyberscout_app` (`BYPASSRLS=False`).
