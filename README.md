# CyberScout AI

> **Tagline:** Never Miss a Cybersecurity Opportunity Again.

CyberScout AI is an open-source Cybersecurity Opportunity Intelligence Platform designed to automatically discover, normalize, rank, and report high-value cybersecurity opportunities—including internships, jobs, free courses, certifications, scholarships, hackathons, CTFs, security tools, and news.

---

## 🎯 Architecture Overview

CyberScout AI operates as a modular knowledge pipeline:

```
Internet ➔ Search Intelligence ➔ Collectors ➔ Processors ➔ Ranking ➔ SQLite ➔ HTML Email
```

- **Separation of Concerns:** Each layer has exactly one responsibility.
- **Data Model:** The `Opportunity` object is the single source of truth across all modules.
- **Zero Cost Cloud Dependency:** Built using Python 3.12+, Requests, Playwright, BeautifulSoup, PyYAML, and SQLite.

---

## 💻 Command Line Interface (CLI)

CyberScout AI includes built-in diagnostic and health management CLI commands:

```bash
# View Version & Build Information
python main.py --version

# Run System Health Checks
python main.py --health

# Verify Configuration Validity
python main.py --config-check

# Verify Database Connectivity & Schema Integrity
python main.py --db-check

# Run Default Application Bootstrap & Shutdown
python main.py

# Display Help
python main.py --help
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.12 or higher

### 2. Installation
```bash
# Clone repository
git clone https://github.com/CyberScoutAI/cyberscout-ai.git
cd CyberScoutAI

# Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Diagnostics
```bash
python main.py --health
```

Expected Output:
```json
{
  "overall_status": "HEALTHY",
  "healthy": true,
  "checks": [
    {
      "component": "configuration",
      "status": true,
      "message": "Configuration loaded and validated.",
      "details": {
        "app_env": "development",
        "db_name": "cyberscout.db"
      }
    },
    {
      "component": "database",
      "status": true,
      "message": "Database healthy.",
      "details": {
        "ping": true,
        "integrity": true,
        "schema_version": 1,
        "table_count": 8
      }
    },
    {
      "component": "directories",
      "status": true,
      "message": "All runtime directories verified.",
      "details": {
        "verified_count": 3,
        "failed": []
      }
    }
  ]
}
```

---

## 📁 Repository Structure

```
CyberScoutAI/
├── config/             # YAML configuration files (sources, keywords, schedule, weights)
├── data/               # SQLite database storage (cyberscout.db) & backups
├── docs/               # Architecture documents and Phase 0/0.5 specifications
├── logs/               # Rotating application log files
├── reports/            # Output email HTML and audit summaries
├── src/
│   ├── collectors/     # Abstract collector contracts & concrete collectors (Phase 3)
│   ├── core/           # Config, logging, version, context, health, bootstrap
│   ├── database/       # SQLite manager, repositories, migrations, seed, backups
│   ├── intelligence/   # Keyword taxonomy & search query builder
│   ├── models/         # Canonical Opportunity dataclass & authoritative Enums
│   ├── notifier/       # Email template rendering and SMTP delivery (Phase 7)
│   ├── processors/     # Validation, cleaning, normalization, dedup contracts (Phase 4-5)
│   ├── scheduler/      # Pluggable job scheduler, event bus, metrics, retry backoff
│   ├── services/       # Core service contracts
│   ├── utils/          # Helper utilities (date, string, validation, path, file I/O)
│   └── main.py         # Main CLI entry point
├── tests/              # Automated unit and smoke tests
├── .env.example        # Environment variable template
├── main.py             # Root CLI execution entry point
├── pyproject.toml      # Project configuration and metadata
├── README.md           # Project documentation
└── requirements.txt    # Production & development dependencies
```

---

## 📄 License

Distributed under the MIT License.
