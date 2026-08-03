# Processor Contracts

Each processor implements exactly one stage from [pipeline.md](pipeline.md). All processors share a common shape convention: a pure transformation from a list of `Opportunity`-shaped dicts into another list of the same shape, with the canonical field names from [data_model.md](data_model.md) and the enums in [enums.md](enums.md).

---

## 1. Validator

- **Responsibilities:** Enforce the required-field rules from [data_model.md](data_model.md); split input into `valid_items` and `rejected_items` with reasons.
- **Input:** Raw items from all collectors in the current run.
- **Output:** `(valid_items, rejected_items)`.
- **Dependencies:** The canonical field rules in [data_model.md](data_model.md).
- **Expected behavior:** Deterministic and non-mutating; the same input always produces the same split.

## 2. Cleaner

- **Responsibilities:** Strip HTML, collapse whitespace, truncate descriptions, and sanitize URLs.
- **Input:** `valid_items` from the Validator.
- **Output:** `cleaned_items`.
- **Dependencies:** Text helper utilities and the canonical field contract in [data_model.md](data_model.md).
- **Expected behavior:** Idempotent; cleaning should not keep changing already-cleaned values.

## 3. Normalizer

- **Responsibilities:** Convert `price_raw` into `price_normalized`, parse date strings into ISO 8601, canonicalize `location`/`remote`, and map difficulty vocabulary to the fixed enum.
- **Input:** `cleaned_items`.
- **Output:** `normalized_items`.
- **Dependencies:** Date helpers and the canonical enums in [enums.md](enums.md).
- **Expected behavior:** Unparseable values degrade to `null` or `unknown` instead of raising.

## 4. Duplicate Detector

- **Responsibilities:** Flag within-run and against-history duplicates.
- **Input:** `normalized_items` plus read-only access to existing active records through the Storage Manager interface.
- **Output:** Items annotated with `is_duplicate` and, when applicable, `duplicate_of_id`.
- **Dependencies:** The storage layer and the duplicate rules described in [pipeline.md](pipeline.md).
- **Expected behavior:** Fails closed; ambiguous cases should be treated as not-duplicate rather than suppressing a real record.

## 5. Category Classifier

- **Responsibilities:** Assign the final `category` and populate `tags` from taxonomy matches.
- **Input:** Non-duplicate `normalized_items`.
- **Output:** Items with `category` and `tags` populated.
- **Dependencies:** The taxonomy and the source defaults in [sources.yaml](../../config/sources.yaml).
- **Expected behavior:** Always produces a non-null `category`; fallback to `news` if no other evidence is available.

## 6. Ranking Engine

- **Responsibilities:** Compute `score` and `score_breakdown` according to [ranking_algorithm.md](ranking_algorithm.md).
- **Input:** Categorized items.
- **Output:** Items with `score` and `score_breakdown` populated.
- **Dependencies:** [weights.yaml](../../config/weights.yaml).
- **Expected behavior:** Purely additive, deterministic, and explainable; each contribution should be traceable in the score breakdown.

## 7. Storage Manager

- **Responsibilities:** Upsert processed items into SQLite, transition `status`, log runs to `SearchHistory`, and expose the read-only queries used by duplicate detection and email generation.
- **Input:** Fully processed items for a given `run_id`.
- **Output:** Write confirmation and row counts.
- **Dependencies:** [sqlite_schema.md](sqlite_schema.md).
- **Expected behavior:** Transactional and idempotent; a re-run of the same inputs should not create duplicate rows.

---

## Shared Conventions Across All Processors

- No network calls; every processor operates on in-memory data and the local storage layer only.
- No processor should import another processor's internals; all composition occurs in the pipeline orchestrator.
- Every processor should be unit-testable against fixture data and should preserve the canonical field names from [data_model.md](data_model.md).
