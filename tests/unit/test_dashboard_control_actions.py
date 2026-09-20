"""
Unit Tests for Dashboard System Control Actions (All 11 Endpoints).

Validates:
- Authentication & CSRF protections
- Asynchronous action launching & tracking via ActionJobManager
- Measurable stage progress reporting & job telemetry
- Destructive operation confirmation safeguards & preview endpoint
- Database reconnection, ping, and schema metadata reporting
- Error and conflict handling (HTTP 409, 400, 403)
"""

import json
import threading
from unittest.mock import MagicMock, patch
import pytest
from flask import Flask

from src.automation.action_job_manager import ActionJobManager, action_job_manager
from src.automation.job_manager import scan_job_manager


@pytest.fixture
def client():
    """Creates test client for CyberScout AI application with active admin session."""
    from dashboard.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as test_client:
        with test_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_username"] = "admin"
            sess["admin_csrf_token"] = "test_csrf_token_12345"
            sess["user_id"] = "admin-uuid-1234"
        yield test_client


@pytest.fixture(autouse=True)
def clean_action_manager():
    """Ensures clean ActionJobManager state and idle scan manager between test cases."""
    with action_job_manager._job_lock:
        action_job_manager._jobs.clear()
        action_job_manager._active_job_id = None
    with scan_job_manager._job_lock:
        scan_job_manager._jobs.clear()
        scan_job_manager._active_job_id = None

    with patch.object(scan_job_manager, "is_scan_active", return_value=False):
        yield

    with action_job_manager._job_lock:
        action_job_manager._jobs.clear()
        action_job_manager._active_job_id = None
    with scan_job_manager._job_lock:
        scan_job_manager._jobs.clear()
        scan_job_manager._active_job_id = None


def test_unauthenticated_requests_blocked(client):
    """Verifies that all action endpoints reject unauthenticated requests."""
    with client.session_transaction() as sess:
        sess.clear()

    endpoints = [
        ("POST", "/admin/api/run"),
        ("POST", "/admin/api/email/test"),
        ("POST", "/admin/api/report/trigger"),
        ("POST", "/admin/api/analytics/refresh"),
        ("POST", "/admin/api/scheduler/pause"),
        ("POST", "/admin/api/scheduler/resume"),
        ("POST", "/admin/api/scheduler/restart"),
        ("GET",  "/admin/api/opportunities/clear-old/preview"),
        ("POST", "/admin/api/opportunities/clear-old"),
        ("POST", "/admin/api/db/test"),
        ("POST", "/admin/api/db/reconnect"),
        ("GET",  "/admin/api/db/info"),
    ]

    for method, ep in endpoints:
        if method == "POST":
            res = client.post(ep, headers={"X-CSRF-Token": "invalid", "X-Requested-With": "XMLHttpRequest"})
        else:
            res = client.get(ep, headers={"X-Requested-With": "XMLHttpRequest"})
        # Should redirect to login (302) or return 401/403
        assert res.status_code in (302, 401, 403), f"Endpoint {ep} allowed unauthenticated access with status {res.status_code}"


def test_csrf_token_missing_rejected(client):
    """Verifies that mutating action endpoints reject requests missing CSRF token."""
    post_endpoints = [
        "/admin/api/run",
        "/admin/api/email/test",
        "/admin/api/report/trigger",
        "/admin/api/analytics/refresh",
        "/admin/api/scheduler/pause",
        "/admin/api/scheduler/resume",
        "/admin/api/scheduler/restart",
        "/admin/api/opportunities/clear-old",
        "/admin/api/db/reconnect",
    ]

    for ep in post_endpoints:
        res = client.post(ep, headers={"X-Requested-With": "XMLHttpRequest"})
        assert res.status_code == 403, f"Endpoint {ep} did not enforce CSRF protection"
        data = res.get_json()
        assert data.get("success") is False


