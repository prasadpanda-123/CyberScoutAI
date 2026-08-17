import math
from flask import Blueprint, render_template, request
from dashboard.services.dashboard_service import DashboardService
from src.auth.decorators import login_required

opportunities_bp = Blueprint("opportunities_ui", __name__)
dash_service = DashboardService()


@opportunities_bp.route("/opportunities")
@login_required
def index():
    """Renders Opportunities table view with server-side pagination, sorting, and filters."""
    category = request.args.get("category", "all")
    search_q = request.args.get("q", "")
    deadline_f = request.args.get("deadline", "all")
    sort_by = request.args.get("sort", "relevance")
    view_mode = request.args.get("view", "all")

    # Sanitize page parameter
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1

    # Sanitize per_page parameter (allowed: 20, 50, 100)
    try:
        per_page = int(request.args.get("per_page", 20))
    except (TypeError, ValueError):
        per_page = 20
    if per_page not in [20, 50, 100]:
        per_page = 20

    offset = (page - 1) * per_page

    try:
        res = dash_service.get_opportunities(
            category=category,
            search_query=search_q,
            deadline_filter=deadline_f if deadline_f != "all" else None,
            sort_by=sort_by,
            limit=per_page,
            offset=offset,
            return_total=True,
        )
        opps = res.get("items", [])
        total_count = res.get("total_count", 0)
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Failed to fetch opportunities for route /opportunities: {e}")
        opps = []
        total_count = 0

    total_pages = max(1, math.ceil(total_count / per_page)) if total_count > 0 else 1

    # Adjust page if requested page exceeds total_pages
    if page > total_pages and total_count > 0:
        page = total_pages
        offset = (page - 1) * per_page
        try:
            res = dash_service.get_opportunities(
                category=category,
                search_query=search_q,
                deadline_filter=deadline_f if deadline_f != "all" else None,
                sort_by=sort_by,
                limit=per_page,
                offset=offset,
                return_total=True,
            )
            opps = res.get("items", [])
        except Exception:
            opps = []

    start_item = (page - 1) * per_page + 1 if total_count > 0 else 0
    end_item = min(page * per_page, total_count)

    # Window of page numbers for pagination controls
    start_p = max(1, page - 2)
    end_p = min(total_pages, page + 2)
    page_numbers = list(range(start_p, end_p + 1))

    return render_template(
        "opportunities.html",
        active_page="opportunities",
        opportunities=opps,
        selected_category=category,
        search_query=search_q,
        selected_deadline=deadline_f,
        selected_sort=sort_by,
        view_mode=view_mode,
        page=page,
        per_page=per_page,
        total_count=total_count,
        total_pages=total_pages,
        start_item=start_item,
        end_item=end_item,
        has_prev=page > 1,
        has_next=page < total_pages,
        page_numbers=page_numbers,
    )


