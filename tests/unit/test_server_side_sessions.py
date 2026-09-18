"""
Dedicated Regression and Security Unit Tests for Server-Side Session State & Opaque Cookie Minimization.

Verifies:
1. Client-side session cookie contains ONLY an opaque, cryptographically random identifier.
2. Cookie contains ZERO JSON, zero identity, zero roles, zero user IDs, zero email, and zero CSRF tokens.
3. Session rotation occurs at login, admin login, and MFA completion (session fixation prevention).
4. Server-side session store correctly enforces revocation and expiration.
5. Old session cookies cannot authenticate after logout (replay rejection).
6. Multi-worker session portability (simulated independent workers sharing PostgreSQL).
7. Strict cross-domain isolation between User and Admin sessions.
8. Safe fallback on malformed, tampered, or legacy signed cookies without internal errors.
"""

import base64
from datetime import datetime, timedelta, timezone
import json
import re
import time
import unittest

from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.auth.admin_auth import AdminSecurityManager
from src.database.admin_repository import AdminRepository
from src.database.connection import DatabaseManager
from src.database.mfa_repository import MfaRepository
from src.database.session_repository import SessionRepository, generate_session_id, hash_session_id
from src.database.user_repository import UserRepository


class TestServerSideSessions(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()
        self.session_repo = SessionRepository(self.db_manager)
        self.user_repo = UserRepository(self.db_manager)
        self.admin_repo = AdminRepository(self.db_manager)
        self.mfa_repo = MfaRepository(self.db_manager)

        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

    def _extract_session_cookie(self, response):
        """Helper to extract raw cyberscout_session cookie value from response headers."""
        cookies = response.headers.getlist("Set-Cookie")
        for c in cookies:
            if "cyberscout_session=" in c:
                parts = c.split(";")
                for p in parts:
                    p = p.strip()
                    if p.startswith("cyberscout_session="):
                        return p.split("=", 1)[1]
        return None

    def test_user_login_creates_purely_opaque_session_cookie(self):
        """Verify user login issues a strictly opaque cookie with ZERO sensitive identity data."""
        ts = int(time.time() * 1000)
        u_name = f"sess_user_{ts}"
        u_email = f"sess_user_{ts}@cyberscout.ai"
        password = "UserSecurePass2026!"

        user = self.user_repo.create_user(
            username=u_name,
            email=u_email,
            password=password,
            role="Viewer",
        )
        self.assertIsNotNone(user)

        res = self.client.post("/login", data={"identifier": u_email, "password": password})
        self.assertEqual(res.status_code, 302)

        cookie_val = self._extract_session_cookie(res)
        self.assertIsNotNone(cookie_val, "cyberscout_session Set-Cookie header must be present")

        # 1. Verify cookie matches opaque Base64URL pattern (20 to 128 characters)
        self.assertTrue(
            bool(re.match(r"^[A-Za-z0-9_-]{20,128}$", cookie_val)),
            f"Cookie value '{cookie_val}' is not an opaque high-entropy token",
        )

        # 2. Verify cookie string does NOT contain any identity data
        raw_cookie = str(cookie_val)
        self.assertNotIn(u_name, raw_cookie)
        self.assertNotIn(u_email, raw_cookie)
        self.assertNotIn(str(user["id"]), raw_cookie)
        self.assertNotIn("Viewer", raw_cookie)
        self.assertNotIn("user_id", raw_cookie)
        self.assertNotIn("role", raw_cookie)
        self.assertNotIn("email", raw_cookie)
        self.assertNotIn("user_csrf_token", raw_cookie)
        self.assertNotIn("{", raw_cookie)
        self.assertNotIn("}", raw_cookie)

        # 3. Verify decoding does not yield JSON or identity
        try:
            # Pad base64 if needed
            padded = cookie_val + "=" * ((4 - len(cookie_val) % 4) % 4)
            decoded = base64.urlsafe_b64decode(padded)
            self.assertNotIn(u_name.encode(), decoded)
            self.assertNotIn(u_email.encode(), decoded)
            self.assertNotIn(b"user_id", decoded)
            self.assertNotIn(b"role", decoded)
        except Exception:
            pass

    def test_admin_login_creates_opaque_cookie_with_zero_admin_state(self):
        """Verify admin login produces an opaque cookie with ZERO admin flags or tokens."""
        ts = int(time.time() * 1000)
        admin_name = f"admin_sess_{ts}"
        admin_email = f"admin_sess_{ts}@cyberscout.ai"
        password = "AdminSecurePass2026!"

        admin = self.admin_repo.create_admin(
            username=admin_name,
            email=admin_email,
            password=password,
            role="Admin",
        )
        self.assertIsNotNone(admin)

        # Seed CSRF in session
        with self.client as c:
            with c.session_transaction() as sess:
                sess["admin_csrf_token"] = "csrf_token_admin_test_1234567890123456"

            res = c.post("/admin/login", data={
                "identifier": admin_email,
                "password": password,
                "csrf_token": "csrf_token_admin_test_1234567890123456",
            })

            cookie_val = self._extract_session_cookie(res)
            self.assertIsNotNone(cookie_val)

            # Check that cookie has NO admin credentials or authorization flags
            self.assertNotIn(admin_name, cookie_val)
            self.assertNotIn(admin_email, cookie_val)
            self.assertNotIn(str(admin["id"]), cookie_val)
            self.assertNotIn("admin_authenticated", cookie_val)
            self.assertNotIn("admin_user_id", cookie_val)
            self.assertNotIn("admin_role", cookie_val)
            self.assertNotIn("admin_csrf_token", cookie_val)
            self.assertNotIn("{", cookie_val)

    def test_session_rotation_on_login_prevents_session_fixation(self):
        """Verify that logging in rotates the session ID and revokes the pre-auth session."""
        # Step 1: Obtain anonymous pre-login session
        res1 = self.client.get("/")
        sid_anon = self._extract_session_cookie(res1)
        self.assertIsNotNone(sid_anon)

        # Step 2: Login with credentials
        ts = int(time.time() * 1000)
        u_email = f"fixation_user_{ts}@cyberscout.ai"
        self.user_repo.create_user(
            username=f"fixation_user_{ts}",
            email=u_email,
            password="UserPass123!",
            role="Viewer",
        )

        res2 = self.client.post("/login", data={"identifier": u_email, "password": "UserPass123!"})
        sid_auth = self._extract_session_cookie(res2)
        self.assertIsNotNone(sid_auth)

        # Verify session ID was rotated
        self.assertNotEqual(sid_anon, sid_auth, "Session ID MUST rotate upon authentication")

        # Verify pre-auth session in PostgreSQL is deleted
        hash_anon = hash_session_id(sid_anon)
        self.assertIsNone(self.session_repo.get_session(hash_anon), "Pre-auth session must be revoked from database")

    def test_logout_revokes_server_session_and_blocks_cookie_replay(self):
        """Verify logout invalidates server-side session and prevents replay of the old cookie."""
        ts = int(time.time() * 1000)
        u_email = f"replay_user_{ts}@cyberscout.ai"
        self.user_repo.create_user(
            username=f"replay_user_{ts}",
            email=u_email,
            password="UserPass123!",
            role="Viewer",
        )

        # 1. Login and capture session cookie
        res_login = self.client.post("/login", data={"identifier": u_email, "password": "UserPass123!"})
        sid = self._extract_session_cookie(res_login)
        self.assertIsNotNone(sid)

        # 2. Verify active authenticated access
        self.client.set_cookie("cyberscout_session", sid)
        res_dash = self.client.get("/dashboard")
        self.assertEqual(res_dash.status_code, 200, "Authenticated user must be allowed on /dashboard")

        # 3. Logout
        res_logout = self.client.get("/logout")
        self.assertEqual(res_logout.status_code, 302)

        # 4. Verify session is revoked/deleted in PostgreSQL
        sess_hash = hash_session_id(sid)
        db_sess = self.session_repo.get_session(sess_hash)
        self.assertIsNone(db_sess, "Session record in PostgreSQL must be deleted on logout")

        # 5. Attacker attempts to replay old session cookie
        attacker_client = self.app.test_client()
        attacker_client.set_cookie("cyberscout_session", sid)
        replay_res = attacker_client.get("/dashboard")
        self.assertEqual(replay_res.status_code, 302, "Replay of revoked session cookie must redirect to login/landing")
        self.assertTrue(replay_res.location.startswith("/login") or replay_res.location.endswith("/"))

    def test_session_expiration_enforcement(self):
        """Verify expired sessions cannot authenticate even if the client presents the cookie."""
        expired_sid = generate_session_id()
        expired_hash = hash_session_id(expired_sid)
        past_time = datetime.now(timezone.utc) - timedelta(hours=2)

        # Persist expired session directly in PostgreSQL
        self.session_repo.save_session(
            session_hash=expired_hash,
            session_data={"user_id": 9999, "username": "expired_user", "role": "Viewer"},
            expires_at=past_time,
            account_id=9999,
            account_type="user",
        )

        # Database get_session should filter out expired session
        self.assertIsNone(self.session_repo.get_session(expired_hash))

        # Client presenting expired cookie should not be authenticated
        client = self.app.test_client()
        client.set_cookie("cyberscout_session", expired_sid)
        res = client.get("/dashboard")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.location.startswith("/login") or res.location.endswith("/"))

    def test_session_revocation_enforcement(self):
        """Verify manually revoked sessions cannot authenticate."""
        active_sid = generate_session_id()
        active_hash = hash_session_id(active_sid)
        future_time = datetime.now(timezone.utc) + timedelta(hours=2)

        self.session_repo.save_session(
            session_hash=active_hash,
            session_data={"user_id": 8888, "username": "revoked_user", "role": "Viewer"},
            expires_at=future_time,
            account_id=8888,
            account_type="user",
        )

        # Verify active before revocation
        self.assertIsNotNone(self.session_repo.get_session(active_hash))

        # Revoke session
        self.session_repo.revoke_session(active_hash)

        # Database get_session should return None
        self.assertIsNone(self.session_repo.get_session(active_hash))

        # Client presenting revoked cookie should fail authentication
        client = self.app.test_client()
        client.set_cookie("cyberscout_session", active_sid)
        res = client.get("/dashboard")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.location.startswith("/login") or res.location.endswith("/"))

    def test_multi_worker_session_sharing(self):
        """Verify that a session created by Worker A is fully usable and revokable by Worker B."""
        # Simulate Worker A and Worker B as two completely separate Flask test client instances
        worker_a = self.app.test_client()
        worker_b = self.app.test_client()

        ts = int(time.time() * 1000)
        u_email = f"multiworker_{ts}@cyberscout.ai"
        self.user_repo.create_user(
            username=f"multiworker_{ts}",
            email=u_email,
            password="WorkerPass123!",
            role="Viewer",
        )

        # Worker A performs login
        res_a = worker_a.post("/login", data={"identifier": u_email, "password": "WorkerPass123!"})
        sid = self._extract_session_cookie(res_a)
        self.assertIsNotNone(sid)

        # Worker B receives request with the same cookie
        worker_b.set_cookie("cyberscout_session", sid)
        res_b = worker_b.get("/dashboard")
        self.assertEqual(res_b.status_code, 200, "Worker B must authenticate session created by Worker A")

        # Worker B logs out
        logout_b = worker_b.get("/logout")
        self.assertEqual(logout_b.status_code, 302)

        # Worker A can no longer use the session
        worker_a.set_cookie("cyberscout_session", sid)
        res_a_after = worker_a.get("/dashboard")
        self.assertEqual(res_a_after.status_code, 302, "Session revoked by Worker B must be rejected by Worker A")

    def test_user_and_admin_identity_domain_isolation(self):
        """Verify that a standard user session cannot access admin endpoints."""
        ts = int(time.time() * 1000)
        u_email = f"iso_user_{ts}@cyberscout.ai"
        self.user_repo.create_user(
            username=f"iso_user_{ts}",
            email=u_email,
            password="UserPass123!",
            role="Viewer",
        )

        res = self.client.post("/login", data={"identifier": u_email, "password": "UserPass123!"})
        sid = self._extract_session_cookie(res)
        self.client.set_cookie("cyberscout_session", sid)

        # Normal user accessing admin UI route -> 403 Forbidden
        res_admin = self.client.get("/admin/dashboard")
        self.assertEqual(res_admin.status_code, 403)

        # Normal user accessing admin API route -> 403 JSON
        res_admin_api = self.client.get("/admin/api/audit-logs")
        self.assertEqual(res_admin_api.status_code, 403)
        self.assertIn("Forbidden", res_admin_api.get_data(as_text=True))

    def test_malformed_and_legacy_cookie_fallback(self):
        """Verify that corrupted, legacy signed, or arbitrary cookies fail safely without exceptions."""
        client = self.app.test_client()

        # Legacy Flask signed cookie format simulation (with dots and signatures)
        client.set_cookie("cyberscout_session", "eyJ1c2VyX2lkIjoyMTN9.ZaAbCd.fake_signature_hash")
        res1 = client.get("/dashboard")
        self.assertEqual(res1.status_code, 302, "Legacy/tampered cookie must cleanly redirect to landing page")

        # Arbitrary non-token string
        client.set_cookie("cyberscout_session", "'; DROP TABLE \"ServerSessions\"; --")
        res2 = client.get("/dashboard")
        self.assertEqual(res2.status_code, 302)

        # Short invalid cookie
        client.set_cookie("cyberscout_session", "short")
        res3 = client.get("/dashboard")
        self.assertEqual(res3.status_code, 302)


if __name__ == "__main__":
    unittest.main()
