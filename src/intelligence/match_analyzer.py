"""
Explainable Match Analyzer for CyberScout AI (Phase 9).

Performs deterministic, explainable evaluation of user profile alignment
against an opportunity. Maintains strict conceptual boundaries:
- Eligibility: Evaluated separately via EligibilityChecker.
- Relevance / Matching: Profile-to-opportunity attribute coverage.
- Similarity: Opportunity-to-opportunity overlap (SimilarityEngine).
- Ranking: Multi-signal ordering (RankingService).

Provides auditable, evidence-based explanations without speculative or unsupported claims.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from src.intelligence.skill_normalizer import (
    extract_opportunity_skills,
    normalize_skill,
    normalize_skill_list,
)
from src.models.recommendation_models import MatchAnalysisDTO, UserPreferencesDTO


# Centralized deterministic match weights summing to 1.0
MATCH_SCORE_WEIGHTS: Dict[str, float] = {
    "skill_match": 0.40,
    "category_match": 0.25,
    "type_match": 0.15,
    "remote_match": 0.10,
    "behavior_match": 0.10,
}


class MatchAnalyzer:
    """
    Evaluates profile-to-opportunity alignment and generates truthful,
    transparent match evidence and skill coverage analysis.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or MATCH_SCORE_WEIGHTS

    def analyze_match(
        self,
        opportunity: Any,
        user_preferences: Optional[UserPreferencesDTO] = None,
        saved_profile: Optional[Tuple[List[str], List[str]]] = None,
    ) -> MatchAnalysisDTO:
        """
        Analyzes how strongly and why an opportunity matches a user's declared profile.

        Args:
            opportunity: Opportunity model, DTO, or dictionary.
            user_preferences: Optional declared UserPreferencesDTO.
            saved_profile: Optional tuple of (saved_tags, saved_categories) from user behavior.

        Returns:
            MatchAnalysisDTO containing match status, score, skill coverage, and factual reasons.
        """
        opp_id = str(self._extract_field(opportunity, "id") or "")
        opp_category = self._extract_field(opportunity, "category") or ""
        opp_type = self._extract_field(opportunity, "opportunity_type") or ""
        opp_remote = self._extract_field(opportunity, "remote")
        if opp_remote is None:
            opp_remote = self._extract_field(opportunity, "is_remote")

        # Extract normalized opportunity skills
        opp_skills = extract_opportunity_skills(opportunity)

        # Cold-start or anonymous handling: if user has no preferences, return UNKNOWN match
        if not user_preferences or user_preferences.is_empty:
            return MatchAnalysisDTO(
                opportunity_id=opp_id,
                match_score=0.0,
                skill_coverage_ratio=0.0,
                matched_skills=[],
                missing_skills=opp_skills,
                matched_categories=[],
                matched_types=[],
                matched_preferences=[],
                reasons=[],
                match_strength="moderate",
                status="UNKNOWN",
            )

        user_skills_set = set(normalize_skill_list(user_preferences.skills or []))
        pref_categories_set = {normalize_skill(c) for c in (user_preferences.preferred_categories or []) if c}
        pref_types_set = {normalize_skill(t) for t in (user_preferences.preferred_types or []) if t}
        prefers_remote = user_preferences.prefers_remote

        # 1. Skill Matching & Coverage Categorization
        matched_skills: List[str] = []
        missing_skills: List[str] = []

        for s in opp_skills:
            if s in user_skills_set:
                matched_skills.append(s)
            else:
                # Strictly defined as "Skills not currently listed in your profile"
                missing_skills.append(s)

        matched_skills = sorted(matched_skills)
        missing_skills = sorted(missing_skills)

        if opp_skills:
            coverage_ratio = len(matched_skills) / float(len(opp_skills))
        else:
            # If opportunity lists no explicit skills: neutral coverage
            coverage_ratio = 1.0 if not user_skills_set else 0.5

        # Determine skill match status category
        if not opp_skills:
            status = "UNKNOWN"
        elif coverage_ratio >= 0.80:
            status = "MATCHED"
        elif coverage_ratio > 0.0:
            status = "PARTIAL_MATCH"
        else:
            status = "MISSING"

        # 2. Category & Opportunity Type Matching
        matched_categories: List[str] = []
        norm_cat = normalize_skill(opp_category)
        if norm_cat and norm_cat in pref_categories_set:
            matched_categories.append(norm_cat)
        elif norm_cat:
            # Partial substring matching
            for pc in pref_categories_set:
                if pc in norm_cat or norm_cat in pc:
                    matched_categories.append(pc)
                    break

        matched_types: List[str] = []
        norm_type = normalize_skill(opp_type)
        if norm_type and norm_type in pref_types_set:
            matched_types.append(norm_type)
        elif norm_type:
            for pt in pref_types_set:
                if pt in norm_type or norm_type in pt:
                    matched_types.append(pt)
                    break

        # 3. Remote Preference Matching
        matched_preferences: List[str] = []
        remote_score = 0.5
        if prefers_remote is not None and opp_remote is not None:
            if prefers_remote == opp_remote:
                remote_score = 1.0
                if prefers_remote:
                    matched_preferences.append("Remote Friendly")
                else:
                    matched_preferences.append("On-site Preference Aligned")
            else:
                remote_score = 0.1

        # 4. Behavioral Alignment Signal (from saved opportunities)
        saved_tags = saved_profile[0] if saved_profile else []
        saved_cats = saved_profile[1] if saved_profile else []
        behavior_score = 0.0
        if norm_cat and norm_cat in {normalize_skill(c) for c in saved_cats}:
            behavior_score += 0.5
            matched_preferences.append(f"Saved Similar {opp_category.title()} Opportunities")

        if opp_skills and saved_tags:
            clean_saved_tags = set(normalize_skill_list(saved_tags))
            overlap = set(opp_skills).intersection(clean_saved_tags)
            if overlap:
                behavior_score += min(0.5, len(overlap) * 0.15)

        behavior_score = max(0.0, min(1.0, behavior_score))

        # 5. Deterministic Combined Match Score
        cat_score = 1.0 if matched_categories else 0.0
        type_score = 1.0 if matched_types else 0.0
        skill_score = min(1.0, coverage_ratio)

        match_score = (
            (self.weights.get("skill_match", 0.40) * skill_score)
            + (self.weights.get("category_match", 0.25) * cat_score)
            + (self.weights.get("type_match", 0.15) * type_score)
            + (self.weights.get("remote_match", 0.10) * remote_score)
            + (self.weights.get("behavior_match", 0.10) * behavior_score)
        )
        match_score = max(0.0, min(1.0, match_score))

        # 6. Formulate Truthful, Factual Evidence Reasons
        reasons: List[str] = []

        if matched_categories:
            reasons.append(f"Matches your {matched_categories[0].title()} preference")

        if matched_skills:
            if len(matched_skills) == 1 and len(opp_skills) == 1:
                reasons.append(f"Matches your {matched_skills[0].title()} skill")
            elif opp_skills:
                reasons.append(f"{len(matched_skills)} of {len(opp_skills)} listed skills match your profile")
            else:
                reasons.append(f"Matches skills: {', '.join(s.title() for s in matched_skills[:3])}")

        if prefers_remote is True and opp_remote is True:
            reasons.append("Remote work matches your preference")

        if matched_types:
            reasons.append(f"In your preferred format ({matched_types[0].title()})")

        if behavior_score >= 0.50 and f"Saved Similar {opp_category.title()} Opportunities" not in reasons:
            reasons.append(f"Similar to opportunities you previously saved")

        # Determine match strength designation
        if match_score >= 0.65:
            match_strength = "strong"
        elif match_score >= 0.40:
            match_strength = "good"
        else:
            match_strength = "moderate"

        return MatchAnalysisDTO(
            opportunity_id=opp_id,
            match_score=match_score,
            skill_coverage_ratio=coverage_ratio,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            matched_categories=matched_categories,
            matched_types=matched_types,
            matched_preferences=matched_preferences,
            reasons=reasons[:4],
            match_strength=match_strength,
            status=status,
        )

    def _extract_field(self, item: Any, field_name: str, default: Any = None) -> Any:
        """Safely extracts a field from a model instance, DTO, or dictionary."""
        if isinstance(item, dict):
            return item.get(field_name, default)
        return getattr(item, field_name, default)
