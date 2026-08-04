# Phase 11 — RSS/XML Parser Diagnostics & Recovery Specification

**Version:** v1.1.3  
**Target Release Tag:** `v1.1.3-rss-diagnostics-fix`  
**Status:** Released

---

## 1. Subsystem Architecture

The RSS/XML Parser Diagnostics & Recovery Framework eliminates vague XML parsing errors by capturing detailed provider metadata, HTTP headers, XML error position, payload dumps, and multi-stage recovery attempts.

```text
+-----------------------------------------------------------------------------------+
|               RSS/XML PARSER DIAGNOSTICS & RECOVERY PIPELINE                      |
|                                                                                   |
|  [ RSS Feed Response Payload ]                                                   |
|        │                                                                          |
|        ▼                                                                          |
|  [ Content-Type & Payload Inspector ]                                             |
|        ├─ HTML / Cloudflare Page? ──► Log Warning & Recommend HtmlScraperCollector|
|        ├─ JSON Response Payload? ──► Log Warning & Recommend API / JSON Collector  |
|        └─ Valid XML / Feed Payload ──► Proceed to ElementTree XML Parser          |
|                                                                                   |
|        ▼                                                                          |
|  [ ElementTree XML Parser ]                                                       |
|        ├─ Success ───────────────► Record Feed Success & Return Parsed Items      |
|        └─ ET.ParseError Exception                                                 |
|               │                                                                   |
|               ▼                                                                   |
|  [ RSSDiagnosticsManager (src/core/rss_diagnostics.py) ]                          |
|        ├─ Log Provider ID, Collector, URL, HTTP Status, Line, Col, & Exception    |
|        └─ Save response dump to logs/rss_errors/rss_error_<timestamp>_<source>.xml |
|               │                                                                   |
|               ▼                                                                   |
|  [ Multi-Stage Fallback Recovery ]                                                |
|        ├─ Stage 1: Attempt lxml.etree (recover=True)                              |
|        └─ Stage 2: Entity (& ➔ &amp;) & Control Character Regex Sanitization     |
+-----------------------------------------------------------------------------------+
```

---

## 2. Web Dashboard & CLI Integration

- **Web Dashboard**: Navigation link `/system-diagnostics` rendering `system_diagnostics.html` with healthy vs broken feed cards, response times, and XML error logs.
- **CLI Commands**:
  - `python main.py --validate-rss`: Validates live RSS feeds and checks parsing health.
  - `python main.py --rss-report`: Outputs JSON diagnostic report of feeds and XML errors.
  - `python main.py --repair-config`: Automatically updates `config/sources.yaml` recommendations based on response inspections.
