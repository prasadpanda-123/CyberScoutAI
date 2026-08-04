# Freshness & Decay Engine Specification (`FRESHNESS_ENGINE.md`)

## Overview

The **Freshness Engine** (`freshness_analyzer.py`) computes publication decay, calculates days remaining until deadlines, and automatically archives stale or expired opportunities.

---

## Status Classification

- **Fresh**: Published within 30 days and deadline > 5 days remaining. (`freshness_score: 80–100%`)
- **Aging**: Published 30–60 days ago. (`freshness_score: 40–79%`)
- **Expiring Soon**: Deadline within 5 days.
- **Expired**: Deadline passed or age exceeds `archive_after_days` (default 60 days). (`freshness_score: 0–10%`)

Expired opportunities are automatically set to `expired = 1` and `archived = 1` to ensure they never appear in email digests or active listings.
