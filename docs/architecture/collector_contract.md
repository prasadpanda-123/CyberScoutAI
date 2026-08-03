# Collector Contract

This document defines the interface every collector must satisfy. The collector's responsibility is to fetch and parse source data into the canonical `Opportunity` shape defined in [data_model.md](data_model.md) and use the enumerations in [enums.md](enums.md).

---

## 1. Responsibilities and Non-Responsibilities

A collector is responsible for:
- Fetching raw data from exactly one source using the method declared in [sources.yaml](../../config/sources.yaml).
- Parsing that data into a list of `Opportunity`-shaped records, preserving the original payload in `raw_data`.
- Reporting success, partial failure, or complete failure honestly.

A collector is not responsible for:
- Cleaning, normalizing, deduplicating, categorizing, or scoring items.
- Deciding whether an item is good enough to keep; the collector returns everything it can parse.
- Writing to the database; storage is handled later by the pipeline.

## 2. Input

Every collector receives a single `CollectionTask` produced by the Search Intelligence layer:
```
{
  source_id: str,
  method: str,
  url_or_query: str,
  params: dict
}
```
The collector must be able to act on this task plus its own module-level configuration (for example, API tokens loaded from the environment) without needing any hidden state.

## 3. Output

Every collector returns a `CollectorResult`:
```
{
  source_id: str,
  task: CollectionTask,
  items: list[Opportunity-shaped dict],
  fetched_count: int,
  errors: list[str],
  status: "ok" | "partial" | "failed"
}
```
- `status: "ok"` — fetch succeeded and all parseable items were emitted.
- `status: "partial"` — fetch succeeded but some records were skipped or malformed; `items` contains what did parse.
- `status: "failed"` — the fetch itself failed; `items` is empty.

A collector must never raise an uncaught exception to the pipeline runner. Every failure mode must be expressed as a structured result and error message.

## 4. Error Handling

- Distinguish transient errors (timeouts, 503, rate-limits) from permanent ones (404, structure change, auth failure).
- Never let one malformed item abort the whole fetch; skip it, record it in `errors`, and continue.

## 5. Logging

- `INFO` on task start and task end.
- `WARNING` for item-level parse failures contributing to a partial result.
- `ERROR` for failed fetches, including the relevant exception or HTTP status.
- Every log line should include `source_id` and the pipeline `run_id` when available.

## 6. Retries

- Retries apply only to transient errors.
- Default policy is up to two retries with exponential backoff starting at five seconds, unless the source configuration overrides it.
- A collector should stop retrying after the configured retry budget and return `status: "failed"`.

## 7. Rate Limiting and Timeouts

- Each collector must respect the configured `max_requests_per_run` and `request_delay_ms` values declared in [sources.yaml](../../config/sources.yaml).
- Network calls must use explicit timeouts and should never wait indefinitely.

## 8. Validation (Minimal Collector-Level)

A collector performs only minimal validation before returning an item. At minimum, it must be able to populate the required model fields `title`, `url`, `source_id`, and enough context to derive `discovered_date`. Items that fail this bar are not emitted.

## 9. Return Format

Collectors must return the standardized `CollectorResult` shape described above. No collector should return bare lists or source-specific payloads.

## 10. Collector Lifecycle

```
 instantiate(config)
        │
        ▼
   validate_config()
        │
        ▼
   fetch(task) ──────────▶ raw response (HTML/JSON/RSS-XML)
        │
        ▼
   parse(raw response) ──▶ list of Opportunity-shaped dicts
        │
        ▼
   minimal_validate(items)
        │
        ▼
   wrap in CollectorResult
        │
        ▼
   return to pipeline runner
```

- `validate_config()` runs once per collector instantiation and should fail fast when required credentials are missing.
- Collectors should be stateless between runs; durable state belongs in the database or the configuration layer, not in memory.

## 11. Standalone Runnability

Every collector must be runnable in isolation for local debugging and review: `python -m collectors.<name>` with a sample task should print a formatted `CollectorResult`.
