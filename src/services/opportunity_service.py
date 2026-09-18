"""
Opportunity Service for CyberScout AI.

Orchestrates SSR discovery, full-text search, facet filtering, server-side
pagination, opportunity details, and user saved opportunities.
"""

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.user_preferences_repository import UserPreferencesRepository
from src.models.opportunity import Opportunity
from src.models.query_filter_dto import (
    OpportunityCardDTO,
    OpportunityDetailDTO,
    PaginatedResultDTO,
    QueryFilterDTO,
)
from src.models.recommendation_models import UserPreferencesDTO
from src.services.ranking_service import RankingService
from src.intelligence.match_analyzer import MatchAnalyzer
from src.intelligence.similarity_engine import SimilarityEngine
from src.core.logging import get_logger

logger = get_logger(__name__)


class OpportunityService:
    """Business logic for SSR-first opportunity discovery, personalization, and bookmarks."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        opportunity_repo: Optional[OpportunityRepository] = None,
        user_prefs_repo: Optional[UserPreferencesRepository] = None,
        ranking_service: Optional[RankingService] = None,
        match_analyzer: Optional[MatchAnalyzer] = None,
        similarity_engine: Optional[SimilarityEngine] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.repo = opportunity_repo or OpportunityRepository(db_manager=self.db_manager)
        self.user_prefs_repo = user_prefs_repo or UserPreferencesRepository(db_manager=self.db_manager)
        self.ranking_service = ranking_service or RankingService()
        self.match_analyzer = match_analyzer or MatchAnalyzer()
        self.similarity_engine = similarity_engine or SimilarityEngine(db_manager=self.db_manager)

    def search_opportunities(self, filter_dto: QueryFilterDTO) -> PaginatedResultDTO:
        """
        Execute server-side search, filtering, ranking, and pagination.
        Returns PaginatedResultDTO containing OpportunityCardDTO items and facet counts.
        """
        raw_items, total_count, facet_counts = self.repo.query_opportunities(filter_dto)

        # Determine saved status for current user if authenticated
        saved_ids: Set[str] = set()
        if filter_dto.user_id and raw_items:
            item_ids = [str(item["id"]) for item in raw_items]
            saved_ids = self.repo.get_saved_ids_for_user(filter_dto.user_id, item_ids)

        # Load personalization signals if user is authenticated
        user_prefs: Optional[UserPreferencesDTO] = None
        user_behavior: Optional[Tuple[List[str], List[str]]] = None
        if filter_dto.user_id:
            try:
                user_prefs = self.user_prefs_repo.get_preferences(filter_dto.user_id)
                user_behavior = self.user_prefs_repo.get_user_behavior_profile(filter_dto.user_id)
            except Exception as pe:
                logger.warning(f"Could not load preferences for user {filter_dto.user_id}: {pe}")

        today_dt = datetime.now(timezone.utc).date()
        cards: List[OpportunityCardDTO] = []

        for item in raw_items:
            item_id = str(item.get("id", ""))
            deadline_str = item.get("deadline")
            days_until = None
            is_expired = False

            if deadline_str:
                try:
                    d_clean = deadline_str.split("T")[0].split(" ")[0].strip()
                    d_date = datetime.strptime(d_clean, "%Y-%m-%d").date()
                    delta = (d_date - today_dt).days
                    days_until = delta
                    is_expired = delta < 0
                except Exception:
                    pass

            # Parse tags
            raw_tags = item.get("tags")
            tags: List[str] = []
            if isinstance(raw_tags, list):
                tags = [str(t).strip() for t in raw_tags if t]
            elif isinstance(raw_tags, str) and raw_tags.strip():
                try:
                    loaded = json.loads(raw_tags)
                    if isinstance(loaded, list):
                        tags = [str(t).strip() for t in loaded if t]
                    else:
                        tags = [str(loaded).strip()]
                except Exception:
                    tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

            # Description snippet
            desc = item.get("description") or ""
            clean_desc = re.sub(r"<[^>]+>", " ", desc)
            clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
            snippet = clean_desc[:220] + ("..." if len(clean_desc) > 220 else "")

            # Organization
            org = item.get("company") or item.get("provider") or item.get("source_id") or "CyberScout Verified"

            # Has stipend flag
            stipend_type = (item.get("stipend_type") or "unknown").lower()
            stipend_amt = item.get("stipend_amount")
            has_stipend = (
                stipend_type in {"paid", "performance_based", "expenses_covered"}
                or (stipend_amt is not None and float(stipend_amt) > 0)
            )

            # Is saved
            is_saved = item_id in saved_ids or filter_dto.saved_only

            # Evaluate scoring, explanation, and eligibility
            try:
                score_res = self.ranking_service.score_single_candidate(
                    candidate=item,
                    user_preferences=user_prefs,
                    saved_profile=user_behavior,
                    has_search_query=bool(filter_dto.keyword),
                    search_rank_score=float(item["rank"]) if "rank" in item and item["rank"] is not None else None,
                )
                rec_explanation = score_res.explanation.to_dict()
                match_strength = score_res.explanation.match_strength
                elig_status = score_res.eligibility.status.value
                ranking_score = score_res.final_score
            except Exception as se:
                logger.warning(f"Failed to score card {item_id}: {se}")
                rec_explanation = None
                match_strength = None
                elig_status = "UNKNOWN"
                ranking_score = 0.0

            lifecycle_status = item.get("lifecycle_status") or (
                "closing_soon" if (days_until is not None and 0 <= days_until <= 3) else ("expired" if is_expired else "active")
            )
            quality_status = item.get("quality_status") or "passed"
            is_closing_soon = (lifecycle_status == "closing_soon") or (days_until is not None and 0 <= days_until <= 3)
            is_verified = (quality_status == "passed") and ((item.get("completeness_score") is None) or float(item.get("completeness_score") or 0.0) >= 0.70)

            last_changed_str = item.get("last_changed_at") or item.get("updated_at")
            recently_updated = False
            if last_changed_str:
                try:
                    lc_date = datetime.fromisoformat(str(last_changed_str).replace("Z", "+00:00")).date()
                    if (today_dt - lc_date).days <= 7:
                        recently_updated = True
                except Exception:
                    pass

            card = OpportunityCardDTO(
                id=item_id,
                title=item.get("title") or "Untitled Opportunity",
                organization=org,
                category=item.get("category") or "general",
                opportunity_type=item.get("opportunity_type") or "other",
                description_snippet=snippet,
                url=item.get("url") or "",
                remote=bool(item.get("remote")),
                location=item.get("location"),
                pricing_type=item.get("pricing_type"),
                is_free=bool(item.get("is_free")),
                stipend_type=stipend_type if stipend_type != "unknown" else None,
                has_stipend=has_stipend,
                difficulty=item.get("difficulty"),
                score=float(item.get("score") or 0.0),
                deadline=deadline_str,
                days_until_deadline=days_until,
                is_expired=is_expired,
                source_name=item.get("source_id") or "verified",
                tags=tags[:5],
                is_saved=is_saved,
                relevance_rank=float(item["rank"]) if "rank" in item and item["rank"] is not None else None,
                recommendation_explanation=rec_explanation,
                match_strength=match_strength,
                eligibility_status=elig_status,
                lifecycle_status=lifecycle_status,
                quality_status=quality_status,
                is_closing_soon=is_closing_soon,
                is_verified=is_verified,
                recently_updated=recently_updated,
            )
            card._ranking_score = ranking_score  # type: ignore[attr-defined]
            cards.append(card)

        # If user explicitly requested 'recommended' sorting, reorder page results by dynamic ranking score
        if filter_dto.sort == "recommended":
            cards.sort(key=lambda c: getattr(c, "_ranking_score", 0.0), reverse=True)

        # Pagination calculations
        per_page = filter_dto.per_page
        page = filter_dto.page
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        has_next = page < total_pages
        has_prev = page > 1

        return PaginatedResultDTO(
            items=cards,
            total_count=total_count,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
            filter_dto=filter_dto,
            category_counts=facet_counts.get("categories", {}),
            type_counts=facet_counts.get("opportunity_types", {}),
            source_counts=facet_counts.get("sources", {}),
        )

    def get_opportunity_detail(
        self, opportunity_id: str, user_id: Optional[str] = None
    ) -> Optional[OpportunityDetailDTO]:
        """Fetch and assemble an OpportunityDetailDTO omitting internal secrets and tokens."""
        opp: Optional[Opportunity] = self.repo.read_by_id(opportunity_id)
        if not opp:
            return None

        # Check saved state
        is_saved = False
        if user_id:
            is_saved = self.repo.is_opportunity_saved(user_id, opp.id)

        today_dt = datetime.now(timezone.utc).date()
        days_until = None
        is_expired = False
        if opp.deadline:
            try:
                d_clean = opp.deadline.split("T")[0].split(" ")[0].strip()
                d_date = datetime.strptime(d_clean, "%Y-%m-%d").date()
                delta = (d_date - today_dt).days
                days_until = delta
                is_expired = delta < 0
            except Exception:
                pass

        org = opp.company or opp.provider or opp.source_id or "CyberScout Verified"
        stipend_type_val = (
            opp.stipend_type.value if hasattr(opp.stipend_type, "value") else (opp.stipend_type or "unknown")
        ).lower()
        has_stipend = (
            stipend_type_val in {"paid", "performance_based", "expenses_covered"}
            or (opp.stipend_amount is not None and float(opp.stipend_amount) > 0)
        )

        lifecycle_status = getattr(opp, "lifecycle_status", None) or (
            "closing_soon" if (days_until is not None and 0 <= days_until <= 3) else ("expired" if is_expired else "active")
        )
        quality_status = getattr(opp, "quality_status", None) or "passed"
        is_closing_soon = (lifecycle_status == "closing_soon") or (days_until is not None and 0 <= days_until <= 3)
        is_verified = (quality_status == "passed") and ((getattr(opp, "completeness_score", None) is None) or float(opp.completeness_score or 0.0) >= 0.70)

        last_changed_str = getattr(opp, "last_changed_at", None) or getattr(opp, "updated_at", None)
        recently_updated = False
        if last_changed_str:
            try:
                lc_date = datetime.fromisoformat(str(last_changed_str).replace("Z", "+00:00")).date()
                if (today_dt - lc_date).days <= 7:
                    recently_updated = True
            except Exception:
                pass

        # Phase 9: Compute Opportunity-to-Opportunity Similar Opportunities (available to all users)
        similar_cards: List[Dict[str, Any]] = []
        try:
            similar_raw = self.similarity_engine.find_similar_opportunities(opp, limit=4)
            for cand_dict, sim_score in similar_raw:
                c_tags = cand_dict.get("tags") or []
                if isinstance(c_tags, str):
                    try:
                        c_tags = json.loads(c_tags)
                    except Exception:
                        c_tags = [t.strip() for t in c_tags.split(",") if t.strip()]
                similar_cards.append({
                    "id": cand_dict.get("id"),
                    "title": cand_dict.get("title"),
                    "organization": cand_dict.get("company") or cand_dict.get("provider") or "CyberScout Verified",
                    "category": cand_dict.get("category") or "general",
                    "opportunity_type": cand_dict.get("opportunity_type") or "other",
                    "remote": cand_dict.get("remote"),
                    "deadline": cand_dict.get("deadline"),
                    "score": float(cand_dict.get("score") or 0.0),
                    "tags": c_tags[:4] if isinstance(c_tags, list) else [],
                    "similarity_score": round(sim_score, 2),
                })
        except Exception as se:
            logger.warning(f"Failed to find similar opportunities for {opportunity_id}: {se}")

        # Phase 9: Compute Explainable Match Analysis for authenticated users
        match_analysis = None
        if user_id:
            try:
                user_prefs = self.user_prefs_repo.get_preferences(user_id)
                user_behavior = self.user_prefs_repo.get_user_behavior_profile(user_id)
                if user_prefs:
                    match_analysis = self.match_analyzer.analyze_match(
                        opportunity=opp,
                        user_preferences=user_prefs,
                        saved_profile=user_behavior,
                    )
            except Exception as me:
                logger.warning(f"Failed to analyze match for user {user_id} on opp {opportunity_id}: {me}")

        return OpportunityDetailDTO(
            id=opp.id,
            title=opp.title or "Untitled Opportunity",
            organization=org,
            category=opp.category or "general",
            opportunity_type=opp.opportunity_type.value if hasattr(opp.opportunity_type, "value") else (opp.opportunity_type or "other"),
            description=opp.description or "No description provided.",
            url=opp.url or "",
            remote=opp.remote,
            location=opp.location,
            pricing_type=opp.pricing_type.value if hasattr(opp.pricing_type, "value") else (opp.pricing_type or "unknown"),
            is_free=bool(opp.is_free),
            stipend_type=stipend_type_val if stipend_type_val != "unknown" else None,
            stipend_amount=opp.stipend_amount,
            currency=opp.stipend_currency or opp.currency or "USD",
            has_stipend=has_stipend,
            difficulty=opp.difficulty,
            score=float(opp.score or 0.0),
            deadline=opp.deadline,
            days_until_deadline=days_until,
            is_expired=is_expired,
            source_id=opp.source_id,
            source_name=opp.source_id or "Verified Source",
            eligibility=opp.eligibility,
            duration=opp.duration,
            tags=list(opp.tags) if opp.tags else [],
            is_saved=is_saved,
            created_at=opp.first_seen_at or opp.discovered_date or "",
            last_harvested=opp.last_harvested_at or opp.last_seen or "",
            lifecycle_status=lifecycle_status,
            quality_status=quality_status,
            is_closing_soon=is_closing_soon,
            is_verified=is_verified,
            recently_updated=recently_updated,
            match_analysis=match_analysis,
            similar_opportunities=similar_cards,
        )

    def toggle_save_opportunity(self, user_id: str, opportunity_id: str) -> Dict[str, Any]:
        """
        Toggle bookmark status for user and opportunity.
        Returns dict with status: {'saved': bool, 'opportunity_id': str, 'saved_count': int}
        """
        if not user_id:
            raise ValueError("Authenticated user_id required to save opportunities.")

        is_currently_saved = self.repo.is_opportunity_saved(user_id, opportunity_id)
        if is_currently_saved:
            self.repo.unsave_opportunity_for_user(user_id, opportunity_id)
            new_saved = False
        else:
            self.repo.save_opportunity_for_user(user_id, opportunity_id)
            new_saved = True

        total_saved = self.repo.count_saved_opportunities(user_id)
        return {
            "success": True,
            "saved": new_saved,
            "opportunity_id": opportunity_id,
            "saved_count": total_saved,
        }

    def get_saved_count(self, user_id: Optional[str]) -> int:
        """Returns the number of saved opportunities for user."""
        if not user_id:
            return 0
        return self.repo.count_saved_opportunities(user_id)

    def get_recommended_for_you(
        self, user_id: Optional[str], limit: int = 6
    ) -> List[OpportunityCardDTO]:
        """
        Surfaces top recommended opportunities tailored to the user's explicit profile
        and behavioral patterns. Applies strict eligibility filtering (ineligible excluded)
        and controlled diversity (max 2 per provider).
        """
        user_prefs: Optional[UserPreferencesDTO] = None
        user_behavior: Optional[Tuple[List[str], List[str]]] = None
        if user_id:
            try:
                user_prefs = self.user_prefs_repo.get_preferences(user_id)
                user_behavior = self.user_prefs_repo.get_user_behavior_profile(user_id)
            except Exception as e:
                logger.warning(f"Error fetching user personalization data: {e}")

        # Fetch active candidate pool from database
        candidate_filter = QueryFilterDTO(
            page=1,
            per_page=48,
            sort="recommended",
            user_id=user_id,
        )
        candidates, _, _ = self.repo.query_opportunities(candidate_filter)
        if not candidates:
            return []

        saved_ids: Set[str] = set()
        if user_id:
            saved_ids = self.repo.get_saved_ids_for_user(user_id, [c["id"] for c in candidates])

        # Rank candidates using RankingService
        ranked_pairs = self.ranking_service.rank_candidates(
            candidates=candidates,
            user_preferences=user_prefs,
            saved_profile=user_behavior,
            has_search_query=False,
        )

        # Apply diversity & filter out ineligible
        diverse_pairs = self.ranking_service.filter_diverse_recommendations(
            scored_pairs=ranked_pairs,
            limit=limit,
        )

        today_dt = datetime.now(timezone.utc).date()
        result_cards: List[OpportunityCardDTO] = []

        for item, ranking_res in diverse_pairs:
            item_id = str(item.get("id", ""))
            deadline_str = item.get("deadline")
            days_until = None
            is_expired = False
            if deadline_str:
                try:
                    d_clean = deadline_str.split("T")[0].split(" ")[0].strip()
                    d_date = datetime.strptime(d_clean, "%Y-%m-%d").date()
                    delta = (d_date - today_dt).days
                    days_until = delta
                    is_expired = delta < 0
                except Exception:
                    pass

            raw_tags = item.get("tags")
            tags: List[str] = []
            if isinstance(raw_tags, list):
                tags = [str(t).strip() for t in raw_tags if t]
            elif isinstance(raw_tags, str) and raw_tags.strip():
                try:
                    loaded = json.loads(raw_tags)
                    if isinstance(loaded, list):
                        tags = [str(t).strip() for t in loaded if t]
                    else:
                        tags = [str(loaded).strip()]
                except Exception:
                    tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

            desc = item.get("description") or ""
            clean_desc = re.sub(r"<[^>]+>", " ", desc)
            clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
            snippet = clean_desc[:220] + ("..." if len(clean_desc) > 220 else "")

            org = item.get("company") or item.get("provider") or item.get("source_id") or "CyberScout Verified"
            stipend_type = (item.get("stipend_type") or "unknown").lower()
            stipend_amt = item.get("stipend_amount")
            has_stipend = (
                stipend_type in {"paid", "performance_based", "expenses_covered"}
                or (stipend_amt is not None and float(stipend_amt) > 0)
            )

            lifecycle_status = item.get("lifecycle_status") or (
                "closing_soon" if (days_until is not None and 0 <= days_until <= 3) else ("expired" if is_expired else "active")
            )
            quality_status = item.get("quality_status") or "passed"
            is_closing_soon = (lifecycle_status == "closing_soon") or (days_until is not None and 0 <= days_until <= 3)
            is_verified = (quality_status == "passed") and ((item.get("completeness_score") is None) or float(item.get("completeness_score") or 0.0) >= 0.70)

            last_changed_str = item.get("last_changed_at") or item.get("updated_at")
            recently_updated = False
            if last_changed_str:
                try:
                    lc_date = datetime.fromisoformat(str(last_changed_str).replace("Z", "+00:00")).date()
                    if (today_dt - lc_date).days <= 7:
                        recently_updated = True
                except Exception:
                    pass

            card = OpportunityCardDTO(
                id=item_id,
                title=item.get("title") or "Untitled Opportunity",
                organization=org,
                category=item.get("category") or "general",
                opportunity_type=item.get("opportunity_type") or "other",
                description_snippet=snippet,
                url=item.get("url") or "",
                remote=bool(item.get("remote")),
                location=item.get("location"),
                pricing_type=item.get("pricing_type"),
                is_free=bool(item.get("is_free")),
                stipend_type=stipend_type if stipend_type != "unknown" else None,
                has_stipend=has_stipend,
                difficulty=item.get("difficulty"),
                score=float(item.get("score") or 0.0),
                deadline=deadline_str,
                days_until_deadline=days_until,
                is_expired=is_expired,
                source_name=item.get("source_id") or "verified",
                tags=tags[:5],
                is_saved=item_id in saved_ids,
                recommendation_explanation=ranking_res.explanation.to_dict(),
                match_strength=ranking_res.explanation.match_strength,
                eligibility_status=ranking_res.eligibility.status.value,
                lifecycle_status=lifecycle_status,
                quality_status=quality_status,
                is_closing_soon=is_closing_soon,
                is_verified=is_verified,
                recently_updated=recently_updated,
            )
            result_cards.append(card)

        return result_cards