def test_get_active_action_endpoint(client):
    """Verifies GET /admin/api/actions/active accurately reports idle vs active states."""
    # When idle:
    res = client.get("/admin/api/actions/active")
    assert res.status_code == 200
    data = res.get_json()
    assert data.get("active") is False
    assert data.get("job") is None

    # When job active (holding lock briefly to verify status):
    evt = threading.Event()
    def long_task(cb):
        evt.wait(timeout=2.0)
        return {"done": True}

    job = action_job_manager.start_action(
        action_name="test_action",
        action_label="Test Action",
        task_fn=long_task,
    )
    try:
        res2 = client.get("/admin/api/actions/active")
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert data2.get("active") is True
        assert data2.get("job") is not None
        assert data2["job"]["job_id"] == job["job_id"]
    finally:
        evt.set()


def test_execute_scan_now_endpoint(client):
    """Verifies POST /admin/api/run triggers scan and returns accepted 202."""
    with patch("dashboard.services.api_service.APIService.trigger_scan") as mock_scan:
        mock_scan.return_value = {"success": True, "job_id": "job-abc12345", "status": "started"}
        res = client.post("/admin/api/run", headers={"X-CSRF-Token": "test_csrf_token_12345"})
        assert res.status_code == 202
        data = res.get_json()
        assert data.get("success") is True
        assert data.get("job_id") == "job-abc12345"
        assert data.get("action_name") == "execute_scan"


def test_send_test_email_endpoint(client):
    """Verifies POST /admin/api/email/test launches asynchronous job with stages."""
    with patch("dashboard.services.api_service.APIService.send_test_email") as mock_email:
        mock_email.return_value = {"success": True, "status": "completed", "message": "Email sent"}
        res = client.post("/admin/api/email/test", headers={"X-CSRF-Token": "test_csrf_token_12345"})
        assert res.status_code == 202
        data = res.get_json()
        assert data.get("success") is True
        assert "job_id" in data
        assert data.get("action_name") == "send_test_email"

        # Check job telemetry
        status_res = client.get(f"/admin/api/actions/{data['job_id']}")
        assert status_res.status_code == 200
        job_data = status_res.get_json()
        assert job_data.get("action_name") == "send_test_email"


def test_send_daily_report_now_endpoint(client):
    """Verifies POST /admin/api/report/trigger launches asynchronous report job."""
    with patch("dashboard.services.api_service.APIService.send_daily_report_now") as mock_report:
        mock_report.return_value = {"success": True, "status": "completed", "message": "Daily report sent"}
        res = client.post("/admin/api/report/trigger", headers={"X-CSRF-Token": "test_csrf_token_12345"})
        assert res.status_code == 202
        data = res.get_json()
        assert data.get("success") is True
        assert "job_id" in data
        assert data.get("action_name") == "send_report_now"


def test_refresh_analytics_endpoint(client):
    """Verifies POST /admin/api/analytics/refresh recalculates provider statistics."""
    with patch("dashboard.services.api_service.APIService.refresh_analytics") as mock_analytics:
        mock_analytics.return_value = {"success": True, "status": "completed", "recalculated_providers": 8}
        res = client.post("/admin/api/analytics/refresh", headers={"X-CSRF-Token": "test_csrf_token_12345"})
        assert res.status_code == 202
        data = res.get_json()
        assert data.get("success") is True
        assert "job_id" in data
        assert data.get("action_name") == "refresh_analytics"


