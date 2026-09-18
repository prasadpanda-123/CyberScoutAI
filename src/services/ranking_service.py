"""
Ranking Service for CyberScout AI.

Provides deterministic, explainable, multi-signal ranking and personalization
above the database discovery layer.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from src.core.logging import get_logger
from src.intelligence.ranking_config import (
    DEFAULT_DISCOVERY_WEIGHTS,
    DEFAULT_SEARCH_WEIGHTS,
    MAX_PER_ORGANIZATION_RECOMMENDATIONS,
    STRONG_MATCH_THRESHOLD,
    GOOD_MATCH_THRESHOLD,
    validate_weights,
)
from src.intelligence.feature_extractors import (
    compute_skill_match,
    compute_category_match,
    compute_type_match,
    compute_remote_match,
    compute_deadline_urgency,
    compute_freshness,
    compute_source_trust,
    compute_base_quality,
    compute_user_behavior_match,
    compute_search_relevance,
)
from src.intelligence.eligibility_checker import EligibilityChecker
from src.models.recommendation_models import (
    EligibilityResult,
    EligibilityStatus,
    RankingResultDTO,
    RecommendationExplanationDTO,
    UserPreferencesDTO,
)

logger = get_logger(__name__)


class RankingService:
    """Orchestrates candidate scoring, personalization, diversity filtering, and explanation generation."""

    def __init__(
        self,
        discovery_weights: Optional[Dict[str, float]] = None,
        search_weights: Optional[Dict[str, float]] = None,
        eligibility_checker: Optional[EligibilityChecker] = None,
    ):
        self.discovery_weights = discovery_weights or DEFAULT_DISCOVERY_WEIGHTS
        self.search_weights = search_weights or DEFAULT_SEARCH_WEIGHTS
        validate_weights(self.discovery_weights)
        validate_weights(self.search_weights)
        self.eligibility_checker = eligibility_checker or EligibilityChecker()

    def _extract_field(self, item: Any, field_name: str, default: Any = None) -> Any:
        """Safely extracts a field from a DTO, model instance, or dictionary."""
        if isinstance(item, dict):
            return item.get(field_name, default)
        return getattr(item, field_name, default)

    def generate_explanation(
        self,
        feature_scores: Dict[str, float],
        matched_skills: List[str],
        matched_cat: Optional[str],
        matched_type: Optional[str],
        prefers_remote: Optional[bool],
        opp_remote: Optional[bool],
        days_left: Optional[int],
        final_score: float,
        provider: Optional[str],
    ) -> RecommendationExplanationDTO:
        """Generates 1 to 3 human-readable, truthful explanation reasons for a recommendation."""
        reasons: List[str] = []
        highlight_tags: List[str] = []

        # 1. Skill match explanation
        if matched_skills:
            if len(matched_skills) <= 2:
                reasons.append(f"Matches skills: {', '.join(s.title() for s in matched_skills)}")
            else:
                top_s = [s.title() for s in matched_skills[:2]]
                reasons.append(f"Matches {len(matched_skills)} skills ({', '.join(top_s)}, +{len(matched_skills)-2} more)")
            highlight_tags.extend(matched_skills[:3])

        # 2. Category / Type match
        if matched_type:
            reasons.append(f"Matches your {matched_type.title()} preference")
        elif matched_cat:
            reasons.append(f"In your preferred category ({matched_cat.title()})")

        # 3. Remote match
        if prefers_remote is True and opp_remote is True:
            reasons.append("Remote friendly")

        # 4. Closing soon urgency
        if days_left is not None and 0 <= days_left <= 14:
            if days_left == 0:
                reasons.append("Closes today")
            elif days_left == 1:
                reasons.append("Closing tomorrow")
            else:
                reasons.append(f"Closing in {days_left} days")

        # 5. Search relevance signal
        if feature_scores.get("search_relevance", 0.0) >= 0.70 and len(reasons) < 3:
            reasons.append("Strong keyword relevance")

        # 6. Source trust signal
        if feature_scores.get("source_trust", 0.0) >= 0.90 and len(reasons) < 3:
            reasons.append(f"Official opportunity from {provider or 'verified authority'}")

        # 7. Saved behavior signal
        if feature_scores.get("user_behavior", 0.0) >= 0.50 and len(reasons) < 3:
            reasons.append("Similar to opportunities you saved")

        # Fallback explanation if no explicit match found
        if not reasons:
            if final_score >= STRONG_MATCH_THRESHOLD:
                reasons.append("High quality verified opportunity")
            else:
                reasons.append("Popular in discovery")

        # Determine match strength label
        if final_score >= STRONG_MATCH_THRESHOLD:
            strength = "strong"
        elif final_score >= GOOD_MATCH_THRESHOLD:
            strength = "good"
        else:
            strength = "moderate"

        return RecommendationExplanationDTO(
            reasons=reasons[:4],
            highlight_tags=highlight_tags,
            match_strength=strength,
        )

    def score_single_candidate(
        self,
        candidate: Any,
        user_preferences: Optional[UserPreferencesDTO] = None,
        saved_profile: Optional[Tuple[List[str], List[str]]] = None,
        has_search_query: bool = False,
        search_rank_score: Optional[float] = None,
    ) -> RankingResultDTO:
        """
        Calculates all features and the final ranking score for a single candidate.
        """
        weights = self.search_weights if has_search_query else self.discovery_weights

        # Extract candidate attributes safely
        cand_id = str(self._extract_field(candidate, "id") or "")
        title = str(self._extract_field(candidate, "title") or "")
        desc = str(self._extract_field(candidate, "description") or "")
        tags = self._extract_field(candidate, "tags") or []
        category = self._extract_field(candidate, "category")
        opp_type = self._extract_field(candidate, "opportunity_type")
        is_remote = self._extract_field(candidate, "remote")
        if is_remote is None:
            is_remote = self._extract_field(candidate, "is_remote")
        deadline = self._extract_field(candidate, "deadline")
        first_seen = self._extract_field(candidate, "first_seen_at") or self._extract_field(candidate, "discovered_date")
        source_id = self._extract_field(candidate, "source_id")
        provider = self._extract_field(candidate, "provider") or self._extract_field(candidate, "organization")
        base_score = self._extract_field(candidate, "score")

        full_text = f"{title} {desc}"

        user_skills = user_preferences.skills if user_preferences else []
        pref_cats = user_preferences.preferred_categories if user_preferences else []
        pref_types = user_preferences.preferred_types if user_preferences else []
        prefers_remote = user_preferences.prefers_remote if user_preferences else None

        saved_tags = saved_profile[0] if saved_profile else []
        saved_cats = saved_profile[1] if saved_profile else []

        quality_status = self._extract_field(candidate, "quality_status")
        last_harvested = self._extract_field(candidate, "last_harvested_at")

        # 1. Compute Individual Normalized Features in [0.0, 1.0]
        f_skill, matched_skills = compute_skill_match(user_skills, tags, full_text)
        f_cat, matched_cat = compute_category_match(pref_cats, category)
        f_type, matched_type = compute_type_match(pref_types, opp_type)
        f_remote = compute_remote_match(prefers_remote, is_remote)
        f_deadline, days_left = compute_deadline_urgency(deadline)
        f_freshness = compute_freshness(
            first_seen_at=first_seen,
            quality_status=quality_status,
            last_harvested_at=last_harvested,
        )
        f_source = compute_source_trust(source_id, provider)
        f_base = compute_base_quality(base_score)
        f_behavior = compute_user_behavior_match(saved_tags, saved_cats, tags, category)
        f_relevance = compute_search_relevance(search_rank_score)

        features = {
            "skill_match": f_skill,
            "category_match": f_cat,
            "type_match": f_type,
            "remote_match": f_remote,
            "deadline_urgency": f_deadline,
            "freshness": f_freshness,
            "source_trust": f_source,
            "base_quality": f_base,
            "user_behavior": f_behavior,
            "search_relevance": f_relevance,
        }

        # 2. Weighted Sum
        final_score = 0.0
        for feat_name, weight in weights.items():
            final_score += features.get(feat_name, 0.0) * weight

        # Guarantee bounded score in [0.0, 1.0]
        final_score = max(0.0, min(1.0, final_score))

        # Phase 6 Quarantine Isolation: Quarantined candidates receive 0.0 score
        if (quality_status or "").lower().strip() == "quarantined":
            final_score = 0.0

        # 3. Independent Eligibility Evaluation
        eligibility = self.eligibility_checker.check_eligibility(candidate, user_preferences)

        # 4. Human-Readable Explanation
        explanation = self.generate_explanation(
            feature_scores=features,
            matched_skills=matched_skills,
            matched_cat=matched_cat,
            matched_type=matched_type,
            prefers_remote=prefers_remote,
            opp_remote=is_remote,
            days_left=days_left,
            final_score=final_score,
            provider=provider,
        )

        return RankingResultDTO(
            opportunity_id=cand_id,
            final_score=final_score,
            feature_scores=features,
            eligibility=eligibility,
            explanation=explanation,
        )

    def rank_candidates(
        self,
        candidates: List[Any],
        user_preferences: Optional[UserPreferencesDTO] = None,
        saved_profile: Optional[Tuple[List[str], List[str]]] = None,
        has_search_query: bool = False,
    ) -> List[Tuple[Any, RankingResultDTO]]:
        """
        Ranks candidate opportunities with deterministic tie-breaking.
        """
        if not candidates:
            return []

        scored_pairs: List[Tuple[Any, RankingResultDTO]] = []

        for cand in candidates:
            rank_score = self._extract_field(cand, "rank_score")
            try:
                res = self.score_single_candidate(
                    candidate=cand,
                    user_preferences=user_preferences,
                    saved_profile=saved_profile,
                    has_search_query=has_search_query,
                    search_rank_score=rank_score,
                )
            except Exception as e:
                logger.warning(f"Error scoring candidate {cand}: {e}")
                # Fallback ranking result
                res = RankingResultDTO(
                    opportunity_id=str(self._extract_field(cand, "id", "")),
                    final_score=0.10,
                )
            scored_pairs.append((cand, res))

        # Deterministic sorting:
        # 1. First sort by opportunity_id ASC as a stable baseline
        scored_pairs.sort(key=lambda pair: str(self._extract_field(pair[0], "id", "")))

        # 2. Sort by final_score DESC, base_quality DESC, eligibility DESC
        scored_pairs.sort(
            key=lambda pair: (
                pair[1].final_score,
                pair[1].feature_scores.get("base_quality", 0.0),
                1 if pair[1].eligibility.status == EligibilityStatus.ELIGIBLE else 0,
            ),
            reverse=True,
        )

        return scored_pairs

    def filter_diverse_recommendations(
        self,
        scored_pairs: List[Tuple[Any, RankingResultDTO]],
        limit: int = 6,
    ) -> List[Tuple[Any, RankingResultDTO]]:
        """
        Applies controlled diversity and strict eligibility exclusion:
        - Never recommends INELIGIBLE opportunities.
        - Never recommends QUARANTINED, SEVERELY_STALE, or REMOVED opportunities.
        - Strictly limits occurrences from any single provider/organization to MAX_PER_ORGANIZATION_RECOMMENDATIONS.
        """
        selected: List[Tuple[Any, RankingResultDTO]] = []
        org_counts: Dict[str, int] = {}

        for cand, res in scored_pairs:
            if len(selected) >= limit:
                break

            # Ineligible opportunities MUST NEVER be surfaced in recommendations
            if res.eligibility.status == EligibilityStatus.INELIGIBLE:
                continue

            # Phase 6 Quarantine & Stale Exclusion: Quarantined, removed, or severely stale opportunities MUST NEVER be recommended
            q_status = str(self._extract_field(cand, "quality_status") or "").lower().strip()
            l_status = str(self._extract_field(cand, "lifecycle_status") or "").lower().strip()
            if q_status in ("quarantined", "severely_stale") or l_status in ("removed", "closed"):
                continue

            provider = str(self._extract_field(cand, "organization") or self._extract_field(cand, "provider") or "unknown").strip().lower()
            current_org_count = org_counts.get(provider, 0)

            if current_org_count < MAX_PER_ORGANIZATION_RECOMMENDATIONS:
                selected.append((cand, res))
                org_counts[provider] = current_org_count + 1

        return selected
