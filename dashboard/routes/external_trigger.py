"""
External Scheduler Webhook Trigger Route (Google Apps Script -> CyberScout AI).

Provides secure server-to-server endpoint for triggering scans with HMAC-SHA256
authentication, timestamp validation, replay protection, and server-side email chaining.
"""

from flask import Blueprint, jsonify, request
from src.scheduler.external_trigger_service import ExternalTriggerService
from src.utils.ip_utils import get_client_ip
from src.database.login_attempt_repository import LoginAttemptRepository
from src.auth.decorators import admin_required

external_trigger_bp = Blueprint("external_trigger_api", __name__)
_trigger_limit_repo = None


def get_trigger_service() -> ExternalTriggerService:
    from flask import current_app
    db_mgr = getattr(current_app, "db_manager", None) if current_app else None
    return ExternalTriggerService(db_manager=db_mgr)


def _get_trigger_limit_repo():
    global _trigger_limit_repo
    if _trigger_limit_repo is None:
        from flask import current_app
        _trigger_limit_repo = LoginAttemptRepository(db_manager=getattr(current_app, "db_manager", None))
    return _trigger_limit_repo


@external_trigger_bp.route("/api/scheduler/trigger", methods=["POST"])
@external_trigger_bp.route("/api/external/scheduler/trigger", methods=["POST"])
def trigger_external_schedule():
    """
    POST /api/scheduler/trigger & POST /api/external/scheduler/trigger

    Receives HMAC-SHA256 signed POST requests from external schedulers (Google Apps Script).
    Validates HMAC signature, timestamp window, and nonce/request-id uniqueness before
    launching the scan pipeline and chained server-side email dispatch.
    """
    client_ip = get_client_ip(request)

    try:
        allowed = _get_trigger_limit_repo().check_and_record_rate_limit(
            client_ip, "external-scheduler", "scheduler_webhook", max_attempts=20, window_minutes=15
        )
    except Exception:
        return jsonify({"success": False, "status": "unavailable", "error": "Trigger service temporarily unavailable"}), 503
    if not allowed:
        return jsonify({"success": False, "status": "rejected", "error": "Too many trigger requests"}), 429

    # 1. Validate Content-Type
    content_type = request.headers.get("Content-Type", "")
    if not content_type.startswith("application/json") and not request.is_json:
        return jsonify({
            "success": False,
            "status": "rejected",
            "error": "Content-Type must be application/json",
        }), 400

    # 2. Extract raw body bytes and headers
    if request.content_length is not None and request.content_length > 8192:
        return jsonify({"success": False, "status": "rejected", "error": "Request body is too large"}), 413
    raw_body = request.stream.read(8193)
    if len(raw_body) > 8192:
        return jsonify({"success": False, "status": "rejected", "error": "Request body is too large"}), 413
    headers_dict = {k: v for k, v in request.headers.items()}

    # 3. Process trigger via ExternalTriggerService
    service = get_trigger_service()
    response_data, status_code = service.process_trigger(
        headers=headers_dict,
        raw_body=raw_body,
        source_ip=client_ip,
        async_execution=True,
    )

    return jsonify(response_data), status_code


@external_trigger_bp.route("/api/scheduler/status", methods=["GET"])
@external_trigger_bp.route("/api/external/scheduler/status", methods=["GET"])
@admin_required
def get_scheduler_status():
    """
    GET /api/scheduler/status
    Returns safe telemetry regarding external scheduler trigger mode.
    """
    from flask import current_app
    from dashboard.services.api_service import APIService
    db_mgr = getattr(current_app, "db_manager", None) if current_app else None
    api_svc = APIService(db_manager=db_mgr)
    status_info = api_svc.get_scheduler_status()
    latest_trigger = status_info.get("latest_external_trigger") or {}

    current_status = "running" if status_info.get("is_running") else "idle"
    last_run_status = status_info.get("last_run_status") or latest_trigger.get("status", "idle")
    last_email_status = status_info.get("last_email_status", "idle")

    return jsonify({
        "scheduler_mode": "external",
        "trigger_source": "google_apps_script",
        "current_status": current_status,
        "last_run_status": last_run_status,
        "last_email_status": last_email_status,
    }), 200
