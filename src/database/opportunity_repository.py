"""
Opportunity Repository for CyberScout AI.

Handles database CRUD, upserts, duplicate management, and lifecycle status
updates for Opportunity objects in PostgreSQL.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from src.database.base_repository import BaseRepository
from src.database.connection import DatabaseManager
from src.database.interfaces import IOpportunityRepository
from src.models.enums import ChangeClassification, Status
from src.models.opportunity import Opportunity
from src.core.exceptions import RepositoryError
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PersistenceResult:
    """Metrics and counts resulting from a harvesting persistence operation."""

    collected_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    reopened_count: int = 0
    duplicate_count: int = 0
    quarantined_count: int = 0
    failed_count: int = 0
    saved_count: int = 0
    new_items: List[Opportunity] = field(default_factory=list)
    updated_items: List[Opportunity] = field(default_factory=list)
    reopened_items: List[Opportunity] = field(default_factory=list)

    def __int__(self) -> int:
        return self.saved_count

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, int):
            return self.saved_count == other
        return super().__eq__(other)

    def __index__(self) -> int:
        return self.saved_count

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OpportunityRepository(BaseRepository[Opportunity], IOpportunityRepository):
    """
    DAO for managing Opportunity records in PostgreSQL.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        super().__init__(db_manager=db_manager)

    @property
    def table_name(self) -> str:
        return "Opportunities"

    @property
    def primary_key(self) -> str:
        return "id"

    def _entity_to_dict(self, entity: Opportunity) -> Dict[str, Any]:
        opp = entity
        url_hash = opp.generate_url_hash()
        return {
            "id": opp.id,
            "title": opp.title,
            "description": opp.description,
            "url": opp.url,
            "url_hash": url_hash,
            "source_id": opp.source_id,
            "category": opp.category,
            "provider": opp.provider,
            "company": opp.company,
            "location": opp.location,
            "remote": opp.remote,
            "paid": opp.paid,
            "certificate": opp.certificate,
            "price_raw": opp.price_raw,
            "price_normalized": opp.price_normalized,
            "currency": opp.currency,
            "deadline": opp.deadline,
            "published_date": opp.published_date,
            "discovered_date": opp.discovered_date,
            "duration": opp.duration,
            "difficulty": opp.difficulty,
            "tags": json.dumps(opp.tags),
            "beginner_friendly": opp.beginner_friendly,
            "score": opp.score,
            "score_breakdown": json.dumps(opp.score_breakdown),
            "confidence_score": opp.confidence_score,
            "quality_score": opp.quality_score,
            "is_rejected": opp.is_rejected,
            "rejection_reason": opp.rejection_reason,
            "quality_flags": opp.quality_flags,
            "topic_score": opp.topic_score,
            "keyword_score": opp.keyword_score,
            "spam_score": opp.spam_score,
            "freshness_score": opp.freshness_score,
            "provider_score": opp.provider_score,
            "link_status": opp.link_status,
            "verification_status": opp.verification_status,
            "last_verified": opp.last_verified,
            "expired": opp.expired,
            "archived": opp.archived,
            "status": opp.status,
            "duplicate_of_id": opp.duplicate_of_id,
            "run_id": opp.run_id,
            "raw_data": json.dumps(opp.raw_data),
            "last_seen": opp.last_seen,
            "opportunity_type": opp.opportunity_type.value if hasattr(opp.opportunity_type, "value") else opp.opportunity_type,
            "pricing_type": opp.pricing_type.value if hasattr(opp.pricing_type, "value") else (opp.pricing_type or "UNKNOWN"),
            "price_amount": opp.price_amount,
            "application_fee": opp.application_fee,
            "certificate_fee": opp.certificate_fee,
            "is_free": opp.is_free,
            "free_conditions": opp.free_conditions,
            "stipend_type": opp.stipend_type.value if hasattr(opp.stipend_type, "value") else (opp.stipend_type or "UNKNOWN"),
            "stipend_amount": opp.stipend_amount,
            "stipend_currency": opp.stipend_currency,
            "certificate_available": opp.certificate_available.value if hasattr(opp.certificate_available, "value") else (opp.certificate_available or "UNKNOWN"),
            "certificate_cost": opp.certificate_cost.value if hasattr(opp.certificate_cost, "value") else (opp.certificate_cost or "UNKNOWN"),
            "eligibility": opp.eligibility,
            "requirements": opp.requirements,
            "source_external_id": opp.source_external_id,
            "canonical_url": opp.canonical_url or opp.url,
            "identity_fingerprint": opp.identity_fingerprint or opp.compute_identity_fingerprint(),
            "first_seen_at": opp.first_seen_at,
            "last_seen_at": opp.last_seen_at,
            "last_changed_at": opp.last_changed_at,
            "last_harvested_at": opp.last_harvested_at,
            "lifecycle_status": getattr(opp, "lifecycle_status", "active") or "active",
            "quality_status": getattr(opp, "quality_status", "passed") or "passed",
            "completeness_score": float(getattr(opp, "completeness_score", 1.0) or 1.0),
            "quarantine_reason": getattr(opp, "quarantine_reason", None),
            "stale_at": getattr(opp, "stale_at", None),
            "absence_count": int(getattr(opp, "absence_count", 0) or 0),
        }

    def _get_table_columns(self) -> List[str]:
        if not hasattr(self, "_existing_cols_cache") or self._existing_cols_cache is None:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                if self.db_manager.get_engine().dialect.name == "postgresql":
                    cursor.execute(
                        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND LOWER(table_name) = 'opportunities';"
                    )
                    self._existing_cols_cache = [r[0].lower() for r in cursor.fetchall()]
                else:
                    cursor.execute("PRAGMA table_info(Opportunities);")
                    self._existing_cols_cache = [row[1].lower() for row in cursor.fetchall()]
            except Exception:
                self._existing_cols_cache = []
            finally:
                cursor.close()
        return self._existing_cols_cache

    def _row_to_entity(self, row: Any) -> Opportunity:
        def _get_field(key: str, default: Any = None) -> Any:
            try:
                val = row[key]
                return val if val is not None else default
            except (IndexError, KeyError):
                return default

        def _parse_json(val: Any, default: Any) -> Any:
            if val is None:
                return default
            if isinstance(val, (dict, list)):
                return val
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except Exception:
                    return default
            return default

        def _to_str(val: Any) -> Optional[str]:
            if val is None:
                return None
            if hasattr(val, "isoformat"):
                return val.isoformat()
            return str(val)

        tags = _parse_json(_get_field("tags"), [])
        score_breakdown = _parse_json(_get_field("score_breakdown"), {})
        raw_data = _parse_json(_get_field("raw_data"), {})

        return Opportunity(
            id=row["id"],
            title=row["title"],
            description=_get_field("description"),
            url=row["url"],
            source_id=row["source_id"],
            category=row["category"],
            provider=_get_field("provider"),
            company=_get_field("company"),
            location=_get_field("location"),
            remote=bool(_get_field("remote", False)),
            paid=bool(_get_field("paid")) if _get_field("paid") is not None else None,
            certificate=bool(_get_field("certificate", False)),
            price_raw=_get_field("price_raw"),
            price_normalized=_get_field("price_normalized"),
            currency=_get_field("currency"),
            deadline=_to_str(_get_field("deadline")),
            published_date=_to_str(_get_field("published_date")),
            discovered_date=_to_str(_get_field("discovered_date")) or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            duration=_get_field("duration"),
            difficulty=_get_field("difficulty", "unknown"),
            tags=tags,
            beginner_friendly=bool(_get_field("beginner_friendly")) if _get_field("beginner_friendly") is not None else None,
            score=_get_field("score", 0),
            score_breakdown=score_breakdown,
            confidence_score=float(_get_field("confidence_score", 0.0)),
            quality_score=float(_get_field("quality_score", 0.0)),
            is_rejected=bool(_get_field("is_rejected", False)),
            rejection_reason=_get_field("rejection_reason", ""),
            quality_flags=_get_field("quality_flags", ""),
            topic_score=float(_get_field("topic_score", 0.0)),
            keyword_score=float(_get_field("keyword_score", 0.0)),
            spam_score=float(_get_field("spam_score", 0.0)),
            freshness_score=float(_get_field("freshness_score", 100.0)),
            provider_score=float(_get_field("provider_score", 100.0)),
            link_status=_get_field("link_status", "valid"),
            verification_status=_get_field("verification_status", "verified"),
            last_verified=_get_field("last_verified"),
            expired=int(_get_field("expired", 0)),
            archived=int(_get_field("archived", 0)),
            status=_get_field("status", "active"),
            duplicate_of_id=_get_field("duplicate_of_id"),
            run_id=_get_field("run_id"),
            raw_data=raw_data,
            last_seen=_get_field("last_seen"),
            opportunity_type=_get_field("opportunity_type"),
            pricing_type=_get_field("pricing_type", "UNKNOWN"),
            price_amount=float(_get_field("price_amount")) if _get_field("price_amount") is not None else None,
            application_fee=float(_get_field("application_fee")) if _get_field("application_fee") is not None else None,
            certificate_fee=float(_get_field("certificate_fee")) if _get_field("certificate_fee") is not None else None,
            is_free=bool(_get_field("is_free")) if _get_field("is_free") is not None else None,
            free_conditions=_get_field("free_conditions"),
            stipend_type=_get_field("stipend_type", "UNKNOWN"),
            stipend_amount=float(_get_field("stipend_amount")) if _get_field("stipend_amount") is not None else None,
            stipend_currency=_get_field("stipend_currency"),
            certificate_available=_get_field("certificate_available", "UNKNOWN"),
            certificate_cost=_get_field("certificate_cost", "UNKNOWN"),
            eligibility=_get_field("eligibility"),
            requirements=_get_field("requirements"),
            source_external_id=_get_field("source_external_id"),
            canonical_url=_get_field("canonical_url"),
            identity_fingerprint=_get_field("identity_fingerprint"),
            first_seen_at=str(_get_field("first_seen_at")) if _get_field("first_seen_at") else None,
            last_seen_at=str(_get_field("last_seen_at")) if _get_field("last_seen_at") else None,
            last_changed_at=str(_get_field("last_changed_at")) if _get_field("last_changed_at") else None,
            last_harvested_at=str(_get_field("last_harvested_at")) if _get_field("last_harvested_at") else None,
            lifecycle_status=_get_field("lifecycle_status", "active"),
            quality_status=_get_field("quality_status", "passed"),
            completeness_score=float(_get_field("completeness_score", 1.0)),
            quarantine_reason=_get_field("quarantine_reason"),
            stale_at=str(_get_field("stale_at")) if _get_field("stale_at") else None,
            absence_count=int(_get_field("absence_count", 0)),
        )

    def upsert(self, opp: Opportunity) -> str:
        """Inserts or updates an Opportunity based on ID or url_hash, adapting to existing columns in the table."""
        data = self._entity_to_dict(opp)
        table_cols = self._get_table_columns()

        base_fields = [
            "id", "title", "description", "url", "url_hash", "source_id", "category",
            "provider", "company", "location", "remote", "paid", "certificate",
            "price_raw", "price_normalized", "currency", "deadline", "published_date",
            "discovered_date", "duration", "difficulty", "tags", "beginner_friendly",
            "score", "score_breakdown",
            "confidence_score", "quality_score", "is_rejected", "rejection_reason",
            "quality_flags", "topic_score", "keyword_score", "spam_score",
            "status", "duplicate_of_id", "run_id",
            "raw_data", "last_seen"
        ]

        phase2_fields = [
            "opportunity_type", "pricing_type", "price_amount", "application_fee",
            "certificate_fee", "is_free", "free_conditions", "stipend_type",
            "stipend_amount", "stipend_currency", "certificate_available",
            "certificate_cost", "eligibility", "requirements"
        ]

        phase2_1_fields = [
            "source_external_id", "canonical_url", "identity_fingerprint",
            "first_seen_at", "last_seen_at", "last_changed_at", "last_harvested_at"
        ]

        phase6_fields = [
            "lifecycle_status", "quality_status", "completeness_score",
            "quarantine_reason", "stale_at", "absence_count"
        ]

        # Only include fields that exist in the physical table
        if table_cols:
            all_target = base_fields + [f for f in phase2_fields if f.lower() in table_cols] + [f for f in phase2_1_fields if f.lower() in table_cols] + [f for f in phase6_fields if f.lower() in table_cols]
            active_fields = [f for f in all_target if f.lower() in table_cols]
        else:
            active_fields = base_fields

        cols_str = ", ".join(active_fields)
        placeholders_str = ", ".join(["?"] * len(active_fields))

        # Build update clause for all non-key fields
        non_update = {"id", "url_hash", "discovered_date", "run_id", "first_seen_at"}
        update_fields = [f for f in active_fields if f not in non_update]
        update_str = ", ".join([f"{f} = excluded.{f}" for f in update_fields])

        sql = f"""
        INSERT INTO Opportunities (
            {cols_str}
        ) VALUES (
            {placeholders_str}
        )
        ON CONFLICT(url_hash) DO UPDATE SET
            {update_str}
        RETURNING id;
        """
        values = tuple(data[f] for f in active_fields)

        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, values)
                row = cursor.fetchone()
                if row and row[0]:
                    opp.id = str(row[0])
                    return opp.id
            return opp.id
        except Exception as e:
            err_msg = str(e).lower()
            if "uq_opportunities_source_ext_id" in err_msg or "source_external_id" in err_msg:
                # Concurrent worker or conflict on (source_id, source_external_id)
                existing = self.find_existing_opportunity(opp)
                if existing:
                    opp.id = existing.id
                    return opp.id
            raise RepositoryError(f"Failed to upsert Opportunity '{opp.id}': {e}", original_exception=e)

    def find_existing_opportunity(self, opp: Opportunity) -> Optional[Opportunity]:
        """
        Layered opportunity identity resolution (Priority A -> Priority B -> Priority C):
        Priority A: source_id + source_external_id (when external_id is present and non-empty)
        Priority B: canonical url_hash
        Priority C: deterministic identity_fingerprint within same source
        """
        # Priority A: Source ID + Stable External ID
        if opp.source_external_id and opp.source_external_id.strip():
            found = self.search(
                where_clause="source_id = ? AND source_external_id = ?",
                params=(opp.source_id, opp.source_external_id.strip()),
                limit=1,
            )
            if found:
                return found[0]

        # Priority B: Canonical url_hash
        uh = opp.generate_url_hash()
        found = self.search(where_clause="url_hash = ?", params=(uh,), limit=1)
        if found:
            return found[0]

        # Priority C: Deterministic identity fingerprint within same source
        fp = opp.identity_fingerprint or opp.compute_identity_fingerprint()
        if fp:
            found = self.search(
                where_clause="source_id = ? AND identity_fingerprint = ?",
                params=(opp.source_id, fp),
                limit=1,
            )
            if found:
                return found[0]

        return None

    def classify_candidate(
        self, candidate: Opportunity, existing: Optional[Opportunity]
    ) -> ChangeClassification:
        """
        Deterministically classifies incoming candidate relative to existing database record.
        Returns:
            ChangeClassification: NEW, UPDATED, UNCHANGED, REOPENED, DUPLICATE, or QUARANTINED.
        """
        # 1. Quarantine check
        cand_quality = getattr(candidate, "quality_status", "")
        if cand_quality == "quarantined" or (getattr(candidate, "is_rejected", False) and "quarantine" in getattr(candidate, "rejection_reason", "").lower()):
            return ChangeClassification.QUARANTINED

        if not existing:
            return ChangeClassification.NEW

        # 2. Check if previously closed/expired/archived opportunity became active again
        is_previously_inactive = (
            (getattr(existing, "lifecycle_status", None) in ("expired", "archived", "closed"))
            or ((existing.status or "").lower() in ("expired", "archived", "closed"))
            or (getattr(existing, "expired", 0) == 1)
            or (getattr(existing, "archived", 0) == 1)
        )
        cand_active = ((candidate.status or "").lower() == Status.ACTIVE.value) and (getattr(candidate, "lifecycle_status", None) != "expired")
        if is_previously_inactive and cand_active:
            return ChangeClassification.REOPENED

        # 3. Content diff check: determine if any substantive fields changed
        substantive_changes = []
        cand_canon = (candidate.canonical_url or candidate.url or "").strip()
        exist_canon = (existing.canonical_url or existing.url or "").strip()
        if cand_canon != exist_canon:
            substantive_changes.append("canonical_url")
        if (candidate.title or "").strip() != (existing.title or "").strip():
            substantive_changes.append("title")
        if (candidate.description or "").strip() != (existing.description or "").strip():
            substantive_changes.append("description")
        cand_deadline = candidate.deadline.isoformat() if hasattr(candidate.deadline, "isoformat") else (candidate.deadline or "")
        exist_deadline = existing.deadline.isoformat() if hasattr(existing.deadline, "isoformat") else (existing.deadline or "")
        if cand_deadline.strip() != exist_deadline.strip():
            substantive_changes.append("deadline")
        if candidate.price_amount != existing.price_amount:
            substantive_changes.append("price_amount")
        if candidate.stipend_amount != existing.stipend_amount:
            substantive_changes.append("stipend_amount")
        if (candidate.pricing_type or "").lower() != (existing.pricing_type or "").lower():
            substantive_changes.append("pricing_type")
        if (candidate.stipend_type or "").lower() != (existing.stipend_type or "").lower():
            substantive_changes.append("stipend_type")
        if (candidate.eligibility or "").strip() != (existing.eligibility or "").strip():
            substantive_changes.append("eligibility")
        if (candidate.requirements or "").strip() != (existing.requirements or "").strip():
            substantive_changes.append("requirements")
        if set(candidate.tags or []) != set(existing.tags or []):
            substantive_changes.append("tags")
        if candidate.remote != existing.remote:
            substantive_changes.append("remote")
        if candidate.certificate != existing.certificate:
            substantive_changes.append("certificate")

        if substantive_changes:
            return ChangeClassification.UPDATED
        else:
            return ChangeClassification.UNCHANGED

    def save_or_update(self, opp: Opportunity) -> Tuple[str, ChangeClassification]:
        """
        Idempotently persists or updates a single Opportunity with layered identity and classification.
        Preserves existing primary key ID, first_seen_at timestamps, and enforces the Safe Update Policy.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        existing = self.find_existing_opportunity(opp)
        classification = self.classify_candidate(opp, existing)

        table_cols = self._get_table_columns()

        if existing:
            opp.id = existing.id
            opp.first_seen_at = existing.first_seen_at or existing.discovered_date
            opp.last_seen_at = now_iso
            opp.last_harvested_at = now_iso
            opp.last_seen = now_iso

            # SAFE UPDATE POLICY: Protect valid existing fields from being wiped out by corrupt or empty incoming data
            if not opp.title or len(opp.title.strip()) < 3:
                opp.title = existing.title
            if not opp.description and existing.description:
                opp.description = existing.description
            if not opp.deadline and existing.deadline:
                opp.deadline = existing.deadline if isinstance(existing.deadline, str) else existing.deadline.isoformat()
            if opp.price_amount is None and existing.price_amount is not None:
                opp.price_amount = existing.price_amount
            if opp.stipend_amount is None and existing.stipend_amount is not None:
                opp.stipend_amount = existing.stipend_amount
            if not opp.location and existing.location:
                opp.location = existing.location
            if existing.tags:
                opp.tags = list(set(existing.tags or []) | set(opp.tags or []))

            if classification == ChangeClassification.UNCHANGED:
                # Minimal write: touch only timestamp tracking fields without updating last_changed_at
                try:
                    with self.db_manager.transaction() as cursor:
                        if "last_seen_at" in table_cols:
                            sql = 'UPDATE "Opportunities" SET last_seen_at = ?, last_harvested_at = ?, last_seen = ? WHERE id = ?;'
                            cursor.execute(sql, (now_iso, now_iso, now_iso, opp.id))
                        else:
                            sql = 'UPDATE "Opportunities" SET last_seen = ? WHERE id = ?;'
                            cursor.execute(sql, (now_iso, opp.id))
                    return (opp.id, ChangeClassification.UNCHANGED)
                except Exception as e:
                    raise RepositoryError(f"Failed to touch unchanged Opportunity '{opp.id}': {e}", original_exception=e)

            elif classification in (ChangeClassification.UPDATED, ChangeClassification.REOPENED, ChangeClassification.QUARANTINED):
                opp.last_changed_at = now_iso
                if classification == ChangeClassification.REOPENED:
                    opp.status = Status.ACTIVE.value
                    opp.lifecycle_status = "active"
                elif classification == ChangeClassification.QUARANTINED:
                    opp.quality_status = "quarantined"
                    opp.is_rejected = True

                data = self._entity_to_dict(opp)
                non_update = {"id", "discovered_date", "run_id", "first_seen_at"}
                update_cols = [k for k in data.keys() if (not table_cols or k.lower() in table_cols) and k not in non_update]
                set_clause = ", ".join([f"{c} = ?" for c in update_cols])
                values = tuple(data[c] for c in update_cols) + (opp.id,)

                try:
                    with self.db_manager.transaction() as cursor:
                        sql = f'UPDATE "Opportunities" SET {set_clause} WHERE id = ?;'
                        cursor.execute(sql, values)
                    return (opp.id, classification)
                except Exception as e:
                    raise RepositoryError(f"Failed to update Opportunity '{opp.id}': {e}", original_exception=e)

        # New record
        opp.first_seen_at = now_iso
        opp.last_seen_at = now_iso
        opp.last_harvested_at = now_iso
        opp.last_changed_at = now_iso

        if classification == ChangeClassification.QUARANTINED:
            opp.quality_status = "quarantined"
            opp.is_rejected = True

        inserted_id = self.upsert(opp)
        return (inserted_id, classification)

    def upsert_batch(self, opps: List[Opportunity]) -> PersistenceResult:
        """
        Executes an idempotent batch persistence operation with layered identity,
        in-batch deduplication, and deterministic change classification.
        """
        result = PersistenceResult(collected_count=len(opps))
        if not opps:
            return result

        # 1. Deduplicate within the incoming batch itself
        seen_batch_identities: Set[str] = set()
        unique_candidates: List[Opportunity] = []

        for opp in opps:
            # Build unique key for this candidate
            if opp.source_external_id and opp.source_external_id.strip():
                batch_key = f"ext:{opp.source_id}:{opp.source_external_id.strip()}"
            else:
                batch_key = f"url:{opp.generate_url_hash()}"

            if batch_key in seen_batch_identities:
                result.duplicate_count += 1
                continue

            seen_batch_identities.add(batch_key)
            unique_candidates.append(opp)

        # 2. Persist each unique candidate with change classification
        try:
            with self.db_manager.transaction() as cursor:
                for opp in unique_candidates:
                    opp_id, classification = self.save_or_update(opp)
                    if classification == ChangeClassification.NEW:
                        result.new_count += 1
                        result.new_items.append(opp)
                    elif classification == ChangeClassification.UPDATED:
                        result.updated_count += 1
                        result.updated_items.append(opp)
                    elif classification == ChangeClassification.UNCHANGED:
                        result.unchanged_count += 1
                    elif classification == ChangeClassification.REOPENED:
                        result.reopened_count += 1
                        result.reopened_items.append(opp)
                    elif classification == ChangeClassification.DUPLICATE:
                        result.duplicate_count += 1
                    elif classification == ChangeClassification.QUARANTINED:
                        result.quarantined_count += 1

            result.saved_count = result.new_count + result.updated_count + result.reopened_count + result.unchanged_count
            return result
        except Exception as e:
            result.failed_count = len(unique_candidates)
            raise RepositoryError(f"Failed batch upsert for {len(opps)} opportunities: {e}", original_exception=e)

    def get_by_id(self, opp_id: str) -> Optional[Opportunity]:
        return self.read_by_id(opp_id)

    def get_by_url_hash(self, url_hash: str) -> Optional[Opportunity]:
        results = self.search(where_clause="url_hash = ?", params=(url_hash,), limit=1)
        return results[0] if results else None

    def get_active_opportunities(
        self, limit: int = 50, category: Optional[str] = None
    ) -> List[Opportunity]:
        return self.get_paginated_opportunities(limit=limit, offset=0, category=category)

    def _build_active_where(
        self,
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        deadline_filter: Optional[str] = None,
    ) -> tuple[str, tuple[Any, ...]]:
        where_clause = "status = ? AND (is_rejected IS NOT TRUE) AND (expired = 0 OR expired IS NULL) AND (archived = 0 OR archived IS NULL)"
        table_cols = self._get_table_columns()
        if "quality_status" in table_cols:
            where_clause += " AND (quality_status IS NULL OR quality_status != 'quarantined')"
        if "lifecycle_status" in table_cols:
            where_clause += " AND (lifecycle_status IS NULL OR lifecycle_status NOT IN ('quarantined', 'removed'))"
        params: List[Any] = [Status.ACTIVE.value]

        if category and category.lower() != "all":
            where_clause += " AND LOWER(category) = LOWER(?)"
            params.append(category.strip())

        if search_query and search_query.strip():
            where_clause += " AND search_vector @@ websearch_to_tsquery('english', ?)"
            params.append(search_query.strip())

        if deadline_filter:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if deadline_filter == "closing_soon":
                from datetime import timedelta
                soon_str = (datetime.now(timezone.utc) + timedelta(days=14)).strftime("%Y-%m-%d")
                where_clause += " AND (deadline IS NOT NULL AND deadline != '' AND deadline >= ? AND deadline <= ?)"
                params.extend([today_str, soon_str])
            elif deadline_filter == "no_deadline":
                where_clause += " AND (deadline IS NULL OR deadline = '')"
            elif deadline_filter == "passed":
                where_clause += " AND (deadline IS NOT NULL AND deadline != '' AND deadline < ?)"
                params.append(today_str)
            elif deadline_filter == "active":
                where_clause += " AND (deadline IS NULL OR deadline = '' OR deadline >= ?)"
                params.append(today_str)

        return where_clause, tuple(params)

    def count_paginated_opportunities(
        self,
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        deadline_filter: Optional[str] = None,
    ) -> int:
        """Counts active opportunities matching category, search, and deadline filters."""
        where_clause, params = self._build_active_where(
            category=category,
            search_query=search_query,
            deadline_filter=deadline_filter,
        )
        return self.count(where_clause=where_clause, params=params)

    def get_paginated_opportunities(
        self,
        limit: int = 20,
        offset: int = 0,
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        deadline_filter: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> List[Opportunity]:
        """Queries active opportunities using PostgreSQL server-side pagination with flexible sorting."""
        safe_limit = max(1, min(limit, 200))
        safe_offset = max(0, offset)
        where_clause, params = self._build_active_where(
            category=category,
            search_query=search_query,
            deadline_filter=deadline_filter,
        )

        order_by = "score DESC, discovered_date DESC"
        if sort_by == "newest":
            order_by = "discovered_date DESC, score DESC"
        elif sort_by == "deadline_soonest":
            order_by = "CASE WHEN deadline IS NOT NULL AND deadline != '' THEN deadline ELSE '9999-12-31' END ASC, score DESC"
        elif sort_by == "score" or sort_by == "relevance":
            order_by = "score DESC, discovered_date DESC"

        return self.search(
            where_clause=where_clause,
            params=params,
            order_by=order_by,
            limit=safe_limit,
            offset=safe_offset,
        )


    def get_rejected_opportunities(
        self, limit: int = 100
    ) -> List[Opportunity]:
        """Retrieves rejected opportunities for quality reporting."""
        return self.search(
            where_clause="is_rejected IS TRUE OR is_rejected = 1",
            order_by="discovered_date DESC",
            limit=limit,
        )

    def get_quality_stats(self) -> Dict[str, Any]:
        """Computes quality intelligence statistics from the database."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            stats = {}
            cursor.execute("SELECT COUNT(*) FROM Opportunities WHERE is_rejected IS NOT TRUE;")
            row = cursor.fetchone()
            stats["accepted_count"] = row[0] if row else 0

            cursor.execute("SELECT COUNT(*) FROM Opportunities WHERE is_rejected IS TRUE;")
            row = cursor.fetchone()
            stats["rejected_count"] = row[0] if row else 0

            cursor.execute("SELECT AVG(confidence_score) FROM Opportunities WHERE (is_rejected IS NOT TRUE) AND confidence_score > 0;")
            row = cursor.fetchone()
            stats["avg_confidence"] = round(float(row[0]) if row and row[0] is not None else 0.0, 1)

            cursor.execute("SELECT AVG(quality_score) FROM Opportunities WHERE (is_rejected IS NOT TRUE) AND quality_score > 0;")
            row = cursor.fetchone()
            stats["avg_quality"] = round(float(row[0]) if row and row[0] is not None else 0.0, 1)

            cursor.execute("SELECT rejection_reason, COUNT(*) FROM Opportunities WHERE is_rejected IS TRUE GROUP BY rejection_reason ORDER BY COUNT(*) DESC LIMIT 10;")
            rows = cursor.fetchall()
            stats["top_rejection_reasons"] = {r[0]: r[1] for r in rows} if rows else {}

            return stats
        finally:
            cursor.close()

    def update_status(self, opp_id: str, new_status: str) -> None:
        sql = "UPDATE Opportunities SET status = ? WHERE id = ?;"
        with self.db_manager.transaction() as cursor:
            cursor.execute(sql, (new_status, opp_id))

    def mark_as_duplicate(self, opp_id: str, canonical_id: str) -> None:
        sql = "UPDATE Opportunities SET status = ?, duplicate_of_id = ? WHERE id = ?;"
        with self.db_manager.transaction() as cursor:
            cursor.execute(sql, (Status.DUPLICATE.value, canonical_id, opp_id))

    def count_old_records(self, days: int = 30) -> int:
        """Counts opportunities discovered more than specified days ago without deleting."""
        from datetime import datetime, timedelta, timezone
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        sql = 'SELECT COUNT(*) FROM "Opportunities" WHERE discovered_date < %s;'
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (cutoff_date,))
                row = cursor.fetchone()
                if row:
                    return int(row[0] if isinstance(row, (tuple, list)) else row.get("count", 0))
                return 0
            finally:
                cursor.close()
        except Exception as e:
            from src.core.logging import get_logger
            get_logger(__name__).error(f"Error counting old opportunities: {e}")
            return 0

    def delete_old_records(self, days: int = 30) -> int:
        """Deletes opportunities discovered more than specified days ago using safe PostgreSQL query."""
        from datetime import datetime, timedelta, timezone
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        sql = 'DELETE FROM "Opportunities" WHERE discovered_date < %s;'
        with self.db_manager.transaction() as cursor:
            cursor.execute(sql, (cutoff_date,))
            return cursor.rowcount if hasattr(cursor, "rowcount") and cursor.rowcount is not None else 0


    def save_opportunity_with_deduplication(self, opp: Opportunity) -> Tuple[str, bool]:
        """
        Pre-insert duplicate detection & field merging based on canonical URL.

        Returns:
            Tuple of (opportunity_id, is_duplicate_boolean).
        """
        url_hash = opp.generate_url_hash()
        existing = self.get_by_url_hash(url_hash)

        if existing:
            # Merge missing / higher-quality fields into existing survivor
            if not existing.deadline and opp.deadline:
                existing.deadline = opp.deadline
            elif existing.deadline and opp.deadline and opp.deadline != existing.deadline:
                existing.deadline = opp.deadline
            if not existing.published_date and opp.published_date:
                existing.published_date = opp.published_date
            if (not existing.description or len(opp.description or "") > len(existing.description or "")) and opp.description:
                existing.description = opp.description
            if not existing.provider and opp.provider:
                existing.provider = opp.provider
            if not existing.company and opp.company:
                existing.company = opp.company
            if not existing.location and opp.location:
                existing.location = opp.location
            if (existing.category == "other" or not existing.category) and opp.category and opp.category != "other":
                existing.category = opp.category
            if (opp.score or 0) > (existing.score or 0):
                existing.score = opp.score
            if opp.last_seen:
                existing.last_seen = opp.last_seen

            self.upsert(existing)
            logger.info(f"Duplicate opportunity merged: '{opp.title}' -> canonical ID '{existing.id}'")
            return existing.id, True

        saved_id = self.upsert(opp)
        return saved_id, False

    def cleanup_database_duplicates(self) -> Dict[str, Any]:
        """
        Scans existing Opportunities table for duplicate url_hash groups, merges missing fields,
        repoints foreign key references, and marks redundant records with status='duplicate'.

        Survivor Strategy:
        1. Most complete record (deadline, published_date, description, company, provider, score, category)
        2. Most recent record (discovered_date / last_seen)
        3. Stable deterministic ID (alphanumeric) as final tie-breaker
        """
        stats: Dict[str, Any] = {
            "total_opportunities": 0,
            "unique_canonical_urls": 0,
            "duplicate_groups_found": 0,
            "records_merged": 0,
            "duplicates_cleaned": 0,
        }

        with self.db_manager.transaction() as cursor:
            cursor.execute("SELECT COUNT(*) FROM Opportunities;")
            row = cursor.fetchone()
            stats["total_opportunities"] = row[0] if row else 0

            cursor.execute("SELECT COUNT(DISTINCT url_hash) FROM Opportunities;")
            row = cursor.fetchone()
            stats["unique_canonical_urls"] = row[0] if row else 0

            # Single batch fetch of all rows belonging to duplicate url_hash groups
            cursor.execute(
                "SELECT id, title, url, source_id, category, description, deadline, published_date, "
                "discovered_date, company, provider, location, score, status, duplicate_of_id, last_seen, url_hash "
                "FROM Opportunities WHERE url_hash IN ("
                "    SELECT url_hash FROM Opportunities GROUP BY url_hash HAVING COUNT(*) > 1"
                ");"
            )
            rows = cursor.fetchall()

            if not rows:
                return stats

            # Group rows by url_hash in memory
            from collections import defaultdict
            groups = defaultdict(list)
            for row in rows:
                uh = row[16]
                rec = Opportunity(
                    id=str(row[0]),
                    title=str(row[1] or ""),
                    url=str(row[2] or ""),
                    source_id=str(row[3] or ""),
                    category=str(row[4] or "other"),
                    description=str(row[5]) if row[5] is not None else None,
                    deadline=str(row[6]) if row[6] is not None else None,
                    published_date=str(row[7]) if row[7] is not None else None,
                    discovered_date=str(row[8] or ""),
                    company=str(row[9]) if row[9] is not None else None,
                    provider=str(row[10]) if row[10] is not None else None,
                    location=str(row[11]) if row[11] is not None else None,
                    score=int(row[12] or 0),
                    status=str(row[13] or "active"),
                    duplicate_of_id=str(row[14]) if row[14] is not None else None,
                    last_seen=str(row[15]) if row[15] is not None else None,
                )
                groups[uh].append(rec)

            stats["duplicate_groups_found"] = len(groups)

            def sort_key(item: Opportunity):
                completeness = 0
                if item.deadline: completeness += 10
                if item.published_date: completeness += 5
                if item.description and len(item.description.strip()) > 20: completeness += 8
                if item.category and item.category != "other": completeness += 4
                if item.company: completeness += 3
                if item.provider: completeness += 3
                completeness += (item.score or 0)
                recency = item.last_seen or item.discovered_date or ""
                return (completeness, recency, item.id)

            dup_updates = []
            survivor_updates = []
            email_history_updates = []

            for uh, records in groups.items():
                if len(records) <= 1:
                    continue

                records.sort(key=sort_key, reverse=True)
                survivor = records[0]

                for dup in records[1:]:
                    # Merge metadata into survivor
                    if not survivor.deadline and dup.deadline:
                        survivor.deadline = dup.deadline
                    if not survivor.published_date and dup.published_date:
                        survivor.published_date = dup.published_date
                    if (not survivor.description or len(dup.description or "") > len(survivor.description or "")) and dup.description:
                        survivor.description = dup.description
                    if not survivor.provider and dup.provider:
                        survivor.provider = dup.provider
                    if not survivor.company and dup.company:
                        survivor.company = dup.company
                    if not survivor.location and dup.location:
                        survivor.location = dup.location
                    if (survivor.category == "other" or not survivor.category) and dup.category and dup.category != "other":
                        survivor.category = dup.category
                    if (dup.score or 0) > (survivor.score or 0):
                        survivor.score = dup.score

                    email_history_updates.append((survivor.id, dup.id))
                    dup_updates.append((Status.DUPLICATE.value, survivor.id, dup.id))
                    stats["duplicates_cleaned"] += 1

                survivor_updates.append((
                    survivor.deadline, survivor.published_date, survivor.description,
                    survivor.provider, survivor.company, survivor.location, survivor.category,
                    survivor.score, Status.ACTIVE.value, survivor.id
                ))
                stats["records_merged"] += 1

            if email_history_updates:
                try:
                    cursor.executemany(
                        "UPDATE EmailHistory SET opportunity_id = ? WHERE opportunity_id = ?;",
                        email_history_updates
                    )
                except Exception:
                    pass

            if dup_updates:
                cursor.executemany(
                    "UPDATE Opportunities SET status = ?, duplicate_of_id = ? WHERE id = ?;",
                    dup_updates
                )

            if survivor_updates:
                cursor.executemany(
                    "UPDATE Opportunities SET deadline = ?, published_date = ?, description = ?, "
                    "provider = ?, company = ?, location = ?, category = ?, score = ?, status = ? WHERE id = ?;",
                    survivor_updates
                )

        return stats

    def update_lifecycle_states(self) -> Dict[str, int]:
        """
        Executes an efficient database-side batch update of opportunity lifecycle states
        (EXPIRED and CLOSING_SOON) without loading millions of rows into Python memory.
        """
        results = {"expired_updated": 0, "closing_soon_updated": 0}
        try:
            with self.db_manager.transaction() as cursor:
                # 1. Update expired opportunities
                cursor.execute("""
                    UPDATE "Opportunities"
                    SET lifecycle_status = 'expired',
                        status = 'expired',
                        expired = 1
                    WHERE deadline < CURRENT_DATE
                      AND lifecycle_status != 'expired';
                """)
                results["expired_updated"] = cursor.rowcount if hasattr(cursor, "rowcount") and cursor.rowcount >= 0 else 0

                # 2. Update closing soon opportunities (0 to 3 days remaining)
                cursor.execute("""
                    UPDATE "Opportunities"
                    SET lifecycle_status = 'closing_soon'
                    WHERE deadline >= CURRENT_DATE 
                      AND deadline <= (CURRENT_DATE + INTERVAL '3 days')
                      AND lifecycle_status = 'active';
                """)
                results["closing_soon_updated"] = cursor.rowcount if hasattr(cursor, "rowcount") and cursor.rowcount >= 0 else 0
        except Exception as e:
            logger.warning(f"Error executing batch update_lifecycle_states: {e}")
        return results

    # =========================================================================
    # PHASE 4: SSR-FIRST DISCOVERY, FTS SEARCH & SAVED OPPORTUNITY METHODS
    # =========================================================================

    def query_opportunities(
        self, filter_dto: Any
    ) -> Tuple[List[Dict[str, Any]], int, Dict[str, Dict[str, int]]]:
        """
        Execute an optimized SSR search and filter query against PostgreSQL.
        Leverages PostgreSQL Full-Text Search (tsvector + GIN index), allowlisted
        facets, deterministic tie-breakers, and server-side pagination.
        """
        # Check if caller requested specific lifecycle filter (e.g. 'expired', 'closing_soon', 'all')
        target_lifecycle = getattr(filter_dto, "lifecycle_status", None)
        if target_lifecycle == "expired":
            where_clauses: List[str] = ["(o.lifecycle_status = 'expired' OR o.status = 'expired')"]
        elif target_lifecycle == "closing_soon":
            where_clauses: List[str] = ["o.lifecycle_status = 'closing_soon'"]
        elif target_lifecycle == "all":
            where_clauses: List[str] = ["1=1"]
        else:
            where_clauses: List[str] = ["o.status = 'active'"]

        # Phase 6 Quarantine & Removal Isolation: Never display quarantined or removed items in normal discovery
        where_clauses.append("(o.quality_status IS NULL OR o.quality_status != 'quarantined')")
        where_clauses.append("(o.lifecycle_status IS NULL OR o.lifecycle_status != 'removed')")

        params: List[Any] = []
        rank_select = "0.0 AS rank"
        rank_param = []

        # 1. Full-Text Search
        if filter_dto.keyword and filter_dto.keyword.strip():
            kw = filter_dto.keyword.strip()
            where_clauses.append("o.search_vector @@ websearch_to_tsquery('english', %s)")
            params.append(kw)
            rank_select = "ts_rank(o.search_vector, websearch_to_tsquery('english', %s)) AS rank"
            rank_param = [kw]

        # 2. Facet filters
        if filter_dto.category:
            where_clauses.append("lower(o.category) = lower(%s)")
            params.append(filter_dto.category.strip())

        if filter_dto.opportunity_type:
            where_clauses.append("lower(o.opportunity_type) = lower(%s)")
            params.append(filter_dto.opportunity_type.strip())

        if filter_dto.source_id:
            where_clauses.append("lower(o.source_id) = lower(%s)")
            params.append(filter_dto.source_id.strip())

        if filter_dto.is_free is not None:
            where_clauses.append("o.is_free = %s")
            params.append(filter_dto.is_free)

        if filter_dto.pricing_type:
            where_clauses.append("lower(o.pricing_type) = lower(%s)")
            params.append(filter_dto.pricing_type.strip())

        if filter_dto.stipend_type:
            where_clauses.append("lower(o.stipend_type) = lower(%s)")
            params.append(filter_dto.stipend_type.strip())

        if filter_dto.remote is not None:
            where_clauses.append("o.remote = %s")
            params.append(filter_dto.remote)

        if filter_dto.difficulty:
            where_clauses.append("lower(o.difficulty) = lower(%s)")
            params.append(filter_dto.difficulty.strip())

        if filter_dto.deadline:
            dl = filter_dto.deadline.strip().lower()
            if dl == "active":
                where_clauses.append("(o.deadline IS NULL OR o.deadline >= CURRENT_DATE)")
            elif dl == "upcoming":
                where_clauses.append("(o.deadline >= CURRENT_DATE AND o.deadline <= (CURRENT_DATE + INTERVAL '14 days'))")
            elif dl == "past":
                where_clauses.append("(o.deadline < CURRENT_DATE)")
            else:
                where_clauses.append("o.deadline <= %s::date")
                params.append(dl)

        # 3. Saved Only Join
        join_clause = ""
        if filter_dto.saved_only and filter_dto.user_id:
            try:
                import uuid
                uid_str = str(uuid.UUID(str(filter_dto.user_id).strip()))
                join_clause = 'INNER JOIN "SavedOpportunities" so ON so.opportunity_id = o.id AND so.user_id = %s'
                params.append(uid_str)
            except (ValueError, TypeError, AttributeError):
                join_clause = 'INNER JOIN "SavedOpportunities" so ON 1=0'

        where_sql = " AND ".join(where_clauses)

        # 4. Sorting logic with deterministic tie-breakers
        sort_field = getattr(filter_dto, "sort", "relevance")
        sort_dir = getattr(filter_dto, "sort_dir", "desc").upper()
        if sort_dir not in {"ASC", "DESC"}:
            sort_dir = "DESC"

        if sort_field == "relevance":
            if filter_dto.keyword:
                order_by = "ORDER BY rank DESC, o.score DESC, o.id ASC"
            else:
                order_by = "ORDER BY o.score DESC, o.discovered_date DESC, o.id ASC"
        elif sort_field == "newest":
            order_by = f"ORDER BY o.discovered_date {sort_dir}, o.id ASC"
        elif sort_field == "deadline":
            order_by = f"ORDER BY (o.deadline IS NULL), o.deadline {sort_dir}, o.id ASC"
        elif sort_field == "score":
            order_by = f"ORDER BY o.score {sort_dir}, o.id ASC"
        elif sort_field == "recommended":
            if filter_dto.keyword:
                order_by = "ORDER BY rank DESC, o.score DESC, o.id ASC"
            else:
                order_by = "ORDER BY o.score DESC, (o.deadline IS NULL), o.discovered_date DESC, o.id ASC"
        else:
            order_by = "ORDER BY o.score DESC, o.id ASC"

        # 5. Count query
        count_sql = f'SELECT COUNT(*) FROM "Opportunities" o {join_clause} WHERE {where_sql};'

        # 6. Items query with pagination
        limit = max(1, min(200, getattr(filter_dto, "per_page", 24)))
        page = max(1, getattr(filter_dto, "page", 1))
        offset = (page - 1) * limit

        query_sql = f"""
            SELECT 
                o.id, o.title, o.description, o.url, o.source_id, o.category, 
                o.provider, o.company, o.location, o.remote, o.is_free, 
                o.pricing_type, o.stipend_type, o.stipend_amount, o.stipend_currency,
                o.difficulty, o.score, o.deadline, o.tags, o.discovered_date, 
                o.opportunity_type, {rank_select}
            FROM "Opportunities" o
            {join_clause}
            WHERE {where_sql}
            {order_by}
            LIMIT %s OFFSET %s;
        """

        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            # Execute Count
            cursor.execute(count_sql, tuple(params))
            count_row = cursor.fetchone()
            total_count = int(count_row[0] if count_row else 0)

            # Execute Query (rank_param is needed if rank_select has placeholder)
            full_query_params = tuple(rank_param + params + [limit, offset])
            cursor.execute(query_sql, full_query_params)
            rows = cursor.fetchall() or []
            desc_cols = [c[0] for c in cursor.description] if cursor.description else []
            items = [dict(r) if hasattr(r, "keys") else dict(zip(desc_cols, r)) for r in rows]

            # Facet aggregations for filters UI
            facet_counts = self._get_facet_counts(cursor)

            cursor.close()
            return items, total_count, facet_counts
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _get_facet_counts(self, cursor) -> Dict[str, Dict[str, int]]:
        """Retrieve active counts for top categories, types, and sources."""
        facets: Dict[str, Dict[str, int]] = {
            "categories": {},
            "opportunity_types": {},
            "sources": {}
        }
        try:
            cursor.execute("""
                SELECT category, COUNT(*) as cnt 
                FROM "Opportunities" 
                WHERE status = 'active' AND category IS NOT NULL AND category != ''
                GROUP BY category 
                ORDER BY cnt DESC 
                LIMIT 20;
            """)
            for r in cursor.fetchall():
                key = r[0] if not hasattr(r, "get") else r["category"]
                cnt = r[1] if not hasattr(r, "get") else r["cnt"]
                if key:
                    facets["categories"][str(key)] = int(cnt)

            cursor.execute("""
                SELECT opportunity_type, COUNT(*) as cnt 
                FROM "Opportunities" 
                WHERE status = 'active' AND opportunity_type IS NOT NULL AND opportunity_type != ''
                GROUP BY opportunity_type 
                ORDER BY cnt DESC 
                LIMIT 20;
            """)
            for r in cursor.fetchall():
                key = r[0] if not hasattr(r, "get") else r["opportunity_type"]
                cnt = r[1] if not hasattr(r, "get") else r["cnt"]
                if key:
                    facets["opportunity_types"][str(key)] = int(cnt)

            cursor.execute("""
                SELECT source_id, COUNT(*) as cnt 
                FROM "Opportunities" 
                WHERE status = 'active' AND source_id IS NOT NULL AND source_id != ''
                GROUP BY source_id 
                ORDER BY cnt DESC 
                LIMIT 20;
            """)
            for r in cursor.fetchall():
                key = r[0] if not hasattr(r, "get") else r["source_id"]
                cnt = r[1] if not hasattr(r, "get") else r["cnt"]
                if key:
                    facets["sources"][str(key)] = int(cnt)
        except Exception as e:
            logger.warning(f"Error computing facet counts: {e}")

        return facets

    # -------------------------------------------------------------------------
    # Saved Opportunities Management (PostgreSQL, RLS-aware, Paginated)
    # -------------------------------------------------------------------------

    def save_opportunity_for_user(self, user_id: Any, opportunity_id: str, notes: Optional[str] = None) -> bool:
        """Saves an opportunity for a given user. Idempotent on conflict."""
        try:
            import uuid
            uid_str = str(uuid.UUID(str(user_id).strip()))
        except (ValueError, TypeError, AttributeError):
            logger.warning(f"Invalid non-UUID user_id {user_id}")
            return False

        saved_id = f"saved_{uid_str[:8]}_{opportunity_id}"
        sql = """
            INSERT INTO "SavedOpportunities" (id, user_id, opportunity_id, notes)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, opportunity_id) DO UPDATE SET notes = EXCLUDED.notes;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (saved_id, uid_str, opportunity_id, notes))
            return True
        except Exception as e:
            logger.error(f"Failed to save opportunity {opportunity_id} for user {user_id}: {e}")
            raise RepositoryError(f"Failed to save opportunity: {e}", original_exception=e)

    def unsave_opportunity_for_user(self, user_id: Any, opportunity_id: str) -> bool:
        """Removes an opportunity from a user's saved list."""
        try:
            import uuid
            uid_str = str(uuid.UUID(str(user_id).strip()))
        except (ValueError, TypeError, AttributeError):
            return False

        sql = 'DELETE FROM "SavedOpportunities" WHERE user_id = %s AND opportunity_id = %s;'
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (uid_str, opportunity_id))
            return True
        except Exception as e:
            logger.error(f"Failed to unsave opportunity {opportunity_id} for user {user_id}: {e}")
            raise RepositoryError(f"Failed to unsave opportunity: {e}", original_exception=e)

    def is_opportunity_saved(self, user_id: Any, opportunity_id: str) -> bool:
        """Checks whether a user has saved a specific opportunity."""
        try:
            import uuid
            uid_str = str(uuid.UUID(str(user_id).strip()))
        except (ValueError, TypeError, AttributeError):
            return False

        sql = 'SELECT 1 FROM "SavedOpportunities" WHERE user_id = %s AND opportunity_id = %s LIMIT 1;'
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (uid_str, opportunity_id))
            row = cursor.fetchone()
            cursor.close()
            return bool(row)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get_saved_ids_for_user(self, user_id: Any, opportunity_ids: Optional[List[str]] = None) -> Set[str]:
        """Returns the set of opportunity IDs saved by the user."""
        if not user_id:
            return set()
        try:
            import uuid
            uid_str = str(uuid.UUID(str(user_id).strip()))
        except (ValueError, TypeError, AttributeError):
            return set()

        if opportunity_ids:
            sql = 'SELECT opportunity_id FROM "SavedOpportunities" WHERE user_id = %s AND opportunity_id = ANY(%s);'
            params = (uid_str, list(opportunity_ids))
        else:
            sql = 'SELECT opportunity_id FROM "SavedOpportunities" WHERE user_id = %s;'
            params = (uid_str,)

        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            cursor.close()
            return {r[0] if not hasattr(r, "get") else r["opportunity_id"] for r in rows}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def count_saved_opportunities(self, user_id: Any) -> int:
        """Counts total saved opportunities for a user."""
        if not user_id:
            return 0
        try:
            import uuid
            uid_str = str(uuid.UUID(str(user_id).strip()))
        except (ValueError, TypeError, AttributeError):
            return 0

        sql = 'SELECT COUNT(*) FROM "SavedOpportunities" WHERE user_id = %s;'
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (uid_str,))
            row = cursor.fetchone()
            cursor.close()
            return int(row[0] if row else 0)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def update_lifecycle_states(self) -> Dict[str, int]:
        """
        Executes atomic, high-performance database-side lifecycle updates for opportunities:
        1. Transitions opportunities whose deadline has passed to 'expired'.
        2. Transitions opportunities whose deadline is within 3 days to 'closing_soon'.
        3. Marks unconfirmed opportunities with absence_count >= 3 as 'removed'.
        Returns dictionary of affected row counts: {'expired': int, 'closing_soon': int, 'removed': int}.
        """
        table_cols = self._get_table_columns()
        if "lifecycle_status" not in table_cols:
            return {"expired": 0, "closing_soon": 0, "removed": 0}

        counts = {"expired": 0, "closing_soon": 0, "removed": 0}
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        soon_dt = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")

        try:
            with self.db_manager.transaction() as cursor:
                # 1. Expire past-deadline active/closing_soon opportunities
                sql_expire = """
                    UPDATE "Opportunities"
                    SET lifecycle_status = 'expired',
                        status = 'expired',
                        expired = 1
                    WHERE (lifecycle_status IN ('active', 'closing_soon') OR status = 'active')
                      AND deadline IS NOT NULL
                      AND deadline < ?;
                """
                cursor.execute(sql_expire, (today_str,))
                counts["expired"] = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0

                # 2. Mark opportunities closing soon (deadline between today and today + 3 days)
                sql_closing_soon = """
                    UPDATE "Opportunities"
                    SET lifecycle_status = 'closing_soon'
                    WHERE (lifecycle_status = 'active' OR lifecycle_status IS NULL)
                      AND status = 'active'
                      AND deadline IS NOT NULL
                      AND deadline >= ?
                      AND deadline <= ?;
                """
                cursor.execute(sql_closing_soon, (today_str, soon_dt))
                counts["closing_soon"] = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0

                # 3. Mark opportunities with absence_count >= 3 as removed
                if "absence_count" in table_cols:
                    sql_removed = """
                        UPDATE "Opportunities"
                        SET lifecycle_status = 'removed',
                            status = 'archived'
                        WHERE absence_count >= 3
                          AND lifecycle_status != 'removed';
                    """
                    cursor.execute(sql_removed)
                    counts["removed"] = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0

            return counts
        except Exception as e:
            logger.error(f"Failed to execute database-side lifecycle updates: {e}")
            return counts


