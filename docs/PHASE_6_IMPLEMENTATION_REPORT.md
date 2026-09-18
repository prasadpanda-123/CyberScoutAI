# PHASE 6 IMPLEMENTATION REPORT
## Industrial Data Quality, Opportunity Lifecycle & Freshness Intelligence

**Platform**: CyberScout AI  
**Author**: Implementation Engineer  
**Date**: September 15, 2026  
**Status**: COMPLETE  
**Zero-Paid-Resource Compliance**: 100% Free / Open-Source (PostgreSQL 17 Native, Python Standard Library, Flask/Jinja2 SSR, Brevo Free-tier compatible)

---

### Executive Summary

Phase 6 implements an industrial-grade **Data Quality Engine**, **Opportunity Lifecycle Engine**, **Freshness Engine**, **Source Anomaly Detector**, and **Quarantine/Validation Pipeline** within CyberScout AI. 

The core objective is fulfilled:
> *"The opportunities shown to users should be accurate, current, complete enough to be useful, and trustworthy."*

All quality, lifecycle, and freshness decisions are deterministic, bounded, testable, and explainable without machine learning or paid cloud services.

```
       SOURCE
         |
         v
      DISCOVER
         |
         v
       FETCH
         |
         v
       PARSE
         |
         v
      VALIDATE
         |
         v
     NORMALIZE
         |
         v
  IDENTIFY / DEDUP (Phase 2.1 Layered Identity)
         |
         v
    DATA QUALITY ENGINE
         |
         +--------------------+
         |                    |
         v                    v
      ACCEPT              QUARANTINE (Isolated from discovery & recommendations)
         |                    |
         v                    v
     LIFECYCLE          ADMIN REVIEW / TRIAGE
         |
         v
      PERSIST (Safe Update Policy)
         |
         v
     FRESHNESS (Decay Penalties)
         |
         v
    SCORE / RANK (Phase 5 Deterministic Engine)
         |
         v
   SSR SEARCH / UI (Phase 4 Progressive Enhancement)
         |
         v
       USER
```

---

### 1. Existing vs. New Lifecycle Architecture

Prior to Phase 6, opportunities held coarse status flags (`status = 'active' | 'expired' | 'archived'`). Phase 6 separates **Data Quality Status** from **Lifecycle State**:

- **Lifecycle State** reflects real-world operational availability (e.g. deadline timing, explicit closure, reopening, disappearance).
- **Data Quality State** reflects data completeness, validity, syntactic correctness, and contradiction absence.

#### State Machine Flow

```
                      [ Incoming Opportunity ]
                                 |
                                 v
                    [ Data Quality Gate ]
                     /                \
         (Valid / Normalized)     (Critical Error / Contradiction)
                   /                    \
                  v                      v
             [ ACCEPT ]            [ QUARANTINE ]
                  |                      |
                  v                 (Isolated from Search,
        [ Lifecycle Evaluation ]     Rankings & Alerts)
          /        |         \           |
         /         |          \          v
        v          v           v    [ Admin Review ]
   (Future dl)  (dl <= 3d) (dl < today)  /      \
      |            |           |    (Approve) (Reject)
      v            v           v        |         |
   ACTIVE ---> CLOSING_SOON -> EXPIRED  v         v
      ^                         |    ACTIVE    REMOVED
      |       (Future dl)       |
      +-------------------------+
             (REOPENED)
```

---

### 2. Quality States & Classification

| Quality Status | Definition | Discovery Exposure | Ranking Behavior |
| :--- | :--- | :--- | :--- |
| `PASSED` | Fully valid, no contradictions, completeness score $\ge 0.70$. | Normal discovery | Full ranking eligibility |
| `NEEDS_REVIEW` | Valid required fields; minor optional field omissions. | Normal discovery | Minor freshness/quality penalty |
| `STALE` | Unrefreshed for $> 7$ days or source health degraded. | Normal discovery | Meaningful ranking penalty ($\le 0.40$) |
| `SEVERELY_STALE`| Unrefreshed for $> 30$ days or source failing. | Normal discovery | Excluded from recommendations |
| `QUARANTINED` | Missing mandatory field, dangerous URL protocol, or contradiction. | **STRICTLY EXCLUDED** | **Score = 0.0, Excluded** |

---

### 3. Lifecycle States & Transitions

