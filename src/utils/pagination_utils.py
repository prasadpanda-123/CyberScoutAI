"""
Pagination and Query Limit Utilities for CyberScout AI.

Provides safe numeric parameter parsing and strict upper bounding to defend against
uncontrolled database queries and unhandled conversion 500 errors (SEC-05).
"""

from typing import Any, Tuple


def parse_pagination(
    request: Any,
    default_page: int = 1,
    default_limit: int = 50,
    max_limit: int = 200,
) -> Tuple[int, int]:
    """
    Safely extracts and validates pagination parameters (page, limit / per_page) from request.args.

    Defensive behaviors:
    - Non-numeric strings (e.g. ?page=abc, ?limit=xyz) fallback safely to defaults (zero 500s).
    - Page numbers < 1 are normalized to 1.
    - Limits < 1 are normalized to default_limit.
    - Limits exceeding max_limit are strictly capped at max_limit (target: 200).

    Returns:
        Tuple of (clean_page: int, clean_limit: int)
    """
    args = getattr(request, "args", {}) if request else {}

    # 1. Parse Page
    raw_page = args.get("page", default_page)
    try:
        page = int(raw_page)
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = default_page

    # 2. Parse Limit (supports 'limit' or 'per_page')
    raw_limit = args.get("limit") or args.get("per_page") or default_limit
    try:
        limit = int(raw_limit)
        if limit < 1:
            limit = default_limit
        elif limit > max_limit:
            limit = max_limit
    except (ValueError, TypeError):
        limit = default_limit

    return page, limit
