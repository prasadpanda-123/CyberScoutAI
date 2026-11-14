from datetime import date

from flask import Flask
import pytest

from dashboard.routes.admin_api import admin_api_bp
from src.core.exceptions import RepositoryError
from src.discovery.promotion_models import DailyReportMetadata
from src.discovery.promotion_repository import PromotionRepository


def test_admin_dashboard_stats_returns_pipeline_metrics(monkeypatch):
    monkeypatch.setattr(
        PromotionRepository,
        "__init__",
        lambda self, db_manager=None, opp_repo=None: None,
    )
    monkeypatch.setattr(
        PromotionRepository,
        "get_daily_summary_counts",
        lambda self, report_date, run_id=None, strict=False: DailyReportMetadata(
            report_date=report_date,
            total_active_production=12,
            total_discovered=8,
            total_extracted=6,
            total_classified=5,
            total_approved=3,
            total_quarantined=1,
            total_rejected=1,
        ),
    )

    app = Flask(__name__)
    app.secret_key = "test-only"
    app.register_blueprint(admin_api_bp)
    client = app.test_client()
    with client.session_transaction() as admin_session:
        admin_session["admin_authenticated"] = True
        admin_session["admin_role"] = "Admin"

    response = client.get("/admin/api/stats")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["report_date"] == date.today().isoformat()
    assert payload == {
        "status": "success",
        "report_date": payload["report_date"],
        "total_production": 12,
        "total_discovered": 8,
        "total_extracted": 6,
        "total_classified": 5,
        "total_approved": 3,
        "total_quarantined": 1,
        "total_rejected": 1,
    }


def test_daily_api_budgets_are_available_to_admins():
    app = Flask(__name__)
    app.secret_key = "test-only"
    app.register_blueprint(admin_api_bp)
    client = app.test_client()
    with client.session_transaction() as admin_session:
        admin_session["admin_authenticated"] = True
        admin_session["admin_role"] = "Admin"

    response = client.get("/admin/api/daily-budgets")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["scope"] == "application_config"
    assert payload["usage_tracking"] == "not_persisted"
    assert {item["provider"] for item in payload["daily_limits"]} == {
        "Tavily",
        "Firecrawl",
        "Groq / Gemini",
    }


def test_daily_summary_strict_mode_surfaces_schema_failure(monkeypatch):
    repository = PromotionRepository.__new__(PromotionRepository)
    monkeypatch.setattr(repository, "ensure_schema", lambda: False)

    with pytest.raises(RepositoryError, match="schema"):
        repository.get_daily_summary_counts(report_date=date.today().isoformat(), strict=True)
