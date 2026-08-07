"""
Opportunities Page & Export Routes (Page 2).
"""

import csv
import io
import json
from flask import Blueprint, Response, jsonify, render_template, request
from dashboard.services.dashboard_service import DashboardService
from src.auth.decorators import login_required

opportunities_bp = Blueprint("opportunities_ui", __name__)
dash_service = DashboardService()


@opportunities_bp.route("/opportunities")
@login_required
def index():
    """Renders Opportunities table view."""
    category = request.args.get("category", "all")
    search_q = request.args.get("q", "")
    try:
        opps = dash_service.get_opportunities(category=category, search_query=search_q, limit=100)
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Failed to fetch opportunities for route /opportunities: {e}")
        opps = []

    return render_template(
        "opportunities.html",
        active_page="opportunities",
        opportunities=opps,
        selected_category=category,
        search_query=search_q,
    )


@opportunities_bp.route("/opportunities/export/csv")
@login_required
def export_csv():
    """Exports opportunities dataset as CSV file."""
    opps = dash_service.get_opportunities(limit=500)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Title", "URL", "Category", "Source ID", "Discovered Date"])

    for o in opps:
        writer.writerow([
            o.get("id", ""),
            o.get("title", ""),
            o.get("url", ""),
            o.get("category", ""),
            o.get("source_id", ""),
            o.get("discovered_date", ""),
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=cyberscout_opportunities.csv"},
    )


@opportunities_bp.route("/opportunities/export/json")
@login_required
def export_json():
    """Exports opportunities dataset as JSON file."""
    opps = dash_service.get_opportunities(limit=500)
    return Response(
        json.dumps(opps, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=cyberscout_opportunities.json"},
    )
