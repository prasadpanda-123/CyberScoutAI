# Folder Structure

## Design Principle
Folder boundaries mirror pipeline-stage boundaries and module-ownership boundaries. If a new file cannot be placed cleanly, that is a signal that the responsibility is not yet well-defined.

```
CyberScoutAI/
├── config/
│   ├── keywords.yaml
│   ├── schedule.yaml
│   ├── settings.yaml
│   ├── sources.yaml
│   └── weights.yaml
├── data/
├── docs/
│   ├── architecture/
│   │   ├── adr/
│   │   ├── collector_contract.md
│   │   ├── collector_health.md
│   │   ├── coding_guidelines.md
│   │   ├── data_model.md
│   │   ├── email_design.md
│   │   ├── enums.md
│   │   ├── folder_structure.md
│   │   ├── pipeline.md
│   │   ├── processor_contract.md
│   │   ├── ranking_algorithm.md
│   │   └── sqlite_schema.md
│   ├── development/
│   │   ├── secrets_management.md
│   │   └── testing_strategy.md
│   ├── Phase0/
│   └── diagrams/
├── logs/
├── reports/
├── scripts/
├── src/
│   ├── collectors/
│   ├── core/
│   ├── database/
│   ├── intelligence/
│   ├── models/
│   ├── notifier/
│   ├── processors/
│   ├── scheduler/
│   ├── services/
│   └── utils/
├── tests/
├── .env.example
├── CONTRIBUTING.md
├── LICENSE
├── pyproject.toml
├── README.md
└── requirements.txt
```

---

## Folder-by-Folder Purpose

| Folder | Purpose | Belongs Here | Does NOT Belong Here |
|---|---|---|---|
| `config/` | All externalized, editable-without-code-changes settings. | YAML files only. | Secrets (those go in `.env` / GitHub Actions secrets, never committed). |
| `collectors/` | Source-specific fetch + parse logic, one module per source (or tightly related family, e.g. all YouTube channels sharing one generic RSS collector). | Network calls, HTML/JSON parsing into the shared `Opportunity` shape. | Cleaning, deduping, ranking, DB writes. |
| `processors/` | Pipeline stages 4–8 (Validation → Categorization) from `pipeline.md`. | Pure functions/classes transforming lists of `Opportunity` dicts. | Anything source-specific; anything that makes network calls. |
| `intelligence/` | The "smart" layers: query construction and scoring. | Search Intelligence logic, Ranking Engine, taxonomy matching helpers. | Fetching, storage, email rendering. |
| `database/` | Everything SQLite-related. | Schema definition, connection handling, the Storage Manager (upsert/query logic), versioned migrations. | Business logic about what makes a "good" opportunity (that's `intelligence/`). |
| `notifier/` | Turning stored data into a sent email. | HTML template rendering, SMTP sending. | Deciding *which* items qualify (that's Ranking's job — Notifier just renders what it's given). |
| `scheduler/` | Orchestration only. | The top-level function that calls each pipeline stage in order, wires error isolation, and the GitHub Actions workflow definition. | Any stage's internal logic. |
| `reports/` | Generated artifacts useful for debugging/audit, kept separate from `logs/` (which is raw text logs) and `data/` (which is the DB). | Rendered email HTML snapshots, per-run JSON summaries. | Anything that needs to be version-controlled long-term (these are mostly git-ignored, with maybe a few committed samples for docs). |
| `dashboard/` | Future (Phase 10) local web UI. | Flask/Streamlit app code, kept isolated so its dependencies don't bloat the core pipeline's `requirements.txt`. | Anything the core pipeline depends on — dashboard is a consumer of the DB, never a dependency of the pipeline. |
| `tests/` | All automated tests, organized by type. | `fixtures/` = saved real (or representative) collector output for offline processor testing without live network calls (this is what makes Phase 4 developable before Phase 3 sources are fully live); `unit/` = per-function tests; `integration/` = full-pipeline-with-mocked-network tests. | Live-network tests that would break CI when a live site changes — those are manual/exploratory only. |
| `logs/` | Runtime log files (rotating, git-ignored). | Structured log output from `logging_setup.py`. | Anything meant to be read as a report (that's `reports/`). |
| `utils/` | Small, dependency-free helper functions shared across multiple layers. | Config loading, logging setup, date parsing helpers, text cleaning helpers. | Anything with pipeline-stage-specific business logic — if a "util" starts encoding opportunity-scoring rules, it belongs in `intelligence/` instead. |
| `data/` | The actual SQLite database file and any other persisted local state. | `cyberscout.db`. | Code. |
| `docs/` | Human-facing docs for contributors/users (as opposed to `research/`, which is architectural design history). | README, CONTRIBUTING, a short ARCHITECTURE.md that summarizes and links into `research/`. | Deep design rationale — that lives in `research/` and is linked from here, not duplicated. |
| `research/` | The permanent design record — this document and its siblings. Kept even after implementation, as the "why" reference for future contributors. | Architecture, contracts, rationale docs (Phase 0/0.5 outputs). | Implementation code. |

## Why `research/` Persists Past Phase 0.5
Many project structures treat planning docs as disposable scaffolding, deleted once code exists. CyberScout AI deliberately keeps `research/` as a permanent part of the repository because:
1. It's the answer to "why does the Ranking Engine weight things this way?" months later.
2. It's what makes the project genuinely approachable for open-source contributors — they can read the architecture before reading code.
3. It's cheap to keep (it's just Markdown) and expensive to lose (re-deriving this reasoning from scratch is real work).

## Scalability Note (30+ collectors, 100+ keywords, plugin architecture)
- `collectors/` scaling to 30+ files is intentional and fine — each is small and independent (per the collector contract). If it gets unwieldy, sub-folder by category (`collectors/courses/`, `collectors/news/`, etc.) is a safe later refactor since nothing outside `collectors/` should import by deep path (registration happens via `sources.yaml` + a factory lookup, not direct imports scattered around the codebase).
- A future **plugin architecture** (community-contributed collectors) fits naturally here: a plugin is just a new module implementing `collector_contract.md`'s interface, registered via config rather than modifying core code.