def test_scheduler_lifecycle_actions(client):
    """Verifies Pause, Resume, and Restart scheduler control actions."""
    headers = {"X-CSRF-Token": "test_csrf_token_12345"}

    with patch("dashboard.services.api_service.APIService.pause_scheduler") as mock_p:
        mock_p.return_value = {"success": True, "status": "paused", "message": "Scheduler paused"}
        res = client.post("/admin/api/scheduler/pause", headers=headers)
        assert res.status_code == 200
        assert res.get_json().get("status") == "paused"

    with patch("dashboard.services.api_service.APIService.resume_scheduler") as mock_r:
        mock_r.return_value = {"success": True, "status": "running", "message": "Scheduler resumed"}
        res = client.post("/admin/api/scheduler/resume", headers=headers)
        assert res.status_code == 200
        assert res.get_json().get("status") == "running"

    with patch("dashboard.services.api_service.APIService.restart_scheduler") as mock_rest:
        mock_rest.return_value = {"success": True, "status": "restarted", "message": "Scheduler restarted"}
        res = client.post("/admin/api/scheduler/restart", headers=headers)
        assert res.status_code == 200
        assert res.get_json().get("status") == "restarted"


def test_purge_records_requires_confirmation(client):
    """Verifies POST /admin/api/opportunities/clear-old rejects execution without explicit confirmation."""
    headers = {"X-CSRF-Token": "test_csrf_token_12345", "Content-Type": "application/json"}

    # Attempt 1: Empty body
    res1 = client.post("/admin/api/opportunities/clear-old", headers=headers, data=json.dumps({}))
    assert res1.status_code == 400
    assert res1.get_json().get("status") == "confirmation_required"

    # Attempt 2: confirm = False
    res2 = client.post("/admin/api/opportunities/clear-old", headers=headers, data=json.dumps({"confirm": False, "days": 30}))
    assert res2.status_code == 400
    assert res2.get_json().get("status") == "confirmation_required"


def test_purge_records_preview_and_confirmed_execution(client):
    """Verifies GET preview and POST confirmed execution for purge records."""
    headers = {"X-CSRF-Token": "test_csrf_token_12345", "Content-Type": "application/json"}

    # Test preview
    res_prev = client.get("/admin/api/opportunities/clear-old/preview?days=30")
    assert res_prev.status_code == 200
    prev_data = res_prev.get_json()
    assert prev_data.get("success") is True
    assert "eligible_count" in prev_data
    assert "cutoff_date" in prev_data

    # Test confirmed execution
    with patch("dashboard.services.api_service.APIService.clear_old_opportunities") as mock_clear:
        mock_clear.return_value = {"success": True, "status": "completed", "deleted_count": 0}
        res_exec = client.post(
            "/admin/api/opportunities/clear-old",
            headers=headers,
            data=json.dumps({"confirm": True, "days": 30}),
        )
        assert res_exec.status_code == 202
        exec_data = res_exec.get_json()
        assert exec_data.get("success") is True
        assert exec_data.get("action_name") == "purge_records"


def test_db_ping_endpoint(client):
    """Verifies POST /admin/api/db/test returns connectivity and latency metrics."""
    res = client.post("/admin/api/db/test", headers={"X-CSRF-Token": "test_csrf_token_12345"})
    assert res.status_code == 200
    data = res.get_json()
    assert "success" in data
    assert "connected" in data
    assert "latency_ms" in data
    assert data.get("database_type") == "PostgreSQL"


def test_db_reconnect_endpoint(client):
    """Verifies POST /admin/api/db/reconnect disposes pool and launches reconnect job."""
    with patch("dashboard.services.api_service.APIService.reconnect_database") as mock_recon:
        mock_recon.return_value = {"success": True, "status": "connected", "latency_ms": 1.5}
        res = client.post("/admin/api/db/reconnect", headers={"X-CSRF-Token": "test_csrf_token_12345"})
        assert res.status_code == 202
        data = res.get_json()
        assert data.get("success") is True
        assert data.get("action_name") == "db_reconnect"


def test_db_info_endpoint(client):
    """Verifies GET /admin/api/db/info returns schema breakdown and table row counts without exposing secrets."""
    res = client.get("/admin/api/db/info")
    assert res.status_code == 200
    data = res.get_json()
    assert data.get("success") is True
    assert "tables" in data
    assert "table_counts" in data
    assert "latency_ms" in data
    assert "host" in data
    # Ensure credentials are not exposed
    assert "password" not in data
    assert "postgres://" not in str(data).lower()
