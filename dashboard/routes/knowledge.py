"""
Knowledge Base Route (Page 7).
"""

from flask import Blueprint, render_template

knowledge_bp = Blueprint("knowledge_ui", __name__)


@knowledge_bp.route("/knowledge")
def index():
    """Renders Knowledge Base intelligence page."""
    kb_stats = {
        "total_records": 1284,
        "archived_records": 142,
        "duplicate_rate_pct": 14.8,
        "top_sources": ["GitHub Search", "CTFtime", "SANS"],
        "top_providers": ["GitHub", "SANS", "HackTheBox"],
    }
    return render_template(
        "knowledge.html",
        active_page="knowledge",
        kb_stats=kb_stats,
    )
