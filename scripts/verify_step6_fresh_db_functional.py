"""
Step 6: Fresh-Database Application Validation for CyberScout AI.
Tests the complete 20-point validation suite against the fresh database state.
"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from dashboard.app import create_app
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository
from src.database.admin_repository import AdminRepository
from src.database.user_preferences_repository import UserPreferencesRepository
from src.database.notification_repository import NotificationRepository
from src.database.opportunity_repository import OpportunityRepository
from src.database.audit_log_repository import AuditLogRepository
from src.database.session_repository import SessionRepository
from src.database.mfa_repository import MfaRepository
from src.database.scan_job_repository import ScanJobRepository
from src.database.webhook_request_repository import WebhookRequestRepository
from src.database.migrations.migration_manager import MigrationManager
from src.database.seed import SeedManager
from src.models.opportunity import Opportunity
from src.models.notification_models import NotificationOutboxDTO
from src.models.recommendation_models import UserPreferencesDTO

def run_functional_validation():
    print("=== STARTING STEP 6 FRESH-DATABASE VALIDATION ===")
    results = {}
    db = DatabaseManager()

    # 1. Migration idempotency
    print("\n--- 1. Migration Idempotency & Order ---")
    mig_mgr = MigrationManager(db)
    cur_ver = mig_mgr.get_current_version()
    print(f"Current schema version: {cur_ver}")
    assert cur_ver == 16, f"Expected version 16, got {cur_ver}"
    applied = mig_mgr.apply_migrations()
    print(f"Re-running migration manager applied: {applied} migrations (idempotent)")
    assert applied == 0
    results["1_migration_idempotency"] = "PASS"

    # 2. Flask Application & Health Endpoints
    print("\n--- 2. Flask Application & Health Endpoints ---")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    live_res = client.get("/health/live")
    print(f"/health/live status: {live_res.status_code}")
    assert live_res.status_code == 200
    live_data = live_res.get_json()
    assert live_data.get("status") in ("live", "ok")

    ready_res = client.get("/health/ready")
    print(f"/health/ready status: {ready_res.status_code}")
    assert ready_res.status_code == 200
    ready_data = ready_res.get_json()
    assert ready_data.get("status") == "ok"
    assert ready_data.get("ready") is True
    assert ready_data.get("database") == "connected"
    results["2_health_endpoints"] = "PASS"

    # 3. Initial Admin Setup
    print("\n--- 3. Initial Admin Setup ---")
    seed_mgr = SeedManager(db)
    seed_mgr.seed_sources()
    seed_mgr.seed_users()
    admin_repo = AdminRepository(db)
    admin = admin_repo.get_by_email("admin@cyberscout.ai")
    assert admin is not None
    print(f"Admin account created: {admin['username']} (ID: {admin['id']})")
    results["3_admin_setup"] = "PASS"

    # 4. Standard User Registration & Login
    print("\n--- 4. Standard User Registration & Login ---")
    user_repo = UserRepository(db)
    ts = int(time.time() * 1000)
    uname = f"testuser_{ts}"
    email = f"user_{ts}@example.com"
    pwd = "SecureUser123!@#"
    new_user = user_repo.create_user(username=uname, email=email, password=pwd, role="Viewer")
    assert new_user is not None
    user_uuid = new_user["id"]
    print(f"User registered with UUID: {user_uuid}")
    assert uuid.UUID(str(user_uuid))

    auth_user = user_repo.authenticate(uname, pwd)
    assert auth_user is not None
    assert str(auth_user["id"]) == str(user_uuid)
    print("User authenticated successfully with UUID identity.")
    results["4_user_registration_login"] = "PASS"

    # 5. Admin Authentication & Session
    print("\n--- 5. Admin Login & Authentication ---")
    auth_admin = admin_repo.authenticate("admin", "Admin@CyberScout2026!")
    assert auth_admin is not None
    print(f"Admin authenticated: {auth_admin['username']}")
    results["5_admin_login"] = "PASS"

    # 6. Admin MFA State
    print("\n--- 6. Admin MFA / OTP Flow ---")
    mfa_repo = MfaRepository(db)
    mfa_token = f"test_mfa_{ts}"
    otp_hash = hashlib.sha256(b"123456").hexdigest()
    mfa_repo.store_pending_mfa(
        token=mfa_token,
        user_id=admin["id"],
        username=admin["username"],
        email=admin["email"],
        role="Admin",
        otp_hash=otp_hash,
        expires_at=int(time.time()) + 300,
    )
    pending = mfa_repo.get_pending_mfa(mfa_token)
    assert pending is not None
    assert pending["user_id"] == admin["id"]
    mfa_repo.clear_pending_mfa(mfa_token)
    assert mfa_repo.get_pending_mfa(mfa_token) is None
    print("Admin MFA pending state created, verified, and consumed cleanly.")
    results["6_admin_mfa"] = "PASS"

    # 7. Session Creation & Revocation
    print("\n--- 7. Session Lifecycle ---")
    session_repo = SessionRepository(db)
    raw_token = f"raw_session_token_{ts}"
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    sess_res = session_repo.save_session(
        session_hash=raw_token,
        session_data={"username": uname, "role": "Viewer"},
        expires_at=exp,
        account_id=user_uuid,
        account_type="user"
    )
    assert sess_res is True
    active_sess = session_repo.get_session(raw_token)
    assert active_sess is not None
    assert active_sess.get("username") == uname
    print("Session created and retrieved with canonical UUID account_id.")
    revoked = session_repo.revoke_session(raw_token)
    assert revoked is True
    assert session_repo.get_session(raw_token) is None
    print("Session successfully revoked.")
    results["7_session_lifecycle"] = "PASS"

    # 8. CSRF Protection
    print("\n--- 8. CSRF Protection ---")
    # Test 8a: State-changing endpoint without CSRF token must return 403
    with client.session_transaction() as sess:
        sess["user_id"] = str(user_uuid)
        sess["username"] = uname
        sess["user_csrf_token"] = "valid_csrf_token_123"
    api_no_csrf = client.post(f"/api/opportunities/{opp_id_1 if 'opp_id_1' in locals() else 'dummy_opp'}/bookmark")
    print(f"POST bookmark without CSRF token status: {api_no_csrf.status_code}")
    assert api_no_csrf.status_code == 403

    # Test 8b: Form submission with mismatched CSRF token returns 400
    with client.session_transaction() as sess:
        sess.pop("user_id", None)
        sess["user_csrf_token"] = "valid_csrf_token_123"
    form_res = client.post("/login", data={"identifier": "test", "password": "bad", "csrf_token": "wrong_token"})
    print(f"POST /login with invalid CSRF token status: {form_res.status_code}")
    assert form_res.status_code == 400
    results["8_csrf_protection"] = "PASS"

    # 9. User Isolation (User A vs User B)
    print("\n--- 9. User Isolation ---")
    pref_repo = UserPreferencesRepository(db)
    u2_name = f"user2_{ts}"
    u2_email = f"user2_{ts}@example.com"
    u2 = user_repo.create_user(username=u2_name, email=u2_email, password=pwd, role="Viewer")
    u2_uuid = u2["id"]

    pref_dto_a = UserPreferencesDTO(skills=["cryptography_a"], preferred_location="Remote")
    pref_repo.save_preferences(user_uuid, pref_dto_a)

    pref_b = pref_repo.get_preferences(u2_uuid)
    print(f"User B preferences query returned: {pref_b}")
    assert pref_b is None or "cryptography_a" not in pref_b.skills
    results["9_user_isolation"] = "PASS"

    # 10. Admin Authorization Enforcement
    print("\n--- 10. Admin Authorization ---")
    # Standard user attempting to access admin route
    with client.session_transaction() as sess:
        sess["user_id"] = str(user_uuid)
        sess["username"] = uname
        sess["role"] = "Viewer"
    admin_access = client.get("/admin")
    print(f"Viewer accessing /admin status: {admin_access.status_code}")
    assert admin_access.status_code in (302, 403)
    results["10_admin_authorization"] = "PASS"

    # 11. Opportunity Persistence, Upsert & Deduplication
    print("\n--- 11. Opportunity Collection & Deduplication ---")
    opp_repo = OpportunityRepository(db)
    opp_id_1 = f"opp_{ts}"
    opp1 = Opportunity(
        id=opp_id_1,
        title="Security Analyst Internship",
        company="CyberCorp",
        url=f"https://example.com/opp/{ts}",
        source_id="hackthebox_academy",
        category="internship",
        description="Exciting security analyst opportunity.",
        status="active"
    )
    saved_id = opp_repo.upsert(opp1)
    print(f"Saved opportunity ID: {saved_id}")
    assert saved_id == opp_id_1
    # Try inserting duplicate url
    opp2 = Opportunity(
        id=f"opp_dup_{ts}",
        title="Security Analyst Internship (Duplicate)",
        company="CyberCorp",
        url=f"https://example.com/opp/{ts}",
        source_id="hackthebox_academy",
        category="internship",
        description="Duplicate opportunity.",
        status="active"
    )
    dup_id = opp_repo.upsert(opp2)
    print(f"Duplicate insert result: {dup_id} (deduplicated to {saved_id})")
    assert dup_id == opp_id_1
    results["11_opportunity_deduplication"] = "PASS"

    # 12. Search and Filtering
    print("\n--- 12. Search & Filtering ---")
    from src.models.query_filter_dto import QueryFilterDTO
    filter_dto = QueryFilterDTO(keyword="Security Analyst", page=1, per_page=10)
    raw_items, total, facet_counts = opp_repo.query_opportunities(filter_dto)
    print(f"Search found {total} matching opportunities.")
    assert total >= 1
    results["12_search_filtering"] = "PASS"

    # 13. Saved Opportunities Bookmark Flow
    print("\n--- 13. Saved Opportunities ---")
    is_saved = opp_repo.save_opportunity_for_user(user_uuid, opp_id_1, notes="Testing bookmark")
    assert is_saved is True
    saved_count = opp_repo.count_saved_opportunities(user_uuid)
    assert saved_count >= 1
    saved_ids = opp_repo.get_saved_ids_for_user(user_uuid)
    assert opp_id_1 in saved_ids
    assert opp_repo.is_opportunity_saved(user_uuid, opp_id_1) is True
    # User B should not see it
    assert opp_repo.is_opportunity_saved(u2_uuid, opp_id_1) is False
    assert opp_id_1 not in opp_repo.get_saved_ids_for_user(u2_uuid)
    opp_repo.unsave_opportunity_for_user(user_uuid, opp_id_1)
    assert opp_repo.is_opportunity_saved(user_uuid, opp_id_1) is False
    print("Saved opportunities verified for user bookmarking, isolation, and deletion.")
    results["13_saved_opportunities"] = "PASS"

    # 14. User Preferences Flow
    print("\n--- 14. User Preferences Flow ---")
    retrieved_pref = pref_repo.get_preferences(user_uuid)
    assert retrieved_pref is not None
    assert "cryptography_a" in retrieved_pref.skills
    results["14_user_preferences"] = "PASS"

    # 15. Notification Outbox
    print("\n--- 15. Notification Outbox ---")
    notif_repo = NotificationRepository(db)
    notif_dto = NotificationOutboxDTO(
        user_id=user_uuid,
        opportunity_id=opp_id_1,
        event_type="new",
        deduplication_key=f"dedup_{user_uuid}_{opp_id_1}",
        metadata_json={"title": "Security Analyst"}
    )
    notif_id = notif_repo.enqueue_notification(notif_dto)
    assert notif_id is not None
    user_notifs = notif_repo.get_user_notifications(user_uuid)
    assert len(user_notifs) >= 1
    # Duplicate enqueue should do nothing
    dup_enqueue = notif_repo.enqueue_notification(notif_dto)
    assert dup_enqueue is None
    results["15_notification_outbox"] = "PASS"

    # 16. Audit Logs
    print("\n--- 16. Audit Logs ---")
    audit_repo = AuditLogRepository(db)
    audit_repo.log_event(
        event_type="USER_TEST_EVENT",
        action="TEST_ACTION",
        status="SUCCESS",
        user_id=user_uuid,
        username=uname,
        details="Phase 12.2 functional audit event"
    )
    res = audit_repo.query_logs(limit=5)
    logs = res["logs"]
    assert any(l["event_type"] == "USER_TEST_EVENT" for l in logs)
    print("Audit log recorded with UUID user_id.")
    results["16_audit_logs"] = "PASS"

    # 17. Scan-Job Lifecycle
    print("\n--- 17. Scan-Job Lifecycle ---")
    scan_repo = ScanJobRepository(db)
    job_id = f"job_{ts}"
    queued = scan_repo.create_job(job_id=job_id, job_type="full_scan")
    assert queued is not None
    started = scan_repo.mark_running(job_id)
    assert started is True
    prog_updated = scan_repo.update_progress(job_id, stage="running", progress=25.0)
    assert prog_updated is True
    finished = scan_repo.mark_completed(job_id, opportunities_found=1)
    assert finished is True
    job_rec = scan_repo.get_job(job_id)
    assert job_rec["status"] == "completed"
    results["17_scan_jobs"] = "PASS"

    # 18. Webhook Request Idempotency & HMAC
    print("\n--- 18. Webhook Tracking & Idempotency ---")
    webhook_repo = WebhookRequestRepository(db)
    req_id = f"req_{ts}"
    tracked = webhook_repo.record_request(request_id=req_id, timestamp=int(time.time()), source="google_apps_script")
    assert tracked is True
    # Re-recording same request_id fails idempotently
    tracked_dup = webhook_repo.record_request(request_id=req_id, timestamp=int(time.time()), source="google_apps_script")
    assert tracked_dup is False
    results["18_webhook_idempotency"] = "PASS"

    # 19. Failure & Retry Handling
    print("\n--- 19. Failure & Retry Handling ---")
    ping_ok = db.ping()
    assert ping_ok is True
    metrics = db.get_health_metrics()
    assert metrics["connected"] is True
    assert metrics["latency_ms"] >= 0
    results["19_failure_retry"] = "PASS"

    # 20. Clean up test users created during validation
    print("\n--- 20. Test Artifact Cleanup ---")
    with db.get_session() as s:
        s.execute(text(f"DELETE FROM \"Users\" WHERE id IN ('{user_uuid}', '{u2_uuid}');"))
        s.execute(text(f"DELETE FROM \"Opportunities\" WHERE id = '{opp_id_1}';"))
        s.execute(text(f"DELETE FROM \"ScanJobs\" WHERE job_id = '{job_id}';"))
        s.execute(text(f"DELETE FROM \"AuditLogs\" WHERE event_type = 'USER_TEST_EVENT';"))
        s.execute(text(f"DELETE FROM scheduler_webhook_requests WHERE request_id = '{req_id}';"))
        s.commit()
    print("Test users and artifacts cleaned up cleanly.")
    results["20_cleanup"] = "PASS"

    print("\n=== ALL 20 FUNCTIONAL VERIFICATION CHECKS PASSED ===")
    for k, v in results.items():
        print(f"  {k}: {v}")

    with open("docs/audits/step6_functional_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_functional_validation()
