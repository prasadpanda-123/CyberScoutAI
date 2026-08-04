"""
Phase 12 Production Intelligence Web Dashboard Routes.
"""

from flask import Blueprint, render_template
from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.intelligence.production.production_engine import ProductionEngine

production_bp = Blueprint("production", __name__)
db = DatabaseManager()
repo = OpportunityRepository(db_manager=db)
prod_engine = ProductionEngine()


@production_bp.route("/production")
def production_index():
    """GET /production — Production Intelligence Control Center overview."""
    opps = repo.get_active_opportunities(limit=100)
    evaluated = prod_engine.evaluate_batch(opps)
    trends = prod_engine.trend_detector.analyze_trends(evaluated)
    rankings = prod_engine.reliability.get_provider_rankings()

    return render_template(
        "production.html",
        opportunities=evaluated,
        metrics=prod_engine.metrics.to_dict(),
        trends=trends,
        provider_rankings=rankings,
    )


@production_bp.route("/provider-health")
def provider_health():
    """GET /provider-health — Provider Health & Reliability Rankings."""
    rankings = prod_engine.reliability.get_provider_rankings()
    return render_template("provider_health.html", rankings=rankings)


@production_bp.route("/trends")
def trends():
    """GET /trends — Trend Analytics & Skill Growth Heatmaps."""
    opps = repo.get_active_opportunities(limit=200)
    trend_data = prod_engine.trend_detector.analyze_trends(opps)
    return render_template("trends.html", trends=trend_data)


@production_bp.route("/history")
def history():
    """GET /history — Historical Opportunity Lifecycle Changes."""
    return render_template("history.html")


@production_bp.route("/link-validation")
def link_validation():
    """GET /link-validation — Link Verification Diagnostics Log."""
    opps = repo.get_active_opportunities(limit=100)
    valid_links = [o for o in opps if o.link_status == "VALID"]
    invalid_links = [o for o in opps if o.link_status != "VALID"]
    return render_template("link_validation.html", valid_links=valid_links, invalid_links=invalid_links)


@production_bp.route("/quality-metrics")
def quality_metrics():
    """GET /quality-metrics — Comprehensive Quality & Telemetry Metrics."""
    return render_template("quality_metrics.html", metrics=prod_engine.metrics.to_dict())
