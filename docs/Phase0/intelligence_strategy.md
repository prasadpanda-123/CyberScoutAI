# Opportunity Intelligence Strategy

Covers how raw, cleaned records become **categorized, scored, and curated** opportunities (Phase 5 & 7 logic — documented now so implementation later is mechanical).

---

## 1. Categorization Strategy

Categorization happens **after** cleaning, **before** ranking. Use a two-pass approach:

**Pass 1 — Source-based hint.** Each source in `sources.yaml` declares a `default_category` (e.g., CTFtime → `hackathon`, PortSwigger → `course`). This resolves ~70% of items instantly with zero ambiguity.

**Pass 2 — Keyword-based classification.** For sources that mix categories (e.g., a news RSS feed might occasionally mention a course launch, GitHub search might surface a CTF-writeup repo), match the title+description against the "Opportunity-Type Keywords" section of `keyword_taxonomy.md` using simple weighted keyword scoring — no ML needed for v1. First matching category wins, using this priority order (most specific first): `certification` > `internship` > `hackathon` > `scholarship` > `course` > `workshop` > `webinar` > `conference` > `research_paper` > `github_repository` > `security_tool` > `news` (fallback default).

Multi-category tagging is allowed in the `tags[]` field even when `category` is singular — e.g., an item can have `category: internship` and `tags: [remote, paid, beginner-friendly]`.

## 2. Deduplication Strategy

Two items are considered duplicates if:
- URLs match exactly (after stripping tracking params), OR
- Normalized titles (lowercased, punctuation stripped, whitespace collapsed) have a similarity above a threshold (e.g., Levenshtein ratio ≥ 0.9) **and** they come from the same or related source within a 7-day window.

Dedup happens in two places:
1. **Within a single run** — across collectors (the same TryHackMe room might appear via both the catalog scrape and a news mention).
2. **Against history** — check the `Opportunities` table before inserting; if a duplicate exists, update its `last_seen` timestamp instead of creating a new row, and do not re-email it.

## 3. Ranking Strategy (implements `weights.yaml`)

Ranking is a simple additive scoring model — transparent and debuggable, deliberately not a black-box ML model for v1 (per the "avoid unnecessary complexity" principle). Each field maps to points from `weights.yaml`:

| Signal | Points | Detection Method |
|---|---|---|
| Free | +40 | price field == "free" / "₹0" / null with "free" keyword match |
| Certificate offered | +20 | certificate field == true, or "certificate" keyword in description |
| Remote | +20 | location field == "remote" or keyword match |
| Beginner-friendly | +15 | "beginner" keyword match, or source-level default (e.g., TryHackMe free rooms default beginner-friendly) |
| Recognized provider | +20 | source or company matches Provider Brand Keywords list |
| Deadline soon (≤7 days) | +10 | deadline field within 7 days of today |
| Duplicate | -100 | dedup check (see above) — effectively removes it from consideration |

**Only items scoring above a configurable threshold (default: 50) are included in the daily email.** This threshold lives in `weights.yaml` so it can be tuned without code changes.

## 4. Category Balancing in the Email

Raw score-sorting alone can flood the email with one category (e.g., 15 GitHub tools and 0 internships on a slow-news day). Apply a **soft cap per category** in the email renderer: show top N (default 5) per category, then fill remaining slots with the next-highest-scoring items regardless of category. This keeps the digest genuinely useful rather than monotonous.

## 5. Personalization Hook (Phase 9 groundwork)

Even though adaptive learning is a Phase 9 feature, the schema should support it from day one:
- `EmailHistory` table logs every item ever sent, with a `sent_at` timestamp.
- `Preferences` table can store manually-set keyword boosts (e.g., "always boost OSINT +10") which Phase 9 can later populate automatically based on click-through data (if link tracking is added) or manual thumbs-up/down feedback.

## 6. Explainability

Every emailed item should retain its computed sub-scores (not just the total) in the database, so the email (or future dashboard) can optionally show *why* something ranked highly — e.g., "Free (+40), Certificate (+20), Deadline in 3 days (+10) = 70". This is cheap to implement now (store a JSON breakdown alongside the total score) and valuable for debugging ranking behavior later.
