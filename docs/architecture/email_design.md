# Email Design

## Design Goals
- Scannable in under 2 minutes on a phone.
- Category-balanced (per `intelligence_strategy.md` §4 and `ranking_algorithm.md`'s category cap) — never a wall of 20 GitHub repos and nothing else.
- Explainable enough to build trust in the ranking, without being cluttered — no raw `score_breakdown` JSON in the email itself; save that for a future dashboard drill-down.
- Never sends an empty/broken-looking email even on a slow day (per `pipeline.md` §11's zero-items fallback).

---

## Section-by-Section Layout

```
┌─────────────────────────────────────────┐
│  HEADER                                   │
│  CyberScout AI — Daily Report             │
│  <date>                                    │
├─────────────────────────────────────────┤
│  SUMMARY                                   │
│  "X new opportunities found today,        │
│   Y qualified for this digest"             │
├─────────────────────────────────────────┤
│  STATISTICS                                │
│  [Internships: n] [Courses: n]             │
│  [Hackathons: n] [Free: n%] [Remote: n%]  │
├─────────────────────────────────────────┤
│  INTERNSHIPS                               │
│  (top N, category-capped)                 │
├─────────────────────────────────────────┤
│  COURSES & CERTIFICATIONS                  │
│  (top N)                                   │
├─────────────────────────────────────────┤
│  HACKATHONS & CTFs                         │
│  (top N)                                   │
├─────────────────────────────────────────┤
│  SCHOLARSHIPS                              │
│  (top N, if any qualify)                   │
├─────────────────────────────────────────┤
│  DEADLINES THIS WEEK                       │
│  (cross-category, deadline_soon items)     │
├─────────────────────────────────────────┤
│  RECOMMENDED FOR YOU                       │
│  (Phase 9: personalization-weighted pick) │
├─────────────────────────────────────────┤
│  FOOTER                                    │
│  Sources monitored · Unsubscribe/config    │
│  note · Powered by CyberScout AI           │
└─────────────────────────────────────────┘
```

---

## Section Purpose & Content Rules

### Header
- Project name + tagline, report date, and (subtly) the `run_id`'s timestamp so it's clear this is automated and current — builds trust that the automation is actually running, especially useful when you're debugging.

### Summary
- One or two sentences: total items discovered this run vs. how many cleared the inclusion threshold. This number pair is itself a useful health signal — a sudden drop in "discovered" suggests a collector broke; a sudden drop in "qualified" with stable "discovered" suggests a source-quality shift.

### Statistics
- A compact row of counts/percentages: category breakdown, % free, % remote. Gives an at-a-glance shape of the day's opportunities before scrolling into details — helps a time-pressed reader decide whether to read further today.

### Internships / Courses & Certifications / Hackathons & CTFs / Scholarships
- Each is a **category section**, populated only if at least one qualifying item exists in that category (empty categories are omitted entirely, not shown as "no items today" — keeps the email tight).
- Each item within a section shows: title (linked), one-line description, and a small set of **badge-style tags** (Free / Remote / Certificate / Beginner) drawn directly from the boolean fields — not the numeric score, which stays hidden from the email itself per the Design Goals above.
- Items within each section are sorted by `score` descending, capped at `category_cap_per_email` (default 5, per `weights.yaml`).

### Deadlines This Week
- A **cross-category** section pulling any qualifying item (regardless of category) with `deadline` within 7 days, sorted by soonest-first. This deliberately duplicates items that may already appear above — deadline urgency deserves a second, more prominent surfacing rather than being buried in a longer category list.

### Recommended For You
- Reserved/placeholder section for Phase 9 personalization (keyword boosts from `Preferences`). In v1 (before Phase 9 ships), this section is either omitted or shows the single highest-scoring item overall as a simple "top pick" — avoids shipping a fake-personalized section before real personalization logic exists.

### Footer
- Lists which sources were successfully queried this run (transparency — "you're seeing coverage from these N sources today"), a note on how to adjust preferences/config (even if that's currently "edit `config/*.yaml` and re-run," for a single-developer tool), and a CyberScout AI attribution line.

---

## Visual/Format Notes
- Plain, readable HTML — no heavy CSS frameworks (keeps email client compatibility high across Gmail/Outlook rendering quirks). Inline CSS only, per standard HTML-email best practice.
- A **plain-text fallback** version is generated alongside the HTML version (many email clients and accessibility tools rely on this) — the Email Generation stage produces both from the same underlying selected-items data, not by stripping the HTML after the fact.
- Category section headers use consistent, simple visual hierarchy (bold, slightly larger, maybe a single accent color) — avoid heavy imagery/icons that increase email size and can trigger spam filters.

## Zero-Qualifying-Items Fallback
Per `pipeline.md` §11: if no items clear the threshold, send a minimal email: Header + a one-line Summary ("No new opportunities cleared today's quality bar") + Footer (still listing sources queried, so it's clear this was a successful-but-quiet run, not a broken one). This is a deliberate design choice — silence from the automation would be ambiguous between "nothing happened" and "it's broken."
