"""
Feature Extractors for CyberScout AI Opportunity Ranking.

All extractor functions calculate deterministic, normalized features strictly
bounded within [0.0, 1.0] without external side effects or machine learning dependencies.
"""

from datetime import date, datetime, timezone
import re
from typing import Any, List, Optional, Set, Tuple

from src.intelligence.ranking_config import TRUSTED_PROVIDERS


def normalize_token(text: Optional[str]) -> str:
    """Helper to lowercase, strip, and clean token strings."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text).strip().lower())


def compute_skill_match(
    user_skills: List[str],
    opp_tags: Optional[List[str]],
    opp_text: Optional[str] = None,
) -> Tuple[float, List[str]]:
    """
    Computes normalized skill match between declared user skills and opportunity metadata.

    Args:
        user_skills: List of skills declared by the user.
        opp_tags: Tags or skills associated with the opportunity.
        opp_text: Title + description text to search for skill mentions if tags are sparse.

    Returns:
        Tuple of (score in [0.0, 1.0], list of matched skill names).
    """
    if not user_skills:
        return 0.0, []

    cleaned_user_skills: List[str] = [normalize_token(s) for s in user_skills if normalize_token(s)]
    if not cleaned_user_skills:
        return 0.0, []

    matched_skills: Set[str] = set()

    # 1. Match against opportunity tags
    cleaned_opp_tags = {normalize_token(t) for t in (opp_tags or []) if normalize_token(t)}
    for skill in cleaned_user_skills:
        if skill in cleaned_opp_tags:
            matched_skills.add(skill)

    # 2. Text boundary fallback matching if text provided and tags didn't match all
    if opp_text and len(matched_skills) < len(cleaned_user_skills):
        text_lower = opp_text.lower()
        for skill in cleaned_user_skills:
            if skill in matched_skills:
                continue
            # Use regex word boundary check for safe matching (e.g. 'c' vs 'css', 'go' vs 'good')
            escaped = re.escape(skill)
            pattern = rf"\b{escaped}\b"
            if re.search(pattern, text_lower):
                matched_skills.add(skill)

    ratio = len(matched_skills) / float(len(cleaned_user_skills))
    score = max(0.0, min(1.0, ratio))
    return score, sorted(list(matched_skills))


def compute_category_match(
    preferred_categories: List[str],
    opp_category: Optional[str],
) -> Tuple[float, Optional[str]]:
    """
    Checks if opportunity category matches any of the user's preferred categories.

    Returns:
        Tuple of (1.0 or 0.0, matching category or None).
    """
    if not preferred_categories or not opp_category:
        return 0.0, None

    cleaned_prefs = {normalize_token(c) for c in preferred_categories if normalize_token(c)}
    cleaned_opp_cat = normalize_token(opp_category)

    if cleaned_opp_cat in cleaned_prefs:
        return 1.0, cleaned_opp_cat

    # Partial / substring match for categories (e.g., 'internship' in 'cybersecurity internship')
    for pref in cleaned_prefs:
        if pref in cleaned_opp_cat or cleaned_opp_cat in pref:
            return 1.0, pref

    return 0.0, None


def compute_type_match(
    preferred_types: List[str],
    opp_type: Optional[str],
) -> Tuple[float, Optional[str]]:
    """
    Checks if opportunity type matches user preferences.

    Returns:
        Tuple of (1.0 or 0.0, matching type or None).
    """
    if not preferred_types or not opp_type:
        return 0.0, None

    cleaned_prefs = {normalize_token(t) for t in preferred_types if normalize_token(t)}
    cleaned_opp_type = normalize_token(opp_type)

    if cleaned_opp_type in cleaned_prefs:
        return 1.0, cleaned_opp_type

    for pref in cleaned_prefs:
        if pref in cleaned_opp_type or cleaned_opp_type in pref:
            return 1.0, pref

    return 0.0, None


def compute_remote_match(
    prefers_remote: Optional[bool],
    opp_remote: Optional[bool],
) -> float:
    """
    Scores remote preference alignment. Missing information is treated as neutral (0.5).

    Returns:
        Score in [0.0, 1.0].
    """
    if prefers_remote is None:
        # User has no remote preference: neutral
        return 0.5

    if opp_remote is None:
        # Opportunity remote status is unknown: neutral
        return 0.5

    if prefers_remote == opp_remote:
        return 1.0

    # User prefers remote but opp is strictly onsite, or vice versa
    return 0.1


def compute_deadline_urgency(
    deadline_val: Any,
    current_date: Optional[date] = None,
) -> Tuple[float, Optional[int]]:
    """
    Scores opportunity urgency based on closing deadline proximity.

    Returns:
        Tuple of (score in [0.0, 1.0], days_remaining or None).
    """
    if current_date is None:
        current_date = datetime.now(timezone.utc).date()

    if not deadline_val:
        return 0.3, None  # Neutral baseline for opportunities without explicit deadline

    parsed_date: Optional[date] = None
    if isinstance(deadline_val, datetime):
        parsed_date = deadline_val.date()
    elif isinstance(deadline_val, date):
        parsed_date = deadline_val
    elif isinstance(deadline_val, str):
        deadline_str = deadline_val.strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y/%m/%d"):
            try:
                parsed_date = datetime.strptime(deadline_str[:10], fmt[:8] if "T" in fmt else fmt).date()
                break
            except (ValueError, TypeError):
                continue

    if not parsed_date:
        return 0.3, None

    days_left = (parsed_date - current_date).days

    if days_left < 0:
        # Expired
        return 0.0, days_left
    if days_left <= 3:
        # Very urgent closing soon
        return 1.0, days_left
    if days_left <= 14:
        # Closing in 1-2 weeks
        return 0.85, days_left
    if days_left <= 30:
        # Closing within a month
        return 0.65, days_left
    if days_left <= 60:
        return 0.40, days_left

    # Far away (>60 days)
    return 0.20, days_left


def compute_freshness(
    first_seen_at: Any,
    discovered_date: Any = None,
    current_date: Optional[date] = None,
    quality_status: Optional[str] = None,
    last_harvested_at: Any = None,
) -> float:
    """
    Scores freshness based on genuine ingestion timestamp (preserves Phase 2.1 semantics)
    and applies deterministic stale penalties based on Phase 6 quality_status / harvest recency.

    Returns:
        Score in [0.0, 1.0].
    """
    if current_date is None:
        current_date = datetime.now(timezone.utc).date()

    # Phase 6 Stale status penalties
    clean_status = (quality_status or "").lower().strip()
    if clean_status == "severely_stale":
        return 0.05

    ref_date = first_seen_at or discovered_date
    if not ref_date:
        base_score = 0.3
    else:
        parsed_date: Optional[date] = None
        if isinstance(ref_date, datetime):
            parsed_date = ref_date.date()
        elif isinstance(ref_date, date):
            parsed_date = ref_date
        elif isinstance(ref_date, str):
            try:
                parsed_date = datetime.fromisoformat(ref_date.replace("Z", "+00:00")).date()
            except Exception:
                try:
                    parsed_date = datetime.strptime(ref_date[:10], "%Y-%m-%d").date()
                except Exception:
                    parsed_date = None

        if not parsed_date:
            base_score = 0.3
        else:
            days_old = max(0, (current_date - parsed_date).days)
            if days_old <= 2:
                base_score = 1.0
            elif days_old <= 7:
                base_score = 0.85
            elif days_old <= 14:
                base_score = 0.65
            elif days_old <= 30:
                base_score = 0.45
            else:
                base_score = 0.20

    # Apply stale penalty if quality_status is stale or last_harvested_at is ancient
    if clean_status == "stale":
        return min(base_score, 0.35)

    if last_harvested_at:
        try:
            if isinstance(last_harvested_at, datetime):
                h_date = last_harvested_at.date()
            elif isinstance(last_harvested_at, date):
                h_date = last_harvested_at
            else:
                h_date = datetime.fromisoformat(str(last_harvested_at).replace("Z", "+00:00")).date()
            days_harvest = (current_date - h_date).days
            if days_harvest > 30:
                return 0.05
            elif days_harvest > 7:
                return min(base_score, 0.35)
        except Exception:
            pass

    return base_score


def compute_source_trust(
    source_id: Optional[str] = None,
    provider: Optional[str] = None,
) -> float:
    """
    Evaluates source reliability tier.

    Returns:
        Score in [0.0, 1.0].
    """
    clean_provider = normalize_token(provider)
    clean_source = normalize_token(source_id)

    # Check official trusted cyber bodies (CISA, NIST, SANS, etc.)
    for trusted in TRUSTED_PROVIDERS:
        if trusted in clean_provider or trusted in clean_source:
            return 1.0

    if clean_provider or clean_source:
        return 0.70  # Established identifiable source

    return 0.40  # Generic or unidentified source


def compute_base_quality(opp_score: Optional[float]) -> float:
    """
    Normalizes the Phase 1/2 opportunity score (0-100 scale) to [0.0, 1.0].

    Returns:
        Score in [0.0, 1.0].
    """
    if opp_score is None:
        return 0.30
    try:
        val = float(opp_score)
        if val <= 0.0:
            return 0.0
        if val >= 100.0:
            return 1.0
        return val / 100.0
    except (ValueError, TypeError):
        return 0.30


def compute_user_behavior_match(
    saved_tags: List[str],
    saved_categories: List[str],
    opp_tags: Optional[List[str]],
    opp_category: Optional[str],
) -> float:
    """
    Evaluates alignment with user's past saved opportunity patterns.

    Returns:
        Score in [0.0, 1.0].
    """
    if not saved_tags and not saved_categories:
        return 0.0  # Cold start: neutral, no contribution

    score = 0.0
    matches = 0

    if opp_category and saved_categories:
        norm_cat = normalize_token(opp_category)
        if norm_cat in {normalize_token(c) for c in saved_categories}:
            score += 0.5
            matches += 1

    if opp_tags and saved_tags:
        clean_saved = {normalize_token(t) for t in saved_tags if normalize_token(t)}
        clean_opp = {normalize_token(t) for t in opp_tags if normalize_token(t)}
        overlap = clean_saved.intersection(clean_opp)
        if overlap:
            tag_score = min(0.5, len(overlap) * 0.15)
            score += tag_score
            matches += 1

    return max(0.0, min(1.0, score))


def compute_search_relevance(rank_score: Optional[float]) -> float:
    """
    Normalizes PostgreSQL ts_rank relevance to [0.0, 1.0].

    PostgreSQL ts_rank typically yields values in [0.0, 0.5] for standard queries.
    """
    if rank_score is None:
        return 0.0
    try:
        val = float(rank_score)
        if val <= 0.0:
            return 0.0
        # Scale typical FTS rank score to [0.0, 1.0]
        return min(1.0, val * 2.5)
    except (ValueError, TypeError):
        return 0.0
