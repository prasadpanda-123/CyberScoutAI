"""
Main CLI entry point for CyberScout AI.

Handles command-line flags (--version, --health, --config-check, --db-check, --dashboard, --run-once, --daemon, --dry-run, --scheduler-status, --metrics, --email-test)
and manages application startup & shutdown execution.
"""

import argparse
import json
import sys

from src.core.bootstrap import CyberScoutApp
from src.core.config import config
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

    # Default execution
    app = CyberScoutApp()
    try:
        app.startup()
        app.shutdown()
        return 0
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
