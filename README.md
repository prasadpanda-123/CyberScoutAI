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
|  [ SQLite Database Storage (data/cyberscout.db) ]                             |
|    Schema v2, WAL Mode, Foreign Key Enforcement, 12 Core Tables               |
+-------------------------------------------------------------------------------+
```

---

## 📸 Screenshots & Control Center

Explore visual previews in our [Screenshots Gallery](docs/screenshots/README.md).

| Control Center View | Description |
|---|---|
| **Executive Dashboard** | Real-time KPI statistics, opportunity collection trends, category distribution |
| **Opportunities Explorer** | Multi-criteria search table with CSV/JSON exports |
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
```

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
DB_NAME=cyberscout.db

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
