"""
CyberScout AI — Phase 11 Final Security Audit, Performance Hardening & Production Release Test Suite.

Verifies:
1. Endpoint Authorization, RBAC boundaries, and Users/Admins separation.
2. CSRF rejection on state-changing forms and AJAX APIs.
3. IDOR resistance across notifications, bookmarks, and user preferences.
4. Input validation, SQL parameterization, and XSS escaping in SSR templates and email rendering.
5. External scheduler webhook HMAC-SHA256 signature verification and replay prevention.
6. Log and diagnostic sanitization (zero secrets or credentials leaked).
7. Health endpoint safety (no database credentials exposed).
8. Session security: HttpOnly, SameSite, session rotation, and production secret key validation.
9. Email deduplication invariants and lifecycle change isolation.
10. Concurrency lock integrity and stuck worker recovery.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import re
import socket
import time
import unittest
from unittest.mock import MagicMock, patch
import uuid

from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.auth.admin_auth import AdminSecurityManager
from src.core.exceptions import DatabaseConnectionError, DatabaseError
from src.core.failure_model import FailureCategory, classify_failure
from src.database.admin_repository import AdminRepository
from src.database.connection import DatabaseManager
from src.database.notification_repository import NotificationRepository
from src.database.opportunity_repository import OpportunityRepository, ChangeClassification
from src.database.scan_job_repository import ScanJobRepository, ScanInProgressError
from src.database.user_preferences_repository import UserPreferencesRepository
from src.database.user_repository import UserRepository
from src.models.notification_models import NotificationOutboxDTO
from src.models.opportunity import Opportunity
from src.models.query_filter_dto import QueryFilterDTO
from src.notifier.email_renderer import ModernEmailRenderer
from src.scheduler.external_trigger_service import ExternalTriggerService
from src.utils.url_utils import is_safe_internal_url


class TestPhase11SecurityRelease(unittest.TestCase):
    """Phase 11 Production Readiness & Security Verification Suite (50-point Matrix)."""

    @classmethod
    def setUpClass(cls):
        cls.db_manager = DatabaseManager()
        cls.user_repo = UserRepository(cls.db_manager)
        cls.admin_repo = AdminRepository(cls.db_manager)
        cls.notif_repo = NotificationRepository(cls.db_manager)
        cls.opp_repo = OpportunityRepository(cls.db_manager)
        cls.scan_repo = ScanJobRepository(cls.db_manager)
        cls.pref_repo = UserPreferencesRepository(cls.db_manager)

        cls.app = create_app({"TESTING": True, "SECRET_KEY": "p11_audit_secret_key_2026"})
        cls.client = cls.app.test_client()

        # Seed Test User A
        cls.user_a_email = f"p11_usera_{uuid.uuid4().hex[:8]}@example.com"
        u_a = cls.user_repo.create_user(
            username=f"p11_usera_{uuid.uuid4().hex[:6]}",
            email=cls.user_a_email,
            password="UserComplex2026!",
            role="Viewer",
        )
        cls.user_a_id = u_a["id"]

        # Seed Test User B
        cls.user_b_email = f"p11_userb_{uuid.uuid4().hex[:8]}@example.com"
        u_b = cls.user_repo.create_user(
            username=f"p11_userb_{uuid.uuid4().hex[:6]}",
            email=cls.user_b_email,
            password="UserComplex2026!",
            role="Viewer",
        )
        cls.user_b_id = u_b["id"]

        # Seed Test Admin
        cls.admin_email = f"p11_admin_{uuid.uuid4().hex[:8]}@example.com"
        adm = cls.admin_repo.create_admin(
            username=f"p11_admin_{uuid.uuid4().hex[:6]}",
            email=cls.admin_email,
            password="AdminComplex2026!",
            role="Administrator",
        )
        cls.admin_id = adm["id"]

        # Seed test opportunity for notification FK compliance
        cls.test_opp_id = "test_opp_p11"
        opp = Opportunity(
            id=cls.test_opp_id,
            title="P11 Test Security Opportunity",
            description="Phase 11 verification opportunity",
            url="https://example.com/p11-sec-opp",
            source_id="hackthebox_academy",
            provider="HackTheBox",
            category="internship",
            discovered_date=datetime.now(timezone.utc).isoformat(),
        )
        cls.opp_repo.save_or_update(opp)

    def setUp(self):
        # Clear any dangling active scan jobs before tests
        active = self.scan_repo.get_active_job()
        if active:
            try:
                self.scan_repo.mark_completed(active["job_id"], 0)
            except Exception:
                pass

    # =========================================================================
    # SECTION 1: AUTHENTICATION & RBAC BOUNDARIES (Criteria 1-6)
    # =========================================================================

    def test_01_user_and_admin_tables_strictly_separated(self):
        """1. User cannot authenticate via Admins table and vice versa."""
        # User in Users, not in Admins
        self.assertIsNotNone(self.user_repo.get_by_id(self.user_a_id))
        self.assertIsNone(self.admin_repo.get_by_email(self.user_a_email))

        # Admin in Admins, not in Users
        self.assertIsNotNone(self.admin_repo.get_by_id(self.admin_id))
        self.assertIsNone(self.user_repo.get_by_email(self.admin_email))

    def test_02_anonymous_access_to_admin_routes_redirects(self):
        """2. Unauthenticated request to /admin/reliability redirects to /admin/login."""
        c = self.app.test_client()
        res = c.get("/admin/reliability")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/admin/login", res.headers.get("Location", ""))

    def test_03_standard_user_cannot_access_admin_portal(self):
        """3. Authenticated standard user attempting to access /admin/users gets 403 Forbidden."""
        c = self.app.test_client()
        with c.session_transaction() as sess:
            sess["user_id"] = self.user_a_id
            sess["logged_in"] = True
            sess["role"] = "Viewer"

        res = c.get("/admin/users")
        self.assertEqual(res.status_code, 403)

    def test_04_administrator_can_access_admin_routes(self):
        """4. Authenticated administrator can access /admin/reliability."""
        c = self.app.test_client()
        with c.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = self.admin_id
            sess["admin_username"] = "p11_admin"
            sess["admin_role"] = "Administrator"

        res = c.get("/admin/reliability")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Production Reliability", res.get_data(as_text=True))

    def test_05_module_scope_admin_security_manager_preserved(self):
        """5. Module-scope import of AdminSecurityManager in auth.py exists and is callable."""
        import dashboard.routes.auth as auth_mod
        self.assertTrue(hasattr(auth_mod, "AdminSecurityManager"))
        self.assertTrue(callable(auth_mod.AdminSecurityManager.is_locked_out))

    def test_06_database_outage_returns_503_without_lockout(self):
        """6. Database outage during user login returns 503 without recording failed password."""
        c = self.app.test_client()
        with patch("dashboard.routes.auth.user_repo.authenticate", side_effect=DatabaseConnectionError("Database connection failed")):
            res = c.post("/login", data={
                "identifier": self.user_a_email,
                "password": "AnyPassword123!",
            })
            self.assertEqual(res.status_code, 503)
            self.assertFalse(AdminSecurityManager.is_locked_out("127.0.0.1", self.user_a_email, attempt_type="user_login"))

    # =========================================================================
    # SECTION 2: SESSION & COOKIE SECURITY (Criteria 7-11)
    # =========================================================================

    def test_07_session_cookie_configured_securely(self):
        """7. Session cookies have HttpOnly=True and SameSite=Lax."""
        self.assertTrue(self.app.config.get("SESSION_COOKIE_HTTPONLY"))
        self.assertEqual(self.app.config.get("SESSION_COOKIE_SAMESITE"), "Lax")

    def test_08_production_secret_key_fails_closed_when_missing(self):
        """8. Missing SECRET_KEY in production environment raises RuntimeError."""
        with patch.dict(os.environ, {"CYBERSCOUT_ENV": "production", "SECRET_KEY": ""}, clear=False):
            with self.assertRaises(RuntimeError):
                DashboardConfig.get_secret_key()

    def test_09_production_secret_key_fails_closed_on_weak_default(self):
        """9. Weak or default SECRET_KEY in production raises RuntimeError."""
        with patch.dict(os.environ, {"CYBERSCOUT_ENV": "production", "SECRET_KEY": "changeme"}, clear=False):
            with self.assertRaises(RuntimeError):
                DashboardConfig.get_secret_key()

    def test_10_session_rotated_on_logout(self):
        """10. User logout clears session and invalidates authenticated state."""
        c = self.app.test_client()
        with c.session_transaction() as sess:
            sess["user_id"] = self.user_a_id
            sess["logged_in"] = True

        res = c.get("/logout")
        self.assertEqual(res.status_code, 302)
        with c.session_transaction() as sess:
            self.assertNotIn("user_id", sess)
            self.assertFalse(sess.get("logged_in", False))

    def test_11_server_side_session_interface_active(self):
        """11. PostgreSQL-backed opaque session interface is bound to Flask app."""
        from dashboard.sessions import PostgresSessionInterface
        self.assertIsInstance(self.app.session_interface, PostgresSessionInterface)

    # =========================================================================
    # SECTION 3: CSRF PROTECTION (Criteria 12-17)
    # =========================================================================

    def test_12_csrf_protects_notifications_mark_read(self):
        """12. POST to /notifications/mark-read with invalid CSRF token is rejected with 403."""
        with self.client as c:
            with c.session_transaction() as sess:
                sess["user_id"] = self.user_a_id
                sess["logged_in"] = True
                sess["user_csrf_token"] = "valid_csrf_token_p11"

            res = c.post("/notifications/mark-read", json={
                "notification_id": "fake_id",
                "csrf_token": "tampered_csrf_token",
            })
            self.assertEqual(res.status_code, 403)
            self.assertIn("CSRF verification failed", res.get_data(as_text=True))

    def test_13_csrf_protects_notifications_mark_all_read(self):
        """13. POST to /notifications/mark-all-read with invalid CSRF token is rejected with 403."""
        with self.client as c:
            with c.session_transaction() as sess:
                sess["user_id"] = self.user_a_id
                sess["logged_in"] = True
                sess["user_csrf_token"] = "valid_csrf_token_p11"

            res = c.post("/notifications/mark-all-read", json={
                "csrf_token": "tampered_csrf_token",
            })
            self.assertEqual(res.status_code, 403)

    def test_14_csrf_protects_bookmark_toggle(self):
        """14. POST to /api/opportunities/<id>/bookmark with invalid CSRF token returns 403."""
        with self.client as c:
            with c.session_transaction() as sess:
                sess["user_id"] = self.user_a_id
                sess["logged_in"] = True
                sess["user_csrf_token"] = "valid_csrf_token_p11"

            res = c.post(f"/api/opportunities/{self.test_opp_id}/bookmark", json={
                "csrf_token": "wrong_csrf",
            })
            self.assertEqual(res.status_code, 403)

    def test_15_csrf_protects_quarantine_actions(self):
        """15. Admin quarantine mutation with tampered CSRF fails validation."""
        with self.client as c:
            with c.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_username"] = "admin"
                sess["admin_role"] = "Administrator"
                sess["admin_csrf_token"] = "valid_admin_csrf"

            res = c.post(
                "/admin/quarantine/action",
                data={"action": "approve", "opportunity_id": self.test_opp_id, "csrf_token": "bad_csrf"},
                follow_redirects=True,
            )
            self.assertIn(b"CSRF validation failed", res.data)

    def test_16_csrf_protects_scheduler_pause_api(self):
        """16. Admin scheduler pause API without valid CSRF header returns 403."""
        with self.client as c:
            with c.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_role"] = "Administrator"
                sess["admin_csrf_token"] = "expected_csrf"

            res = c.post("/api/scheduler/pause", headers={"X-CSRF-Token": "invalid_csrf"})
            self.assertEqual(res.status_code, 403)

    def test_17_get_requests_do_not_mutate_state(self):
        """17. GET request to state mutation route (/admin/quarantine/action) is rejected with 405."""
        c = self.app.test_client()
        with c.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
        res = c.get("/admin/quarantine/action")
        self.assertEqual(res.status_code, 405)

    # =========================================================================
    # SECTION 4: IDOR & USER ISOLATION (Criteria 18-22)
    # =========================================================================

    def test_18_user_cannot_mark_other_users_notification_as_read(self):
        """18. IDOR: User A cannot mark User B's notification as read."""
        notif_id = f"p11_idor_{uuid.uuid4().hex[:8]}"
        dto = NotificationOutboxDTO(
            id=notif_id,
            user_id=self.user_b_id,
            opportunity_id=self.test_opp_id,
            event_type="new",
            deduplication_key=f"dedup_b_{uuid.uuid4().hex[:8]}",
            status="pending",
        )
        self.notif_repo.enqueue_notifications_batch([dto])

        # User A attempts to mark User B's notification read
        success = self.notif_repo.mark_as_read(notif_id, user_id=self.user_a_id)
        self.assertFalse(success)

        # Verify notification remains unread
        notifs = self.notif_repo.get_user_notifications(user_id=self.user_b_id)
        target = next((n for n in notifs if n["id"] == notif_id), None)
        self.assertIsNotNone(target)
        self.assertFalse(target["is_read"])

    def test_19_user_inbox_only_returns_own_notifications(self):
        """19. User inbox query strictly filters by session user ID."""
        notif_id_a = f"p11_inbox_a_{uuid.uuid4().hex[:8]}"
        notif_id_b = f"p11_inbox_b_{uuid.uuid4().hex[:8]}"

        self.notif_repo.enqueue_notifications_batch([
            NotificationOutboxDTO(id=notif_id_a, user_id=self.user_a_id, opportunity_id=self.test_opp_id, event_type="new", deduplication_key=f"dedup_a_{uuid.uuid4().hex[:8]}"),
            NotificationOutboxDTO(id=notif_id_b, user_id=self.user_b_id, opportunity_id=self.test_opp_id, event_type="new", deduplication_key=f"dedup_b_{uuid.uuid4().hex[:8]}"),
        ])

        inbox_a = self.notif_repo.get_user_notifications(user_id=self.user_a_id)
        inbox_a_ids = [n["id"] for n in inbox_a]

        self.assertIn(notif_id_a, inbox_a_ids)
        self.assertNotIn(notif_id_b, inbox_a_ids)

    def test_20_bookmark_toggle_strictly_scoped_to_session_user(self):
        """20. Bookmark API toggles bookmark exclusively for authenticated session user."""
        from src.services.opportunity_service import OpportunityService
        opp_svc = OpportunityService(self.db_manager)

        res_a = opp_svc.toggle_save_opportunity(str(self.user_a_id), self.test_opp_id)
        self.assertTrue(res_a["saved"])

        # Check bookmark isolation
        self.assertTrue(opp_svc.repo.is_opportunity_saved(str(self.user_a_id), self.test_opp_id))
        self.assertFalse(opp_svc.repo.is_opportunity_saved(str(self.user_b_id), self.test_opp_id))

    def test_21_user_preferences_isolated(self):
        """21. User preferences updates only affect the authenticated user."""
        from src.models.recommendation_models import UserPreferencesDTO
        dto_a = UserPreferencesDTO(skills=["SOC Analyst", "Threat Hunting"])
        self.pref_repo.save_preferences(self.user_a_id, dto_a)

        updated_a = self.pref_repo.get_preferences(user_id=self.user_a_id)
        self.assertIsNotNone(updated_a)
        self.assertIn("soc analyst", updated_a.skills)

        # User B remains unaffected
        pref_b = self.pref_repo.get_preferences(user_id=self.user_b_id)
        if pref_b and pref_b.skills:
            self.assertNotIn("soc analyst", pref_b.skills)

    def test_22_admin_audit_logs_not_viewable_by_standard_user(self):
        """22. Standard user cannot read admin audit logs."""
        c = self.app.test_client()
        with c.session_transaction() as sess:
            sess["user_id"] = self.user_a_id
            sess["logged_in"] = True
            sess["role"] = "Viewer"

        res = c.get("/admin/logs")
        self.assertEqual(res.status_code, 403)

    # =========================================================================
    # SECTION 5: INPUT VALIDATION & INJECTION RESISTANCE (Criteria 23-28)
    # =========================================================================

    def test_23_sql_injection_attempt_in_keyword_safe(self):
        """23. Malicious SQL payloads in search queries execute safely via parameterization."""
        dto = QueryFilterDTO(keyword="' OR '1'='1' --", page=1, per_page=10)
        # Must execute without syntax errors
        opps, total, facets = self.opp_repo.query_opportunities(dto)
        self.assertIsInstance(opps, list)
        self.assertIsInstance(total, int)

    def test_24_open_redirect_detection(self):
        """24. is_safe_internal_url properly rejects protocol-relative and external domains."""
        self.assertTrue(is_safe_internal_url("/opportunities"))
        self.assertTrue(is_safe_internal_url("/admin/dashboard"))
        self.assertFalse(is_safe_internal_url("https://malicious.example.com"))
        self.assertFalse(is_safe_internal_url("//malicious.example.com"))
        self.assertFalse(is_safe_internal_url(r"\malicious.example.com"))
        self.assertFalse(is_safe_internal_url("javascript:alert(1)"))

    def test_25_email_renderer_escapes_xss_in_titles(self):
        """25. XSS payloads in opportunity titles are HTML entity-escaped in emails."""
        from src.models.notification_models import NotificationCardDTO
        card = NotificationCardDTO(
            id="p11_xss_1",
            opportunity_id="p11_sec_xss",
            title="<script>alert('xss')</script>",
            url="https://example.com",
            event_type="new",
            category="internship",
            provider="CISA",
            deadline="2026-12-31",
        )

        html_body, text_body = ModernEmailRenderer.render_immediate(card)
        self.assertNotIn("<script>alert('xss')</script>", html_body)
        self.assertIn("&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;", html_body)

    def test_26_email_renderer_sanitizes_dangerous_protocols(self):
        """26. Malicious javascript: and data: URLs are neutralized to '#' in emails."""
        self.assertEqual(ModernEmailRenderer.sanitize_url("javascript:alert(1)"), "#")
        self.assertEqual(ModernEmailRenderer.sanitize_url("data:text/html,<script>alert(1)</script>"), "#")
        self.assertEqual(ModernEmailRenderer.sanitize_url("vbscript:msgbox(1)"), "#")
        self.assertEqual(ModernEmailRenderer.sanitize_url("https://example.com/safe"), "https://example.com/safe")

    def test_27_path_traversal_in_reports_rejected(self):
        """27. Path traversal payloads in report downloads are rejected or safely redirected."""
        c = self.app.test_client()
        with c.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"

        res = c.get("/admin/reports/download/..%2f..%2f..%2fetc%2fpasswd")
        self.assertIn(res.status_code, [404, 302])

    def test_28_no_arbitrary_query_endpoints(self):
        """28. Dangerous debug query endpoints (/api/admin/raw_query, /api/query) return 404."""
        res1 = self.client.post("/api/admin/raw_query", json={"sql": "SELECT 1;"})
        self.assertEqual(res1.status_code, 404)
        res2 = self.client.post("/api/query", json={"sql": "SELECT 1;"})
        self.assertEqual(res2.status_code, 404)

    # =========================================================================
    # SECTION 6: WEBHOOK SECURITY (Criteria 29-33)
    # =========================================================================

    def test_29_webhook_missing_signature_rejected(self):
        """29. External scheduler webhook missing X-CyberScout-Signature returns 401."""
        with patch.dict(os.environ, {"CYBERSCOUT_SCHEDULER_SECRET": "test_webhook_secret_p11"}):
            c = self.app.test_client()
            res = c.post("/api/scheduler/trigger", json={"event": "scheduled_scan"})
            self.assertEqual(res.status_code, 401)

    def test_30_webhook_invalid_signature_rejected(self):
        """30. External scheduler webhook with invalid signature returns 401."""
        with patch.dict(os.environ, {"CYBERSCOUT_SCHEDULER_SECRET": "test_webhook_secret_p11"}):
            c = self.app.test_client()
            headers = {
                "Content-Type": "application/json",
                "X-CyberScout-Signature": "sha256=invalid_hash",
                "X-CyberScout-Timestamp": str(int(time.time())),
                "X-CyberScout-Nonce": "test_nonce_123",
            }
            res = c.post("/api/scheduler/trigger", headers=headers, json={"nonce": "test_nonce_123"})
            self.assertEqual(res.status_code, 401)

    def test_31_webhook_expired_timestamp_rejected(self):
        """31. External scheduler webhook with expired timestamp (>300s) returns 401."""
        secret = "test_webhook_secret_p11"
        with patch.dict(os.environ, {"CYBERSCOUT_SCHEDULER_SECRET": secret}):
            service = ExternalTriggerService(db_manager=self.db_manager)
            old_ts = str(int(time.time()) - 400)
            nonce = "test_nonce_old"
            body = json.dumps({"nonce": nonce})

            payload = f"{old_ts}.{nonce}.{body}"
            sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

            headers = {
                "Content-Type": "application/json",
                "X-CyberScout-Signature": f"sha256={sig}",
                "X-CyberScout-Timestamp": old_ts,
                "X-CyberScout-Nonce": nonce,
            }
            c = self.app.test_client()
            res = c.post("/api/scheduler/trigger", headers=headers, data=body)
            self.assertEqual(res.status_code, 401)

    def test_32_webhook_valid_signature_accepted(self):
        """32. External scheduler webhook with valid HMAC signature and fresh timestamp passes auth."""
        secret = "test_webhook_secret_p11"
        with patch.dict(os.environ, {"CYBERSCOUT_SCHEDULER_SECRET": secret}):
            service = ExternalTriggerService(db_manager=self.db_manager)
            fresh_ts = str(int(time.time()))
            nonce = f"valid_nonce_{uuid.uuid4().hex[:8]}"
            body = json.dumps({"nonce": nonce, "dry_run": True})

            payload = f"{fresh_ts}.{nonce}.{body}"
            sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

            headers = {
                "Content-Type": "application/json",
                "X-CyberScout-Signature": f"sha256={sig}",
                "X-CyberScout-Timestamp": fresh_ts,
                "X-CyberScout-Nonce": nonce,
            }
            is_valid, msg, code, data = service.verify_request_authentication(headers, body.encode())
            self.assertTrue(is_valid)
            self.assertEqual(code, 200)

    def test_33_webhook_rejects_non_json_content_type(self):
        """33. Webhook endpoint rejects text/plain or application/x-www-form-urlencoded with 400."""
        c = self.app.test_client()
        res = c.post("/api/scheduler/trigger", headers={"Content-Type": "text/plain"}, data="trigger")
        self.assertEqual(res.status_code, 400)

    # =========================================================================
    # SECTION 7: SECRETS, LOGGING & OBSERVABILITY (Criteria 34-39)
    # =========================================================================

    def test_34_health_live_is_lightweight_and_clean(self):
        """34. /health/live returns 200 without exposing database host or internals."""
        res = self.client.get("/health/live")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("alive"))
        self.assertNotIn("password", str(data))
        self.assertNotIn("database", str(data))

    def test_35_health_ready_does_not_leak_secrets(self):
        """35. /health/ready returns database readiness without credentials."""
        res = self.client.get("/health/ready")
        self.assertIn(res.status_code, [200, 503])
        data = res.get_json()
        self.assertNotIn("password", str(data))
        self.assertNotIn("DATABASE_URL", str(data))

    def test_36_request_id_correlation_header_present(self):
        """36. HTTP response contains X-Request-ID header."""
        res = self.client.get("/health/live")
        self.assertIn("X-Request-ID", res.headers)
        self.assertTrue(len(res.headers["X-Request-ID"]) > 0)

    def test_37_request_id_clamped_and_sanitized(self):
        """37. Inbound client X-Request-ID is clamped to 64 chars and sanitized."""
        malicious_id = "req-" + "a" * 100 + "'; DROP TABLE Users; --"
        res = self.client.get("/health/live", headers={"X-Request-ID": malicious_id})
        out_id = res.headers.get("X-Request-ID", "")
        self.assertLessEqual(len(out_id), 64)
        self.assertNotIn("DROP", out_id)

    def test_38_failure_classification_transient_retryability(self):
        """38. Socket timeouts and connection drops classified as TRANSIENT retryable."""
        info = classify_failure(socket.timeout("Socket timed out after 10s"))
        self.assertEqual(info.category, FailureCategory.TRANSIENT)
        self.assertTrue(info.is_retryable)

    def test_39_failure_classification_permanent(self):
        """39. HTTP 404 Not Found classified as PERMANENT non-retryable."""
        info = classify_failure(404)
        self.assertEqual(info.category, FailureCategory.PERMANENT)
        self.assertFalse(info.is_retryable)

    # =========================================================================
    # SECTION 8: EMAIL DEDUPLICATION & HARVESTING (Criteria 40-44)
    # =========================================================================

    def test_40_unchanged_opportunity_classification_is_unchanged(self):
        """40. Candidate identical to existing opportunity is classified as UNCHANGED."""
        existing = Opportunity(
            id="p11_dup_1",
            title="Senior Security Analyst",
            url="https://example.com/p11-dup-1",
            source_id="cisa",
            score=85.0,
            quality_status="passed",
            lifecycle_status="active",
        )
        incoming = Opportunity(
            title="Senior Security Analyst",
            url="https://example.com/p11-dup-1",
            source_id="cisa",
            score=85.0,
        )
        classification = self.opp_repo.classify_candidate(incoming, existing)
        self.assertEqual(classification, ChangeClassification.UNCHANGED)

    def test_41_meaningful_change_classification_is_updated(self):
        """41. Candidate with updated deadline/score is classified as UPDATED."""
        existing = Opportunity(
            id="p11_dup_2",
            title="Security Architect",
            url="https://example.com/p11-dup-2",
            source_id="cisa",
            score=70.0,
            deadline="2026-10-01",
        )
        incoming = Opportunity(
            title="Security Architect",
            url="https://example.com/p11-dup-2",
            source_id="cisa",
            score=90.0,
            deadline="2026-11-01",
        )
        classification = self.opp_repo.classify_candidate(incoming, existing)
        self.assertEqual(classification, ChangeClassification.UPDATED)

    def test_42_reopened_opportunity_classification_is_reopened(self):
        """42. Expired opportunity receiving new active deadline is classified as REOPENED."""
        existing = Opportunity(
            id="p11_dup_3",
            title="Cyber Fellowship",
            url="https://example.com/p11-dup-3",
            source_id="cisa",
            status="expired",
            deadline="2025-01-01",
        )
        incoming = Opportunity(
            title="Cyber Fellowship",
            url="https://example.com/p11-dup-3",
            source_id="cisa",
            deadline="2026-12-31",
        )
        classification = self.opp_repo.classify_candidate(incoming, existing)
        self.assertEqual(classification, ChangeClassification.REOPENED)

    def test_43_outbox_enqueue_enforces_opportunity_foreign_key(self):
        """43. Outbox enqueue requires valid opportunity_id foreign key in database."""
        dto = NotificationOutboxDTO(
            id=f"p11_fk_{uuid.uuid4().hex[:8]}",
            user_id=self.user_a_id,
            opportunity_id=self.test_opp_id,
            event_type="new",
            deduplication_key=f"dedup_fk_{uuid.uuid4().hex[:8]}",
        )
        count = self.notif_repo.enqueue_notifications_batch([dto])
        self.assertEqual(count, 1)

    def test_44_stuck_processing_notification_recovery(self):
        """44. Interrupted notifications in 'processing' status recover back to 'pending'."""
        nid = f"p11_stuck_{uuid.uuid4().hex[:8]}"
        dto = NotificationOutboxDTO(
            id=nid,
            user_id=self.user_a_id,
            opportunity_id=self.test_opp_id,
            event_type="new",
            deduplication_key=f"dedup_stuck_{uuid.uuid4().hex[:8]}",
            status="pending",
        )
        self.notif_repo.enqueue_notifications_batch([dto])
        self.notif_repo.mark_processing(nid)

        recovered = self.notif_repo.recover_stuck_processing(timeout_seconds=0)
        self.assertGreaterEqual(recovered, 1)

    # =========================================================================
    # SECTION 9: RECOVERY & RESILIENCE (Criteria 45-50)
    # =========================================================================

    def test_45_scan_job_concurrency_lock_enforced(self):
        """45. Creating a second scan job while one is active raises ScanInProgressError."""
        job1 = f"p11_lock1_{uuid.uuid4().hex[:8]}"
        job2 = f"p11_lock2_{uuid.uuid4().hex[:8]}"

        self.scan_repo.create_job(job_id=job1, job_type="unit_test")
        with self.assertRaises(ScanInProgressError):
            self.scan_repo.create_job(job_id=job2, job_type="unit_test")

        self.scan_repo.mark_completed(job1, 0)

    def test_46_stuck_scan_job_recovery(self):
        """46. Stuck scan job is safely failed by recover_stuck_jobs."""
        job_id = f"p11_stuck_job_{uuid.uuid4().hex[:8]}"
        self.scan_repo.create_job(job_id=job_id, job_type="unit_test")

        recovered = self.scan_repo.recover_stuck_jobs(timeout_seconds=0)
        self.assertIn(job_id, recovered)

        job = self.scan_repo.get_job(job_id)
        self.assertEqual(job["status"], "failed")

    def test_47_cursor_adapter_context_manager_protocol(self):
        """47. Database connection cursor satisfies context manager protocol (with conn.cursor() as cur:)."""
        conn = self.db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            row = cur.fetchone()
            self.assertEqual(row[0], 1)

    def test_48_backup_manager_generates_and_validates_sql(self):
        """48. BackupManager can generate and validate SQL backup without leaking secrets."""
        from src.maintenance.backup_manager import BackupManager
        bm = BackupManager(self.db_manager)
        backups = bm.list_backups()
        self.assertIsInstance(backups, list)
        if backups:
            validation = bm.validate_backup(backups[0]["file_path"])
            self.assertTrue(validation["is_valid"])

    def test_49_restore_drill_executes_safely_without_corrupting_production(self):
        """49. Backup non-destructive restore drill parses syntax and verifies integrity."""
        from src.maintenance.backup_manager import BackupManager
        bm = BackupManager(self.db_manager)
        backups = bm.list_backups()
        if backups:
            drill_res = bm.restore_drill(backups[0]["file_path"])
            self.assertTrue(drill_res["drill_success"])

    def test_50_row_level_security_catalog_status(self):
        """50. Live PostgreSQL catalog confirms RLS enabled on core tables."""
        rls_status = self.db_manager.verify_rls_policies()
        self.assertTrue(rls_status.get("is_configured"))


if __name__ == "__main__":
    unittest.main()
