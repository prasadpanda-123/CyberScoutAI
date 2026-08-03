# Phase 6 — Knowledge Base & Historical Intelligence Specification

## 1. Architecture Overview

The **Knowledge Base & Historical Intelligence Layer** (v0.7.0) provides persistent tracking of opportunity lifecycles, search and collection history, provider reputation metrics, trend calculation, automated retention policies, and JSON report generation.

```text
+-----------------------------------------------------------------------------------+
|                        KNOWLEDGE BASE & ANALYTICS                                 |
|                                                                                   |
|  Incoming Opportunity                                                             |
|         │                                                                         |
|         ▼                                                                         |
|  [ KnowledgeManager ]         ──> Determines lifecycle state                      |
|                                   (NEVER_SEEN, SEEN_BEFORE, UPDATED, EXPIRED)     |
|         │                                                                         |
|         ▼                                                                         |
|  [ HistoryManager ]           ──> Logs state transitions & execution records      |
|         │                                                                         |
|         ▼                                                                         |
|  [ ProviderStatisticsTracker ] ─> Aggregates provider activity & average score    |
|         │                                                                         |
|         ▼                                                                         |
|  [ AnalyticsEngine & Trend ]  ──> Computes active/expired rates, top providers    |
|         │                                                                         |
|         ▼                                                                         |
|  [ RetentionPolicyManager ]   ──> Archives expired records (Migration v2)         |
|         │                                                                         |
|         ▼                                                                         |
|  [ ReportGenerator ]          ──> Exports JSON reports for Email/Dashboard        |
+-----------------------------------------------------------------------------------+
```

---

## 2. Sequence Diagram

```text
[ Processing Pipeline ]           [ KnowledgeManager ]           [ History / Provider Tracker ]        [ Database (v2) ]
           |                               |                                  |                              |
           | 1. process_opportunity_state()|                                  |                              |
           |------------------------------>|                                  |                              |
           |                               | 2. find_by_url_hash()            |                              |
           |                               |---------------------------------------------------------------->|
           |                               | 3. (Return state: NEVER_SEEN)    |                              |
           |                               |<----------------------------------------------------------------|
           |                               |                                  |                              |
           |                               | 4. record_change()               |                              |
           |                               |--------------------------------->|                              |
           |                               | 5. update_provider_stats()       |                              |
           |                               |--------------------------------->|                              |
           |                               |                                  | 6. INSERT / UPDATE           |
           |                               |                                  |----------------------------->|
```

---

## 3. Database Schema v2 (Migration v2)

- **`trend_snapshots`**: Stores historical trend snapshots.
- **`provider_statistics`**: Aggregates total opportunities, active counts, and average score per provider.
- **`opportunity_history`**: Audit trail of state transitions (`old_value`, `new_value`, `change_type`).
- **`retention_logs`**: Logs automated archiving and cleanup executions.

---

## 4. Configuration Files

- `config/retention.yaml`: Retention thresholds and cleanup rules.
- `config/analytics.yaml`: Time windows and top-rank limits.
- `config/knowledge.yaml`: Opportunity lifecycle state definitions.
- `config/history.yaml`: History record limits.
- `config/statistics.yaml`: Auto-aggregation settings.
