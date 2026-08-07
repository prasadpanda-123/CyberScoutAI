# Database Schema Design

No SQL here — this document describes the structural contract the future database layer should implement. The field names below are intentionally aligned with [data_model.md](data_model.md) and the enums in [enums.md](enums.md).

---

## 1. Tables Overview

| Table | Purpose |
|---|---|
| `Opportunities` | One row per discovered opportunity; the core storage of the `Opportunity` model. |
| `Sources` | One row per registered source; mirrors the static configuration in [sources.yaml](../../config/sources.yaml) while preserving historical runtime metadata. |
| `Keywords` | One row per taxonomy keyword; joins against `tags` for analytics and future refinements. |
| `EmailHistory` | One row per opportunity ever included in a sent email; prevents re-sending. |
| `SearchHistory` | One row per pipeline run; traceability and health monitoring. |
| `Statistics` | Aggregated counts by day/source/category for future dashboards and reporting. |
| `Preferences` | User-set overrides for personalization features in later phases. |

---

## 2. Table Details

### `Opportunities`
| Column | Type | Notes |
|---|---|---|
| `id` | TEXT (UUID) | Primary key |
| `title` | TEXT | Required |
| `description` | TEXT | Nullable |
| `url` | TEXT | Required |
| `url_hash` | TEXT | Indexed; normalized hash of `url` used for dedup/upsert lookups |
| `source_id` | TEXT | Foreign key → `Sources.id` |
| `category` | TEXT | Required, indexed; uses `OpportunityCategory` values |
| `provider` | TEXT | Nullable |
| `company` | TEXT | Nullable |
| `location` | TEXT | Nullable |
| `remote` | BOOLEAN | Default `false` |
| `paid` | BOOLEAN | Nullable |
| `certificate` | BOOLEAN | Default `false` |
| `price_raw` | TEXT | Original price text as found in the source |
| `price_normalized` | TEXT | Canonical value such as `free`, `paid`, or `unknown` |
| `currency` | TEXT | Nullable |
| `deadline` | DATE | Nullable, indexed |
| `published_date` | DATE | Nullable |
| `discovered_date` | DATE | Required, indexed, immutable |
| `duration` | TEXT | Nullable |
| `difficulty` | TEXT | Default `unknown`; uses `Difficulty` values |
| `tags` | TEXT (JSON) | Array of taxonomy tags |
| `beginner_friendly` | BOOLEAN | Derived, nullable |
| `score` | INTEGER | Indexed; used by the email-selection query |
| `score_breakdown` | TEXT (JSON) | JSON object explaining score contributions |
| `status` | TEXT | Indexed; uses `Status` values |
| `duplicate_of_id` | TEXT | Nullable, self-referential foreign key → `Opportunities.id` |
| `run_id` | TEXT | Foreign key → `SearchHistory.run_id` |
| `raw_data` | TEXT (JSON) | Original unprocessed collector payload |
| `last_seen` | TIMESTAMP | Updated when a later run re-encounters the item |

### `Sources`
| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | Primary key; matches the source id in [sources.yaml](../../config/sources.yaml) |
| `name` | TEXT | Display name |
| `collection_method` | TEXT | Uses `CollectionMethod` values |
| `default_category` | TEXT | Default category for that source |
| `status` | TEXT | Uses `SourceStatus` values |
| `enabled` | BOOLEAN | Whether the source is currently enabled |
| `official` | BOOLEAN | Whether the source is an official provider |
| `trust_score` | REAL | Static trust signal for sorting and review |
| `maintenance_level` | TEXT | Stable / experimental / deprecated |
| `update_frequency` | TEXT | e.g. `hourly`, `daily`, `weekly` |
| `max_requests_per_run` | INTEGER | Static request budget |
| `request_delay_ms` | INTEGER | Static minimum delay between requests |

### `Keywords`
| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | Primary key |
| `term` | TEXT | Canonical keyword |
| `domain` | TEXT | e.g. `offensive_security`, `networking` |
| `synonym_of` | TEXT | Nullable, self-referential foreign key |

### `EmailHistory`
| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | Primary key |
| `opportunity_id` | TEXT | Foreign key → `Opportunities.id` |
| `email_run_id` | TEXT | Groups all items sent in one digest |
| `sent_at` | TIMESTAMP | |
| `clicked` | BOOLEAN | Nullable; for future engagement tracking |

### `SearchHistory`
| Column | Type | Notes |
|---|---|---|
| `run_id` | TEXT | Primary key |
| `triggered_at` | TIMESTAMP | |
| `completed_at` | TIMESTAMP | Nullable until the run finishes |
| `status` | TEXT | `success`, `partial`, or `failed` |
| `sources_run` | TEXT (JSON list) | Which sources were included |
| `items_collected` | INTEGER | |
| `items_after_dedup` | INTEGER | |
| `items_emailed` | INTEGER | |
| `errors` | TEXT (JSON list) | Error summaries across the run |

### `Statistics`
| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | Primary key |
| `date` | DATE | Indexed |
| `source_id` | TEXT | Nullable foreign key → `Sources.id` |
| `category` | TEXT | Nullable; null indicates a rollup across categories |
| `count` | INTEGER | |
| `avg_score` | REAL | |

### `Preferences`
| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | Primary key |
| `key` | TEXT | e.g. `keyword_boost:osint`, `category_mute:webinar` |
| `value` | TEXT | e.g. `"+10"`, `"true"` |
| `updated_at` | TIMESTAMP | |

---

## 3. Relationships

```
Sources (1) ──────< (many) Opportunities
Opportunities (1) ──self-ref──< (many) Opportunities   [duplicate_of_id]
SearchHistory (1) ──────< (many) Opportunities          [run_id]
Opportunities (1) ──────< (many) EmailHistory
Keywords (1) ──self-ref──< (many) Keywords              [synonym_of]
Sources (1) ──────< (many) Statistics
```

## 4. Indexes

- `Opportunities.url_hash` — fast dedup/upsert lookups.
- `Opportunities.status` — email-selection queries filter on `status='active'`.
- `Opportunities.score` — combined with `status` to select the top items.
- `Opportunities.discovered_date` — analytics and dashboard time-range queries.
- `Opportunities.deadline` — daily housekeeping to transition `active` → `expired`.
- `Opportunities.category` — category-aware selection and reporting.
- `SearchHistory.triggered_at` — health dashboards and run review.
- `EmailHistory.opportunity_id` — ensures a digest does not re-send a previously emailed item.

## 5. Primary and Foreign Keys Summary

- Every table uses text-based identifiers for stability and portability across future migrations.
- `Opportunities.source_id` → `Sources.id`
- `Opportunities.duplicate_of_id` → `Opportunities.id` (self, nullable)
- `Opportunities.run_id` → `SearchHistory.run_id`
- `EmailHistory.opportunity_id` → `Opportunities.id`
- `Statistics.source_id` → `Sources.id` (nullable)
- `Keywords.synonym_of` → `Keywords.id` (self, nullable)

## 6. Normalization and Expansion Notes

- The schema remains in third normal form for structural data while intentionally storing `raw_data` and `score_breakdown` as JSON blobs because those values are flexible and source-specific.
- The schema should remain additive over time; new fields should be optional and documented in this file before implementation.
- Future expansion may add a `Meta` key-value table for schema versioning without changing the core shape of `Opportunities`.
