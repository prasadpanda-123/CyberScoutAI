# Data Model — The `Opportunity` Object

## Why a Formal Data Model Matters

Every collector, processor, ranking rule, database column, and email template in CyberScout AI ultimately operates on one shared shape: the `Opportunity`. This document is the authoritative contract for that shape and should be treated as the source of truth for field names, types, and lifecycle semantics.

This document is the authoritative definition. Any breaking change to the model must be versioned and documented in [sqlite_schema.md](sqlite_schema.md) and the enum definitions in [enums.md](enums.md).

---

## 1. Canonical Field Specification

The field names below are the canonical names used across collectors, processors, the database schema, and ranking logic.

| Field | Type | Required? | Description | Example | Validation Rules |
|---|---|---|---|---|---|
| `id` | string (UUID v4) | Required | Internal unique identifier, generated at ingestion and independent of source URLs. | `"a1b2c3d4-..."` | Must be a valid UUID4; generated once and never regenerated. |
| `title` | string | Required | Human-readable title of the opportunity. | `"Free CTF: picoCTF 2026"` | 3–200 chars after cleaning; HTML stripped; whitespace collapsed. |
| `description` | string | Optional | Short summary/body text describing the opportunity. | `"Beginner-friendly CTF running..."` | Max 2000 chars; HTML stripped and truncated if needed. |
| `url` | string (URL) | Required | Canonical link to the opportunity. | `"https://picoctf.org/"` | Must pass URL validation; tracking query params are stripped before storage. |
| `source_id` | string | Required | Identifier of the collector/source registered in [sources.yaml](../../config/sources.yaml). | `"ctftime"` | Must match a registered source id in the configuration. |
| `category` | string (enum) | Required | Normalized opportunity type. | `"hackathon"` | Must use a value from [enums.md](enums.md) `OpportunityCategory`; assigned by the Category Classifier. |
| `provider` | string | Optional | Organization running the opportunity, which may differ from the source that discovered it. | `"picoCTF / Carnegie Mellon"` | Free text, trimmed; used for provider trust signals. |
| `company` | string | Optional | Employer for internships/jobs. | `"Cisco"` | Free text; should be null for non-employment categories. |
| `location` | string | Optional | Physical location if relevant. | `"Bengaluru, India"` or `"Remote"` | Free text; `"Remote"` is a reserved value that also sets `remote=true`. |
| `remote` | boolean | Optional (defaults to `false`) | Whether the opportunity can be done remotely. | `true` | Derived from `location` or target keywords; absence of evidence means `false`. |
| `paid` | boolean or `null` | Optional | Whether the opportunity is compensated. | `true` | `null` means unknown/not applicable; `true`/`false` only when determinable. |
| `certificate` | boolean | Optional (defaults to `false`) | Whether completion grants a certificate. | `true` | Derived from metadata or keyword/phrase matching. |
| `price_raw` | string | Optional | Raw cost string as found in the source. | `"Free"`, `"$49"`, `"₹0"` | Retained for display/debugging. |
| `price_normalized` | string (enum) | Optional | Canonical normalized price state. | `"free"`, `"paid"`, `"unknown"` | Must use a value from the normalization vocabulary in [enums.md](enums.md) or the processor contract. |
| `currency` | string (ISO 4217) | Optional | Currency code if a price is stated. | `"USD"`, `"INR"` | Null when free/unknown; valid 3-letter ISO code when present. |
| `deadline` | date (ISO 8601) | Optional | Application/registration deadline. | `"2026-09-15"` | Must be a valid date; used to mark items expired. |
| `published_date` | date (ISO 8601) | Optional | When the source originally published the opportunity. | `"2026-08-01"` | If unavailable, falls back to `discovered_date`. |
| `discovered_date` | date (ISO 8601) | Required | When CyberScout first found the item. | `"2026-08-03"` | Set once at first insert and never updated. |
| `duration` | string | Optional | How long the opportunity lasts. | `"6 weeks"`, `"3 months"` | Free text; not strictly parsed in v1. |
| `difficulty` | string (enum) | Optional | Skill level. | `"beginner"` | Must use a value from [enums.md](enums.md) `Difficulty`. |
| `tags` | array[string] | Optional | Keyword tags from the taxonomy. | `["osint", "beginner-friendly", "remote"]` | Deduplicated and lowercased. |
| `beginner_friendly` | boolean | Optional (derived) | Whether the opportunity is suitable for beginners. | `true` | Derived by the Category Classifier/Normalizer from difficulty and tags. |
| `score` | integer | Required (computed) | Final ranking score from the Ranking Engine. | `85` | Computed by the Ranking Engine and always present after ranking. |
| `score_breakdown` | object (JSON) | Required (computed) | Explains how the score was derived. | `{"free": 40, "remote": 20, "total": 90}` | Stored as JSON alongside the final score. |
| `status` | string (enum) | Required | Lifecycle state of the record. | `"active"` | Must use a value from [enums.md](enums.md) `Status`. |
| `duplicate_of_id` | string (UUID) | Optional | Reference to the canonical opportunity when this record is a duplicate. | `"a1b2c3d4-..."` | Set only when `status="duplicate"`. |
| `run_id` | string | Optional | Identifier of the pipeline run that last touched the record. | `"run-20260803-001"` | Used for traceability and health audits. |
| `raw_data` | object (JSON) | Required | Original unprocessed payload returned by the collector. | `{...}` | Preserved as-is for reprocessing and debugging. |
| `last_seen` | date-time | Optional | Most recent time the opportunity was encountered. | `"2026-08-03T12:34:56Z"` | Updated when the item is re-seen in a later run. |

