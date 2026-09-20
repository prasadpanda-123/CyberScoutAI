"""
Opportunities Controller for CyberScout AI Presentation Layer.

Provides SSR-first opportunity discovery, full-text search, multi-facet filtering,
server-side pagination, opportunity details, and saved opportunities bookmarking
with progressive enhancement.
"""

import math
from typing import List, Optional
from flask import Blueprint, flash, jsonify, make_response, redirect, render_template, request, session, url_for
from src.auth.decorators import login_required
from src.core.logging import get_logger
from src.models.query_filter_dto import QueryFilterDTO
from src.services.opportunity_service import OpportunityService

logger = get_logger(__name__)
opportunities_bp = Blueprint("opportunities_ui", __name__)
opp_service = OpportunityService()


def _verify_csrf(req) -> bool:
    """Validates CSRF token from Form, JSON body, or X-CSRF-Token header."""
    submitted = None
    if req.is_json and req.json:
        submitted = req.json.get("csrf_token")
    if not submitted:
        submitted = req.form.get("csrf_token") or req.headers.get("X-CSRF-Token")
    expected = session.get("user_csrf_token") or session.get("admin_csrf_token") or session.get("csrf_token")
    if not submitted or not expected or submitted != expected:
        return False
    return True


@opportunities_bp.route("/opportunities", methods=["GET"])
@login_required
def index():
    """
    Renders SSR-first opportunity discovery view with complete initial HTML,
    PostgreSQL full-text search, server-side facet filtering, intelligent ranking,
    and personalized recommendations.
    """
    user_id = session.get("user_id") or session.get("admin_user_id")
    
    # Check if this is the saved-opportunities tab/view
    default_saved_only = request.args.get("view") == "saved" or request.args.get("saved_only") == "true"
    
    filter_dto = QueryFilterDTO.from_request_args(
        request.args,
        user_id=str(user_id) if user_id else None,
        default_saved_only=default_saved_only,
    )

    try:
        paginated = opp_service.search_opportunities(filter_dto)
    except Exception as e:
        logger.error(f"Error querying opportunities: {e}", exc_info=True)
        # Safe fallback for error states
        from src.models.query_filter_dto import PaginatedResultDTO
        paginated = PaginatedResultDTO(
            items=[],
            total_count=0,
            page=filter_dto.page,
            per_page=filter_dto.per_page,
            total_pages=1,
            has_next=False,
            has_prev=False,
            filter_dto=filter_dto,
        )

    # Surface "Recommended for You" highlight on the first page of discovery
    recommendations = []
    if user_id and not filter_dto.saved_only and filter_dto.page == 1:
        try:
            recommendations = opp_service.get_recommended_for_you(str(user_id), limit=3)
        except Exception as re:
            logger.warning(f"Could not load recommendations for user {user_id}: {re}")

    # Record search history if keyword query provided
    if filter_dto.keyword and user_id:
        try:
            opp_service.user_prefs_repo.record_search(
                user_id=str(user_id),
                query_text=filter_dto.keyword,
                filters={"category": filter_dto.category, "type": filter_dto.opportunity_type},
            )
        except Exception as se:
            logger.warning(f"Failed to record search: {se}")

    # Calculate pagination display window
    start_p = max(1, paginated.page - 2)
    end_p = min(paginated.total_pages, paginated.page + 2)
    page_numbers = list(range(start_p, end_p + 1))

    start_item = (paginated.page - 1) * paginated.per_page + 1 if paginated.total_count > 0 else 0
    end_item = min(paginated.page * paginated.per_page, paginated.total_count)

    # Saved count for current user
    saved_count = opp_service.get_saved_count(str(user_id)) if user_id else 0

    rendered_html = render_template(
        "opportunities.html",
        active_page="opportunities",
        result=paginated,
        filter_dto=filter_dto,
        active_filters=filter_dto.active_filter_summary(),
        page_numbers=page_numbers,
        saved_count=saved_count,
        recommendations=recommendations,
        # Backward-compatible variables for existing tests/templates
        opportunities=paginated.items,
        selected_category=filter_dto.category or "all",
        search_query=filter_dto.keyword or "",
        selected_deadline=filter_dto.deadline or "all",
        selected_sort=filter_dto.sort,
        view_mode="saved" if filter_dto.saved_only else request.args.get("view", "all"),
        page=paginated.page,
        per_page=paginated.per_page,
        total_count=paginated.total_count,
        total_pages=paginated.total_pages,
        start_item=start_item,
        end_item=end_item,
        has_prev=paginated.has_prev,
        has_next=paginated.has_next,
    )

    # Enforce strict private cache policy for personalized content (Principle 37)
    response = make_response(rendered_html)
    response.headers["Cache-Control"] = "private, no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@opportunities_bp.route("/opportunities/<opportunity_id>", methods=["GET"])
