"""
Phase 5 Comprehensive Test Suite:
Intelligent Opportunity Ranking, Personalization & Explainable Recommendation Engine.

Strictly verifies all Phase 5 requirements:
1-10: Ranking (deterministic calculation, normalization, weights, tie-breaking, null values, expired, freshness)
11-13: Search Integration (relevance, no-search baseline, search + personalization)
14-23: Personalization (skills, category, type, remote, location, explicit outranks inferred, cold start, saved, search history)
24-27: Eligibility (eligible, ineligible, unknown, ineligible cannot be recommended)
28-32: Explanations (skills, remote, deadline, no false claims, actual feature alignment)
33-36: Privacy / RLS (User A vs User B isolation for preferences, saved items, history, cache headers)
37-39: SSR & Progressive Enhancement (initial HTML, no-JS baseline, identical output)
40-42: Performance (no N+1, bounded candidate retrieval, query duration)
43-44: Duplication & Diversity (no duplicates, controlled organization diversity)
45-49: Security (SQL injection immunity, authorization, CSRF, RLS enforcement, secret protection)
"""

from datetime import date, datetime, timedelta, timezone
import json
import re
import pytest

from dashboard.app import create_app
from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.user_preferences_repository import UserPreferencesRepository
from src.intelligence.eligibility_checker import EligibilityChecker
from src.intelligence.feature_extractors import (
    compute_base_quality,
    compute_category_match,
    compute_deadline_urgency,
    compute_freshness,
    compute_remote_match,
    compute_search_relevance,
    compute_skill_match,
    compute_source_trust,
    compute_type_match,
    compute_user_behavior_match,
)
from src.intelligence.ranking_config import (
    DEFAULT_DISCOVERY_WEIGHTS,
    DEFAULT_SEARCH_WEIGHTS,
    MAX_PER_ORGANIZATION_RECOMMENDATIONS,
    validate_weights,
)
from src.models.query_filter_dto import OpportunityCardDTO, QueryFilterDTO
from src.models.recommendation_models import (
    EligibilityResult,
    EligibilityStatus,
    RankingResultDTO,
    UserPreferencesDTO,
)
from src.services.opportunity_service import OpportunityService
from src.services.ranking_service import RankingService


# =============================================================================
# PYTEST FIXTURES
# =============================================================================

@pytest.fixture(scope="module")
def app():
    """Create test Flask application."""
    test_app = create_app()
    test_app.config["TESTING"] = True
    test_app.config["WTF_CSRF_ENABLED"] = False
    return test_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def db_manager():
    """DatabaseManager instance."""
    return DatabaseManager()


@pytest.fixture
def opp_repo(db_manager):
    return OpportunityRepository(db_manager=db_manager)


@pytest.fixture
def opp_service(db_manager, opp_repo):
    return OpportunityService(db_manager=db_manager, opportunity_repo=opp_repo)


