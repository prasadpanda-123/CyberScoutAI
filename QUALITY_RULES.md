# Quality Intelligence Rules & Weighted Scoring Specification

This document details the exact rule definitions, weighted 100-point scoring algorithm, keyword dictionaries, blacklists, and topic taxonomies used by the Quality Intelligence Engine (`src/intelligence/`).

---

## 1. 100-Point Weighted Scoring Algorithm

Confidence scores are calculated independently across 7 distinct metadata components (Maximum Score: 100):

| Component | Max Points | Description |
| :--- | :--- | :--- |
| **Repository Name / Title** | 20 pts | Cybersecurity vocabulary matched in repository name or title |
| **Description** | 20 pts | Cybersecurity vocabulary matched in description or homepage summary |
| **GitHub Topics** | 20 pts | Approved cybersecurity topics matched in repository topics list |
| **README Content** | 15 pts | Cybersecurity terms in README (or graceful fallback if uncollected) |
| **Popularity** | 10 pts | Community adoption proof based on stars, forks, watchers, contributors |
| **Freshness** | 10 pts | Recent activity timestamps (`pushed_at`, `updated_at`, `last_commit`, `archived`) |
| **Language Relevance** | 5 pts | Primary programming language suitability (Python, Go, C, Rust, etc.) |

---

## 2. 4-Tier Decision Matrix & Threshold Tuning

Evaluation results map to configurable decision tiers in `config/quality.yaml`:

- **80 – 100**: `ACCEPTED` (High Confidence)
- **60 – 79**: `ACCEPTED` (Medium Confidence)
- **40 – 59**: `ACCEPTED` (Needs Review - Flagged with `NEEDS_REVIEW`)
- **Below 40**: `REJECTED` (`LOW_CONFIDENCE`)

Thresholds are configurable in `config/quality.yaml`:
```yaml
thresholds:
  accept_high_threshold: 80.0
  accept_medium_threshold: 60.0
  needs_review_threshold: 40.0
```

---

## 3. How to Add New Cybersecurity Keywords

To expand the cybersecurity vocabulary:
1. Open [config/quality.yaml](file:///d:/VibeCoding/CyberScout%20AI/CyberScoutAI/config/quality.yaml).
2. Add terms to `preferred_keywords` for title/description/readme matching.
3. Add lowercase/hyphenated topic tags to `approved_topics` for GitHub topic matching.
4. Run `pytest` to verify acceptance.

---

## 4. Blacklist Term Rules (Immediate Discard)

Any opportunity whose title, description, or payload contains blacklisted terms is **immediately rejected** with `rejection_reason = "BLACKLIST_KEYWORD"` or `"PLAYLIST_DETECTED"`:

- **Streaming / IPTV**: `iptv`, `m3u`, `#extm3u`, `playlist`, `movie`, `tv channels`, `streaming channels`, `radio playlist`, `free movies`
- **Entertainment / Gaming**: `anime`, `music`, `spotify`, `netflix`
- **P2P / Piracy**: `torrent`, `warez`, `keygen`, `crack`, `serial`, `telegram dump`, `proxy list`, `ebook collection`
- **Commercial / Spam**: `coupon`, `promo code`, `discount`
- **Adult**: `adult`, `porn`

---

## 5. Diagnostic Log Format

When debug/evaluation occurs, QualityEngine generates structured explainable logs:

```
------------------------------------------------
Repository:
bl4de/security-tools

Keyword Score:
20

Description Score:
18

Topics Score:
20

README Score:
14

Popularity:
10

Freshness:
9

Language:
5

Final Confidence:
96

Decision:
ACCEPTED

Reason:
Repository contains multiple cybersecurity indicators with strong community adoption.
------------------------------------------------
```
