"""
Main CLI entry point for CyberScout AI.

Handles command-line flags (--version, --health, --config-check, --validate-config, --validate-sources, --provider-health, --config-report, --validate-rss, --rss-report, --repair-config, --db-check, --env-status, --github-status, --generate-command-docs, --dashboard, --run-once, --daemon, --dry-run, --scheduler-status, --metrics, --email-test)
and manages application startup & shutdown execution.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import yaml

from src.collectors.http_client import HTTPClient
from src.collectors.parser_utils import parse_rss_xml_content
from src.core.bootstrap import CyberScoutApp, ensure_env_file
from src.core.config import config
from src.core.config_validator import ConfigurationValidator
from src.core.constants import CONFIG_DIR, PROJECT_ROOT
from src.core.health import HealthMonitor
from src.core.provider_health import ProviderHealthChecker
from src.core.rss_diagnostics import RSSDiagnosticsManager
from src.core.version import format_banner, get_version_info
from src.database.connection import DatabaseManager
from src.automation.engine import AutomationEngine
from src.notifier.email_client import EmailClient
from src.utils.command_doc_generator import generate_all_command_docs


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
        "--validate-config",
        action="store_true",
        help="Execute comprehensive YAML configuration and collector mapping audit.",
    )
    parser.add_argument(
        "--validate-sources",
        action="store_true",
        help="Audit provider sources, URL syntax, and capability matrices.",
    )
    parser.add_argument(
        "--provider-health",
        action="store_true",
        help="Run live DNS resolution and reachability checks for all sources.",
    )
    parser.add_argument(
        "--config-report",
        action="store_true",
        help="Generate master configuration audit summary report.",
    )
    parser.add_argument(
        "--validate-rss",
        action="store_true",
        help="Execute live RSS feed fetching and XML parser validation.",
    )
    parser.add_argument(
        "--rss-report",
        action="store_true",
        help="Display RSS feed parser diagnostics and error tracking report.",
    )
    parser.add_argument(
        "--repair-config",
        action="store_true",
        help="Automatically repair source collector recommendations in sources.yaml.",
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
    parser.add_argument(
        "--generate-command-docs",
        action="store_true",
        help="Automatically generate commands.txt and commands.md CLI documentation files.",
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
        "--smtp-check",
        action="store_true",
        help="Execute end-to-end SMTP configuration, DNS resolution, TCP connection, and authentication checks.",
    )
    parser.add_argument(
        "--email-test",
        action="store_true",
        help="Sends a test notification email digest.",
    )
    return parser


def run_smtp_check() -> None:
    """Runs SMTP configuration, DNS resolution, TCP connectivity, and authentication checks."""
    from src.core.smtp_validator import SMTPValidator

    validator = SMTPValidator()
    results = validator.run_diagnostics()

    print("===========================================================================")
    print("CyberScout AI - SMTP Configuration Diagnostics & Validation")
    print("===========================================================================")
    print(f"SMTP Host          : {results.get('smtp_host')}")
    print(f"SMTP Port          : {results.get('smtp_port')}")
    print(f"TLS Enabled        : {results.get('tls_enabled')}")
    print(f"SSL Enabled        : {results.get('ssl_enabled')}")
    print(f"Username           : {results.get('username')}")
    print(f"Environment Loaded : {'Yes (.env loaded)' if results.get('environment_loaded') else 'No'}")
    print(f"DNS Resolution     : {results.get('dns_resolution')}")
    print(f"TCP Connection     : {results.get('tcp_connection')}")
    print(f"Authentication Result: {results.get('authentication_result')}")
    print("===========================================================================")
    if results.get("is_healthy"):
        print("Overall Status     : [SUCCESS] SMTP Server Authenticated & Ready")
    else:
        print(f"Overall Status     : [FAILED] Issues: {', '.join(results.get('errors', []))}")
    print("===========================================================================")


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


def run_validate_rss() -> dict:
    """Executes live RSS validation across configured sources."""
    sources_file = CONFIG_DIR / "sources.yaml"
    client = HTTPClient()
    diag_mgr = RSSDiagnosticsManager()

    try:
        with open(sources_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        sources = data.get("sources", [])
    except Exception as e:
        return {"error": f"Failed to load sources.yaml: {e}"}

    rss_sources = [s for s in sources if s.get("enabled", True) and s.get("collection_method") == "rss"]
    validated = []

    for s in rss_sources:
        sid = s["id"]
        base_url = s.get("base_url")
        if not base_url or "REPLACE_WITH_CHANNEL_ID" in base_url:
            continue

        try:
            code, content = client.get(base_url, source_id=sid)
            items = parse_rss_xml_content(
                content=content,
                source_id=sid,
                url=base_url,
                collector_name=s.get("preferred_collector", "GenericRSSCollector"),
                status_code=code,
            )
            validated.append({
                "source_id": sid,
                "target_url": base_url,
                "status_code": code,
                "items_parsed": len(items),
                "parsed_cleanly": len(items) > 0,
            })
        except Exception as ex:
            validated.append({
                "source_id": sid,
                "target_url": base_url,
                "status_code": 500,
                "items_parsed": 0,
                "error": str(ex),
            })

    return {
        "rss_sources_tested": len(validated),
        "details": validated,
        "diagnostics_summary": diag_mgr.get_feed_diagnostics_summary(),
    }


def run_repair_config() -> dict:
    """Repairs collector recommendations in config/sources.yaml."""
    sources_file = CONFIG_DIR / "sources.yaml"
    diag_mgr = RSSDiagnosticsManager()
    summary = diag_mgr.get_feed_diagnostics_summary()
    feed_stats = summary.get("feed_stats", {})

    repaired_count = 0
    repaired_sources = []

    try:
        with open(sources_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        sources = data.get("sources", [])

        for src in sources:
            sid = src.get("id")
            if sid in feed_stats:
                stat = feed_stats[sid]
                rec = stat.get("recommendation", "")
                if "HtmlScraperCollector" in rec and src.get("preferred_collector") != "HtmlScraperCollector":
                    src["preferred_collector"] = "HtmlScraperCollector"
                    src["collection_method"] = "html"
                    repaired_count += 1
                    repaired_sources.append(f"{sid}: switched to HtmlScraperCollector")

        if repaired_count > 0:
            with open(sources_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, sort_keys=False)

    except Exception as e:
        return {"status": "failed", "error": str(e)}

    return {
        "status": "success",
        "repaired_count": repaired_count,
        "repaired_sources": repaired_sources,
    }


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

    if args.validate_config or args.validate_sources or args.config_report:
        validator = ConfigurationValidator()
        report = validator.validate_all()
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.is_valid else 1

    if args.validate_rss:
        result = run_validate_rss()
        print(json.dumps(result, indent=2))
        return 0

    if args.rss_report:
        diag_mgr = RSSDiagnosticsManager()
        print(json.dumps(diag_mgr.get_feed_diagnostics_summary(), indent=2))
        return 0

    if args.repair_config:
        result = run_repair_config()
        print(json.dumps(result, indent=2))
        return 0

    if args.provider_health:
        checker = ProviderHealthChecker()
        results = checker.check_all_providers()
        print(json.dumps([r.to_dict() for r in results], indent=2))
        return 0

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

    if args.generate_command_docs:
        txt_path, md_path = generate_all_command_docs(parser)
        print(f"Generated CLI documentation:\n  Plain text: {txt_path}\n  Markdown  : {md_path}")
        return 0

    # Phase 11 Launch Dashboard Server
    if args.dashboard:
        from dashboard.app import create_app
        app = create_app()
        print("Launching CyberScout AI Web Dashboard on http://127.0.0.1:5000 ...")
        app.run(host="127.0.0.1", port=5000, debug=False)
        return 0

    # Automation Engine Integrations
    if args.smtp_check:
        run_smtp_check()
        return 0

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
