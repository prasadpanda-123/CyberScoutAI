"""
External Scheduler Webhook Trigger Route (Google Apps Script -> CyberScout AI).

Provides secure server-to-server endpoint for triggering scans with HMAC-SHA256
authentication, timestamp validation, replay protection, and server-side email chaining.
"""

from flask import Blueprint, jsonify, request
from src.scheduler.external_trigger_service import ExternalTriggerService
from src.utils.ip_utils import get_client_ip

external_trigger_bp = Blueprint("external_trigger_api", __name__)


def get_trigger_service() -> ExternalTriggerService:
    from flask import current_app
    db_mgr = getattr(current_app, "db_manager", None) if current_app else None
    return ExternalTriggerService(db_manager=db_mgr)


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

    # 1. Validate Content-Type
    content_type = request.headers.get("Content-Type", "")
    if not content_type.startswith("application/json") and not request.is_json:
        return jsonify({
            "success": False,
            "status": "rejected",
            "error": "Content-Type must be application/json",
        }), 400

    # 2. Extract raw body bytes and headers
    raw_body = request.get_data()
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
        "last_run_id": latest_trigger.get("request_id"),
        "last_run_status": last_run_status,
        "last_run_at": latest_trigger.get("received_at", status_info.get("last_run_time")),
        "last_email_status": last_email_status,
    }), 200
