"""
Main CLI entry point for CyberScout AI.

Handles command-line flags (--version, --health, --config-check, --db-check)
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

    # Default execution: run full application bootstrap and graceful shutdown
    app = CyberScoutApp()
    try:
        app.startup()
        # Infrastructure integration verified; pipeline execution will hook here in future phases.
        app.shutdown()
        return 0
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
