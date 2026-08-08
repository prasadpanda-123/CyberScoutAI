# CyberScout AI

```text
  ____ _   _ ____  _____ ____  ____   ____ ___  _   _ _____   _    ___ 
 / ___| | | | __ )| ____|  _ \/ ___| / ___/ _ \| | | |_   _| / \  |_ _|
| |   | | | |  _ \|  _| | |_) \___ \| |  | | | | | | | | |  / _ \  | | 
| |___| |_| | |_) | |___|  _ < ___) | |__| |_| | |_| | | | / ___ \ | | 
 \____|\___/|____/|_____|_| \_\____/ \____\___/ \___/  |_|/_/   \_\___|
```

> **Never Miss a Cybersecurity Opportunity Again.**

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests Passing](https://img.shields.io/badge/tests-131%2F131%20passing-brightgreen.svg)](tests/)
[![Version](https://img.shields.io/badge/version-1.1.1-blue.svg)](CHANGELOG.md)
[![GitHub Stars](https://img.shields.io/badge/stars-★%20placeholder-orange.svg)](#)

CyberScout AI is a 100% free, open-source Cybersecurity Opportunity Intelligence Platform and Control Center. It autonomously scans, aggregates, normalizes, ranks, and delivers high-value cybersecurity opportunities—including internships, jobs, free courses, certifications, scholarships, CTFs, and bug bounties.

---

## 🎯 Architecture Overview

CyberScout AI is built on a strictly decoupled presentation-engine-data architecture:

```text
+-------------------------------------------------------------------------------+
|                           CYBERSCOUT AI ARCHITECTURE                          |
|                                                                               |
|  [ Web Dashboard Presentation Layer (dashboard/) ]                             |
|    Flask 3.1, Bootstrap 5 Dark Theme, Chart.js Analytics, REST API            |
|                                                                               |
|  [ Automation & Scheduler Engine (src/automation/) ]                          |
|    Background Daemon Thread, YAML Interval Triggers, Signal Handlers          |
|                                                                               |
|  [ 6-Stage Intelligence & Processing Pipeline (src/) ]                        |
|    SearchPlanner ➔ Collectors ➔ Processors ➔ Ranking ➔ KB ➔ Notifier         |
|                                                                               |
|  [ PostgreSQL / Supabase Database Storage ]                                   |
|    Schema v2, Transaction Pooler, Foreign Key Enforcement, 12 Core Tables     |
+-------------------------------------------------------------------------------+
```

---

## 📸 Screenshots & Control Center

Explore visual previews in our [Screenshots Gallery](docs/screenshots/README.md).

| Control Center View | Description |
|---|---|
| **Executive Dashboard** | Real-time KPI statistics, opportunity collection trends, category distribution |
| **Opportunities Explorer** | Multi-criteria search table with category filters and keyword search |
| **Analytics & Trends** | Growth timeline metrics, provider comparison, keyword frequencies |
| **Collector Management** | Real-time collector status cards and manual trigger execution |
| **System Health Grid** | Visual health diagnostics matching `python main.py --health` |

---

## 🚀 Quick Start & Installation

### 1. Requirements
- Python 3.12 or higher
- Git

### 2. Setup
```bash
# Clone repository
git clone https://github.com/CyberScoutAI/cyberscout-ai.git
cd CyberScoutAI

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 💻 Operating CyberScout AI

### Web Dashboard & Control Center
Launch the browser control center on `http://127.0.0.1:5000`:
```bash
python main.py --dashboard
```

### Automation Daemon
Run continuous background background scan loops according to `config/scheduler.yaml`:
```bash
python main.py --daemon
```

### CLI Diagnostic Commands
```bash
# Execute single pipeline scan iteration
python main.py --run-once

# Execute single scan in dry-run mode (skip DB writes & emails)
python main.py --run-once --dry-run

# Inspect local .env environment variable configuration status
python main.py --env-status

# Inspect GitHub API token authentication & rate limit status
python main.py --github-status

# Inspect system health diagnostic status
python main.py --health

# Inspect version information
python main.py --version

# Automatically regenerate commands.txt and commands.md CLI reference files
python main.py --generate-command-docs
```

> 📖 **Full CLI Documentation Reference**: See [commands.txt](commands.txt) and [commands.md](commands.md) for a categorized quick reference table and common operational workflow guides.

---

## 🚂 Railway Cloud Deployment Guide

CyberScout AI is fully compatible with [Railway](https://railway.app) for zero-downtime containerized cloud hosting.

### 1. Automatic Environment & Port Detection
When deployed on Railway, the system automatically detects the assigned `PORT` environment variable and launches the continuous Web Dashboard server on `0.0.0.0:${PORT}` instead of exiting CLI startup.

### 2. Operational Modes
- **Local CLI**: `python main.py` (runs initialization pipeline and CLI startup/shutdown).
- **Local Dashboard**: `python main.py --dashboard` (launches Flask control center on `0.0.0.0:5000`).
- **Railway Production Web Server**: Automatically executed via `Procfile` (`web: python main.py` or `gunicorn wsgi:app`).

### 3. Environment Variables & Production Email Setup
Configure the following environment variables in your Render / Cloud Project Settings:
- `PORT` (assigned automatically by cloud platforms)
- `APP_ENV` (set to `production`)
- `SECRET_KEY` (Flask session secret key)
- `GITHUB_TOKEN` (optional: Personal Access Token for GitHub API collector)

#### Production Email Delivery via Brevo REST API (Recommended for Render)
Cloud container environments (such as Render) restrict outbound TCP connections on SMTP ports 587/25. CyberScout AI supports **Brevo REST API over HTTPS (Port 443)** for zero-downtime, non-blocking email delivery:
- `EMAIL_PROVIDER`: Set to `brevo` (Production) or `smtp` (Local dev default)
- `BREVO_API_KEY`: Your Brevo v3 API key (`xkeysib-...`)
- `EMAIL_FROM`: Sender email address verified in Brevo
- `EMAIL_TO`: Recipient email address for intelligence reports

##### Step-by-Step Brevo API Setup for Render:
1. Create a free account at [Brevo (formerly Sendinblue)](https://www.brevo.com/).
2. Navigate to **SMTP & API** -> **API Keys** and click **Generate a new API key**.
3. In your **Render Dashboard** -> **Environment**, add `EMAIL_PROVIDER=brevo` and `BREVO_API_KEY=xkeysib-...`.
4. Click **Save Changes**. Email reports will now be delivered via HTTPS REST API port 443!

### 4. Continuous Health Probes
- `GET /`: Returns HTTP 200 (Dashboard HTML or JSON `{"status": "ok", "application": "CyberScout AI", "version": "1.2.0"}`).
- `GET /health`: Returns HTTP 200 (System Health Dashboard or JSON `{"healthy": true}`).

---

## 🔐 Local Environment Configuration (`.env`)

CyberScout AI automatically manages environment settings using a root-level `.env` file:

1. **Automatic Initialization**: On first startup, if `.env` does not exist, it is automatically generated from `.env.example`.
2. **Manual Configuration**: You can also copy and customize `.env` manually:
```bash
cp .env.example .env
```
3. **Configure Secrets**: Add your credentials to `.env`:
```ini
APP_ENV=development
LOG_LEVEL=INFO
LOG_FILE=cyberscout.log
DATABASE_URL=postgresql://postgres:password@localhost:5432/cyberscout

# Optional GitHub Personal Access Token (5,000 req/hr capacity)
GITHUB_TOKEN=ghp_your_actual_token_here

# Optional SMTP Email Settings
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASSWORD=your_smtp_app_password
RECIPIENT_EMAIL=user@example.com
```
4. **Inspect Environment Status**:
```bash
python main.py --env-status
```
> [!IMPORTANT]
> **Security Guarantee**: The `.env` file is excluded from Git tracking in `.gitignore`. Secrets (`GITHUB_TOKEN`, `SMTP_PASSWORD`) are masked (`[REDACTED]`) in all logs, terminal outputs, and reports.

---

## 📁 Repository Directory Structure

```text
CyberScoutAI/
├── config/                     # YAML Configuration files (settings, sources, keywords, scheduler)
├── dashboard/                  # Presentation Layer (Flask web application, templates, static CSS/JS)
│   ├── app.py                  # Flask application factory
│   ├── routes/                 # 12 Modular Flask Blueprints (dashboard, opportunities, api, etc.)
│   ├── services/               # Presentation service wrappers (DashboardService, APIService)
│   ├── static/                 # Custom dark cybersecurity CSS & JavaScript
│   └── templates/              # 11 Jinja2 HTML templates
├── docs/                       # Comprehensive documentation & engineering audits
│   ├── api/                    # REST API Reference docs
│   ├── audits/                 # System, Performance, Memory, & Security audit reports
│   ├── design/                 # Architecture design specs
│   └── screenshots/            # Control center screenshot gallery
├── src/                        # Core Application Subsystems
│   ├── automation/             # Scheduler daemon & pipeline runner engine
│   ├── collectors/             # Universal collection framework & core collectors
│   ├── core/                   # Bootstrap, logging, health, constants, version
│   ├── database/               # Database connection, migrations, repositories
│   ├── intelligence/           # Search planner, query builder, template engine
│   ├── models/                 # Canonical Opportunity data models & enums
│   ├── notifier/               # Email client, HTML Jinja2 renderer, SMTP sender
│   └── processors/             # Processing pipeline (cleaning, deduplication, quality check)
├── tests/                      # Automated Test Suite (131/131 passing)
│   └── unit/                   # Unit, resilience, memory leak, security, & route tests
├── main.py                     # Primary CLI entry point
├── requirements.txt            # Dependency requirements
├── LICENSE                     # MIT License
└── README.md                   # Project documentation
```

---

## ❓ FAQ & Troubleshooting

<details>
<summary><strong>Is CyberScout AI completely free?</strong></summary>
Yes! CyberScout AI is 100% free and open-source under the MIT license. It uses zero paid APIs, cloud services, or commercial scraping platforms.
</details>

<details>
<summary><strong>How does duplicate detection work?</strong></summary>
CyberScout AI computes SHA-256 hashes of canonical URLs and evaluates title similarity using a dedicated <code>DeduplicatorProcessor</code> with 100% precision.
</details>

---

## 🗺️ Project Roadmap

See our full [ROADMAP.md](ROADMAP.md) for future vision including:
- [x] Phase 1–10: Core Foundation, Search Intelligence, Collectors, Processors, KB, Notifier, Hardening
- [x] Phase 11: Web Dashboard & Control Center (v1.1.0)
- [ ] Phase 12: Plugin Extension Framework
- [ ] Phase 13: Containerized Docker Deployment

---

## 🤝 Contributing

Contributions are welcome! Please review our [CONTRIBUTING.md](CONTRIBUTING.md) guide and adhere to our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## 📄 License

CyberScout AI is licensed under the [MIT License](LICENSE).