1. **`ACTIVE`**: Verified open opportunity with future deadline or ongoing participation.
2. **`CLOSING_SOON`**: Active opportunity with deadline $\le 3\text{ days}$ ($72\text{ hours}$). Visualized with the `🔥 Closing Soon` badge.
3. **`EXPIRED`**: Opportunity whose deadline is in the past ($< \text{today}$).
4. **`CLOSED`**: Opportunity explicitly marked closed or filled by the upstream source.
5. **`REOPENED`**: Opportunity previously expired that receives a verified future deadline. Preserves canonical ID, `first_seen_at`, and identity fingerprint.
6. **`REMOVED`**: Opportunity missing from consecutive harvests ($\ge 3$ consecutive absences) following safe disappearance policy. Excluded from normal discovery.

---

### 4. Deterministic Completeness Model

The `DataQualityEngine` evaluates field completeness using a bounded, tiered scoring model $[0.0, 1.0]$:

- **REQUIRED FIELDS** (Instant Quarantine if missing):
  - `title`: Non-empty string $\ge 3$ characters, $\le 500$ characters.
  - `url`: Valid HTTP/HTTPS protocol, valid hostname.
  - `source_id`: Registered collector identifier.
- **IMPORTANT FIELDS** (Completeness penalties):
  - `description`: Missing $\rightarrow -0.15$
  - `category`: Uncategorized / other $\rightarrow -0.10$
  - `opportunity_type`: Missing $\rightarrow -0.10$
- **OPTIONAL FIELDS** (Minor completeness penalties):
  - `tags`: Missing or empty $\rightarrow -0.05$
  - `pricing_type` / `price_amount`: Missing $\rightarrow -0.05$
  - `location` / `remote`: Missing $\rightarrow -0.05$

---

### 5. Contradiction Detection

The engine detects structural, deterministic contradictions without ambiguous heuristics:
1. **Free vs. Fee**: `is_free = True` AND (`price_amount > 0` OR `application_fee > 0`).
2. **Stipend Type vs. Amount**: `stipend_type in ('none', 'unpaid')` AND `stipend_amount > 0`.
3. **Temporal Inversion**: `deadline < published_date`.
4. **Remote Conflict**: `remote = False` AND `location in ('remote', 'remote only')`.

Any detected contradiction triggers automatic quarantine (`quality_status = 'quarantined'`).

---

### 6. Safe Update Policy

Harvester regressions or partial feeds must never destroy existing canonical data. In `OpportunityRepository.save_or_update()`:

```python
# SAFE UPDATE POLICY: Protect valid existing fields from corrupt or empty incoming data
if not opp.title or len(str(opp.title).strip()) < 3:
    opp.title = existing.title
if not opp.description and existing.description:
    opp.description = existing.description
if not opp.deadline and existing.deadline:
    opp.deadline = str(existing.deadline)
if opp.price_amount is None and existing.price_amount is not None:
    opp.price_amount = existing.price_amount
if opp.stipend_amount is None and existing.stipend_amount is not None:
    opp.stipend_amount = existing.stipend_amount
if not opp.location and existing.location:
    opp.location = existing.location
if existing.tags:
    opp.tags = list(set(existing.tags or []) | set(opp.tags or []))
```

#### Timestamp Invariant
- **Unchanged Harvest**: Updates `last_seen_at` and `last_harvested_at`. **Does not touch `last_changed_at`**.
- **Meaningful Content Update**: Updates `last_seen_at`, `last_harvested_at`, and `last_changed_at`.

---

### 7. Source Health & Anomaly Detection

The `SourceAnomalyDetector` isolates collector failures and detects batch-level regressions:
1. **Yield Drop Anomaly**: If historical average $\ge 10$ items and incoming batch suffers $\ge 90\%$ yield collapse, an anomaly alert is raised and batch is quarantined from overwriting good canonical data.
2. **Malformed Rate Anomaly**: If incoming batch has $\ge 5$ items and $\ge 90\%$ fail validation, the collector is flagged as degraded.
3. **Failure Isolation**: One failed collector does not halt the harvesting pipeline for other sources.

---

### 8. Database Schema Changes & Migration 14

Migration 14 added Phase 6 lifecycle and quality columns to the PostgreSQL `Opportunities` table:

