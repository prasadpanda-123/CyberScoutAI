# Phase 11.5 — Opportunity Quality Intelligence & Relevance Engine Architecture

## 1. Executive Summary & Objective

CyberScout AI is an automated cybersecurity opportunity intelligence engine. Phase 11.5 introduces the **Opportunity Quality Intelligence Engine**, designed to eliminate false positive items (such as IPTV playlists, movie dumps, streaming lists, or commercial spam) and ensure that only highly relevant cybersecurity opportunities reach the database, web dashboard, and email digest.

The system acts like an experienced cybersecurity analyst evaluating ingested metadata across 10 deterministic processing stages.

---

## 2. Architecture Overview

```
Collectors
   │
   ▼
Processing Engine (Cleaning & Normalization)
   │
   ▼
Quality Intelligence Engine (Stage 1 to 10 Evaluation)
   │
   ▼
Ranking Engine (P0 - P3 Priority Assignment)
   │
   ▼
Database Manager (Migration v3 Schema Extension)
   │
   ▼
Email & Web Dashboard Delivery
```

No opportunity bypasses the Quality Intelligence Engine.

---

## 3. Core Modules (`src/intelligence/`)

| Module | Responsibilities |
|---|---|
| `quality_engine.py` | Pipeline master coordinator evaluating 10 processing stages |
| `content_validator.py` | Length checks, required metadata, forbidden patterns, URL structure |
| `topic_analyzer.py` | GitHub repository topic taxonomy analysis (Stage 2) |
| `language_filter.py` | Primary language detection & markup penalties (Stage 3) |
| `keyword_classifier.py` | Cybersecurity term density & weighting (Stage 4) |
| `spam_detector.py` | Blacklist keywords, README url density, auto-generated dumps (Stage 5 & 6) |
| `repository_classifier.py` | Stargazers count, forks, social proof credibility boosts |
| `confidence_score.py` | Composite score synthesis (0-100) combining all factors (Stage 9) |
| `quality_metrics.py` | Aggregated telemetry & performance metrics |
| `quality_rules.py` | Dynamic loader for `config/quality.yaml` rules |
| `exceptions.py` | Custom intelligence exception definitions |

---

## 4. Rejection Diagnosis Codes (Stage 10)

Every rejected opportunity is assigned a clear, human-readable diagnosis reason:
- `BLACKLIST_KEYWORD`
- `PLAYLIST_DETECTED`
- `MEDIA_REPOSITORY`
- `SPAM`
- `LOW_CONFIDENCE`
- `NO_SECURITY_KEYWORDS`
- `INVALID_CONTENT`
- `INVALID_TOPIC`
- `INVALID_LANGUAGE`
- `DUPLICATE`

---

## 5. Database Schema Extension (Migration v3)

Extends `Opportunities` table with:
- `confidence_score` (`REAL DEFAULT 0.0`)
- `quality_score` (`REAL DEFAULT 0.0`)
- `is_rejected` (`INTEGER DEFAULT 0`)
- `rejection_reason` (`TEXT`)
- `quality_flags` (`TEXT`)
- `topic_score` (`REAL DEFAULT 0.0`)
- `keyword_score` (`REAL DEFAULT 0.0`)
- `spam_score` (`REAL DEFAULT 0.0`)

---

## 6. Verification & Telemetry

- Run CLI check: `python main.py --quality-test`
- Run CLI report: `python main.py --quality-report`
- View Dashboard: `http://127.0.0.1:5000/quality`