---

## 2. `status` Lifecycle

```
        ┌──────────┐   deadline passed    ┌──────────┐
        │  active  │ ────────────────────▶│ expired  │
        └────┬─────┘                       └──────────┘
             │
             │ dedup match found
             ▼
        ┌──────────┐
        │duplicate │  (not emailed, linked to the canonical id)
        └──────────┘

        ┌──────────┐   manual/periodic cleanup, or > N days old
        │ archived │ ◀──────────────────────────────────────────
        └──────────┘
```

- `active` — eligible for ranking and email selection.
- `expired` — deadline has passed; retained for history and analytics, excluded from email.
- `duplicate` — a near-identical active record already exists; this record stores `duplicate_of_id`.
- `archived` — old and no longer relevant even for historical surfacing; a soft-delete state, not a hard delete.

## 3. Derived and Computed Fields

The following fields are not scraped directly from every source. They are created later in the processing pipeline.

| Field | Created by | How it is calculated | When it is calculated |
|---|---|---|---|
| `category` | Category Classifier | Source-default category is applied first, then overridden by keyword taxonomy matches if stronger evidence exists. | After duplicate detection and before ranking. |
| `tags` | Category Classifier | Keyword taxonomy matches are normalized, deduplicated, and lowercased. | After category assignment. |
| `beginner_friendly` | Normalizer / Category Classifier | Derived from `difficulty` and/or taxonomy tags like `beginner-friendly`. | During normalization and classification. |
| `price_normalized` | Normalizer | Raw price text is canonicalized to `free`, `paid`, or `unknown`. | During normalization. |
| `remote` | Normalizer | Inferred from `location` or keyword cues such as `remote`, `online`, or `virtual`. | During normalization. |
| `score` | Ranking Engine | Sum of additive factors from [ranking_algorithm.md](ranking_algorithm.md) and the configured weights in [weights.yaml](../../config/weights.yaml). | After categorization and before storage. |
| `score_breakdown` | Ranking Engine | A JSON object containing the contributing factors and their individual points. | At the same time as `score`. |
| `status` | Storage Manager | Based on duplicate detection, deadline checks, and lifecycle rules. | When the record is stored. |
| `duplicate_of_id` | Duplicate Detector / Storage Manager | Populated when an item is determined to be a duplicate of an existing canonical record. | During duplicate detection and storage. |

## 4. Schema Versioning

- The data model has an implicit version. Any breaking change must be accompanied by a migration note in [sqlite_schema.md](sqlite_schema.md) and a bump to a `schema_version` constant used by the Storage Manager.
- Additive changes are safe and should be preferred over breaking changes; `raw_data` exists specifically to preserve the source payload for reprocessing without re-fetching.

## 5. Why These Specific Fields Exist

- `id` vs `url`: URLs change over time; the UUID keeps downstream modules stable even when a page is moved or rewritten.
- `source_id` vs `provider`: the source is where CyberScout discovered the item, while the provider is the actual organizer/employer.
- `raw_data`: the collector payload is preserved so future processors can re-run against historical data without re-scraping.
- `score_breakdown`: ranking decisions become auditable and explainable over time.
- `status`: lifecycle is centralized so the repository does not need to re-derive relevance from ad hoc queries.
