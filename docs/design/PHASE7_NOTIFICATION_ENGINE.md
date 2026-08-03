# Phase 7 — Notification Engine Specification

## 1. Architecture Overview

The **Notification Engine** (`src/notifier/`) compiles daily opportunity digests, runs statistics summaries, maps layouts to responsive HTML components, and delivers reports via SMTP.

```text
+-----------------------------------------------------------------------------------+
|                           NOTIFICATION ENGINE PIPELINE                            |
|                                                                                   |
|  [ Database (Knowledge Base) ]                                                    |
|         │                                                                         |
|         ▼                                                                         |
|  [ DigestBuilder ]            ──> Loads active opportunities & groups by category |
|         │                                                                         |
|         ▼                                                                         |
|  [ HTMLRenderer ]             ──> Renders report.html via TemplateLoader          |
|         │                                                                         |
|         ▼                                                                         |
|  [ SMTPSender & retry_smtp ]  ──> Delivers secure email (TLS/SSL) with retries    |
|         │                                                                         |
|         ▼                                                                         |
|  [ HistoryTracker & Metrics ] ──> Updates delivery stats & EmailHistory logs      |
+-----------------------------------------------------------------------------------+
```

---

## 2. Sequence Diagram

```text
[ EmailClient ]              [ DigestBuilder ]            [ HTMLRenderer ]           [ SMTPSender ]
       │                             │                            │                         │
       │ 1. send_daily_digest()      │                            │                         │
       |---------------------------->|                            |                         |
       │                             │ 2. Query active & stats    │                         │
       │                             |--------------------------->|                         │
       │                             │ 3. ReportDigest            │                         │
       │                             |<---------------------------|                         │
       │                                                          │                         │
       │ 4. render_report(digest)                                 │                         │
       |--------------------------------------------------------->|                         │
       │                                                          │ 5. Render HTML/Text     │
       │                                                          |<------------------------│
       │                                                                                    │
       │ 6. send_email(html, text)                                                          │
       |----------------------------------------------------------------------------------->|
       │                                                                                    │ 7. Connect & Deliver
       │                                                                                    |------------------->
```

---

## 3. Class Diagram

- **`EmailClient`**: Coordinator orchestrator.
- **`DigestBuilder`**: Prepares `ReportDigest` models.
- **`TemplateLoader`**: Loads HTML files securely via Jinja2.
- **`HTMLRenderer`**: Generates HTML markup and plain text copy.
- **`SMTPSender`**: Handles connection sessions and delivery loops.
- **`HistoryTracker`**: Records transaction rows into the DB database.

---

## 4. Configuration parameters

All parameters are configured declaratively in `config/email.yaml`. SMTP credentials are loaded securely from `.env` via `SMTP_USER` and `SMTP_PASSWORD`.
