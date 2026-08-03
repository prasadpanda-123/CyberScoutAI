# Phase 2 — Search Intelligence Layer Specification

## 1. Architecture Overview

The **Search Intelligence Layer** is responsible for deciding **WHAT** to search, **WHERE** to search, and **HOW** to search. It does NOT make network requests or scrape web pages. Its primary output is a structured, source-mapped `SearchPlan` containing validated `SearchTask` definitions ready for Phase 3 Collectors.

```text
+-----------------------------------------------------------------------+
|                       CONFIG (YAML Driven)                            |
|  keywords.yaml | synonyms.yaml | search_templates.yaml | sources.yaml |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                    SEARCH INTELLIGENCE ENGINE                         |
|                                                                       |
|   +------------------+         +-----------------------+              |
|   |  KeywordEngine   |         | SearchTemplateEngine  |              |
|   +------------------+         +-----------------------+              |
|            |                               |                          |
|            +---------------+---------------+                          |
|                            |                                          |
|                            v                                          |
|                  +--------------------+                               |
|                  |   QueryBuilder     |                               |
|                  +--------------------+                               |
|                            |                                          |
|                            v                                          |
|                  +--------------------+                               |
|                  |  SourceRegistry    |                               |
|                  +--------------------+                               |
|                            |                                          |
|                            v                                          |
|                  +--------------------+                               |
|                  |   SearchPlanner    |                               |
|                  +--------------------+                               |
|                            |                                          |
|                            v                                          |
|                  +--------------------+                               |
|                  |   QueryValidator   |                               |
|                  +--------------------+                               |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                        OUTPUT: SearchPlan                             |
|        List[SearchTask(source_id, query_text, target_url, ...)]       |
+-----------------------------------------------------------------------+
                                   |
                                   v
                      (Future Phase 3 Collectors)
```

---

## 2. ASCII Data Flow & Sequence Diagram

```text
[ User / Scheduler ]
        |
        | 1. create_search_plan(categories=['internship', 'ctf'])
        v
 [ SearchPlanner ]
        |
        | 2. get_keywords_by_category('internship') + expand_keyword()
        v
 [ KeywordEngine ] --------------------> (Reads keywords.yaml & synonyms.yaml)
        |
        | 3. render_queries(keyword, category='internship')
        v
 [ SearchTemplateEngine ] -------------> (Reads search_templates.yaml)
        |
        | 4. generate_queries()
        v
 [ QueryBuilder ] ---------------------> Returns List[SearchQuery]
        |
        | 5. get_sources_for_category('internship')
        v
 [ SourceRegistry ] -------------------> (Reads source_capabilities.yaml)
        |
        | 6. Map queries to sources & format URLs
        v
 [ SearchPlanner ]
        |
        | 7. validate_plan(plan)
        v
 [ QueryValidator ] -------------------> Checks empty text, unrendered templates, dupes
        |
        | 8. Return validated SearchPlan
        v
[ SearchPlan ] (Consumed by Phase 3 Collectors)
```

---

## 3. Module Responsibilities

1. **`KeywordEngine`** (`keyword_engine.py`): Loads keyword categories and synonym dictionaries. Expands base keywords into full synonym sets.
2. **`SearchTemplateEngine`** (`template_engine.py`): Loads YAML query templates (e.g. `{keyword} internship`, `{keyword} ctf`) and renders keyword-template combinations.
3. **`SourceRegistry`** (`source_registry.py`): Central registry of target sources, capabilities (`supports_search`, `supports_api`, `supports_rss`), rate limits, and preferred collectors.
4. **`QueryBuilder`** (`query_builder.py`): Combines `KeywordEngine` and `SearchTemplateEngine` to construct dynamic, unhardcoded `SearchQuery` objects.
5. **`QueryValidator`** (`query_validator.py`): Ensures generated plans have no empty queries, unrendered `{keyword}` placeholders, duplicate tasks, or unsupported sources.
6. **`SearchPlanner`** (`search_planner.py`): Master orchestrator creating source-mapped `SearchPlan` objects.
7. **`planner_models.py`**: Typed dataclasses (`SearchTemplate`, `SearchTask`, `SearchPlan`, `SearchResultMetadata`, `SearchValidationResult`).

---

## 4. Integration Contract with Phase 3 Collectors

Phase 3 Collectors consume `SearchTask` instances from `SearchPlan.tasks`:

```python
for task in plan.tasks:
    collector_cls = get_collector_for_name(task.metadata["preferred_collector"])
    collector = collector_cls(source_id=task.source_id)
    raw_results = collector.collect(task)
```