def detail(opportunity_id: str):
    """
    Renders SSR opportunity detail view.
    Exposes canonical structured fields, similar opportunities, and explainable
    match analysis for authenticated users while supporting anonymous public access.
    """
    user_id = session.get("user_id") or session.get("admin_user_id")
    opp = opp_service.get_opportunity_detail(opportunity_id, user_id=str(user_id) if user_id else None)

    if not opp:
        return render_template(
            "opportunity_detail.html",
            opportunity=None,
            active_page="opportunities",
            error_message="Opportunity Unavailable: Not found, expired, or archived.",
        ), 404

    return render_template(
        "opportunity_detail.html",
        active_page="opportunities",
        opportunity=opp,
        match_analysis=opp.match_analysis,
        similar_opportunities=opp.similar_opportunities,
        is_authenticated=bool(user_id),
    )


@opportunities_bp.route("/opportunities/<opportunity_id>/toggle-save", methods=["POST"])
@login_required
def toggle_save_form(opportunity_id: str):
    """
    Non-JavaScript HTML form fallback for saving/unsaving an opportunity.
    Redirects back to previous page preserving filter and pagination state.
    """
    if not _verify_csrf(request):
        flash("Security validation failed (invalid CSRF token).", "error")
        return redirect(url_for("opportunities_ui.index"))

    user_id = session.get("user_id") or session.get("admin_user_id")
    if not user_id:
        flash("You must be logged in to save opportunities.", "error")
        return redirect(url_for("auth_ui.login"))

    try:
        res = opp_service.toggle_save_opportunity(str(user_id), opportunity_id)
        session["_cached_saved_count"] = res.get("saved_count", 0)
        if res.get("saved"):
            flash("Opportunity saved to bookmarks.", "success")
        else:
            flash("Opportunity removed from bookmarks.", "info")
    except Exception as e:
        logger.error(f"Error toggling save for opportunity {opportunity_id}: {e}")
        flash("Failed to update saved status.", "error")

    # Safe redirect
    redirect_to = request.form.get("redirect_to")
    if not redirect_to or not redirect_to.startswith("/"):
        redirect_to = url_for("opportunities_ui.index")

    return redirect(redirect_to)


@opportunities_bp.route("/api/opportunities/<opportunity_id>/bookmark", methods=["POST"])
@login_required
def toggle_save_api(opportunity_id: str):
    """
    Progressive enhancement asynchronous AJAX endpoint for saving/unsaving.
    Returns JSON response for client-side state update.
    """
    if not _verify_csrf(request):
        return jsonify({"status": "failed", "error": "CSRF verification failed"}), 403

    user_id = session.get("user_id") or session.get("admin_user_id")
    if not user_id:
        return jsonify({"status": "failed", "error": "Authentication required"}), 401

    try:
        res = opp_service.toggle_save_opportunity(str(user_id), opportunity_id)
        session["_cached_saved_count"] = res.get("saved_count", 0)
        return jsonify({
            "status": "success",
            "saved": res["saved"],
            "saved_count": res["saved_count"],
            "opportunity_id": opportunity_id,
        })
    except Exception as e:
        logger.error(f"Error toggling bookmark for {opportunity_id}: {e}")
        return jsonify({"status": "failed", "error": "Internal server error"}), 500
