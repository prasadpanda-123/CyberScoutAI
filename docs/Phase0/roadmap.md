# CyberScout AI — Project Roadmap

## Purpose
This roadmap sequences the build so that **every phase ships a working, runnable piece of the system**. No phase should leave the project in a broken or purely theoretical state.

## Guiding Rule
> Build the thinnest possible vertical slice first (one source → one email), then widen.

---

## Phase 0 — Research & Planning (this phase)
**Output:** `research/` docs + `config/` YAML skeletons
**Exit criteria:** Every source we plan to collect from is documented with a collection method. No code written yet.

## Phase 1 — Foundation
**Goal:** Repo skeleton, virtual environment, config loader, logging, `.env` handling, SQLite schema created (empty).
**Deliverable:** `python main.py --init` creates the DB and prints "CyberScout initialized."

## Phase 2 — Search Intelligence Layer
**Goal:** A query-builder module that turns `keywords.yaml` + `sources.yaml` into concrete search queries/URLs per source (Google dorks, GitHub search API queries, RSS URLs).
**Deliverable:** `python -m search.build_queries` prints a list of ready-to-fetch queries.

## Phase 3 — Collectors
**Goal:** One collector per source, each returning the shared data schema. Start with the 3 highest-priority, lowest-difficulty sources (see `collector_priority.md`).
**Deliverable:** Each collector runnable standalone: `python -m collectors.github` prints raw JSON results.

## Phase 4 — Processing Engine
**Goal:** Clean, deduplicate, normalize fields (deadline, price, certificate, location, company, duration, coupon).
**Deliverable:** Raw collector output → clean structured records, testable on saved sample data.

## Phase 5 — Opportunity Intelligence
**Goal:** Categorization (internship/course/cert/hackathon/etc.) + tagging with keyword taxonomy.
**Deliverable:** Clean records get a `category` and `tags[]` field.

## Phase 6 — Database
**Goal:** Persist processed + ranked opportunities into SQLite (schema in `database/schema.sql`), with dedup against history.
**Deliverable:** Running the pipeline twice does not duplicate rows.

## Phase 7 — Ranking + Email Engine
**Goal:** Apply `weights.yaml` scoring, select top N, render HTML email, send via SMTP.
**Deliverable:** A real email arrives in your inbox with today's top opportunities.

## Phase 8 — Automation
**Goal:** GitHub Actions workflow (cron every 6h) running collect → process → store → email end-to-end, with secrets for SMTP.
**Deliverable:** Scheduled run works unattended for 3+ consecutive days.

## Phase 9 — Personal Intelligence
**Goal:** Learn from what you click/apply to (via `Preferences` + `EmailHistory` tables) to bias future ranking.
**Deliverable:** Ranking weights adapt slightly based on historical engagement signals you log manually or via tracked links.

## Phase 10 — CyberScout Intelligence OS
**Goal:** Local dashboard (Flask/Streamlit, still free), optional Ollama-based summarization of long descriptions, richer sources (research papers, podcasts).
**Deliverable:** A local web dashboard showing trend charts and searchable historical opportunities.

---

## Suggested Timeline (self-paced student project)
| Phase | Est. Effort |
|---|---|
| 0 | 2–3 days (this) |
| 1 | 1–2 days |
| 2 | 2–3 days |
| 3 | 1 week (3 collectors) |
| 4 | 3–4 days |
| 5 | 3–4 days |
| 6 | 2 days |
| 7 | 3–4 days |
| 8 | 1–2 days |
| 9 | ongoing |
| 10 | ongoing |

## Immediate Next Step After Phase 0
Begin **Phase 1** using the schema implied by `config/sources.yaml` and the DB tables listed in the original project memory (Sources, Opportunities, Keywords, EmailHistory, SearchHistory, Statistics, Preferences).
