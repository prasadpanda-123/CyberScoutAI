from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from dashboard.routes.api import api_bp
from src.models.query_filter_dto import QueryFilterDTO


@dataclass
class OpportunityCard:
    id: str
    title: str
    description_snippet: str
    is_saved: bool


def test_opportunity_api_filter_contract_accepts_feed_filters_and_title_sort():
    filters = QueryFilterDTO.from_request_args(
        {
            "q": "cloud security",
            "category": "Internship",
            "remote": "true",
            "is_free": "true",
            "sort": "title",
            "sort_dir": "asc",
            "page": "3",
            "per_page": "9",
        },
        user_id="user-123",
    )

    assert filters.keyword == "cloud security"
    assert filters.category == "Internship"
    assert filters.remote is True
    assert filters.is_free is True
    assert filters.sort == "title"
    assert filters.sort_dir == "asc"
    assert filters.page == 3
    assert filters.per_page == 9
    assert filters.user_id == "user-123"


def test_opportunity_api_filter_contract_rejects_untrusted_sort_expression():
    filters = QueryFilterDTO.from_request_args(
        {"sort": "title; DROP TABLE Opportunities"}
    )

    assert filters.sort == "newest"


def test_opportunities_endpoint_returns_paginated_cards_and_uses_authenticated_user():
    result = SimpleNamespace(
        items=[OpportunityCard("opp-1", "Security internship", "Learn security.", True)],
        total_count=17,
        page=2,
        per_page=9,
        total_pages=2,
        has_next=False,
        has_prev=True,
    )
    app = Flask(__name__)
    app.secret_key = "isolated-test-key"
    app.register_blueprint(api_bp)

    with patch("dashboard.routes.api.OpportunityService") as service_class:
        service_class.return_value.search_opportunities.return_value = result
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = "user-123"
            session["role"] = "Viewer"

        response = client.get(
            "/api/opportunities?page=2&per_page=9&sort=title&remote=true&is_free=true"
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 17
    assert data["page"] == 2
    assert data["per_page"] == 9
    assert data["opportunities"][0]["is_saved"] is True
    filters = service_class.return_value.search_opportunities.call_args.args[0]
    assert filters.user_id == "user-123"
    assert filters.sort == "title"
    assert filters.remote is True
    assert filters.is_free is True
