# Phase 11 — Web Dashboard & Control Center Specification

**Version:** v1.1.0  
**Author:** Lead Software Architect, Senior Flask Developer, UI/UX Engineer  
**Status:** Released

---

## 1. Architecture & Presentation Isolation

The Web Dashboard is built as a pure presentation layer (`dashboard/`) over the existing CyberScout AI v1.0.0 backend architecture.

```text
+-------------------------------------------------------------------------------+
|                       WEB DASHBOARD PRESENTATION LAYER                        |
|                                                                               |
|  [ Web Browser ]                                                              |
|        │                                                                      |
|        ▼                                                                      |
|  [ Flask Application Factory (dashboard/app.py) ]                             |
|        ├─ Blueprints: dashboard, opportunities, analytics, collectors,        |
|        │  scheduler, notifications, knowledge, config, logs, health, system   |
|        └─ REST API Blueprint: /api/*                                          |
|        │                                                                      |
|        ▼                                                                      |
|  [ Dashboard Service Layer (dashboard/services/) ]                            |
|        ├─ DashboardService    ──> Queries DatabaseManager & Repositories     |
|        ├─ StatisticsService   ──> Aggregates category & priority counts        |
|        ├─ AnalyticsService    ──> Calculates growth & keyword frequencies      |
|        └─ APIService          ──> Invokes AutomationEngine & EmailClient       |
|        │                                                                      |
|        ▼                                                                      |
|  [ Existing Backend Core (src/) ]                                             |
|        SQLite Database, Repositories, Scheduler, Notifier, Collectors         |
+-------------------------------------------------------------------------------+
```

---

## 2. Page Navigation Structure (11 HTML Views)

1. **Dashboard (`/`)**: High-level Executive Control Center with KPI cards, Chart.js trends, category doughnut chart, and quick scan triggers.
2. **Opportunities (`/opportunities`)**: Filterable table view supporting category filtering, text search, and CSV/JSON data export.
3. **Analytics (`/analytics`)**: Historical growth charts, provider comparison metrics, and keyword frequency counts.
4. **Collectors (`/collectors`)**: Collector status overview cards showing yield counts and status toggle triggers.
5. **Scheduler (`/scheduler`)**: Scheduler daemon control center (Resume, Pause, Restart).
6. **Notifications (`/notifications`)**: Email delivery history and HTML digest template preview.
7. **Knowledge Base (`/knowledge`)**: Record metrics, archive stats, and top intelligence source rankings.
8. **Configuration (`/configuration`)**: Live YAML configuration file editor for `settings.yaml`, `sources.yaml`, `scheduler.yaml`, etc.
9. **Logs (`/logs`)**: Live application log viewer with level filters (INFO, WARNING, ERROR, DEBUG).
10. **Health (`/health`)**: Visual system health diagnostic dashboard.
11. **System Info (`/system`)**: Environment specifications (Python, SQLite, OS, Uptime).

---

## 3. UI Design Tokens & Theme

- **Background Dark**: `#0D1117`
- **Card Containers**: `#161B22`
- **Borders**: `#30363D`
- **Primary Accent**: `#58A6FF`
- **Success Accent**: `#3FB950`
- **Warning Accent**: `#D29922`
- **Danger Accent**: `#F85149`
