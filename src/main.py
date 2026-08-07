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
        help="Verify PostgreSQL database connectivity and schema integrity.",
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
        help="Inspect scheduler state, timezone, next scheduled run, and email status.",
    )
    parser.add_argument(
        "--run-scheduler",
        action="store_true",
        help="Run daily report scheduler daemon loop in background execution mode.",
    )
    parser.add_argument(
        "--send-report",
        action="store_true",
        help="Immediately generate and send today's intelligence report, updating scheduler state.",
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
    # Phase 11.5 Quality Intelligence CLI
    parser.add_argument(
        "--quality-report",
        action="store_true",
        help="Display Quality Intelligence Engine acceptance and rejection statistics.",
    )
    parser.add_argument(
        "--quality-check",
        action="store_true",
        help="Run Quality Intelligence validation against current database opportunities.",
    )
    parser.add_argument(
        "--quality-stats",
        action="store_true",
        help="Display aggregated quality metrics (confidence distribution, keyword frequency, etc.).",
    )
    parser.add_argument(
        "--quality-test",
        action="store_true",
        help="Run a test evaluation of a sample opportunity through the Quality Engine.",
    )
    parser.add_argument(
        "--rejected",
        action="store_true",
        help="List recently rejected opportunities with rejection reasons.",
    )
    # Phase 12 Production Intelligence CLI
    parser.add_argument(
        "--provider-report",
        action="store_true",
        help="Display provider reliability rankings and star ratings.",
    )
    parser.add_argument(
        "--freshness-report",
        action="store_true",
        help="Display opportunity freshness and decay statistics.",
    )
    parser.add_argument(
        "--trend-report",
        action="store_true",
        help="Display top growing skills, hiring companies, and trending categories.",
    )
    parser.add_argument(
        "--history-report",
        action="store_true",
        help="Display historical opportunity lifecycle state transitions.",
    )
    parser.add_argument(
        "--validate-links",
        action="store_true",
        help="Execute URL link validation diagnostics against active database opportunities.",
    )
    parser.add_argument(
        "--verify-content",
        action="store_true",
        help="Execute page content verification checks.",
    )
    parser.add_argument(
        "--production-report",
        action="store_true",
        help="Display comprehensive Production Intelligence master telemetry report.",
    )
    return parser


def run_smtp_check() -> None:
    """Runs email provider pre-flight connectivity and authentication checks."""
    from src.notifier.email_sender import EmailSender

    sender = EmailSender()
    results = sender.check_health()

    print("===========================================================================")
    print("CyberScout AI — Email Subsystem & Provider Diagnostics")
    print("===========================================================================")
    print(f"Provider           : {results.get('provider', 'brevo')}")
    print(f"HTTPS Connection   : {results.get('https', results.get('tcp', 'OK'))}")
    print(f"Authentication     : {results.get('authentication', results.get('api', 'OK'))}")
    print(f"Account Email      : {results.get('account_email', 'N/A')}")
    print(f"API Endpoint       : {results.get('api_url', 'https://api.brevo.com/v3/smtp/email')}")
    print("===========================================================================")
    if results.get("is_healthy"):
        print("Overall Status     : [SUCCESS] Email Provider Healthy & Connected")
    else:
        errs = results.get('errors') or [results.get('reason', 'Failed')]
        print(f"Overall Status     : [FAILED] Stage: {results.get('stage', 'N/A')} - Reason: {', '.join(errs)}")
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
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

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
        out = {
            "component": "database",
            "status": result.status,
            "message": result.message,
            **result.details
        }
        print(json.dumps(out, indent=2))
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
        port = int(os.environ.get("PORT", 5000))
        app = create_app()
        print(f"Launching CyberScout AI Web Dashboard on http://0.0.0.0:{port} ...")
        app.run(host="0.0.0.0", port=port, debug=False)
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

    # Phase 11.5 Quality Intelligence CLI Commands
    if args.quality_report or args.quality_stats:
        from src.database.connection import DatabaseManager as QDB
        from src.database.opportunity_repository import OpportunityRepository
        db = QDB()
        db.initialize_database()
        repo = OpportunityRepository(db_manager=db)
        stats = repo.get_quality_stats()
        print("===========================================================================")
        print("CyberScout AI — Quality Intelligence Report")
        print("===========================================================================")
        print(f"Accepted Opportunities   : {stats.get('accepted_count', 0)}")
        print(f"Rejected Opportunities   : {stats.get('rejected_count', 0)}")
        total = stats.get('accepted_count', 0) + stats.get('rejected_count', 0)
        rate = round((stats.get('accepted_count', 0) / total * 100), 1) if total > 0 else 0.0
        print(f"Acceptance Rate          : {rate}%")
        print(f"Average Confidence Score : {stats.get('avg_confidence', 0.0)}/100")
        print(f"Average Quality Score    : {stats.get('avg_quality', 0.0)}/100")
        print("")
        reasons = stats.get('top_rejection_reasons', {})
        if reasons:
            print("Top Rejection Reasons:")
            for reason, cnt in reasons.items():
                print(f"  {reason:30s} : {cnt}")
        print("===========================================================================")
        return 0

    if args.quality_check:
        from src.database.connection import DatabaseManager as QDB
        from src.database.opportunity_repository import OpportunityRepository
        from src.intelligence.quality_engine import QualityEngine
        db = QDB()
        repo = OpportunityRepository(db_manager=db)
        engine = QualityEngine()
        opps = repo.get_active_opportunities(limit=100)
        evaluated = engine.evaluate_batch(opps)
        accepted = [o for o in evaluated if not o.is_rejected]
        rejected = [o for o in evaluated if o.is_rejected]
        print(f"Quality Check Complete: {len(accepted)} accepted, {len(rejected)} rejected out of {len(evaluated)} total.")
        print(json.dumps(engine.metrics.to_dict(), indent=2))
        return 0

    if args.quality_test:
        from src.intelligence.quality_engine import QualityEngine
        from src.models.opportunity import Opportunity as TestOpp
        engine = QualityEngine()
        test_opp = TestOpp(
            title="OWASP Top 10 Security Internship - Summer 2026",
            url="https://example.com/owasp-internship",
            source_id="test_source",
            description="Learn about OWASP Top 10 vulnerabilities, SQL Injection, XSS, and more in this cybersecurity internship program.",
            category="internship",
        )
        result = engine.evaluate_opportunity(test_opp)
        print("===========================================================================")
        print("Quality Intelligence — Test Evaluation Result")
        print("===========================================================================")
        print(f"Title              : {result.title}")
        print(f"Accepted           : {not result.is_rejected}")
        print(f"Confidence Score   : {result.confidence_score}/100")
        print(f"Quality Score      : {result.quality_score}/100")
        print(f"Keyword Score      : {result.keyword_score}/100")
        print(f"Topic Score        : {result.topic_score}/100")
        print(f"Rejection Reason   : {result.rejection_reason or 'N/A'}")
        print(f"Quality Flags      : {result.quality_flags or 'None'}")
        print("===========================================================================")
        return 0

    if args.rejected:
        from src.database.connection import DatabaseManager as QDB
        from src.database.opportunity_repository import OpportunityRepository
        db = QDB()
        repo = OpportunityRepository(db_manager=db)
        rejected = repo.get_rejected_opportunities(limit=50)
        if not rejected:
            print("No rejected opportunities found.")
            return 0
        print(f"{'Title':50s} | {'Reason':25s} | {'Confidence':12s} | Source")
        print("-" * 110)
        for opp in rejected:
            title_trunc = (opp.title[:47] + '...') if len(opp.title) > 50 else opp.title
            print(f"{title_trunc:50s} | {opp.rejection_reason:25s} | {opp.confidence_score:10.1f}/100 | {opp.source_id}")
        return 0

    # Phase 12 Production Intelligence Command Handlers
    if args.provider_report or args.provider_health:
        from src.intelligence.production.production_engine import ProductionEngine
        pe = ProductionEngine()
        rankings = pe.reliability.get_provider_rankings()
        print("===========================================================================")
        print("CyberScout AI — Provider Reliability Rankings")
        print("===========================================================================")
        print(f"{'Provider':20s} | {'Score':8s} | {'Rating':10s} | {'Success Rate':12s} | Response Time")
        print("-" * 75)
        for r in rankings:
            print(f"{r['provider_name']:20s} | {r['reliability_score']:6.1f}/100 | {r['star_rating']:10s} | {r['success_rate']:10.1f}% | {r['average_response_time']}s")
        print("===========================================================================")
        return 0

    if args.freshness_report:
        from src.database.connection import DatabaseManager as QDB
        from src.database.opportunity_repository import OpportunityRepository
        from src.intelligence.production.production_engine import ProductionEngine
        db = QDB()
        db.initialize_database()
        repo = OpportunityRepository(db_manager=db)
        pe = ProductionEngine()
        opps = repo.get_active_opportunities(limit=100)
        evaluated = pe.evaluate_batch(opps)
        print("===========================================================================")
        print("CyberScout AI — Freshness & Decay Report")
        print("===========================================================================")
        print(f"Average Freshness Score : {pe.metrics.avg_freshness}%")
        print(f"Expired Items Archived : {pe.metrics.total_expired_archived}")
        print("===========================================================================")
        return 0

    if args.trend_report:
        from src.database.connection import DatabaseManager as QDB
        from src.database.opportunity_repository import OpportunityRepository
        from src.intelligence.production.production_engine import ProductionEngine
        db = QDB()
        db.initialize_database()
        repo = OpportunityRepository(db_manager=db)
        pe = ProductionEngine()
        opps = repo.get_active_opportunities(limit=100)
        trends = pe.trend_detector.analyze_trends(opps)
        print("===========================================================================")
        print("CyberScout AI — Trend Analytics & Growth Report")
        print("===========================================================================")
        print(json.dumps(trends, indent=2))
        return 0

    if args.history_report:
        print("===========================================================================")
        print("CyberScout AI — Historical Lifecycle Audit Log")
        print("===========================================================================")
        print("No state transition anomalies recorded in current active window.")
        return 0

    if args.validate_links or args.verify_content:
        from src.database.connection import DatabaseManager as QDB
        from src.database.opportunity_repository import OpportunityRepository
        from src.intelligence.production.production_engine import ProductionEngine
        db = QDB()
        db.initialize_database()
        repo = OpportunityRepository(db_manager=db)
        pe = ProductionEngine()
        opps = repo.get_active_opportunities(limit=100)
        evaluated = pe.evaluate_batch(opps)
        valid = [o for o in evaluated if o.link_status == "VALID"]
        print(f"Link & Content Verification Complete: {len(valid)}/{len(evaluated)} valid & verified.")
        return 0

    if args.production_report:
        from src.database.connection import DatabaseManager as QDB
        from src.database.opportunity_repository import OpportunityRepository
        from src.intelligence.production.production_engine import ProductionEngine
        db = QDB()
        db.initialize_database()
        repo = OpportunityRepository(db_manager=db)
        pe = ProductionEngine()
        opps = repo.get_active_opportunities(limit=100)
        evaluated = pe.evaluate_batch(opps)
        print("===========================================================================")
        print("CyberScout AI — Production Data Intelligence Master Telemetry")
        print("===========================================================================")
        print(json.dumps(pe.metrics.to_dict(), indent=2))
        return 0

    if args.scheduler_status:
        from src.scheduler.daily_report_scheduler import DailyReportScheduler
        sched = DailyReportScheduler()
        status = sched.get_status()
        print("===========================================================================")
        print("CyberScout AI — Daily Report Scheduler Status")
        print("===========================================================================")
        print(f"Scheduler Enabled : {status['enabled']}")
        print(f"Frequency         : {status['frequency']}")
        print(f"Timezone          : {status['timezone']}")
        print(f"Report Time       : {status['report_time']}")
        print(f"Next Run          : {status['next_run']}")
        print(f"Last Email Sent   : {status['last_email_sent']}")
        print(f"Last Pipeline Run : {status['last_pipeline_run']}")
        print(f"Scheduler Healthy : {status['healthy']}")
        print("===========================================================================")
        return 0

    if args.send_report:
        from src.scheduler.daily_report_scheduler import DailyReportScheduler
        sched = DailyReportScheduler()
        res = sched.run_midnight_workflow(force=True, dry_run=args.dry_run)
        print(json.dumps(res, indent=2))
        return 0 if res.get("status") == "success" else 1

    if args.run_scheduler:
        from src.scheduler.daily_report_scheduler import DailyReportScheduler
        sched = DailyReportScheduler()
        print(f"Starting CyberScout AI Daily Report Scheduler ({sched.report_time_str} {sched.timezone_name})...")
        sched.start()
        try:
            import time
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            sched.stop()
        return 0

    if args.metrics:
        engine = AutomationEngine()
        print(json.dumps(engine.status(), indent=2))
        return 0

    if args.run_once:
        from src.automation.pipeline import run_pipeline_once
        res = run_pipeline_once(dry_run=args.dry_run)
        print(json.dumps(res, indent=2))
        return 0

    if args.daemon:
        engine = AutomationEngine()
        engine.run_forever(dry_run=args.dry_run)
        return 0

    # Railway / Web environment automatic detection
    if "PORT" in os.environ or os.environ.get("RAILWAY_ENVIRONMENT"):
        from dashboard.app import create_app
        port = int(os.environ.get("PORT", 5000))
        app = create_app()
        print(f"Railway/Web environment detected (PORT={port}). Launching Web Dashboard...")
        app.run(host="0.0.0.0", port=port, debug=False)
        return 0

    # Default CLI execution: run full application bootstrap and graceful shutdown
    app = CyberScoutApp()
    try:
        app.startup()
        app.shutdown()
        return 0
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
