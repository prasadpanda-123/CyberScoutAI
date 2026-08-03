# Collector Priority

Build order for Phase 3, derived from `feasibility_matrix.md` scores, source diversity (don't build 5 RSS collectors before any API/HTML collector — you want the shared schema stress-tested against different data shapes early), and category coverage (internships, courses, CTFs, news, tools should all appear in the very first working end-to-end demo).

---

## Sprint 1 — "Prove the pipeline works end-to-end" (build these 3 first)
1. **`collectors/github.py`** — GitHub Search API. Covers: open-source tools, repos. Score 4.75. Validates API-key auth handling + JSON parsing.
2. **`collectors/news_rss.py`** (generic RSS collector, configured for The Hacker News + BleepingComputer) — Covers: news. Score 4.5. Validates the RSS parsing path, reusable for every other RSS source later (YouTube, arXiv, blogs) with just a config change.
3. **`collectors/ctftime.py`** — CTFtime API. Covers: hackathons/CTFs. Score 4.75. Validates date-range/deadline field handling, which is core to the ranking engine's "Deadline Soon" bonus.

**Why these three:** together they exercise all three collection methods (REST API, RSS, and a second REST API with different auth), and cover 3 of the 4 most-requested opportunity categories (tools, news, CTFs) without touching fragile HTML.

## Sprint 2 — "Add the free-course backbone"
4. **`collectors/portswigger.py`** — Static HTML, very stable. Covers: courses/certs.
5. **`collectors/tryhackme.py`** — HTML, public listing page. Covers: courses/certs.
6. **`collectors/hackthebox.py`** — HTML, public catalog. Covers: courses/certs.

## Sprint 3 — "Broaden category coverage"
7. **`collectors/youtube_rss.py`** — Reuses the generic RSS collector pattern from Sprint 1, configured with channel IDs. Covers: tutorials.
8. **`collectors/awesome_lists.py`** — Parses curated GitHub README lists. Covers: tools, repos (secondary source).
9. **`collectors/cisco_netacad.py`** — HTML catalog. Covers: courses/certs.

## Sprint 4 — "Internships & hackathons breadth"
10. **`collectors/unstop.py`** — HTML listing. Covers: hackathons/competitions (India-focused, relevant to your context).
11. **`collectors/devpost.py`** — HTML listing. Covers: hackathons.
12. **`collectors/internshala.py`** — Playwright required (JS-rendered). Covers: internships. Deliberately last among "core" collectors because it's the highest-effort build.

## Deferred / Special Handling
- **LinkedIn** — Do not build a direct scraper (ToS risk, score 2.0). Revisit later via a saved-search email-to-RSS bridge, or skip entirely.
- **arXiv, scholarships, Meetup/OWASP events** — Deferred to Phase 9/10 once the core daily-digest loop is proven and useful.

## Definition of Done for Each Collector
A collector is "done" when:
1. It can run standalone (`python -m collectors.<name>`) and print valid JSON matching the shared schema.
2. It handles "zero results" and "network error" gracefully (returns empty list, logs a warning — never crashes the whole pipeline run).
3. It respects the rate-limit defaults in `search_templates.md`.
4. A sample of its raw output is saved under `tests/fixtures/<name>.json` for offline Processing Engine testing (Phase 4).
