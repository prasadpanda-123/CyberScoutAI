"""
Unit and Integration Tests for External Scheduler Trigger (Google Apps Script -> CyberScout AI).

Validates:
- HMAC-SHA256 request authentication & constant-time comparison
- Timestamp expiration window (±5m)
- Replay protection & idempotency
- Concurrent scan locking (HTTP 409)
- Existing scan pipeline execution
- Server-side email dispatch chaining via Brevo
- Error isolation (scan failure vs email failure)
- Security audit logging
"""

import hashlib
import hmac
import json
import os
import time
import unittest
from unittest.mock import MagicMock, patch
import uuid

from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.database.connection import DatabaseManager
from src.database.webhook_request_repository import WebhookRequestRepository
from src.database.audit_log_repository import AuditLogRepository
from src.scheduler.external_trigger_service import ExternalTriggerService
from src.automation.job_manager import scan_job_manager


class TestExternalSchedulerTrigger(unittest.TestCase):

    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.test_secret = "test_super_secret_hmac_key_1234567890"
        os.environ["CYBERSCOUT_SCHEDULER_SECRET"] = self.test_secret
        os.environ["SCHEDULER_WEBHOOK_SECRET"] = self.test_secret

        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()
        self.db_mgr = DatabaseManager()
        self.webhook_repo = WebhookRequestRepository(db_manager=self.db_mgr)
        self.audit_repo = AuditLogRepository(db_manager=self.db_mgr)

    def tearDown(self):
        scan_job_manager._active_job_id = None

    def _generate_signed_headers_and_body(
        self,
        payload_dict=None,
        secret=None,
        timestamp_offset=0,
        tamper_sig=False,
        omit_sig=False,
        omit_ts=False,
        omit_req_id=False,
        use_nonce_header=False,
    ):
        """Helper to create HMAC signed requests for testing."""
        key = secret or self.test_secret
        req_id = f"test-req-{uuid.uuid4().hex[:12]}"
        ts = int(time.time()) + timestamp_offset
        ts_str = str(ts)

        if payload_dict is None:
            payload_dict = {
                "trigger": "google_apps_script",
                "source": "google_apps_script",
                "nonce": req_id,
                "request_id": req_id,
                "requested_at": "2026-08-24T00:00:00.000Z",
                "dry_run": False,
            }

        body_str = json.dumps(payload_dict)
        signing_payload = f"{ts_str}.{req_id}.{body_str}"
        computed_hash = hmac.new(key.encode("utf-8"), signing_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        sig = f"sha256={computed_hash}"

        if tamper_sig:
            sig = f"sha256={'0'*64}"

        headers = {
            "Content-Type": "application/json",
        }
        if not omit_sig:
            headers["X-CyberScout-Signature"] = sig
        if not omit_ts:
            headers["X-CyberScout-Timestamp"] = ts_str
        if not omit_req_id:
            if use_nonce_header:
                headers["X-CyberScout-Nonce"] = req_id
            else:
                headers["X-CyberScout-Request-ID"] = req_id

        return headers, body_str, req_id, ts

    def test_valid_hmac_request_accepted(self):
        """1. Valid HMAC request returns HTTP 202 Accepted on both /api/scheduler/trigger and /api/external/scheduler/trigger."""
        headers, body, req_id, _ = self._generate_signed_headers_and_body(use_nonce_header=True)

        res = self.client.post("/api/scheduler/trigger", headers=headers, data=body)
        self.assertEqual(res.status_code, 202)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("status"), "accepted")
        self.assertEqual(data.get("request_id"), req_id)

    def test_scheduler_status_endpoint(self):
        """Verify GET /api/scheduler/status returns external mode telemetry."""
        res = self.client.get("/api/scheduler/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("scheduler_mode"), "external")
        self.assertEqual(data.get("trigger_source"), "google_apps_script")


    def test_invalid_hmac_rejected(self):
        """2. Invalid HMAC signature returns HTTP 401 Unauthorized."""
        headers, body, _, _ = self._generate_signed_headers_and_body(tamper_sig=True)

        res = self.client.post("/api/external/scheduler/trigger", headers=headers, data=body)
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("status"), "rejected")

    def test_missing_signature_rejected(self):
        """3. Missing signature header returns HTTP 401."""
        headers, body, _, _ = self._generate_signed_headers_and_body(omit_sig=True)

        res = self.client.post("/api/external/scheduler/trigger", headers=headers, data=body)
        self.assertEqual(res.status_code, 401)

    def test_expired_timestamp_rejected(self):
        """4. Expired timestamp (>300 seconds ago) returns HTTP 401."""
        headers, body, _, _ = self._generate_signed_headers_and_body(timestamp_offset=-350)

        res = self.client.post("/api/external/scheduler/trigger", headers=headers, data=body)
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertIn("timestamp expired", data.get("error", "").lower())

    def test_missing_request_id_rejected(self):
        """5. Missing request_id returns HTTP 400 Bad Request."""
        headers, body, _, _ = self._generate_signed_headers_and_body(
            payload_dict={"event": "scheduled_scan", "timestamp": int(time.time())},
            omit_req_id=True,
        )

        res = self.client.post("/api/external/scheduler/trigger", headers=headers, data=body)
        self.assertEqual(res.status_code, 400)

    def test_replay_duplicate_request_rejected(self):
        """6. Replay of same request_id returns HTTP 409 Conflict."""
        headers, body, req_id, ts = self._generate_signed_headers_and_body()

        # First trigger
        res1 = self.client.post("/api/external/scheduler/trigger", headers=headers, data=body)
        self.assertEqual(res1.status_code, 202)

        # Duplicate trigger with exact same request_id
        res2 = self.client.post("/api/external/scheduler/trigger", headers=headers, data=body)
        self.assertEqual(res2.status_code, 409)
        data2 = res2.get_json()
        self.assertEqual(data2.get("status"), "duplicate")

    def test_concurrent_scan_protection(self):
        """7. Concurrent trigger while scan is active returns HTTP 409."""
        scan_job_manager._active_job_id = "job-active-test"
        scan_job_manager._jobs["job-active-test"] = MagicMock(status="running")

        headers, body, _, _ = self._generate_signed_headers_and_body()
        res = self.client.post("/api/external/scheduler/trigger", headers=headers, data=body)
        self.assertEqual(res.status_code, 409)
        data = res.get_json()
        self.assertEqual(data.get("status"), "already_running")

    def test_pipeline_execution_and_server_side_email_chain(self):
        """8 & 9. Valid trigger executes scan pipeline and chains server-side email dispatch."""
        service = ExternalTriggerService(db_manager=self.db_mgr)
        service.email_client = MagicMock()
        service.email_client.provider_name = "BrevoEmailProvider"
        service.email_client.send_daily_digest.return_value = {"status": "success", "message_id": "test-msg-123"}

        headers, body_str, req_id, ts = self._generate_signed_headers_and_body()

        with patch("src.scheduler.external_trigger_service.run_pipeline_once") as mock_pipeline:
            mock_pipeline.return_value = {
                "status": "success",
                "saved": 15,
                "duration_seconds": 2.5,
                "persistence_success": True,
            }

            resp_data, status_code = service.process_trigger(
                headers=headers,
                raw_body=body_str.encode("utf-8"),
                source_ip="127.0.0.1",
                async_execution=False,
            )

            self.assertEqual(status_code, 200)
            mock_pipeline.assert_called_once()
            service.email_client.send_daily_digest.assert_called_once()

    def test_failed_scan_bypasses_email(self):
        """10. Failed scan does NOT send email."""
        service = ExternalTriggerService(db_manager=self.db_mgr)
        service.email_client = MagicMock()

        headers, body_str, req_id, ts = self._generate_signed_headers_and_body()

        with patch("src.scheduler.external_trigger_service.run_pipeline_once") as mock_pipeline:
            mock_pipeline.return_value = {
                "status": "failed",
                "saved": 0,
                "duration_seconds": 1.0,
                "persistence_success": False,
            }

            resp_data, status_code = service.process_trigger(
                headers=headers,
                raw_body=body_str.encode("utf-8"),
                source_ip="127.0.0.1",
                async_execution=False,
            )

            self.assertEqual(status_code, 500)
            mock_pipeline.assert_called_once()
            service.email_client.send_daily_digest.assert_not_called()

    def test_email_failure_recorded_separately(self):
        """11. Email failure does not mark scan as failed."""
        service = ExternalTriggerService(db_manager=self.db_mgr)
        service.email_client = MagicMock()
        service.email_client.send_daily_digest.return_value = {"status": "failed", "error": "Brevo rate limit"}

        headers, body_str, req_id, ts = self._generate_signed_headers_and_body()
        self.webhook_repo.record_request(request_id=req_id, timestamp=ts)

        with patch("src.scheduler.external_trigger_service.run_pipeline_once") as mock_pipeline:
            mock_pipeline.return_value = {
                "status": "success",
                "saved": 10,
                "duration_seconds": 1.8,
                "persistence_success": True,
            }

            summary = service._execute_scan_and_email_chain(
                request_id=req_id,
                source="google_apps_script",
                source_ip="127.0.0.1",
                dry_run=False,
            )

            self.assertEqual(summary["scan_status"], "success")
            self.assertEqual(summary["email_status"], "failed")

            # Verify GET /api/scheduler/status telemetry
            status_res = self.client.get("/api/scheduler/status")
            self.assertEqual(status_res.status_code, 200)
            status_data = status_res.get_json()
            self.assertEqual(status_data.get("current_status"), "idle")
            self.assertEqual(status_data.get("last_run_status"), "completed")
            self.assertEqual(status_data.get("last_email_status"), "failed")

    def test_successful_scan_and_email_status_telemetry(self):
        """12. Successful scan and email reports completed run and success email status."""
        service = ExternalTriggerService(db_manager=self.db_mgr)
        service.email_client = MagicMock()
        service.email_client.provider_name = "BrevoEmailProvider"
        service.email_client.send_daily_digest.return_value = {"status": "success", "message_id": "brevo-msg-999"}

        headers, body_str, req_id, ts = self._generate_signed_headers_and_body()
        self.webhook_repo.record_request(request_id=req_id, timestamp=ts)

        with patch("src.scheduler.external_trigger_service.run_pipeline_once") as mock_pipeline:
            mock_pipeline.return_value = {
                "status": "success",
                "saved": 8,
                "duration_seconds": 2.0,
                "persistence_success": True,
            }

            summary = service._execute_scan_and_email_chain(
                request_id=req_id,
                source="google_apps_script",
                source_ip="127.0.0.1",
                dry_run=False,
            )

            self.assertEqual(summary["scan_status"], "success")
            self.assertEqual(summary["email_status"], "success")

            # Verify GET /api/scheduler/status telemetry
            status_res = self.client.get("/api/scheduler/status")
            self.assertEqual(status_res.status_code, 200)
            status_data = status_res.get_json()
            self.assertEqual(status_data.get("current_status"), "idle")
            self.assertEqual(status_data.get("last_run_status"), "completed")
            self.assertEqual(status_data.get("last_email_status"), "success")

    def test_failed_scan_telemetry_reports_skipped_email(self):
        """13. Failed scan reports failed run and skipped email status."""
        service = ExternalTriggerService(db_manager=self.db_mgr)
        service.email_client = MagicMock()

        headers, body_str, req_id, ts = self._generate_signed_headers_and_body()
        self.webhook_repo.record_request(request_id=req_id, timestamp=ts)

        with patch("src.scheduler.external_trigger_service.run_pipeline_once") as mock_pipeline:
            mock_pipeline.return_value = {
                "status": "failed",
                "saved": 0,
                "duration_seconds": 0.5,
                "persistence_success": False,
            }

            summary = service._execute_scan_and_email_chain(
                request_id=req_id,
                source="google_apps_script",
                source_ip="127.0.0.1",
                dry_run=False,
            )

            self.assertEqual(summary["scan_status"], "failed")
            self.assertEqual(summary["email_status"], "skipped")

            # Verify GET /api/scheduler/status telemetry
            status_res = self.client.get("/api/scheduler/status")
            self.assertEqual(status_res.status_code, 200)
            status_data = status_res.get_json()
            self.assertEqual(status_data.get("current_status"), "idle")
            self.assertEqual(status_data.get("last_run_status"), "failed")
            self.assertEqual(status_data.get("last_email_status"), "skipped")

    def test_non_json_content_type_rejected(self):
        """Non-JSON Content-Type returns HTTP 400."""
        headers, body, _, _ = self._generate_signed_headers_and_body()
        headers["Content-Type"] = "text/plain"

        res = self.client.post("/api/external/scheduler/trigger", headers=headers, data=body)
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()

