# Phase 5 — Opportunity Intelligence & Ranking Engine Specification

## 1. Architecture Overview

The **Opportunity Intelligence & Ranking Engine** evaluates, scores, prioritizes, recommends, and ranks clean `Opportunity` objects produced by Phase 4 for CyberScout AI (v0.6.0).

```text
+-----------------------------------------------------------------------------------+
|                         RANKING ENGINE PIPELINE                                  |
|                                                                                   |
|  Clean Opportunity                                                                |
|         │                                                                         |
|         ▼                                                                         |
|  [ ProviderEngine ]           ──> Evaluates provider reputation bonuses           |
|         │                         (CISA, OWASP, SANS: +25; Google, MS, AWS: +20) |
|         ▼                                                                         |
|  [ DeadlineEngine ]           ──> Calculates urgency (URGENT, UPCOMING, EXPIRED) |
|         │                                                                         |
|         ▼                                                                         |
|  [ RuleEngine & ScoreCalculator ] ➔ Weighted rule scoring (Free: +40, Cert: +20) |
|         │                                                                         |
|         ▼                                                                         |
|  [ Quality & ConfidenceEngine ] ──> Data completeness & confidence score %        |
|         │                                                                         |
|         ▼                                                                         |
|  [ PriorityEngine ]           ──> Priority mapping (P0: >=80, P1: >=60, P2, P3)   |
|         │                                                                         |
|         ▼                                                                         |
|  [ RecommendationEngine ]     ──> Human-readable recommendation reason            |
|         │                                                                         |
|         ▼                                                                         |
|  [ DuplicateFilter ]          ──> Preserves highest-scoring unique item          |
|         │                                                                         |
|         ▼                                                                         |
|  Ranked Opportunity (Sorted by Score)                                            |
+-----------------------------------------------------------------------------------+
```

---

## 2. Sequence Diagram

```text
[ Processing Pipeline ]           [ RankingEngine ]             [ Scoring Components ]
           |                              |                                |
           | 1. process_batch(items)      |                                |
           |----------------------------->|                                |
           |                              | 2. ProviderEngine.bonus()      |
           |                              |------------------------------->|
           |                              | 3. DeadlineEngine.evaluate()   |
           |                              |------------------------------->|
           |                              | 4. ScoreCalculator.calculate() |
           |                              |------------------------------->|
           |                              | 5. PriorityEngine.assign()     |
           |                              |------------------------------->|
           |                              | 6. RecommendationEngine()      |
           |                              |------------------------------->|
           |                              | 7. DuplicateFilter.filter()    |
           |                              |------------------------------->|
           |                              |                                |
           | 8. List[Opportunity] (ranked)|                                |
           |<-----------------------------|                                |
```

---

## 3. Priority Levels & Scoring Philosophy

- **P0 (Critical / Immediate Attention):** Score ≥ 80. Free opportunities with certificates, top providers, or urgent deadlines.
- **P1 (High Priority):** Score 60–79. High-reputation courses, tools, and advisories.
- **P2 (Medium Priority):** Score 40–59. Standard learning resources and news.
- **P3 (Low Priority):** Score < 40. Generic or low-metadata items.

---

## 4. Configuration Files

- `config/weights.yaml`: Scoring rule weights and penalties.
- `config/provider_scores.yaml`: Provider reputation bonus scores.
- `config/recommendation_rules.yaml`: Recommendation condition strings.
- `config/priority_levels.yaml`: Score threshold boundaries (P0–P3).
- `config/deadline_rules.yaml`: Days remaining window thresholds.
- `config/quality_weights.yaml`: Quality confidence weights.
