# Historical Lifecycle Tracking Specification (`HISTORICAL_TRACKING.md`)

## Overview

The **Historical Lifecycle Analyzer** (`historical_analyzer.py`) maintains audit trails of opportunity state transitions in the `historical_changes` database table.

---

## Logged Change Events

- `STATUS_CHANGE`: Active $\rightarrow$ Expired $\rightarrow$ Archived.
- `SCORE_CHANGE`: Priority or quality score adjustments.
- `CATEGORY_CHANGE`: Opportunity re-classification.
- `PROVIDER_CHANGE`: Provider source updates.

Every change entry records `opportunity_id`, `change_type`, `old_value`, `new_value`, and UTC timestamp `recorded_at`.
