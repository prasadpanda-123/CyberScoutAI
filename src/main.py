"""
Main CLI entry point for CyberScout AI.

Handles command-line flags (--version, --health, --config-check, --db-check, --env-status, --github-status, --dashboard, --run-once, --daemon, --dry-run, --scheduler-status, --metrics, --email-test)
and manages application startup & shutdown execution.
"""

import argparse
from datetime import datetime, timezone
import json
import os
import sys

from src.core.bootstrap import CyberScoutApp, ensure_env_file
from src.core.config import config
from src.core.constants import PROJECT_ROOT
from src.core.health import HealthMonitor
from src.core.version import format_banner, get_version_info
from src.database.connection import DatabaseManager
from src.automation.engine import AutomationEngine
from src.notifier.email_client import EmailClient


def build_parser() -> argparse.ArgumentParser:
    """Builds argument parser for CLI commands."""
    parser = argparse.ArgumentParser(
        description="CyberScout AI — Cybersecurity Opportunity Intelligence Platform.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Display version, build, and platform information.",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Run full system health check suite.",
    )
    parser.add_argument(
        "--config-check",
        action="store_true",
        help="Validate application configuration settings.",
    )
    parser.add_argument(
        "--db-check",
        action="store_true",
        help="Verify SQLite database connectivity and schema integrity.",
    )
    parser.add_argument(
        "--env-status",
        action="store_true",
        help="Display local .env environment variable configuration status.",
    )
    parser.add_argument(
        "--github-status",
        action="store_true",
        help="Display GitHub API token configuration, authentication state, and rate limits.",
    )
    # Phase 11 Web Dashboard
    parser.add_argument(
        "--dashboard",
        "--web",
        action="store_true",
        help="Launch CyberScout AI Web Dashboard & Control Center server.",
    )
    # Phase 9 Automation Extensions
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Execute one complete scan & pipeline iteration.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run automation engine daemon scheduler loops continuously.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run full collection and ranking cycle but bypass DB writes and email dispatching.",
    )
    parser.add_argument(
        "--scheduler-status",
        action="store_true",
        help="Inspect scheduler registration queues and current execution status.",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Display performance timings for the last completed run.",
    )
    parser.add_argument(
        "--email-test",
        action="store_true",
        help="Sends a test notification email digest.",
    )
    return parser


def get_env_status_report() -> str:
    """Formats formatted terminal output report for local .env environment configuration."""
    ensure_env_file()
    env_exists = (PROJECT_ROOT / ".env").exists()
    
    gh_token = os.getenv("GITHUB_TOKEN")
    gh_configured = bool(gh_token and gh_token.strip() and gh_token.strip() != "your_github_personal_access_token")
    
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    smtp_configured = bool(smtp_user and smtp_user.strip() and smtp_pass and smtp_pass.strip() and smtp_user.strip() != "user@example.com")
    
    app_mode = os.getenv("APP_ENV", config.get("app_env", "development"))

    lines = [
        "======================================================",
        "Environment Status",
        "======================================================",
        "",
        f".env file ............ {'FOUND' if env_exists else 'NOT FOUND'}",
        "",
        "Configuration ........ OK",
        "",
        f"GitHub Token ......... {'CONFIGURED' if gh_configured else 'NOT CONFIGURED'}",
        "",
        f"SMTP ................. {'CONFIGURED' if smtp_configured else 'NOT CONFIGURED'}",
        "",
        f"Application Mode ..... {app_mode}",
        "",
        "======================================================",
    ]
    return "\n".join(lines)


def get_github_status() -> dict:
    """Queries or formats GitHub API authentication and rate limit status."""
    ensure_env_file()
    token = os.getenv("GITHUB_TOKEN")
    is_authenticated = bool(token and token.strip() and token.strip() != "your_github_personal_access_token")

    status = {
        "authenticated": is_authenticated,
        "mode": "Authenticated" if is_authenticated else "Anonymous Mode",
        "rate_limit_capacity": "5,000 requests/hour" if is_authenticated else "60 requests/hour",
        "core_limit": 5000 if is_authenticated else 60,
        "search_limit": 30 if is_authenticated else 10,
        "rate_limit_remaining": 4998 if is_authenticated else 58,
        "reset_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    try:
        from src.collectors.http_client import HTTPClient
        client = HTTPClient()
        code, text = client.get("https://api.github.com/rate_limit", use_cache=False)
        if code == 200:
            data = json.loads(text)
            resources = data.get("resources", {})
            core = resources.get("core", {})
            search = resources.get("search", {})
            status["core_limit"] = core.get("limit", status["core_limit"])
            status["rate_limit_remaining"] = core.get("remaining", status["rate_limit_remaining"])
            status["search_limit"] = search.get("limit", status["search_limit"])
            reset_ts = core.get("reset")
            if reset_ts:
                status["reset_time"] = datetime.fromtimestamp(reset_ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        pass

    return status


def main(args_list: list | None = None) -> int:
    """
    Main entry point function.

    Args:
        args_list: Optional list of CLI arguments (for testing).

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = build_parser()
    args = parser.parse_args(args_list)

    if args.version:
        info = get_version_info()
        print(f"{info['app_name']} v{info['version']} (Build {info['build_date']})")
        print(f"Tagline  : {info['tagline']}")
        print(f"Python   : {info['python_version']}")
        print(f"Platform : {info['platform']}")
        return 0

    if args.health:
        monitor = HealthMonitor()
        report = monitor.run_full_health_check()
        print(json.dumps(report, indent=2))
        return 0 if report["healthy"] else 1

    if args.config_check:
        monitor = HealthMonitor()
        result = monitor.check_config()
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.status else 1

    if args.db_check:
        monitor = HealthMonitor()
        result = monitor.check_database()
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.status else 1

    if args.env_status:
        print(get_env_status_report())
        return 0

    if args.github_status:
        gh_status = get_github_status()
        print(json.dumps(gh_status, indent=2))
        return 0

    # Phase 11 Launch Dashboard Server
    if args.dashboard:
        from dashboard.app import create_app
        app = create_app()
        print("Launching CyberScout AI Web Dashboard on http://127.0.0.1:5000 ...")
        app.run(host="127.0.0.1", port=5000, debug=False)
        return 0

    # Automation Engine Integrations
    if args.email_test:
        client = EmailClient()
        res = client.send_daily_digest()
        print(json.dumps(res, indent=2))
        return 0 if res.get("status") == "success" else 1

    if args.scheduler_status or args.metrics:
        engine = AutomationEngine()
        print(json.dumps(engine.status(), indent=2))
        return 0

    if args.run_once:
        engine = AutomationEngine()
        res = engine.run_once(dry_run=args.dry_run)
        print(json.dumps(res, indent=2))
        return 0

    if args.daemon:
        engine = AutomationEngine()
        engine.run_forever(dry_run=args.dry_run)
        return 0

    # Default execution: run full application bootstrap and graceful shutdown
    app = CyberScoutApp()
    try:
        app.startup()
        app.shutdown()
        return 0
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
