# Phase 11.5 — Opportunity Quality Intelligence & Content Filtering Architecture

## Executive Summary

Phase 11.5 implements a multi-stage **Quality Intelligence Engine** for CyberScout AI to eliminate false positives, filter spam, classify cybersecurity relevance, and compute multidimensional quality and confidence scores for ingested opportunities before indexing or dispatching notifications.

---

## Key Achievements & Implementation Highlights

### 1. Database Schema Extension (Migration v3)
- Created **Migration v3** in `src/database/migrations.py` adding 8 dedicated intelligence columns to the `Opportunities` table:
  - `confidence_score` (`REAL DEFAULT 0.0`): Aggregated multi-factor confidence rating (0-100).
  - `quality_score` (`REAL DEFAULT 0.0`): Content completeness and structural richness rating (0-100).
  - `is_rejected` (`INTEGER DEFAULT 0`): Boolean flag indicating rejection status.
  - `rejection_reason` (`TEXT`): Granular rejection diagnosis.
  - `quality_flags` (`TEXT`): Comma-separated quality & language classification flags.
  - `topic_score` (`REAL DEFAULT 0.0`): Domain topic alignment rating.
  - `keyword_score` (`REAL DEFAULT 0.0`): Cybersecurity keyword density rating.
  - `spam_score` (`REAL DEFAULT 0.0`): Calculated spam risk factor.

### 2. Modular Intelligence Component Architecture (`src/intelligence/`)
- **`QualityEngine` (`src/intelligence/quality_engine.py`)**: Master pipeline orchestrator coordinating content validation, keyword classification, topic analysis, spam detection, language filtering, repository classification, and score synthesis.
- **`ConfidenceScoreCalculator` (`src/intelligence/confidence_score.py`)**: Computes confidence scores combining source trust, keyword relevance, topic match, structural quality, and spam penalty.
- **`ContentValidator` (`src/intelligence/content_validator.py`)**: Validates text length, required metadata, forbidden terms, and structural integrity.
- **`KeywordClassifier` (`src/intelligence/keyword_classifier.py`)**: Evaluates primary, secondary, and negative keyword occurrences with weighting.
- **`SpamDetector` (`src/intelligence/spam_detector.py`)**: Detects clickbait, promotional spam, commercial sales, and repetitive keyphrases.
- **`LanguageFilter` (`src/intelligence/language_filter.py`)**: Detects non-English content and language quality indicators.
- **`TopicAnalyzer` (`src/intelligence/topic_analyzer.py`)**: Classifies domain focus (Security Advisory, Vulnerability, CTF, Career/Internship, Research Paper).
- **`RepositoryClassifier` (`src/intelligence/repository_classifier.py`)**: Evaluates GitHub repository quality (stars, description, activity).

### 3. CLI Quality Diagnostics Suite
Added CLI flags to `src/main.py`:
- `--quality-report` / `--quality-stats`: Displays aggregated quality metrics, acceptance rates, and top rejection reasons.
- `--quality-check`: Evaluates active opportunities in the database against the Quality Engine.
- `--quality-test`: Executes a test evaluation of a sample opportunity.
- `--rejected`: Lists recently rejected opportunities with diagnosis.

### 4. Web Dashboard Control Center Integration (`/quality`)
- Added `/quality` route (`dashboard/routes/quality.py`) and visual report template (`dashboard/templates/quality.html`).
- Added Quality Intelligence link in `sidebar.html`.

---

## Verification & Test Results

```bash
pytest
```

- **Total Unit Tests Executed**: 222
- **Pass Rate**: 100% (222 passed, 0 failed, 0 skipped)
- **Execution Time**: ~14.8 seconds

---

## Updated CLI Documentation

Generated updated CLI documentation reference files via `python src/main.py --generate-command-docs`:
- `commands.txt`
- `commands.md`
