# Coding Guidelines

These standards exist to keep a 30+ collector, multi-contributor, open-source-bound codebase maintainable. They're deliberately conservative and boring — this project values readability and predictability over cleverness (per the original project memory).

---

## 1. Python Style

- Follow **PEP 8** as the baseline; enforce with `black` (formatting) and `ruff` or `flake8` (linting) — both free, both easy to run in GitHub Actions as a CI check.
- Use **type hints** on all function signatures (`def clean_title(raw: str) -> str:`). This project's core value is the shared `Opportunity` contract — type hints make that contract checkable, not just documented.
- Prefer `dataclasses` (or `TypedDict` where a plain dict contract is more appropriate, e.g., matching JSON shapes) for the `Opportunity` model over raw untyped dicts once implementation begins — this turns `data_model.md` into something a type checker (`mypy`) can enforce.
- Line length: 100 characters (black default is 88; 100 is a reasonable relaxation for descriptive variable names common in this domain — e.g., `is_recognized_provider`).

## 2. Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Modules/files | `snake_case` | `news_rss.py` |
| Classes | `PascalCase` | `RankingEngine` |
| Functions/variables | `snake_case` | `compute_score()` |
| Constants | `UPPER_SNAKE_CASE` | `DEFAULT_INCLUSION_THRESHOLD` |
| Private (module-internal) helpers | leading underscore | `_strip_tracking_params()` |
| Collector classes | `<Source>Collector` | `GithubCollector`, `CtftimeCollector` |
| Processor classes | `<Stage>` noun | `Validator`, `Cleaner`, `Deduplicator` |

Names should describe **what**, not **how** — `is_free()` not `check_price_field_for_free_keyword()`.

## 3. Function Size

- Target **under 40 lines** per function. If a function is doing "fetch, then parse, then clean," that's three functions, not one — this directly supports the layered pipeline design where each stage's internals stay swappable.
- A function should have **one reason to change** (Single Responsibility, see §9). If you find yourself writing "and" when describing what a function does, split it.

## 4. Class Design

- Classes are used where **state** or **polymorphism** genuinely helps (e.g., every Collector implements a shared abstract interface — see `collector_contract.md`). Don't wrap stateless logic in a class just for organization; a module of plain functions is fine and often clearer.
- Favor **composition over inheritance** beyond the one level of abstract-base-class-to-concrete-collector. Deep inheritance hierarchies are exactly the kind of "unnecessary complexity" the project explicitly wants to avoid.

## 5. Documentation

- Every public function/class gets a docstring: one-line summary, then `Args`/`Returns`/`Raises` as needed (Google-style docstrings).
- Every module (collector, processor) gets a module-level docstring stating which pipeline stage it implements and linking to the relevant architecture contract file in `docs/architecture/` — this keeps code and architecture docs from drifting apart.
- Non-obvious business rules (e.g., a specific dedup threshold) get an inline comment explaining *why* that number, or a pointer to the research doc that justifies it.

## 6. Logging

- Use Python's standard `logging` module, configured once in `utils/logging_setup.py`, never `print()` in library code (only `main.py`/CLI entry points may print directly to stdout).
- Log levels used consistently:
  - `DEBUG` — per-item processing detail (only visible with `--verbose`).
  - `INFO` — stage start/end, counts (e.g., "GithubCollector: fetched 42 items").
  - `WARNING` — recoverable issues (one item failed validation, one collector timed out) — the kind of thing described throughout `pipeline.md`'s error-handling sections.
  - `ERROR` — a stage failed entirely and had to be skipped/isolated.
  - `CRITICAL` — the whole pipeline run must abort (reserved for truly unrecoverable states, e.g., DB file inaccessible).
- Every log line from within a pipeline run includes the `run_id` for traceability (see `pipeline.md`'s cross-cutting concerns).

## 7. Configuration

- **No hardcoded values** for anything that could plausibly change: URLs, keywords, weights, thresholds, schedules all live in `config/*.yaml` (per `architecture_notes.md` §8).
- Secrets (SMTP credentials, GitHub token) load from environment variables (`.env` locally via `python-dotenv`, GitHub Actions secrets in CI) — never committed, never in YAML.
- A single `utils/config_loader.py` is the only module that reads YAML files directly; everything else receives already-parsed config objects. This means a future config format change (e.g., YAML → TOML) touches one file.

## 8. Error Handling

- Follow the isolation principle from `pipeline.md`: **catch narrowly, log clearly, degrade gracefully.** A single collector's `requests.RequestException` should never propagate past that collector's wrapper.
- Never use bare `except:` — always catch specific exception types.
- Custom exception classes for domain-specific failures (`CollectorError`, `ValidationError`) make it possible for the pipeline runner to distinguish "this source is temporarily down" from "this is a programming bug that should actually crash loudly in CI."
- Fail **loud** in tests and CI type-checking; fail **soft** (log + continue) in production runs — the goal is a robust daily email, not a fragile all-or-nothing script.

## 9. SOLID Principles (applied pragmatically, not dogmatically)

- **S — Single Responsibility:** Each collector does one source. Each processor does one pipeline stage. Reinforced directly by the folder structure.
- **O — Open/Closed:** Adding a new source should never require modifying the pipeline runner — only adding a new collector module + a `sources.yaml` entry. Adding a new ranking factor should only require editing `weights.yaml` and (if it's a genuinely new signal type) one function in the Ranking Engine, not rewriting it.
- **L — Liskov Substitution:** Any concrete Collector must be fully substitutable wherever the abstract `BaseCollector` interface is expected — the pipeline runner never checks "is this the GitHub collector, do something special." See `collector_contract.md`.
- **I — Interface Segregation:** The Collector interface should not force a source to implement methods it can't meaningfully support (e.g., a static-catalog collector shouldn't be forced to implement pagination logic it doesn't need — make such methods optional/default no-ops).
- **D — Dependency Inversion:** Processors depend on the abstract `Opportunity` shape, never on any specific collector's internals. The Storage Manager depends on an abstract "list of processed opportunities," never on knowing which collector produced them.

## 10. Testing

- Every processor (Validator, Cleaner, Normalizer, Deduplicator, Classifier, Ranking Engine) gets **unit tests** using fixture data from `tests/fixtures/` — no live network calls in unit tests, ever.
- Every collector gets at least one test using a **saved sample response** (HTML/JSON snapshot) rather than hitting the live site in CI — live-site tests are flaky by nature and would make CI unreliable as source count grows.
- **Integration tests** run the full pipeline against fixture data end-to-end, asserting on final email content/DB state — these catch stage-boundary contract violations.
- Target: every new collector PR must include its fixture + test before merge — this is the primary quality gate for an open-source project accepting community-contributed collectors.

## 11. Project Organization

- One module = one responsibility, mirroring `folder_structure.md`.
- Shared logic used by 2+ collectors (e.g., "parse a generic RSS feed") becomes a reusable base/utility rather than being copy-pasted per collector — this is *why* `news_rss.py` and future YouTube/arXiv RSS collectors should share one generic RSS-parsing collector class, differing only by config.
- Avoid circular imports by respecting the dependency direction implied by the pipeline: `collectors → processors → intelligence → database → notifier`. A processor should never import from `notifier`, for instance.
