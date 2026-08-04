# Quality Intelligence 10-Stage Pipeline Architecture

This document describes the sequential execution of the 10 quality evaluation stages in `QualityEngine.evaluate_opportunity()`.

---

## Pipeline Execution Stages

```
   Raw Item
      │
[Stage 1: Basic Validation] ──(Fail)──► Reject (INVALID_CONTENT)
      │
[Stage 2: Topic Analysis] ────(Fail)──► Reject (INVALID_TOPIC)
      │
[Stage 3: Language Analysis] ─(Flag)──► Apply Penalty
      │
[Stage 4: Keyword Search] ────(Score)─► Accumulate Weight
      │
[Stage 5: Blacklist Check] ──(Match)─► Reject (BLACKLIST_KEYWORD)
      │
[Stage 6: README Analyzer] ───(Fail)──► Reject (SPAM / PLAYLIST_DETECTED)
      │
[Stage 7: Content Detection] ─(Type)──► Assign Classification
      │
[Stage 8: Duplicate Check] ──(Match)─► Reject (DUPLICATE)
      │
[Stage 9: Confidence Score] ──(<50)───► Reject (LOW_CONFIDENCE)
      │
[Stage 10: Explainability] ───(Pass)──► Index & Rank
```

---

## Detailed Stage Functions

### Stage 1: Basic Validation (`content_validator.py`)
- Asserts title presence (min 5 chars), description presence (min 20 chars), and valid URL format.

### Stage 2: Repository Topic Analysis (`topic_analyzer.py`)
- Evaluates repository topic tags against approved cybersecurity taxonomy.

### Stage 3: Repository Language Analysis (`language_filter.py`)
- Evaluates primary repository language. Penalizes non-code markup-only repositories.

### Stage 4: Keyword Intelligence (`keyword_classifier.py`)
- Scans title, description, and repository tags for cybersecurity terms.

### Stage 5: Blacklist Engine (`spam_detector.py`)
- Fast-path regex and keyword match for forbidden terms (`iptv`, `m3u`, `crack`, `torrent`). Hard rejection.

### Stage 6: README Analyzer (`spam_detector.py`)
- Inspects README link density, image ratio, line repetition, and playlist markers (`#EXTM3U`).

### Stage 7: Content Type Detection (`quality_engine.py`)
- Classifies opportunity type (RSS, GitHub Repository, CTF, Blog, Hackathon, Course).

### Stage 8: Duplicate Detection (`deduplicator.py`)
- Hashes normalized URLs and calculates title string similarity.

### Stage 9: Confidence Score (`confidence_score.py`)
- Synthesizes composite rating (0-100). Rejects items scoring below `minimum_confidence` (default 50.0).

### Stage 10: Explainability (`quality_engine.py`)
- Attaches final quality flags and human-readable `rejection_reason` string.
