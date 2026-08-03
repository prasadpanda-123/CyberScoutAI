# Pipeline Design

## Full Flow

```
   Scheduler
       │
       ▼
Search Intelligence  (build concrete queries/URLs per source)
       │
       ▼
   Collectors  (fetch raw data → shared Opportunity shape, unvalidated)
       │
       ▼
   Validation  (reject/flag malformed records)
       │
       ▼
   Cleaning  (strip HTML, normalize whitespace, truncate)
       │
       ▼
  Normalization  (canonicalize price/date/location/category-hint fields)
       │
       ▼
Duplicate Detection  (within-run + against history)
       │
       ▼
  Categorization  (assign final category + tags)
       │
       ▼
   Ranking  (compute score + score_breakdown)
       │
       ▼
 SQLite Storage  (upsert, update status, log run)
       │
       ▼
Email Generation  (select top items, render HTML)
       │
       ▼
   Notification  (SMTP send, log to EmailHistory)
```

Each arrow is a **hard boundary**: the stage on the right must not need to know anything about how the stage on the left works internally — only the shape of data crossing the boundary (mostly, but not exclusively, the `Opportunity` model from `data_model.md`).

---

## Stage-by-Stage Contract

### 1. Scheduler
- **Input:** Trigger event (GitHub Actions cron tick, or manual `--run-pipeline` invocation).
- **Output:** A run context object: `{run_id, triggered_at, enabled_sources[]}`.
- **Responsibilities:** Decide which sources are due to run (some sources may run less frequently than every 6h — configurable per source later), generate a `run_id` for traceability, invoke Search Intelligence.
- **Error handling:** If the whole pipeline fails, the Scheduler logs the failure to `SearchHistory` with a `failed` status and exits non-zero — but a partial failure in one source must **never** abort the whole run (see Collectors below).
- **Scalability:** As source count grows to 30+, the Scheduler should support per-source frequency overrides (e.g., news RSS every 6h, slower-moving catalog sites once daily) rather than a single global interval.

