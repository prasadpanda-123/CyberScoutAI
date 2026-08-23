"""
External Scheduler Trigger Service for CyberScout AI.

Handles HMAC-SHA256 authenticated server-to-server webhook requests from Google Apps Script,
replay protection via PostgreSQL request tracking, concurrency locking, and server-side
email dispatch chaining via Brevo.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

from src.core.logging import get_logger
from src.database.audit_log_repository import AuditLogRepository
from src.database.connection import DatabaseManager
from src.database.scheduler_repository import SchedulerRepository
from src.database.webhook_request_repository import WebhookRequestRepository
from src.automation.job_manager import scan_job_manager
from src.automation.pipeline import run_pipeline_once
from src.notifier.email_client import EmailClient

logger = get_logger(__name__)

# Maximum acceptable age for incoming webhook requests (±5 minutes)
MAX_WEBHOOK_AGE_SECONDS = 300


class ExternalTriggerService:
    """
    Manages HMAC-SHA256 signature verification, replay protection, scan execution,
    and server-side email dispatch chaining for external webhook scheduler triggers.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        audit_repo: Optional[AuditLogRepository] = None,
        webhook_repo: Optional[WebhookRequestRepository] = None,
        scheduler_repo: Optional[SchedulerRepository] = None,
        email_client: Optional[EmailClient] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.audit_repo = audit_repo or AuditLogRepository(db_manager=self.db_manager)
        self.webhook_repo = webhook_repo or WebhookRequestRepository(db_manager=self.db_manager)
        self.scheduler_repo = scheduler_repo or SchedulerRepository(db_manager=self.db_manager)
        self.email_client = email_client or EmailClient(db_manager=self.db_manager)

    @staticmethod
    def get_webhook_secret() -> str:
        """Retrieves shared HMAC secret from environment variable."""
        return (
            os.getenv("CYBERSCOUT_SCHEDULER_SECRET")
            or os.getenv("SCHEDULER_WEBHOOK_SECRET")
            or ""
        ).strip()

    def verify_request_authentication(
        self,
        headers: Dict[str, str],
        raw_body: bytes,
        source_ip: str = "Unknown",
    ) -> Tuple[bool, str, int, Optional[Dict[str, Any]]]:
        """
        Validates HMAC-SHA256 signature, timestamp expiration, and payload structure.

        Returns:
            Tuple of (is_valid, error_message, http_status_code, parsed_json_payload)
        """
        secret = self.get_webhook_secret()
        if not secret:
            logger.error("[ExternalTrigger] CYBERSCOUT_SCHEDULER_SECRET is not configured on the server.")
            self._log_audit(
                action="TRIGGER_REJECTED",
                status="FAILED",
                source_ip=source_ip,
                details="Webhook trigger rejected: CYBERSCOUT_SCHEDULER_SECRET not configured on server",
            )
            return False, "Server configuration error: scheduler secret not set.", 500, None

        # 1. Normalize headers dictionary for case-insensitive and format-insensitive lookup
        norm_headers = {}
        for k, v in headers.items():
            clean_k = k.lower().replace("_", "-")
            if clean_k.startswith("http-"):
                clean_k = clean_k[5:]
            norm_headers[clean_k] = v.strip()

        header_sig = norm_headers.get("x-cyberscout-signature", "")
        header_ts_str = norm_headers.get("x-cyberscout-timestamp", "")
        header_nonce = norm_headers.get("x-cyberscout-nonce", "") or norm_headers.get("x-cyberscout-request-id", "")

        if not header_sig:
            logger.warning(f"[ExternalTrigger] Missing X-CyberScout-Signature header from IP {source_ip}.")
            self._log_audit(
                action="TRIGGER_REJECTED",
                status="FAILED",
                source_ip=source_ip,
                details="Missing X-CyberScout-Signature header",
            )
            return False, "Unauthorized: missing signature header.", 401, None

        if not header_ts_str:
            logger.warning(f"[ExternalTrigger] Missing X-CyberScout-Timestamp header from IP {source_ip}.")
            self._log_audit(
                action="TRIGGER_REJECTED",
                status="FAILED",
                source_ip=source_ip,
                details="Missing X-CyberScout-Timestamp header",
            )
            return False, "Unauthorized: missing timestamp header.", 401, None

        # 2. Parse and validate timestamp window (±5 minutes)
        try:
            req_ts = int(header_ts_str)
        except (ValueError, TypeError):
            logger.warning(f"[ExternalTrigger] Invalid timestamp format '{header_ts_str}' from IP {source_ip}.")
            self._log_audit(
                action="TRIGGER_REJECTED",
                status="FAILED",
                source_ip=source_ip,
                details="Invalid timestamp format",
            )
            return False, "Unauthorized: invalid timestamp.", 401, None

        current_ts = int(time.time())
        if abs(current_ts - req_ts) > MAX_WEBHOOK_AGE_SECONDS:
            logger.warning(f"[ExternalTrigger] Expired timestamp {req_ts} (current: {current_ts}, diff: {abs(current_ts - req_ts)}s).")
            self._log_audit(
                action="TRIGGER_REJECTED",
                status="FAILED",
                source_ip=source_ip,
                details=f"Timestamp expired (drift: {abs(current_ts - req_ts)}s)",
            )
            return False, "Unauthorized: timestamp expired or outside acceptable window.", 401, None

        # 3. Parse JSON Body
        try:
            raw_body_str = raw_body.decode("utf-8") if isinstance(raw_body, bytes) else str(raw_body)
            body_json = json.loads(raw_body_str) if raw_body_str.strip() else {}
        except Exception as e:
            logger.warning(f"[ExternalTrigger] Malformed JSON body from IP {source_ip}: {e}")
            self._log_audit(
                action="TRIGGER_REJECTED",
                status="FAILED",
                source_ip=source_ip,
                details="Malformed JSON payload",
            )
            return False, "Bad Request: malformed JSON payload.", 400, None

        # Validate required JSON fields / nonce
        body_nonce = str(body_json.get("nonce", "") or body_json.get("request_id", "")).strip()
        req_id = header_nonce or body_nonce
        if not req_id:
            logger.warning(f"[ExternalTrigger] Missing nonce/request_id in request from IP {source_ip}.")
            self._log_audit(
                action="TRIGGER_REJECTED",
                status="FAILED",
                source_ip=source_ip,
                details="Missing nonce/request_id",
            )
            return False, "Bad Request: missing required field 'nonce' or 'request_id'.", 400, None

        # 4. Construct signing payload and verify HMAC-SHA256
        # Signing payload format: timestamp + "." + nonce + "." + raw_body
        signing_payload = f"{header_ts_str}.{req_id}.{raw_body_str}"
        computed_hash = hmac.new(
            secret.encode("utf-8"),
            signing_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        header_sig_clean = header_sig.strip()
        valid = (
            hmac.compare_digest(f"sha256={computed_hash}", header_sig_clean)
            or hmac.compare_digest(computed_hash, header_sig_clean)
        )

        if not valid:
            logger.warning(f"[ExternalTrigger] Invalid HMAC signature from IP {source_ip}.")
            self._log_audit(
                action="TRIGGER_REJECTED",
                status="FAILED",
                source_ip=source_ip,
                request_id=req_id,
                details="Invalid HMAC signature",
            )
            return False, "Unauthorized: invalid signature.", 401, None

        return True, "Valid", 200, {
            "request_id": req_id,
            "nonce": req_id,
            "timestamp": req_ts,
            "event": body_json.get("event", "scheduled_scan"),
            "trigger": body_json.get("trigger", body_json.get("source", "google_apps_script")),
            "source": body_json.get("source", body_json.get("trigger", "google_apps_script")),
            "dry_run": bool(body_json.get("dry_run", False)),
            "send_empty_report": bool(body_json.get("send_empty_report", False)),
        }

    def process_trigger(
        self,
        headers: Dict[str, str],
        raw_body: bytes,
        source_ip: str = "Unknown",
        async_execution: bool = True,
    ) -> Tuple[Dict[str, Any], int]:
        """
        End-to-end trigger processing pipeline:
        1. Authenticate HMAC & Timestamp
        2. Replay Protection (check unique request_id)
        3. Concurrency Protection (check active scan)
        4. Register request and execute scan + chained server-side email
        """
        is_valid, err_msg, status_code, payload = self.verify_request_authentication(
            headers=headers,
            raw_body=raw_body,
            source_ip=source_ip,
        )
        if not is_valid or not payload:
            return {"success": False, "status": "rejected", "error": err_msg}, status_code

        request_id = payload["request_id"]
        req_timestamp = payload["timestamp"]
        source = payload["source"]
        dry_run = payload["dry_run"]
        send_empty_report = payload["send_empty_report"]

        # 2. Replay Protection Check
        existing_req = self.webhook_repo.get_by_request_id(request_id)
        if existing_req:
            logger.warning(f"[ExternalTrigger] Duplicate request_id '{request_id}' rejected (Replay Protection).")
            self._log_audit(
                action="TRIGGER_REPLAY_REJECTED",
                status="FAILED",
                source_ip=source_ip,
                request_id=request_id,
                details=f"Duplicate request_id '{request_id}' replayed from {source}",
            )
            return {
                "success": False,
                "status": "duplicate",
                "message": "Duplicate request ID already processed.",
                "request_id": request_id,
            }, 409

        # 3. Concurrent Scan Check
        if scan_job_manager.is_scan_active():
            logger.warning(f"[ExternalTrigger] Trigger request '{request_id}' rejected: scan currently in progress.")
            self._log_audit(
                action="TRIGGER_ALREADY_RUNNING",
                status="FAILED",
                source_ip=source_ip,
                request_id=request_id,
                details="A scan is already in progress",
            )
            return {
                "success": False,
                "status": "already_running",
                "message": "A CyberScout scan is already running.",
                "request_id": request_id,
            }, 409

        # 4. Register new request in PostgreSQL
        registered = self.webhook_repo.record_request(
            request_id=request_id,
            timestamp=req_timestamp,
            source=source,
            status="accepted",
        )
        if not registered:
            return {
                "success": False,
                "status": "duplicate",
                "message": "Duplicate request ID already processed.",
                "request_id": request_id,
            }, 409

        self._log_audit(
            action="EXTERNAL_TRIGGER_ACCEPTED",
            status="SUCCESS",
            source_ip=source_ip,
            request_id=request_id,
            details=f"External scan trigger accepted from {source}",
        )

        # 5. Launch execution
        if async_execution:
            exec_thread = threading.Thread(
                target=self._execute_scan_and_email_chain,
                args=(request_id, source, source_ip, dry_run, send_empty_report),
                daemon=True,
                name=f"ExternalTriggerWorker-{request_id[:8]}",
            )
            exec_thread.start()

            return {
                "success": True,
                "status": "accepted",
                "message": "CyberScout scan accepted.",
                "request_id": request_id,
                "run_id": request_id,
            }, 202
        else:
            summary = self._execute_scan_and_email_chain(
                request_id=request_id,
                source=source,
                source_ip=source_ip,
                dry_run=dry_run,
                send_empty_report=send_empty_report,
            )
            return {
                "success": summary.get("scan_status") == "success",
                "status": "completed" if summary.get("scan_status") == "success" else "failed",
                "message": "CyberScout scan execution complete.",
                "request_id": request_id,
                "details": summary,
            }, 200 if summary.get("scan_status") == "success" else 500

    def _execute_scan_and_email_chain(
        self,
        request_id: str,
        source: str,
        source_ip: str,
        dry_run: bool = False,
        send_empty_report: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes the complete scan pipeline followed by server-side email dispatch chaining.
        """
        start_time = time.time()
        now_utc = datetime.now(timezone.utc)
        today_str = now_utc.strftime("%Y-%m-%d")
        now_iso = now_utc.isoformat()

        logger.info(f"================================================================")
        logger.info(f"[ExternalTrigger] Executing Scan Pipeline for request_id: {request_id}")
        logger.info(f"================================================================")

        self._log_audit(
            action="SCAN_STARTED",
            status="SUCCESS",
            source_ip=source_ip,
            request_id=request_id,
            details=f"Pipeline scan started by external trigger ({source})",
        )

        scan_result = {}
        scan_ok = False
        email_result = {"status": "skipped"}
        email_ok = False

        try:
            # 1. Execute Scan Pipeline
            scan_result = run_pipeline_once(
                dry_run=dry_run,
                send_email=False,  # Email is managed explicitly in next step
                db_manager=self.db_manager,
            )
            persistence_ok = scan_result.get("persistence_success", True) if not dry_run else True
            scan_ok = (scan_result.get("status") == "success") and persistence_ok

            if scan_ok:
                logger.info(f"[ExternalTrigger] Scan completed successfully (Items saved: {scan_result.get('saved', 0)}).")
                self.webhook_repo.update_status(
                    request_id=request_id,
                    status="completed",
                    execution_details=f"Scan successful. Saved: {scan_result.get('saved', 0)}",
                    email_status="pending",
                )
                self._log_audit(
                    action="SCAN_COMPLETED",
                    status="SUCCESS",
                    source_ip=source_ip,
                    request_id=request_id,
                    details=f"Scan completed successfully ({scan_result.get('saved', 0)} items persisted, duration: {scan_result.get('duration_seconds', 0)}s)",
                )
            else:
                logger.error(f"[ExternalTrigger] Scan failed or persistence failed: {scan_result}")
                self.webhook_repo.update_status(
                    request_id=request_id,
                    status="failed",
                    execution_details="Scan failed or database persistence error",
                    email_status="skipped",
                )
                self._log_audit(
                    action="SCAN_FAILED",
                    status="FAILED",
                    source_ip=source_ip,
                    request_id=request_id,
                    details="Pipeline execution failed or persistence error",
                )

        except Exception as e:
            logger.error(f"[ExternalTrigger] Unhandled exception during scan execution: {e}", exc_info=True)
            self.webhook_repo.update_status(
                request_id=request_id,
                status="failed",
                execution_details=str(e),
                email_status="skipped",
            )
            self._log_audit(
                action="SCAN_FAILED",
                status="FAILED",
                source_ip=source_ip,
                request_id=request_id,
                details=f"Scan crashed: {e}",
            )
            scan_ok = False

        # 2. Server-Side Email Dispatch Chaining (ONLY ON SCAN SUCCESS)
        if scan_ok and not dry_run:
            logger.info("[ExternalTrigger] Triggering server-side email dispatch via Brevo...")
            self._log_audit(
                action="EMAIL_DISPATCH_STARTED",
                status="SUCCESS",
                source_ip=source_ip,
                request_id=request_id,
                details="Server-side Brevo email digest dispatch initiated",
            )
            try:
                email_result = self.email_client.send_daily_digest(send_empty=send_empty_report)
                email_status = email_result.get("status") if isinstance(email_result, dict) else "failed"

                if email_status == "success":
                    email_ok = True
                    self.scheduler_repo.update_last_email_sent(today_str, pipeline_run_time=now_iso)
                    logger.info("[ExternalTrigger] Server-side email report sent successfully.")
                    provider_name = getattr(self.email_client, "provider_name", None) or getattr(getattr(self.email_client, "email_sender", None), "provider_name", "BrevoEmailProvider")
                    self.webhook_repo.update_status(
                        request_id=request_id,
                        status="completed",
                        execution_details=f"Scan completed. Daily email digest sent successfully via {provider_name}.",
                        email_status="success",
                    )
                    self._log_audit(
                        action="EMAIL_DISPATCHED",
                        status="SUCCESS",
                        source_ip=source_ip,
                        request_id=request_id,
                        details=f"Daily email digest sent successfully via {provider_name}",
                    )
                elif email_status == "skipped":
                    email_ok = True
                    self.scheduler_repo.update_last_email_sent(today_str, pipeline_run_time=now_iso)
                    logger.info("[ExternalTrigger] Email skipped (0 new opportunities and send_empty=False).")
                    self.webhook_repo.update_status(
                        request_id=request_id,
                        status="completed",
                        execution_details="Scan completed. Email digest skipped (0 new opportunities).",
                        email_status="skipped",
                    )
                    self._log_audit(
                        action="EMAIL_DISPATCHED",
                        status="SUCCESS",
                        source_ip=source_ip,
                        request_id=request_id,
                        details="Email digest skipped (0 new opportunities to report)",
                    )
                else:
                    email_ok = False
                    err_text = email_result.get("error", "Email dispatch error") if isinstance(email_result, dict) else "Unknown email error"
                    logger.error(f"[ExternalTrigger] Server-side email delivery failed: {err_text}")
                    self.webhook_repo.update_status(
                        request_id=request_id,
                        status="completed",
                        execution_details=f"Scan completed. Email dispatch failed: {err_text}",
                        email_status="failed",
                    )
                    self._log_audit(
                        action="EMAIL_DISPATCH_FAILED",
                        status="FAILED",
                        source_ip=source_ip,
                        request_id=request_id,
                        details=f"Email dispatch failed: {err_text}",
                    )
            except Exception as e:
                logger.error(f"[ExternalTrigger] Exception during server-side email dispatch: {e}", exc_info=True)
                self.webhook_repo.update_status(
                    request_id=request_id,
                    status="completed",
                    execution_details=f"Scan completed. Email dispatch exception: {e}",
                    email_status="failed",
                )
                self._log_audit(
                    action="EMAIL_DISPATCH_FAILED",
                    status="FAILED",
                    source_ip=source_ip,
                    request_id=request_id,
                    details=f"Email dispatch exception: {e}",
                )
                email_ok = False
        elif not scan_ok:
            logger.info("[ExternalTrigger] Scan was not successful. Server-side email dispatch bypassed.")
            self.webhook_repo.update_status(
                request_id=request_id,
                status="failed",
                execution_details="Scan failed. Email dispatch bypassed.",
                email_status="skipped",
            )

        duration = round(time.time() - start_time, 2)
        logger.info(f"[ExternalTrigger] Workflow complete for request_id '{request_id}' in {duration}s. (Scan: {'OK' if scan_ok else 'FAIL'}, Email: {'OK' if email_ok else 'FAIL/SKIPPED'})")
        logger.info(f"================================================================")

        return {
            "request_id": request_id,
            "scan_status": "success" if scan_ok else "failed",
            "email_status": "success" if email_ok else ("skipped" if not scan_ok else "failed"),
            "duration_seconds": duration,
            "scan_result": scan_result,
            "email_result": email_result,
        }

    def _log_audit(
        self,
        action: str,
        status: str,
        source_ip: str = "Unknown",
        request_id: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        """Logs structured security audit event for scheduler activity."""
        try:
            req_info = f" [request_id={request_id}]" if request_id else ""
            clean_details = f"{details or ''}{req_info}".strip()
            self.audit_repo.log_event(
                event_type="SCHEDULER",
                action=action,
                status=status,
                source_ip=source_ip,
                details=clean_details,
            )
        except Exception as e:
            logger.debug(f"Audit log writing note: {e}")
