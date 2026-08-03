# Architecture Notes

Rationale behind key structural decisions, so future-you (or an open-source contributor) understands *why*, not just *what*.

---

## 1. Why a Layered Pipeline Instead of "One Big Scraper Script"

A monolithic scraper script tightly couples fetching, parsing, filtering, and emailing. Any change to one source breaks unrelated logic, and testing becomes impossible without hitting live websites every time.

The layered design (Collect → Extract → Clean → Categorize → Rank → Store → Notify) means:
- Each layer has **one job** and a **stable input/output contract** (the shared opportunity schema).
- You can test the Processing Engine entirely offline using saved sample JSON from collectors — no network calls needed during development.
- Adding a new source only touches the Collectors layer; nothing downstream changes.

## 2. Why Every Collector Returns the Same Schema

```
{
  id,
  title,
  description,
  url,
  source_id,
  category,
  provider,
  company,
  location,
  remote,
  paid,
  certificate,
  price_raw,
  price_normalized,
  currency,
  deadline,
  published_date,
  discovered_date,
  difficulty,
  tags,
  beginner_friendly,
  score,
  score_breakdown,
  status,
  raw_data
}
```

This is the contract that decouples 15+ independent, unreliable, differently-structured websites from the rest of the system. The Processing Engine only ever needs to understand *one* shape of data, regardless of whether it came from an RSS feed, a REST API, or a scraped HTML table. This is the single most important design decision in the project — protect it. If a source can't populate a field, it should return `null`, never omit the key.

## 3. Why SQLite (Not Postgres/MySQL)

- Zero-config, zero-cost, single file — fits the ₹0 budget and single-developer constraint.
- GitHub Actions runners are ephemeral; a file-based DB can be committed back to the repo (or stored as a workflow artifact/cache) between runs without needing a hosted database server.
- SQLite comfortably handles the expected data volume (hundreds to low thousands of opportunities/month).
- Migration path exists later (Phase 10+) to Postgres if the dashboard needs concurrent multi-user access — not needed for a personal tool.

## 4. Why GitHub Actions Over a Local Cron Job

- Runs even when your laptop is off — a personal cron job requires the machine to be on.
- Free tier (2,000 minutes/month for private repos, unlimited for public repos) comfortably covers a 6-hour-interval job.
- Secrets management (SMTP credentials) is built in and doesn't live in a config file.
- Windows Task Scheduler remains documented as a fallback for offline development/testing.

## 5. Why RSS/APIs Are Prioritized Over HTML Scraping

- RSS and official APIs (GitHub, CTFtime, arXiv) are **contracts** — the site operator has committed to a stable structure. HTML scraping depends on undocumented DOM structure that can silently break.
- Lower legal/ToS risk — RSS is explicitly meant for automated consumption; scraping login-gated or ToS-restricted pages (like LinkedIn) is not.
- Feasibility scoring (see `feasibility_matrix.md`) formalizes this preference so collector-building effort goes to the highest-leverage sources first.

## 6. Why Playwright Only Where Necessary

Playwright (headless browser automation) is heavier (slower runs, more memory, harder to run reliably in CI) than Requests+BeautifulSoup. It's reserved for sources that genuinely require JS rendering (e.g., Internshala's dynamic listings). Every other source should use the lighter Requests+BeautifulSoup stack. This keeps CI runs fast and reduces flakiness.

## 7. Why a Ranking Engine Instead of Emailing Everything

Sending every discovered item would recreate the "noisy scraper" problem the project explicitly wants to avoid. The scoring system (`weights.yaml`) converts raw discoveries into a **curated daily digest**, matching the "intelligence platform" framing rather than "dump of links."

## 8. Why Config-Driven Instead of Hardcoded

`sources.yaml`, `keywords.yaml`, `weights.yaml`, `schedule.yaml` externalize everything that's likely to change (new source added, keyword tweaked, ranking weight adjusted, schedule changed) from code that shouldn't need to change for those edits. This directly supports the "avoid hardcoding" and "separate business logic from scraping logic" principles from the project memory, and it's what makes the project genuinely open-source-friendly — a contributor can add a source by editing YAML, not Python.

## 9. Why Optional Local AI (Ollama) Is Deferred to Later Phases

Local AI (e.g., using a small local model to summarize long descriptions or deduplicate near-identical postings semantically) is valuable but not required for the core value proposition (discovery + ranking + email). Deferring it avoids adding a heavy dependency (a running Ollama instance) to the critical path of early phases, keeping Phases 1–8 lightweight and runnable in CI without a GPU or local model server.

## 10. Module Boundary Summary

| Module | Owns | Does NOT own |
|---|---|---|
| `collectors/` | Fetching + parsing one source into the shared schema | Cleaning, ranking, storage |
| `processors/` | Cleaning, deduping, field normalization | Categorization logic, scoring |
| `intelligence/` | Categorization, tagging, ranking/scoring | Fetching, storage, email rendering |
| `database/` | Schema, persistence, dedup-against-history queries | Business logic |
| `notifier/` | HTML rendering, SMTP sending | Ranking decisions |
| `scheduler/` | Orchestrating the run order, GitHub Actions workflow | Any source-specific logic |
