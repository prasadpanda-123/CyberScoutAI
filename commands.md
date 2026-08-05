# CyberScout AI — CLI Command Reference & Workflow Guide

> Complete command reference and operational workflow guide for CyberScout AI.

---

## 📌 Quick Reference Table

| Category | Command | Description |
|---|---|---|
| **SYSTEM** | `python main.py` | Run default application bootstrap & shutdown |
| **HELP** | `python main.py --help` | show this help message and exit |
| **VERSION** | `python main.py --version` | Display version, build, and platform information. |
| **SYSTEM** | `python main.py --health` | Run full system health check suite. |
| **SYSTEM** | `python main.py --config-check` | Validate application configuration settings. |
| **CONFIGURATION** | `python main.py --validate-config` | Execute comprehensive YAML configuration and collector mapping audit. |
| **CONFIGURATION** | `python main.py --validate-sources` | Audit provider sources, URL syntax, and capability matrices. |
| **CONFIGURATION** | `python main.py --provider-health` | Run live DNS resolution and reachability checks for all sources. |
| **CONFIGURATION** | `python main.py --config-report` | Generate master configuration audit summary report. |
| **SYSTEM** | `python main.py --validate-rss` | Execute live RSS feed fetching and XML parser validation. |
| **SYSTEM** | `python main.py --rss-report` | Display RSS feed parser diagnostics and error tracking report. |
| **SYSTEM** | `python main.py --repair-config` | Automatically repair source collector recommendations in sources.yaml. |
| **SYSTEM** | `python main.py --db-check` | Verify SQLite database connectivity and schema integrity. |
| **ENVIRONMENT** | `python main.py --env-status` | Display local .env environment variable configuration status. |
| **ENVIRONMENT** | `python main.py --github-status` | Display GitHub API token configuration, authentication state, and rate limits. |
| **DOCUMENTATION** | `python main.py --generate-command-docs` | Automatically generate commands.txt and commands.md CLI documentation files. |
| **DASHBOARD** | `python main.py --dashboard` | Launch CyberScout AI Web Dashboard & Control Center server. |
| **AUTOMATION** | `python main.py --run-once` | Execute one complete scan & pipeline iteration. |
| **AUTOMATION** | `python main.py --daemon` | Run automation engine daemon scheduler loops continuously. |
| **AUTOMATION** | `python main.py --dry-run` | Run full collection and ranking cycle but bypass DB writes and email dispatching. |
| **AUTOMATION** | `python main.py --scheduler-status` | Inspect scheduler state, timezone, next scheduled run, and email status. |
| **SYSTEM** | `python main.py --run-scheduler` | Run daily report scheduler daemon loop in background execution mode. |
| **SYSTEM** | `python main.py --send-report` | Immediately generate and send today's intelligence report, updating scheduler state. |
| **AUTOMATION** | `python main.py --metrics` | Display performance timings for the last completed run. |
| **SYSTEM** | `python main.py --smtp-check` | Execute end-to-end SMTP configuration, DNS resolution, TCP connection, and authentication checks. |
| **EMAIL** | `python main.py --email-test` | Sends a test notification email digest. |
| **SYSTEM** | `python main.py --quality-report` | Display Quality Intelligence Engine acceptance and rejection statistics. |
| **SYSTEM** | `python main.py --quality-check` | Run Quality Intelligence validation against current database opportunities. |
| **SYSTEM** | `python main.py --quality-stats` | Display aggregated quality metrics (confidence distribution, keyword frequency, etc.). |
| **SYSTEM** | `python main.py --quality-test` | Run a test evaluation of a sample opportunity through the Quality Engine. |
| **SYSTEM** | `python main.py --rejected` | List recently rejected opportunities with rejection reasons. |
| **SYSTEM** | `python main.py --provider-report` | Display provider reliability rankings and star ratings. |
| **SYSTEM** | `python main.py --freshness-report` | Display opportunity freshness and decay statistics. |
| **SYSTEM** | `python main.py --trend-report` | Display top growing skills, hiring companies, and trending categories. |
| **SYSTEM** | `python main.py --history-report` | Display historical opportunity lifecycle state transitions. |
| **SYSTEM** | `python main.py --validate-links` | Execute URL link validation diagnostics against active database opportunities. |
| **SYSTEM** | `python main.py --verify-content` | Execute page content verification checks. |
| **SYSTEM** | `python main.py --production-report` | Display comprehensive Production Intelligence master telemetry report. |

---

## 🛠️ Common Operational Workflows

### 1. Fresh Installation Workflow
```bash
# Clone repository & set up environment
git clone https://github.com/CyberScoutAI/cyberscout-ai.git
cd CyberScoutAI
python -m venv venv
source venv/bin/activate  # Or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Verify configuration and database setup
python main.py --env-status
python main.py --health
```

### 2. Daily Pipeline Scan Workflow
```bash
# Run a single collection & ranking iteration
python main.py --run-once

# Run single iteration in dry-run mode (skip DB writes & email)
python main.py --run-once --dry-run
```

### 3. Health & Environment Diagnostic Check
```bash
# Check complete subsystem health
python main.py --health

# Check local .env setup
python main.py --env-status

# Check GitHub API rate limit status
python main.py --github-status
```

### 4. System Debugging Workflow
```bash
# Verify YAML configuration files
python main.py --validate-config

# Audit source definitions & capability mappings
python main.py --validate-sources

# Check provider DNS reachability
python main.py --provider-health
```

### 5. Web Dashboard Launch Workflow
```bash
# Launch browser control center on http://127.0.0.1:5000
python main.py --dashboard
```

### 6. Continuous Automation Daemon
```bash
# Start background scheduler loop
python main.py --daemon
```

### 7. Email Digest Testing Workflow
```bash
# Send test email digest report
python main.py --email-test
```

### 8. CLI Command Documentation Generator
```bash
# Automatically regenerate commands.txt and commands.md
python main.py --generate-command-docs
```
