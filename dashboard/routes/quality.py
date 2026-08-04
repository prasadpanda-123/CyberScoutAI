"""
Quality Intelligence Dashboard Routes for CyberScout AI.
"""

from flask import Blueprint, render_template
from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository

quality_bp = Blueprint("quality_ui", __name__)


@quality_bp.route("/quality")
def quality_dashboard():
    """Renders the Quality Intelligence Dashboard page."""
    db_manager = DatabaseManager()
    opp_repo = OpportunityRepository(db_manager=db_manager)

    try:
        stats = opp_repo.get_quality_stats()
        rejected = opp_repo.get_rejected_opportunities(limit=50)
    except Exception:
        stats = {
            "accepted_count": 0,
            "rejected_count": 0,
            "avg_confidence": 0.0,
            "avg_quality": 0.0,
            "top_rejection_reasons": {},
        }
        rejected = []

    return render_template(
        "quality.html",
        active_page="quality",
        stats=stats,
        rejected=rejected,
    )
