# Phase 3.2 — Core Collectors Specification

## 1. Architecture Overview

Phase 3.2 implements the first production-ready collectors for CyberScout AI (v0.4.0):
1. **`GenericRSSCollector`**: Collects security advisories, blogs, and news feeds (CISA, OWASP, SANS, Google, Microsoft, Red Hat, Hacker News).
2. **`GithubSearchCollector`**: Collects open-source security tools, repositories, and learning resources via GitHub REST API.
3. **`YouTubeRSSCollector`**: Collects public channel video feeds (IppSec, LiveOverflow, John Hammond, David Bombal) using public RSS without API keys.
4. **`CtftimeCollector`**: Collects upcoming CTF competitions and metadata via CTFtime REST API.

All collectors plug into `CollectorManager`, inherit `BaseCollector`, consume `SearchTask` instances from Phase 2 `SearchPlan`, and normalize raw payloads into canonical `Opportunity` dataclass objects.

```text
+-----------------------------------------------------------------------------------+
|                            COLLECTOR MANAGER                                      |
|                                                                                   |
|  +--------------------+   +---------------------+   +--------------------------+  |
|  | GenericRSSCollector|   |GithubSearchCollector|   |  YouTubeRSSCollector     |  |
|  +--------------------+   +---------------------+   +--------------------------+  |
|            |                         |                            |               |
|            +-------------------------+----------------------------+               |
|                                      |                                            |
|                                      v                                            |
|                        Canonical Opportunity Normalizer                            |
|                                      |                                            |
|                                      v                                            |
|                            CollectorResult(items)                                 |
+-----------------------------------------------------------------------------------+
```

---

## 2. Sequence Diagram

```text
[ SearchPlanner ]               [ CollectorManager ]           [ Concrete Collector ]            [ HTTPClient ]
        |                                |                               |                              |
        | 1. SearchPlan(tasks)           |                               |                              |
        |------------------------------->|                               |                              |
        |                                | 2. execute_task(task)         |                              |
        |                                |------------------------------>|                              |
        |                                |                               | 3. http_client.get(url)      |
        |                                |                               |----------------------------->|
        |                                |                               | 4. (200 OK, raw_payload)     |
        |                                |                               |<-----------------------------|
        |                                |                               |                              |
        |                                |                               | 5. normalize_item()          |
        |                                |                               |    ➔ Opportunity(...)         |
        |                                | 6. CollectorResult(items)     |                              |
        |                                |<------------------------------|                              |
```

---

## 3. Supported Sources & YAML Configurations

- **`config/rss_sources.yaml`**: RSS/Atom feed declarations.
- **`config/github_sources.yaml`**: GitHub search topics and search parameters.
- **`config/youtube_channels.yaml`**: YouTube channel RSS URLs.
- **`config/ctftime.yaml`**: CTFtime API parameters.
- **`config/collector_settings.yaml`**: Settings and optional token overrides (`GITHUB_TOKEN`).

---

## 4. How to Add a New RSS Feed or YouTube Channel

To add a new RSS feed or YouTube channel, edit YAML configuration files without modifying code:

### Add a New RSS Feed in `config/rss_sources.yaml`:
```yaml
feeds:
  my_new_security_blog:
    name: "My Security Blog"
    url: "https://example.com/feed.xml"
    default_category: "blog"
    enabled: true
```

### Add a New YouTube Channel in `config/youtube_channels.yaml`:
```yaml
channels:
  new_creator:
    name: "New Creator"
    channel_id: "UCxxxxxxxxxxxxxx"
    rss_url: "https://www.youtube.com/feeds/videos.xml?channel_id=UCxxxxxxxxxxxxxx"
    default_category: "course"
    enabled: true
```
