# Phase 3.1 — Universal Collection Framework Specification

## 1. Architecture Overview

The **Universal Collection Framework** provides a specialized, Scrapy-like architecture for CyberScout AI (v0.3.0). It makes writing site-specific collectors effortless by providing built-in HTTP session pooling, automatic User-Agent rotation, per-source rate limiting, SQLite response caching, exponential backoff retries, robots.txt compliance checking, parser helper utilities, and isolated exception management.

```text
+-----------------------------------------------------------------------------------+
|                            COLLECTOR MANAGER                                      |
|                                                                                   |
|  +------------------+     +-------------------+     +-------------------------+   |
|  |  SearchTask      | ──> | CollectorFactory  | ──> | BaseCollector Subclass  |   |
|  +------------------+     +-------------------+     +-------------------------+   |
|                                                                |                  |
|                                                                v                  |
|  +-----------------------------------------------------------------------------+  |
|  |                             SHARED HTTP CLIENT                              |  |
|  |                                                                             |  |
|  |   +---------------+   +---------------+   +-----------------------------+   |  |
|  |   | RateLimiter   |   | RobotsChecker |   | CollectorCache (SQLite)    |   |  |
|  |   +---------------+   +---------------+   +-----------------------------+   |  |
|  |           |                   |                          |                  |  |
|  |           v                   v                          v                  |  |
|  |   +-----------------------------------------------------------------+   |  |
|  |   |                     CollectorRetry Policy                       |   |  |
|  |   +-----------------------------------------------------------------+   |  |
|  |                                   |                                     |  |
|  |                                   v                                     |  |
|  |                       (Target Server / API)                             |  |
|  +-----------------------------------------------------------------------------+  |
|                                      |                                            |
|                                      v                                            |
|  +-----------------------------------------------------------------------------+  |
|  |                         PARSER UTILITIES                                    |  |
|  |        parse_rss_xml_content() | parse_html_content() | parse_json()        |  |
|  +-----------------------------------------------------------------------------+  |
|                                      |                                            |
|                                      v                                            |
|                            OUTPUT: CollectorResult                                |
+-----------------------------------------------------------------------------------+
```

---

## 2. Collector Execution Sequence Diagram

```text
[ CollectorManager ]           [ CollectorFactory ]           [ HTTPClient ]            [ Cache / Limiter ]           [ Target Server ]
         |                              |                           |                            |                           |
         | 1. execute_task(task)        |                           |                            |                           |
         |----------------------------->|                           |                            |                           |
         | 2. instantiate BaseCollector |                           |                            |                           |
         |<-----------------------------|                           |                            |                           |
         |                                                          |                            |                           |
         | 3. collector.collect(task)                               |                            |                           |
         |--------------------------------------------------------->|                            |                           |
         |                              |                           | 4. check cache hit         |                           |
         |                              |                           |--------------------------->|                           |
         |                              |                           | 5. wait(rate_limiter)      |                           |
         |                              |                           |--------------------------->|                           |
         |                              |                           |                                                        |
         |                              |                           | 6. HTTP GET (with retry)                               |
         |                              |                           |------------------------------------------------------->|
         |                              |                           | 7. Raw Response Text                                   |
         |                              |                           |<-------------------------------------------------------|
         |                              |                           |                                                        |
         | 8. CollectorResult(items, status, metrics)               |                                                        |
         |<---------------------------------------------------------|                                                        |
```

---

## 3. Class Responsibilities

1. **`BaseCollector`** (`src/collectors/base.py`): Abstract base class requiring `collector_name`, `initialize()`, `collect(task)`, `validate()`, `normalize()`, and `shutdown()`.
2. **`CollectorManager`** (`src/collectors/manager.py`): Orchestrates task execution with exception isolation (failures never halt the pipeline).
3. **`HTTPClient`** (`src/collectors/http_client.py`): Session-pooled HTTP client with header management, gzip decoding, caching, rate limiting, and retry execution.
4. **`CollectorCache`** (`src/collectors/cache.py`): SQLite-backed response caching with TTL expiration.
5. **`RateLimiter`** (`src/collectors/rate_limiter.py`): Per-source request delay throttling.
6. **`RobotsChecker`** (`src/collectors/robots.py`): Evaluates robots.txt rules before crawling.
7. **`CollectorMetrics`** (`src/collectors/metrics.py`): Measures requests, throughput, latency, and bytes downloaded.
8. **`CollectorResult`** (`src/collectors/result.py`): Standardized output container.

---

## 4. Extension Guide: How to Create a New Collector

To create a new collector in Phase 3.2:

```python
from src.collectors.base import BaseCollector
from src.collectors.result import CollectorResult
from src.collectors.parser_utils import parse_rss_xml_content
from src.intelligence.planner_models import SearchTask

class ExampleRSSCollector(BaseCollector):
    @property
    def collector_name(self) -> str:
        return "Example RSS Collector"

    def collect(self, task: SearchTask) -> CollectorResult:
        # Use shared HTTPClient via context
        status_code, content = self.context.http_client.get(task.target_url)
        raw_items = parse_rss_xml_content(content)
        normalized_items = [self.normalize(item) for item in raw_items]
        
        return CollectorResult(
            source_id=self.source_id,
            status="success" if status_code == 200 else "failed",
            items=normalized_items,
        )
```
