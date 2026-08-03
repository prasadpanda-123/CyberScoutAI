# Phase 4 — Processing Engine Specification

## 1. Architecture Overview

The **Processing Engine** transforms raw collected `Opportunity` items into clean, normalized, metadata-enriched, classified, tagged, deduplicated, and quality-scored canonical `Opportunity` dataclasses for CyberScout AI (v0.5.0).

```text
+-----------------------------------------------------------------------------------+
|                           PROCESSING PIPELINE                                     |
|                                                                                   |
|  Raw Opportunity                                                                  |
|         │                                                                         |
|         ▼                                                                         |
|  [ ValidatorProcessor ]      ──> Structural validation & URL format check         |
|         │                                                                         |
|         ▼                                                                         |
|  [ CleanerProcessor ]        ──> HTML strip, whitespace, tracking param removal   |
|         │                                                                         |
|         ▼                                                                         |
|  [ NormalizerProcessor ]     ──> ISO 8601 dates, providers, locations, remote     |
|         │                                                                         |
|         ▼                                                                         |
|  [ MetadataExtractorProcessor ] ➔ Company, certificate, paid state, duration      |
|         │                                                                         |
|         ▼                                                                         |
|  [ KeywordExtractorProcessor ]  ➔ Technology synonyms ("Py" ➔ "Python")           |
|         │                                                                         |
|         ▼                                                                         |
|  [ ClassifierProcessor ]     ──> Rule-based multi-label category matching         |
|         │                                                                         |
|         ▼                                                                         |
|  [ DeduplicatorProcessor ]   ──> SHA-256 URL hash & title dedup                   |
|         │                                                                         |
|         ▼                                                                         |
|  [ QualityCheckerProcessor ] ──> Quality score assignment & spam filter           |
|         │                                                                         |
|         ▼                                                                         |
|  Processed Opportunity                                                            |
+-----------------------------------------------------------------------------------+
```

---

## 2. Sequence Diagram

```text
[ Collector / Caller ]          [ ProcessingPipeline ]           [ Processors (Sequential) ]
          |                               |                                  |
          | 1. process_batch(items)       |                                  |
          |------------------------------>|                                  |
          |                               | 2. process(ValidatorProcessor)   |
          |                               |--------------------------------->|
          |                               | 3. process(CleanerProcessor)     |
          |                               |--------------------------------->|
          |                               | 4. process(NormalizerProcessor)  |
          |                               |--------------------------------->|
          |                               | 5. process(MetadataExtractor)    |
          |                               |--------------------------------->|
          |                               | 6. process(KeywordExtractor)     |
          |                               |--------------------------------->|
          |                               | 7. process(ClassifierProcessor)  |
          |                               |--------------------------------->|
          |                               | 8. process(Deduplicator)         |
          |                               |--------------------------------->|
          |                               | 9. process(QualityChecker)       |
          |                               |--------------------------------->|
          |                               |                                  |
          | 10. List[Opportunity] (clean) |                                  |
          |<------------------------------|                                  |
```

---

## 3. Configuration Files

- `config/taxonomy.yaml`: Categories and tags taxonomy definitions.
- `config/classification_rules.yaml`: Keyword rules for category matching.
- `config/quality_rules.yaml`: Quality scoring weights and spam keywords.
- `config/normalization.yaml`: Tracking parameters and location keywords.
- `config/providers.yaml`: Provider alias mappings.
- `config/skills.yaml`: Skill synonym mappings (`Py` ➔ `Python`, `K8s` ➔ `Kubernetes`).

---

## 4. Extension Guide: Creating a Custom Processor

To add a new custom processor to the pipeline:

```python
from src.processors.base import BaseProcessor
from src.models.opportunity import Opportunity
from typing import Optional

class CustomFilterProcessor(BaseProcessor):
    @property
    def processor_name(self) -> str:
        return "Custom Filter Processor"

    def process(self, opportunity: Opportunity) -> Optional[Opportunity]:
        # Perform custom transformation or validation logic
        return opportunity
```