### 2. Search Intelligence
- **Input:** `run_context` + `sources.yaml` + `keywords.yaml`.
- **Output:** A list of `CollectionTask` objects: `{source_id, method, url_or_query, params}`.
- **Responsibilities:** For search-driven sources, expand keyword templates into concrete queries (see `search_templates.md`). For catalog/RSS sources, just resolve the static endpoint. Deduplicate tasks (don't hit the same URL twice in one run).
- **Error handling:** A malformed template for one source produces a warning and skips only that source's tasks — never crashes the batch.
- **Scalability:** This is the layer that absorbs the growth from ~15 to 100+ keywords without collectors themselves needing changes — collectors stay dumb fetchers; all query-construction intelligence lives here.

### 3. Collectors
- **Input:** One `CollectionTask`.
- **Output:** List of raw `Opportunity`-shaped dicts (fields may be missing/null — Validation handles that next), plus a `CollectorResult` metadata wrapper: `{source_id, task, items[], fetched_count, errors[]}`.
- **Responsibilities:** Fetch, parse into the shared shape, nothing more. See `collector_contract.md` for the full interface.
- **Error handling:** Each collector call is wrapped by the pipeline runner in isolation — a single source's exception is caught, logged, and that source contributes zero items to the run rather than aborting the pipeline. This isolation is critical at 30+ collector scale: one broken HTML selector should never take down the whole daily email.
- **Scalability:** New collectors are added by implementing the contract and registering an entry in `sources.yaml` — the pipeline runner loop doesn't change.

### 4. Validation
- **Input:** All raw items from all `CollectorResult`s in the run.
- **Output:** `(valid_items[], rejected_items[])`.
- **Responsibilities:** Enforce the **required-field** rules from `data_model.md` (id assignable, title present, url present and well-formed, source known, discovered_date assignable). Anything failing required-field checks is rejected, not silently dropped — rejected items are logged with a reason for later collector-quality review.
- **Error handling:** Validation never raises for bad data — bad data is data, and gets routed to `rejected_items` instead of crashing anything downstream.

### 5. Cleaning
- **Input:** `valid_items[]`.
- **Output:** `cleaned_items[]` (same shape, sanitized values).
- **Responsibilities:** Strip HTML tags from `title`/`description`, collapse whitespace, truncate `description` to the max length, strip tracking parameters from `url`.
- **Error handling:** Cleaning is deterministic and should not fail; if a field can't be cleaned safely, it's nulled out and flagged in `raw_data`'s companion metadata rather than causing a pipeline error.

### 6. Normalization
- **Input:** `cleaned_items[]`.
- **Output:** `normalized_items[]`.
- **Responsibilities:** Convert `price` free text into the free/paid/unknown sub-flag, parse `deadline`/`published_date` strings into ISO 8601, canonicalize `location` (e.g., "WFH", "remote-friendly" → `"Remote"` + `remote=true`), map source-specific difficulty vocab into the fixed `difficulty` enum.
- **Error handling:** Unparseable dates/prices default to `null`/`"unknown"` rather than blocking the item — partial data is still useful data.
- **Scalability:** Normalization rules are the most likely place new source-specific quirks accumulate; keep per-field normalizer functions small and independently testable so adding source #31's weird date format doesn't risk breaking source #12's.

### 7. Duplicate Detection
- **Input:** `normalized_items[]` + read access to `Opportunities` table (existing `active` records).
- **Output:** Each item tagged either `is_duplicate: false` (proceeds) or `is_duplicate: true, duplicate_of_id: <id>` (routed to storage as a `duplicate`-status record, not re-ranked or re-emailed).
- **Responsibilities:** Implements the matching rules from `intelligence_strategy.md` §2 (exact URL match after stripping tracking params, or fuzzy title similarity within a time window).
- **Error handling:** A dedup-check failure (e.g., DB read error) should fail closed — treat the item as **not** a duplicate rather than silently dropping it, since false negatives (a rare duplicate slipping through) are far less harmful than false positives (a real new opportunity getting suppressed).
- **Scalability:** At thousands of historical records, a naive O(n²) title-similarity scan becomes slow — index by normalized-title prefix or source to narrow the comparison set before running similarity scoring.

### 8. Categorization
- **Input:** Non-duplicate `normalized_items[]`.
- **Output:** Items with `category` and `tags[]` populated.
- **Responsibilities:** Two-pass classification per `intelligence_strategy.md` §1 — source-based default first, keyword-based override second.
- **Error handling:** If no category can be determined, default to `"news"` (the documented fallback) rather than leaving it null — `category` is a required field downstream.

### 9. Ranking
- **Input:** Categorized items.
- **Output:** Items with `score` and `score_breakdown` populated.
- **Responsibilities:** Apply `weights.yaml` additive scoring per `ranking_algorithm.md`.
- **Error handling:** Missing signals contribute 0 points, never an error — an item with no detectable `certificate` field simply doesn't get the certificate bonus.

### 10. SQLite Storage
- **Input:** All processed items (active, duplicate, and expired-on-arrival if `deadline` already passed).
- **Output:** Confirmation of rows written/updated; a `run_summary` record.
- **Responsibilities:** Upsert into `Opportunities` (insert new, update `last_seen`/`score` for existing actives), write `duplicate` records with their reference, log the run to `SearchHistory`.
- **Error handling:** Wrapped in a transaction per run — either the whole batch commits or the run is marked failed and retried next cycle; partial writes are avoided to keep the DB consistent.
- **Scalability:** Indexes on `url_hash`, `discovered_date`, `category`, and `status` (see `sqlite_schema.md`) keep upserts and the later email-selection query fast even at tens of thousands of rows.

### 11. Email Generation
- **Input:** Query against `Opportunities` for `status=active` items scoring above `email_inclusion_threshold`, not yet in `EmailHistory` for today.
- **Output:** Rendered HTML string + plain-text fallback.
- **Responsibilities:** Apply the category-cap balancing rule, render sections per `email_design.md`.
- **Error handling:** If zero items qualify, generate a short "no new high-quality opportunities today" email rather than sending nothing (keeps the automation's health visible — silence could mean either "no news" or "pipeline broken," and a zero-items email disambiguates that).

### 12. Notification
- **Input:** Rendered email + recipient config.
- **Output:** Send confirmation or failure.
- **Responsibilities:** SMTP send, write sent item ids to `EmailHistory`.
- **Error handling:** Retry per `schedule.yaml`'s `retry_policy`; if all retries fail, log clearly (this is the one failure mode that should be loud, since it means you silently miss a day's digest).

---

## Cross-Cutting Concerns

- **Traceability:** every item carries its originating `run_id` through the whole pipeline (stored in `SearchHistory`, referenced from `Opportunities`), so any record can be traced back to exactly which run discovered/last-touched it.
- **Idempotency:** re-running the same `run_id`'s data through Storage must not create duplicate rows — upserts are keyed by `id` (or `url_hash` for cross-run dedup), not blind inserts.
- **Isolation:** failure in any single collector or normalizer function must degrade gracefully (fewer opportunities that day) rather than catastrophically (no email at all, or a corrupted database).
