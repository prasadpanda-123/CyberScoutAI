"""
Opportunity Similarity Engine for CyberScout AI (Phase 9).

Calculates deterministic, auditable opportunity-to-opportunity similarity
using a two-stage architecture:
- Stage 1: Bounded candidate retrieval via PostgreSQL (category, type, tags).
- Stage 2: In-memory deterministic multi-attribute scoring and diversity filtering.

Guarantees:
1. An opportunity is never returned as its own similar recommendation.
2. Quarantined, removed, or severely stale opportunities are strictly excluded.
3. Max 2 recommendations per organization/provider (controlled diversity).
4. Deterministic tie-breaking without random ordering.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.database.base_repository import row_to_dict
from src.intelligence.skill_normalizer import extract_opportunity_skills, normalize_skill
from src.intelligence.ranking_config import MAX_PER_ORGANIZATION_RECOMMENDATIONS
from src.models.opportunity import Opportunity

logger = get_logger(__name__)


# Centralized deterministic similarity feature weights summing to 1.0
SIMILARITY_WEIGHTS: Dict[str, float] = {
    "skill_overlap": 0.35,
    "category_overlap": 0.30,
    "type_overlap": 0.20,
    "provider_overlap": 0.10,
    "remote_overlap": 0.05,
}


class SimilarityEngine:
    """Computes deterministic similarity between cybersecurity opportunities."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        weights: Optional[Dict[str, float]] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.weights = weights or SIMILARITY_WEIGHTS

    def compute_similarity_score(
        self,
        target_opp: Any,
        candidate_opp: Any,
    ) -> float:
        """
        Computes normalized similarity between target and candidate opportunities in [0.0, 1.0].
        """
        # Strictly prevent self-similarity
        target_id = str(self._extract_field(target_opp, "id") or "")
        cand_id = str(self._extract_field(candidate_opp, "id") or "")
        if target_id and cand_id and target_id == cand_id:
            return 0.0

        # Extract normalized attributes
        target_skills = set(extract_opportunity_skills(target_opp))
        cand_skills = set(extract_opportunity_skills(candidate_opp))

        target_cat = normalize_skill(self._extract_field(target_opp, "category"))
        cand_cat = normalize_skill(self._extract_field(candidate_opp, "category"))

        target_type = normalize_skill(self._extract_field(target_opp, "opportunity_type"))
        cand_type = normalize_skill(self._extract_field(candidate_opp, "opportunity_type"))

        target_prov = normalize_skill(
            self._extract_field(target_opp, "company")
            or self._extract_field(target_opp, "provider")
            or self._extract_field(target_opp, "organization")
        )
        cand_prov = normalize_skill(
            self._extract_field(candidate_opp, "company")
            or self._extract_field(candidate_opp, "provider")
            or self._extract_field(candidate_opp, "organization")
        )

        target_remote = self._extract_field(target_opp, "remote")
        if target_remote is None:
            target_remote = self._extract_field(target_opp, "is_remote")
        cand_remote = self._extract_field(candidate_opp, "remote")
        if cand_remote is None:
            cand_remote = self._extract_field(candidate_opp, "is_remote")

        # 1. Skill Overlap (Jaccard Similarity)
        if target_skills and cand_skills:
            intersection = target_skills.intersection(cand_skills)
            union = target_skills.union(cand_skills)
            skill_score = len(intersection) / float(len(union))
        elif not target_skills and not cand_skills:
            skill_score = 0.5  # Neutral baseline when neither record has skill tags
        else:
            skill_score = 0.0

        # 2. Category Overlap
        cat_score = 1.0 if (target_cat and cand_cat and target_cat == cand_cat) else 0.0

        # 3. Opportunity Type Overlap
        type_score = 1.0 if (target_type and cand_type and target_type == cand_type) else 0.0

        # 4. Provider / Organization Overlap
        prov_score = 1.0 if (target_prov and cand_prov and target_prov == cand_prov) else 0.0

        # 5. Remote Work Status Overlap
        remote_score = 1.0 if (target_remote is not None and cand_remote is not None and target_remote == cand_remote) else 0.5

        score = (
            (self.weights.get("skill_overlap", 0.35) * skill_score)
            + (self.weights.get("category_overlap", 0.30) * cat_score)
            + (self.weights.get("type_overlap", 0.20) * type_score)
            + (self.weights.get("provider_overlap", 0.10) * prov_score)
            + (self.weights.get("remote_overlap", 0.05) * remote_score)
        )

        return max(0.0, min(1.0, score))

    def find_similar_opportunities(
        self,
        target_opp: Any,
        limit: int = 4,
        max_candidates: int = 50,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Retrieves top similar opportunities using two-stage bounded PostgreSQL filtering
        and deterministic diversity re-ranking.

        Returns:
            List of tuples: (candidate_dict, similarity_score).
        """
        target_id = str(self._extract_field(target_opp, "id") or "")
        target_cat = str(self._extract_field(target_opp, "category") or "").strip()
        target_type = str(self._extract_field(target_opp, "opportunity_type") or "").strip()

        if not target_id:
            return []

        # Stage 1: Bounded Candidate Retrieval from PostgreSQL
        # Filters candidates by category or opportunity type, excluding target_id and invalid quality/lifecycle states
        sql = """
        SELECT o.id, o.title, o.category, o.opportunity_type, o.provider, o.company,
               o.location, o.remote, o.is_free, o.pricing_type, o.stipend_type, o.stipend_amount,
               o.deadline, o.tags, o.score, o.quality_status, o.lifecycle_status, o.description
        FROM "Opportunities" o
        WHERE o.id != %s
          AND (o.quality_status IS NULL OR LOWER(o.quality_status) NOT IN ('quarantined', 'severely_stale'))
          AND (o.lifecycle_status IS NULL OR LOWER(o.lifecycle_status) NOT IN ('removed', 'closed'))
          AND (
              (o.category = %s AND %s != '')
              OR (o.opportunity_type = %s AND %s != '')
          )
        ORDER BY o.score DESC, o.id ASC
        LIMIT %s;
        """

        conn = self.db_manager.get_connection()
        candidates: List[Dict[str, Any]] = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                sql,
                (target_id, target_cat, target_cat, target_type, target_type, max_candidates),
            )
            rows = cursor.fetchall()
            cursor.close()
            candidates = [row_to_dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"Error querying similar opportunity candidates for {target_id}: {e}")
            return []
        finally:
            try:
                conn.close()
            except Exception:
                pass

        # Stage 2: Deterministic Scoring & Diversity Filtering
        scored_candidates: List[Tuple[Dict[str, Any], float]] = []
        for cand in candidates:
            sim_score = self.compute_similarity_score(target_opp, cand)
            if sim_score > 0.05:  # Require positive baseline alignment
                scored_candidates.append((cand, sim_score))

        # Deterministic sorting:
        # 1. Base opportunity id ASC for stability
        scored_candidates.sort(key=lambda item: str(item[0].get("id", "")))
        # 2. similarity DESC, base quality score DESC
        scored_candidates.sort(
            key=lambda item: (
                item[1],
                float(item[0].get("score") or 0.0),
            ),
            reverse=True,
        )

        # Enforce controlled diversity: Max recommendations per organization
        selected: List[Tuple[Dict[str, Any], float]] = []
        org_counts: Dict[str, int] = {}

        for cand, score in scored_candidates:
            if len(selected) >= limit:
                break

            provider = normalize_skill(
                cand.get("company") or cand.get("provider") or "CyberScout Verified"
            )
            count = org_counts.get(provider, 0)
            if count < MAX_PER_ORGANIZATION_RECOMMENDATIONS:
                selected.append((cand, score))
                org_counts[provider] = count + 1

        return selected

    def _extract_field(self, item: Any, field_name: str, default: Any = None) -> Any:
        """Safely extracts a field from a model instance, DTO, or dictionary."""
        if isinstance(item, dict):
            return item.get(field_name, default)
        return getattr(item, field_name, default)