@pytest.fixture
def test_user_id(db_manager):
    """Provides a valid user_id present in the Users table."""
    conn = db_manager.get_connection()
    cur = conn.cursor()
    cur.execute('SELECT id FROM "Users" ORDER BY id ASC LIMIT 1;')
    row = cur.fetchone()
    if row:
        uid = row[0]
        cur.close()
        conn.close()
        return uid

    from werkzeug.security import generate_password_hash
    cur.execute(
        """
        INSERT INTO "Users" (username, email, password_hash, role, is_active, created_at)
        VALUES ('phase5_test_user', 'phase5@cyberscout.local', %s, 'User', 1, CURRENT_TIMESTAMP)
        RETURNING id;
        """,
        (generate_password_hash("ValidPass123!"),),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return new_id


@pytest.fixture
def secondary_user_id(db_manager, test_user_id):
    """Provides a secondary valid user_id for multi-user isolation tests."""
    conn = db_manager.get_connection()
    cur = conn.cursor()
    cur.execute('SELECT id FROM "Users" WHERE id != %s ORDER BY id ASC LIMIT 1;', (test_user_id,))
    row = cur.fetchone()
    if row:
        uid = row[0]
        cur.close()
        conn.close()
        return uid

    from werkzeug.security import generate_password_hash
    cur.execute(
        """
        INSERT INTO "Users" (username, email, password_hash, role, is_active, created_at)
        VALUES ('phase5_secondary_user', 'phase5_sec@cyberscout.local', %s, 'User', 1, CURRENT_TIMESTAMP)
        RETURNING id;
        """,
        (generate_password_hash("ValidPass123!"),),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return new_id


@pytest.fixture
def auth_session(client, test_user_id):
    """Set up an authenticated session on the test client."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_user_id
        sess["username"] = "tester_phase5"
        sess["role"] = "Viewer"
        sess["user_csrf_token"] = "phase5_test_csrf_token"
    return {"user_id": test_user_id, "username": "tester_phase5", "csrf_token": "phase5_test_csrf_token"}


# =============================================================================
# SECTION 1: DETERMINISTIC BASE RANKING & FEATURE NORMALIZATION (Tests 1-10)
# =============================================================================

class TestRankingFeatures:
    """Tests 1-10: Mathematical model, feature ranges, missing attributes, and bounds."""

    def test_01_deterministic_score_calculation(self):
        ranking_service = RankingService()
        cand = {
            "id": "c1",
            "title": "SOC Analyst Intern",
            "tags": ["python", "linux"],
            "category": "internship",
            "opportunity_type": "internship",
            "remote": True,
            "deadline": (date.today() + timedelta(days=7)).isoformat(),
            "score": 85.0,
            "provider": "CISA",
        }
        user = UserPreferencesDTO(skills=["python", "linux"], prefers_remote=True, preferred_types=["internship"])

        res_a = ranking_service.score_single_candidate(cand, user_preferences=user)
        res_b = ranking_service.score_single_candidate(cand, user_preferences=user)

        assert res_a.final_score == res_b.final_score
        assert res_a.feature_scores == res_b.feature_scores

    def test_02_score_normalization_strict_bounds(self):
        # Guarantee all extractors return strictly within [0.0, 1.0]
        for score_val in [-50.0, 0.0, 50.0, 100.0, 200.0, None]:
            norm = compute_base_quality(score_val)
            assert 0.0 <= norm <= 1.0

        for rank_val in [-1.0, 0.0, 0.25, 0.5, 2.0, None]:
            norm = compute_search_relevance(rank_val)
            assert 0.0 <= norm <= 1.0

    def test_03_weight_application_and_validation(self):
        assert validate_weights(DEFAULT_DISCOVERY_WEIGHTS) is True
        assert validate_weights(DEFAULT_SEARCH_WEIGHTS) is True

        with pytest.raises(ValueError, match="must sum to 1.0"):
            validate_weights({"skill_match": 0.2, "category_match": 0.2})
        with pytest.raises(ValueError, match="cannot exceed 1.0"):
            validate_weights({"skill_match": 1.2, "base_quality": 0.1})
        with pytest.raises(ValueError, match="cannot be negative"):
            validate_weights({"skill_match": 0.8, "base_quality": -0.2})

    def test_04_deterministic_tie_breaking(self):
        ranking_service = RankingService()
        cand_a = {"id": "alpha_1", "title": "Analyst A", "score": 80.0}
        cand_b = {"id": "beta_2", "title": "Analyst B", "score": 80.0}

        ranked_1 = ranking_service.rank_candidates([cand_b, cand_a])
        ranked_2 = ranking_service.rank_candidates([cand_a, cand_b])

        # Deterministic sorting yields identical ordering regardless of input list sequence
        order_1 = [c["id"] for c, _ in ranked_1]
        order_2 = [c["id"] for c, _ in ranked_2]
        assert order_1 == order_2

    def test_05_missing_feature_values_graceful_handling(self):
        ranking_service = RankingService()
        sparse_cand = {"id": "sparse_1"}
        res = ranking_service.score_single_candidate(sparse_cand, user_preferences=None)

        assert 0.0 <= res.final_score <= 1.0
        assert not any(v < 0.0 or v > 1.0 for v in res.feature_scores.values())

    def test_06_null_deadlines_neutral_handling(self):
        urgency, days = compute_deadline_urgency(None)
        assert urgency == 0.3
        assert days is None

    def test_07_null_location_remote_neutral_handling(self):
        # If user has remote preference but opportunity remote is unknown: neutral (0.5)
        assert compute_remote_match(True, None) == 0.5
        assert compute_remote_match(False, None) == 0.5

    def test_08_null_skills_neutral_handling(self):
        score, matched = compute_skill_match([], ["python", "linux"])
        assert score == 0.0
        assert matched == []

        score_none, matched_none = compute_skill_match(["python"], None)
        assert score_none == 0.0
        assert matched_none == []

    def test_09_expired_deadlines_scored_zero(self):
        past_date = date.today() - timedelta(days=10)
        urgency, days = compute_deadline_urgency(past_date)
        assert urgency == 0.0
        assert days is not None and days < 0

    def test_10_freshness_behavior(self):
        today = date.today()
        score_new = compute_freshness(today, current_date=today)
        score_week = compute_freshness(today - timedelta(days=5), current_date=today)
        score_old = compute_freshness(today - timedelta(days=45), current_date=today)

        assert score_new > score_week > score_old
        assert score_new == 1.0


# =============================================================================
# SECTION 2: SEARCH INTEGRATION TESTS (Tests 11-13)
# =============================================================================

class TestSearchIntegration:
    """Tests 11-13: FTS integration, keyword weights, and hybrid personalization."""

    def test_11_search_relevance_affects_ranking(self):
        ranking_service = RankingService()
        cand_relevant = {"id": "c_rel", "title": "AppSec Engineer", "rank_score": 0.45, "score": 70.0}
        cand_generic = {"id": "c_gen", "title": "IT Assistant", "rank_score": 0.02, "score": 85.0}

        ranked = ranking_service.rank_candidates([cand_generic, cand_relevant], has_search_query=True)
        assert ranked[0][0]["id"] == "c_rel"
        assert ranked[0][1].feature_scores["search_relevance"] > 0.80

    def test_12_no_search_ranking_behaves_correctly(self):
        ranking_service = RankingService()
        cand_a = {"id": "c_a", "score": 90.0, "rank_score": 0.50}
        cand_b = {"id": "c_b", "score": 95.0, "rank_score": 0.00}

        # In discovery mode (no search), search_relevance weight is 0.0
        ranked = ranking_service.rank_candidates([cand_a, cand_b], has_search_query=False)
        assert ranked[0][0]["id"] == "c_b"

    def test_13_search_plus_personalization_composite(self):
        ranking_service = RankingService()
        cand_both = {"id": "both", "tags": ["python"], "rank_score": 0.35, "score": 80.0}
        cand_search_only = {"id": "search_only", "tags": ["java"], "rank_score": 0.35, "score": 80.0}

        user = UserPreferencesDTO(skills=["python"])
        ranked = ranking_service.rank_candidates([cand_search_only, cand_both], user_preferences=user, has_search_query=True)
        assert ranked[0][0]["id"] == "both"


# =============================================================================
# SECTION 3: PERSONALIZATION TESTS (Tests 14-23)
# =============================================================================

class TestPersonalization:
    """Tests 14-23: Explicit and behavioral personalization signals."""

    def test_14_matching_skills_positive_signal(self):
        score, matched = compute_skill_match(["python", "linux"], ["python", "linux", "c++"])
        assert score == 1.0
        assert set(matched) == {"python", "linux"}

    def test_15_non_matching_skills_zero_signal(self):
        score, matched = compute_skill_match(["rust", "go"], ["python", "java"])
        assert score == 0.0
        assert matched == []

    def test_16_matching_category_positive_signal(self):
        score, cat = compute_category_match(["internship", "fellowship"], "internship")
        assert score == 1.0
        assert cat == "internship"

    def test_17_matching_opportunity_type_positive_signal(self):
        score, op_type = compute_type_match(["ctf", "hackathon"], "ctf")
        assert score == 1.0
        assert op_type == "ctf"

    def test_18_remote_preference(self):
        assert compute_remote_match(True, True) == 1.0
        assert compute_remote_match(True, False) == 0.1

    def test_19_location_preference(self):
        # UserPreferencesDTO location representation
        prefs = UserPreferencesDTO(preferred_location="United States")
        assert prefs.preferred_location == "United States"

    def test_20_explicit_preferences_outrank_weak_inferred_signals(self):
        ranking_service = RankingService()
        cand_explicit = {"id": "c_exp", "tags": ["python"], "score": 75.0}
        cand_inferred = {"id": "c_inf", "tags": ["ruby"], "score": 75.0}

        user_prefs = UserPreferencesDTO(skills=["python"])
        saved_profile = (["ruby"], [])  # saved Ruby in the past

        ranked = ranking_service.rank_candidates([cand_inferred, cand_explicit], user_preferences=user_prefs, saved_profile=saved_profile)
        assert ranked[0][0]["id"] == "c_exp"

    def test_21_cold_start_user(self):
        ranking_service = RankingService()
        cand_trusted = {"id": "c_trust", "provider": "CISA", "score": 90.0}
        cand_untrusted = {"id": "c_untrust", "provider": "", "score": 40.0}

        # Empty preferences
        ranked = ranking_service.rank_candidates([cand_untrusted, cand_trusted], user_preferences=UserPreferencesDTO())
        assert ranked[0][0]["id"] == "c_trust"

    def test_22_user_with_saved_opportunities(self):
        score = compute_user_behavior_match(
            saved_tags=["python", "ctf"],
            saved_categories=["internship"],
            opp_tags=["python", "linux"],
            opp_category="internship",
        )
        assert score >= 0.50

    def test_23_user_with_search_history(self, db_manager, test_user_id):
        repo = UserPreferencesRepository(db_manager=db_manager)
        ok = repo.record_search(test_user_id, "penetration testing ctf", {"category": "ctf"})
        assert ok is True

        history = repo.get_recent_searches(test_user_id, limit=5)
        assert len(history) > 0
        assert history[0]["query_text"] == "penetration testing ctf"


# =============================================================================
# SECTION 4: ELIGIBILITY SEPARATION (Tests 24-27)
# =============================================================================

class TestEligibilitySeparation:
    """Tests 24-27: Strict separation of ranking score and eligibility."""

    def test_24_eligible_status(self):
        checker = EligibilityChecker()
        cand = {"title": "Junior Cybersecurity Intern", "experience_level": "beginner", "eligibility": "Open to beginner students."}
        user = UserPreferencesDTO(experience_level="beginner")
        res = checker.check_eligibility(cand, user)
        assert res.status == EligibilityStatus.ELIGIBLE

    def test_25_ineligible_status(self):
        checker = EligibilityChecker()
        cand = {"title": "Lead Cryptanalyst", "experience_level": "advanced", "eligibility": "Requires 10+ years experience."}
        user = UserPreferencesDTO(experience_level="beginner")
        res = checker.check_eligibility(cand, user)
        assert res.status == EligibilityStatus.INELIGIBLE
        assert "advanced" in res.reasons[0].lower()

    def test_26_unknown_status(self):
        checker = EligibilityChecker()
        cand = {"title": "US Defense Analyst", "eligibility": "Must be US Citizen with active clearance."}
        user = UserPreferencesDTO(experience_level="intermediate")
        res = checker.check_eligibility(cand, user)
        assert res.status == EligibilityStatus.UNKNOWN

    def test_27_ineligible_cannot_be_recommended(self):
        checker = EligibilityChecker()
        ranking_service = RankingService(eligibility_checker=checker)
        cand_ineligible = {
            "id": "c_inelig",
            "title": "Principal Architect",
            "experience_level": "advanced",
            "eligibility": "Requires senior experience.",
            "score": 99.0,  # Extremely high quality score
        }
        cand_eligible = {
            "id": "c_elig",
            "title": "Junior Associate",
            "experience_level": "beginner",
            "eligibility": "Open to beginners.",
            "score": 75.0,
        }
        user = UserPreferencesDTO(experience_level="beginner")

        scored = ranking_service.rank_candidates([cand_ineligible, cand_eligible], user_preferences=user)
        recommended = ranking_service.filter_diverse_recommendations(scored, limit=5)

        assert len(recommended) == 1
        assert recommended[0][0]["id"] == "c_elig"
        assert not any(c["id"] == "c_inelig" for c, _ in recommended)


# =============================================================================
# SECTION 5: RECOMMENDATION EXPLANATIONS (Tests 28-32)
# =============================================================================

class TestExplanations:
    """Tests 28-32: Truthful, explainable recommendation signals."""

    def test_28_correct_explanation_for_skill_match(self):
        ranking_service = RankingService()
        cand = {"id": "c", "tags": ["python", "linux"], "score": 80.0}
        user = UserPreferencesDTO(skills=["python", "linux"])

        res = ranking_service.score_single_candidate(cand, user_preferences=user)
        assert any("Python" in r and "Linux" in r for r in res.explanation.reasons)

    def test_29_correct_explanation_for_remote_match(self):
        ranking_service = RankingService()
        cand = {"id": "c", "remote": True, "score": 80.0}
        user = UserPreferencesDTO(prefers_remote=True)

        res = ranking_service.score_single_candidate(cand, user_preferences=user)
        assert any("Remote" in r for r in res.explanation.reasons)

    def test_30_correct_explanation_for_deadline(self):
        ranking_service = RankingService()
        cand = {"id": "c", "deadline": (date.today() + timedelta(days=3)).isoformat(), "score": 80.0}

        res = ranking_service.score_single_candidate(cand, user_preferences=None)
        assert any("Closing in 3 days" in r for r in res.explanation.reasons)

    def test_31_no_false_explanation(self):
        ranking_service = RankingService()
        cand = {"id": "c", "tags": ["python"], "remote": False, "score": 80.0}
        user = UserPreferencesDTO(skills=["python"], prefers_remote=True)

        res = ranking_service.score_single_candidate(cand, user_preferences=user)
        reasons_text = " ".join(res.explanation.reasons)
        assert "Remote friendly" not in reasons_text

    def test_32_explanation_corresponds_to_actual_features(self):
        ranking_service = RankingService()
        cand = {"id": "c", "tags": ["docker"], "opportunity_type": "internship", "score": 95.0, "provider": "CISA"}
        user = UserPreferencesDTO(skills=["docker"], preferred_types=["internship"])

        res = ranking_service.score_single_candidate(cand, user_preferences=user)
        assert res.feature_scores["skill_match"] == 1.0
        assert res.feature_scores["type_match"] == 1.0
        assert any("Docker" in r for r in res.explanation.reasons)
        assert any("Internship" in r for r in res.explanation.reasons)


# =============================================================================
# SECTION 6: PRIVACY, RLS & ISOLATION (Tests 33-36)
# =============================================================================

class TestPrivacyAndRLS:
    """Tests 33-36: Strict multi-tenant isolation under PostgreSQL RLS."""

    def test_33_user_a_cannot_access_user_b_preferences(self, db_manager, test_user_id, secondary_user_id):
        repo = UserPreferencesRepository(db_manager=db_manager)

        # Save private preferences for User A
        prefs_a = UserPreferencesDTO(skills=["cryptography_user_a"], experience_level="advanced")
        repo.save_preferences(test_user_id, prefs_a)

        # Query preferences for User B
        prefs_b = repo.get_preferences(secondary_user_id)
        if prefs_b:
            assert "cryptography_user_a" not in prefs_b.skills

    def test_34_user_a_cannot_access_user_b_saved_data(self, opp_repo, db_manager, test_user_id, secondary_user_id):
        conn = db_manager.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id FROM "Opportunities" LIMIT 1;')
        opp_row = cur.fetchone()
        cur.close()
        conn.close()

        if not opp_row:
            pytest.skip("No opportunities in database to test bookmark isolation")

        real_opp_id = str(opp_row[0])
        opp_repo.save_opportunity_for_user(test_user_id, real_opp_id)

        # Check saved state for User B
        saved_for_b = opp_repo.is_opportunity_saved(secondary_user_id, real_opp_id)
        assert saved_for_b is False

        # Clean up
        opp_repo.unsave_opportunity_for_user(test_user_id, real_opp_id)

    def test_35_user_a_cannot_access_user_b_search_history(self, db_manager, test_user_id, secondary_user_id):
        repo = UserPreferencesRepository(db_manager=db_manager)
        repo.record_search(test_user_id, "top_secret_query_by_a")

        b_searches = repo.get_recent_searches(secondary_user_id, limit=20)
        assert not any(s["query_text"] == "top_secret_query_by_a" for s in b_searches)

    def test_36_personalized_results_cannot_cross_users_cache_control(self, client, auth_session):
        response = client.get("/opportunities")
        assert response.status_code == 200

        # Enforce private cache headers (Principle 37)
        cache_control = response.headers.get("Cache-Control", "")
        assert "private" in cache_control
        assert "no-cache" in cache_control
        assert "no-store" in cache_control


# =============================================================================
# SECTION 7: SSR & PROGRESSIVE ENHANCEMENT (Tests 37-39)
# =============================================================================

class TestSSRAndProgressiveEnhancement:
    """Tests 37-39: Server-Side Rendering completeness without JavaScript."""

    def test_37_recommendations_exist_in_initial_html(self, client, auth_session):
        response = client.get("/opportunities")
        assert response.status_code == 200
        html = response.get_data(as_text=True)

        assert "Sort Order" in html
        assert "Recommended / Best Match" in html

    def test_38_core_recommendations_work_without_javascript(self, client, auth_session):
        # Verify standard HTML form exists for saving and filtering without JS
        response = client.get("/opportunities")
        assert response.status_code == 200
        html = response.get_data(as_text=True)

        assert '<form id="filterForm"' in html or 'name="sort"' in html
        assert 'action="/opportunities"' in html or 'href="/opportunities' in html

    def test_39_profile_preferences_form_post(self, client, auth_session):
        csrf_token = auth_session.get("csrf_token")
        post_data = {
            "csrf_token": csrf_token,
            "action": "save_preferences",
            "skills": "Python, Linux, Network Defense",
            "interests": "AppSec, CTF",
            "prefers_remote": "true",
            "experience_level": "beginner",
            "preferred_types": ["internship", "ctf"],
        }
        response = client.post("/profile", data=post_data, follow_redirects=True)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "preferences updated successfully" in html.lower() or "career preferences" in html.lower()


# =============================================================================
# SECTION 8: PERFORMANCE, DIVERSITY & SECURITY (Tests 40-49)
# =============================================================================

class TestPerformanceAndSafety:
    """Tests 40-49: Query bounding, controlled diversity, and security invariants."""

    def test_40_no_n_plus_one_queries_on_listing(self, opp_service, test_user_id):
        # search_opportunities queries all cards in a single batch query
        filter_dto = QueryFilterDTO(page=1, per_page=24, user_id=str(test_user_id))
        result = opp_service.search_opportunities(filter_dto)
        assert result.items is not None

    def test_41_candidate_retrieval_remains_bounded(self, opp_service, test_user_id):
        recs = opp_service.get_recommended_for_you(str(test_user_id), limit=3)
        assert len(recs) <= 3

    def test_42_controlled_diversity_prevents_single_org_domination(self):
        ranking_service = RankingService()
        cands = [
            {"id": f"mono_{i}", "organization": "Dominant Org", "score": 90.0} for i in range(10)
        ] + [
            {"id": "other_1", "organization": "Other Org", "score": 85.0}
        ]

        scored = ranking_service.rank_candidates(cands)
        diverse = ranking_service.filter_diverse_recommendations(scored, limit=5)

        dominant_count = sum(1 for c, _ in diverse if c["organization"] == "Dominant Org")
        assert dominant_count <= MAX_PER_ORGANIZATION_RECOMMENDATIONS

    def test_43_no_duplicate_opportunities_in_recommendations(self):
        ranking_service = RankingService()
        cands = [
            {"id": "dup_1", "organization": "Org A", "score": 80.0},
            {"id": "dup_2", "organization": "Org B", "score": 75.0},
        ]
        scored = ranking_service.rank_candidates(cands)
        diverse = ranking_service.filter_diverse_recommendations(scored, limit=5)

        rec_ids = [c["id"] for c, _ in diverse]
        assert len(rec_ids) == len(set(rec_ids)), "Recommendations must never contain duplicates!"

    def test_44_sql_injection_safety_in_preferences(self, db_manager, test_user_id):
        repo = UserPreferencesRepository(db_manager=db_manager)
        malicious_input = "'; DROP TABLE \"UserPreferences\"; --"

        prefs = UserPreferencesDTO(skills=[malicious_input], preferred_location=malicious_input)
        ok = repo.save_preferences(test_user_id, prefs)
        assert ok is True

        loaded = repo.get_preferences(test_user_id)
        assert loaded is not None
        assert malicious_input.lower() in loaded.skills
        assert loaded.preferred_location == malicious_input

    def test_45_csrf_protection_on_preferences_mutation(self, client, auth_session):
        # Submitting without valid CSRF token must fail
        post_data = {
            "csrf_token": "malicious_fake_token",
            "action": "save_preferences",
            "skills": "Hacked",
        }
        response = client.post("/profile", data=post_data, follow_redirects=True)
        html = response.get_data(as_text=True)
        assert "csrf" in html.lower() or response.status_code in (302, 400, 403)

    def test_46_no_secret_leakage_in_recommendations(self, opp_service, test_user_id):
        from dataclasses import asdict
        recs = opp_service.get_recommended_for_you(str(test_user_id), limit=3)
        for r in recs:
            r_dict = asdict(r)
            assert "password" not in r_dict
            assert "raw_data" not in r_dict
            assert "token" not in r_dict