```sql
ALTER TABLE "Opportunities" ADD COLUMN IF NOT EXISTS lifecycle_status VARCHAR(32) NOT NULL DEFAULT 'active';
ALTER TABLE "Opportunities" ADD COLUMN IF NOT EXISTS quality_status VARCHAR(32) NOT NULL DEFAULT 'passed';
ALTER TABLE "Opportunities" ADD COLUMN IF NOT EXISTS completeness_score REAL NOT NULL DEFAULT 1.0;
ALTER TABLE "Opportunities" ADD COLUMN IF NOT EXISTS quarantine_reason TEXT NULL;
ALTER TABLE "Opportunities" ADD COLUMN IF NOT EXISTS stale_at TIMESTAMP WITH TIME ZONE NULL;
ALTER TABLE "Opportunities" ADD COLUMN IF NOT EXISTS absence_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_opportunities_lifecycle_status ON "Opportunities"(lifecycle_status);
CREATE INDEX IF NOT EXISTS ix_opportunities_quality_status ON "Opportunities"(quality_status);
CREATE INDEX IF NOT EXISTS ix_opportunities_last_harvested ON "Opportunities"(last_harvested_at);
```

#### Index Justification
- `ix_opportunities_lifecycle_status`: Optimizes SSR discovery query filtering (`lifecycle_status != 'removed'`) and batch lifecycle expiration queries.
- `ix_opportunities_quality_status`: Optimizes quarantine isolation (`quality_status != 'quarantined'`) across listing and recommendation candidates.
- `ix_opportunities_last_harvested`: Accelerates stale data detection queries.

---

### 9. Administrative Portal Additions

Two dedicated SSR views added under `/admin/*`, protected by `@admin_required`, session CSRF, and audit logging:

1. **`/admin/source-health`**:
   - Telemetry table showing Source ID, Health State (`HEALTHY`, `DEGRADED`, `FAILING`), Last Attempt, Last Success, Latency, and Ingested Item Counts.
2. **`/admin/data-quality`**:
   - Metrics summary: Total, Active, Closing Soon, Expired, Stale, Quarantined, Removed, Missing Fields.
   - Quarantined records review table with one-click Approve (promote to active) and Reject (confirm removal) actions.

---

### 10. Performance Benchmark Results

Benchmarked directly against local PostgreSQL 17 database instance:

| Metric | Result | Target |
| :--- | :--- | :--- |
| **DataQualityEngine Evaluation** | **0.059 ms / item** ($> 400\text{ ops/sec}$) | $< 5\text{ ms}$ |
| **LifecycleEngine Evaluation** | **0.014 ms / item** | $< 2\text{ ms}$ |
| **Database `update_lifecycle_states`** | **4.24 ms** (13 expired, atomic transaction) | $< 50\text{ ms}$ |
| **Discovery Query with Lifecycle Filters** | **1.05 ms** (PostgreSQL FTS + Facets) | $< 20\text{ ms}$ |
| **Recommendation Pipeline (48 candidates)**| **2.34 ms** (Score + Explanations + Diversity) | $< 25\text{ ms}$ |

---

### 11. Test Verification Results

All suites executed strictly according to Section 57:

| Suite | Tests | Result | Status |
| :--- | :--- | :--- | :--- |
| **Phase 6 Focused Tests** | 56 | 56 Passed | **100% GREEN** |
| **Phase 5 Ranking Tests** | 46 | 46 Passed | **100% GREEN** |
| **Phase 4 SSR Discovery Tests** | 52 | 52 Passed | **100% GREEN** |
| **Phase 3 Admin Security Tests** | 43 | 43 Passed | **100% GREEN** |
| **Phase 2.1 Idempotent Harvesting** | 22 | 22 Passed | **100% GREEN** |
| **Phase 1.1 Integrity Gate** | 8 | 8 Passed | **100% GREEN** |
| **TOTAL VERIFIED REGRESSION** | **227** | **227 Passed** | **100% GREEN** |

---

### 12. Known Limitations & Future Work

1. **Free-tier Ingestion Latency**: Source health latency metrics rely on native HTTP client timing rather than APM agents (compatible with free-tier hosting).
2. **Disappearance Policy Absence Threshold**: Requires 3 consecutive successful harvest scans of the same source before marking an item `REMOVED`. If a collector is disabled or paused, absence count does not increment.
3. **Deterministic Heuristics**: Contradiction detection covers structured fields. Ambiguous natural language contradictions in freeform text are not evaluated by ML (as per zero-paid/deterministic constraints).
