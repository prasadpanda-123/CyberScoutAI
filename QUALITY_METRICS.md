# Quality Metrics & Telemetry Specification

This document details the telemetry metrics calculated by `src/intelligence/quality_metrics.py`.

---

## 1. Primary Telemetry Fields

- `total_evaluated`: Total number of opportunities processed by the Quality Engine.
- `total_accepted`: Opportunities meeting minimum confidence and quality thresholds.
- `total_rejected`: Opportunities rejected by any stage.
- `acceptance_rate`: `(total_accepted / total_evaluated) * 100`.
- `average_confidence`: Mean composite confidence score across accepted items.
- `average_quality`: Mean content quality score across accepted items.

---

## 2. Telemetry Methods

```python
from src.intelligence.quality_metrics import QualityMetrics

metrics = QualityMetrics()
metrics.record_evaluation(opportunity, is_accepted=True)
stats = metrics.to_dict()
```

The telemetry dictionary is rendered on the Web Dashboard (`/quality`) and accessible via CLI (`python main.py --quality-stats`).
