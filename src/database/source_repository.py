import json
from typing import Any, Dict, List, Optional

from src.database.base_repository import BaseRepository
from src.database.connection import DatabaseManager
from src.database.interfaces import ISourceRepository
from src.models.source import Source
from src.core.exceptions import RepositoryError
from src.core.logging import get_logger

logger = get_logger(__name__)


class SourceRepository(BaseRepository[Source], ISourceRepository):
    """
    DAO for managing target Sources in PostgreSQL / SQLite.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        super().__init__(db_manager=db_manager)
        self._existing_cols_cache: Optional[List[str]] = None

    @property
    def table_name(self) -> str:
        return "Sources"

    @property
    def primary_key(self) -> str:
        return "id"

    def _get_table_columns(self) -> List[str]:
        if self._existing_cols_cache is None:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                if self.db_manager.get_engine().dialect.name == "postgresql":
                    cursor.execute(
                        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND LOWER(table_name) = 'sources';"
                    )
                    self._existing_cols_cache = [r[0].lower() for r in cursor.fetchall()]
                else:
                    cursor.execute("PRAGMA table_info(Sources);")
                    self._existing_cols_cache = [row[1].lower() for row in cursor.fetchall()]
            except Exception:
                self._existing_cols_cache = []
            finally:
                cursor.close()
        return self._existing_cols_cache

    def _entity_to_dict(self, source: Source) -> Dict[str, Any]:
        opp_types = source.opportunity_types
        if isinstance(opp_types, list):
            opp_types_str = json.dumps([t.value if hasattr(t, "value") else str(t) for t in opp_types])
        else:
            opp_types_str = json.dumps([])

        rate_limit_str = (
            json.dumps(source.rate_limit_policy.to_dict() if hasattr(source.rate_limit_policy, "to_dict") else source.rate_limit_policy)
            if source.rate_limit_policy
            else "{}"
        )

        source_fam = source.source_family.value if hasattr(source.source_family, "value") else str(source.source_family or "")
        access_meth = source.access_method.value if hasattr(source.access_method, "value") else str(source.access_method or "")
        trust_t = source.trust_tier.value if hasattr(source.trust_tier, "value") else str(source.trust_tier or "")
        robots_p = source.robots_policy.value if hasattr(source.robots_policy, "value") else str(source.robots_policy or "")
        terms_s = source.terms_review_status.value if hasattr(source.terms_review_status, "value") else str(source.terms_review_status or "")
        health_s = source.health_status.value if hasattr(source.health_status, "value") else str(source.health_status or "HEALTHY")

        return {
            "id": source.id,
            "name": source.name,
            "canonical_url": source.canonical_url or "",
            "organization": source.organization or "",
            "country_scope": source.country_scope or "GLOBAL",
            "language": source.language or "en",
            "source_family": source_fam,
            "opportunity_types": opp_types_str,
            "collection_method": source.collection_method,
            "collector_type": source.collector_type or source.collection_method,
            "access_method": access_meth,
            "default_category": source.default_category,
            "status": source.status,
            "enabled": bool(source.enabled),
            "official": bool(source.official),
            "trust_score": float(source.trust_score or 1.0),
            "trust_tier": trust_t,
            "maintenance_level": source.maintenance_level,
            "update_frequency": source.update_frequency,
            "max_requests_per_run": source.max_requests_per_run,
            "request_delay_ms": source.request_delay_ms,
            "requires_auth": bool(source.requires_auth),
            "rate_limit_policy": rate_limit_str,
            "robots_policy": robots_p,
            "terms_review_status": terms_s,
            "parser_version": source.parser_version or "1.0.0",
            "health_status": health_s,
            "last_success_at": source.last_success_at,
            "last_failure_at": source.last_failure_at,
            "last_checked_at": source.last_checked_at,
            "last_item_count": int(source.last_item_count or 0),
            "last_new_item_count": int(source.last_new_item_count or 0),
            "last_updated_item_count": int(source.last_updated_item_count or 0),
            "failure_count": int(source.failure_count or 0),
            "success_count": int(source.success_count or 0),
        }

    def _row_to_entity(self, row: Any) -> Source:
        def _get(key, default=None):
            try:
                if hasattr(row, "keys") and key in row.keys():
                    v = row[key]
                    return v if v is not None else default
                elif hasattr(row, key):
                    v = getattr(row, key)
                    return v if v is not None else default
            except Exception:
                pass
            return default

        opp_types_raw = _get("opportunity_types", "[]")
        try:
            opp_types = json.loads(opp_types_raw) if isinstance(opp_types_raw, str) else opp_types_raw
        except Exception:
            opp_types = []

        rate_limit_raw = _get("rate_limit_policy", "{}")
        try:
            rate_limit_policy = json.loads(rate_limit_raw) if isinstance(rate_limit_raw, str) else rate_limit_raw
        except Exception:
            rate_limit_policy = {}

        return Source(
            id=_get("id", ""),
            name=_get("name", ""),
            canonical_url=_get("canonical_url", ""),
            organization=_get("organization", ""),
            country_scope=_get("country_scope", "GLOBAL"),
            language=_get("language", "en"),
            source_family=_get("source_family", "OTHER"),
            opportunity_types=opp_types or [],
            collection_method=_get("collection_method", "rss"),
            collector_type=_get("collector_type", _get("collection_method", "rss")),
            access_method=_get("access_method", "manual_review"),
            default_category=_get("default_category", "other"),
            status=_get("status", "active"),
            enabled=bool(_get("enabled", True)),
            official=bool(_get("official", False)),
            trust_score=float(_get("trust_score", 1.0)),
            trust_tier=_get("trust_tier", "TIER_2"),
            maintenance_level=_get("maintenance_level", "stable"),
            update_frequency=_get("update_frequency", "daily"),
            max_requests_per_run=int(_get("max_requests_per_run", 10)),
            request_delay_ms=int(_get("request_delay_ms", 1000)),
            requires_auth=bool(_get("requires_auth", False)),
            rate_limit_policy=rate_limit_policy or {},
            robots_policy=_get("robots_policy", "allow"),
            terms_review_status=_get("terms_review_status", "pending"),
            parser_version=_get("parser_version", "1.0.0"),
            health_status=_get("health_status", "HEALTHY"),
            last_success_at=_get("last_success_at"),
            last_failure_at=_get("last_failure_at"),
            last_checked_at=_get("last_checked_at"),
            last_item_count=int(_get("last_item_count", 0)),
            last_new_item_count=int(_get("last_new_item_count", 0)),
            last_updated_item_count=int(_get("last_updated_item_count", 0)),
            failure_count=int(_get("failure_count", 0)),
            success_count=int(_get("success_count", 0)),
        )

    def save_source(self, source: Source) -> str:
        """Upserts a source record idempotently, adapting to existing columns in the table."""
        data = self._entity_to_dict(source)
        table_cols = self._get_table_columns()

        # If table columns are discovered, restrict insert to existing columns
        if table_cols:
            valid_keys = [k for k in data.keys() if k.lower() in table_cols]
        else:
            valid_keys = list(data.keys())

        if "id" not in valid_keys:
            valid_keys.insert(0, "id")

        cols_str = ", ".join(valid_keys)
        placeholders_str = ", ".join(["?"] * len(valid_keys))
        update_cols = [k for k in valid_keys if k != "id"]
        update_str = ", ".join([f"{k} = excluded.{k}" for k in update_cols])

        sql = f"""
        INSERT INTO Sources ({cols_str})
        VALUES ({placeholders_str})
        ON CONFLICT(id) DO UPDATE SET
            {update_str};
        """
        values = tuple(data[k] for k in valid_keys)

        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, values)
            return source.id
        except Exception as e:
            raise RepositoryError(f"Failed to save Source '{source.id}': {e}", original_exception=e)

    def sync_authoritative_sources(self) -> int:
        """
        Syncs all 75 authoritative target sources from source_definitions into the database in a single transaction.
        """
        from src.collectors.source_definitions import AUTHORITATIVE_SOURCES
        count = 0
        defs_list = AUTHORITATIVE_SOURCES.values() if isinstance(AUTHORITATIVE_SOURCES, dict) else AUTHORITATIVE_SOURCES
        table_cols = self._get_table_columns()

        try:
            with self.db_manager.transaction() as cursor:
                for s_def in defs_list:
                    tier_str = s_def.trust_tier.value if hasattr(s_def.trust_tier, "value") else str(s_def.trust_tier)
                    is_official = (tier_str == "TIER_1")
                    source_obj = Source(
                        id=s_def.source_id,
                        name=s_def.name,
                        canonical_url=s_def.canonical_url,
                        organization=s_def.organization,
                        country_scope=s_def.country_scope,
                        language=s_def.language,
                        source_family=s_def.source_family,
                        opportunity_types=s_def.opportunity_types,
                        collection_method=s_def.collector_type,
                        collector_type=s_def.collector_type,
                        access_method=s_def.access_method,
                        default_category="other",
                        status=s_def.status,
                        enabled=s_def.enabled,
                        official=is_official,
                        trust_score=1.0 if is_official else 0.8,
                        trust_tier=s_def.trust_tier,
                        requires_auth=s_def.requires_auth,
                        rate_limit_policy=s_def.rate_limit_policy.to_dict() if hasattr(s_def.rate_limit_policy, "to_dict") else {},
                        robots_policy=s_def.robots_policy,
                        terms_review_status=s_def.terms_review_status,
                        parser_version=s_def.parser_version,
                        health_status=s_def.health_status,
                    )
                    data = self._entity_to_dict(source_obj)
                    if table_cols:
                        valid_keys = [k for k in data.keys() if k.lower() in table_cols]
                    else:
                        valid_keys = list(data.keys())

                    if "id" not in valid_keys:
                        valid_keys.insert(0, "id")

                    cols_str = ", ".join(valid_keys)
                    placeholders_str = ", ".join(["?"] * len(valid_keys))
                    update_cols = [k for k in valid_keys if k != "id"]
                    update_str = ", ".join([f"{k} = excluded.{k}" for k in update_cols])

                    sql = f"""
                    INSERT INTO Sources ({cols_str})
                    VALUES ({placeholders_str})
                    ON CONFLICT(id) DO UPDATE SET
                        {update_str};
                    """
                    values = tuple(data[k] for k in valid_keys)
                    cursor.execute(sql, values)
                    count += 1
            logger.info(f"Synced {count} authoritative sources into database in single transaction.")
            return count
        except Exception as e:
            raise RepositoryError(f"Failed to sync authoritative sources: {e}", original_exception=e)

    def sync_from_config(self, sources_config: Dict[str, Any]) -> int:
        """
        Syncs source records from loaded sources config dictionary into the database.

        Args:
            sources_config: Master dictionary of sources from config.

        Returns:
            Number of synced source records.
        """
        synced_count = 0
        try:
            sources_list = (
                sources_config.get("sources", [])
                if isinstance(sources_config, dict) and "sources" in sources_config
                else sources_config
            )

            if isinstance(sources_list, dict):
                source_items = [
                    {"id": k, **v} if isinstance(v, dict) else {"id": k}
                    for k, v in sources_list.items()
                ]
            elif isinstance(sources_list, list):
                source_items = sources_list
            else:
                source_items = []

            # Also check if authoritative registry has definitions
            from src.collectors.source_definitions import get_source_definition

            for item in source_items:
                if not isinstance(item, dict) or "id" not in item:
                    continue

                sid = item["id"]
                auth_def = get_source_definition(sid)

                tier_val = (
                    auth_def.trust_tier.value
                    if (auth_def and hasattr(auth_def.trust_tier, "value"))
                    else (str(auth_def.trust_tier) if auth_def else "TIER_2")
                )
                source_obj = Source(
                    id=sid,
                    name=item.get("name", auth_def.name if auth_def else sid.capitalize()),
                    canonical_url=item.get("canonical_url", auth_def.canonical_url if auth_def else ""),
                    organization=item.get("organization", auth_def.organization if auth_def else ""),
                    country_scope=item.get("country_scope", auth_def.country_scope if auth_def else "GLOBAL"),
                    language=item.get("language", auth_def.language if auth_def else "en"),
                    source_family=item.get("source_family", auth_def.source_family if auth_def else "OTHER"),
                    opportunity_types=item.get("opportunity_types", auth_def.opportunity_types if auth_def else []),
                    collection_method=item.get("collection_method", item.get("type", auth_def.collector_type if auth_def else "rss")),
                    collector_type=item.get("collector_type", auth_def.collector_type if auth_def else "rss"),
                    access_method=item.get("access_method", auth_def.access_method if auth_def else "manual_review"),
                    default_category=item.get("default_category", "other"),
                    status=item.get("status", auth_def.status if auth_def else "active"),
                    enabled=bool(item.get("enabled", auth_def.enabled if auth_def else True)),
                    official=bool(item.get("official", tier_val == "TIER_1")),
                    trust_score=float(item.get("trust_score", 1.0 if tier_val == "TIER_1" else 0.8)),
                    trust_tier=item.get("trust_tier", tier_val),
                    maintenance_level=item.get("maintenance_level", "stable"),
                    update_frequency=item.get("update_frequency", "daily"),
                    max_requests_per_run=item.get("max_requests_per_run", 10),
                    request_delay_ms=item.get("request_delay_ms", 1000),
                    requires_auth=bool(item.get("requires_auth", auth_def.requires_auth if auth_def else False)),
                    rate_limit_policy=item.get("rate_limit_policy", auth_def.rate_limit_policy.to_dict() if auth_def and hasattr(auth_def.rate_limit_policy, "to_dict") else {}),
                    robots_policy=item.get("robots_policy", auth_def.robots_policy if auth_def else "allow"),
                    terms_review_status=item.get("terms_review_status", auth_def.terms_review_status if auth_def else "pending"),
                    parser_version=item.get("parser_version", auth_def.parser_version if auth_def else "1.0.0"),
                    health_status=item.get("health_status", auth_def.health_status if auth_def else "HEALTHY"),
                )
                self.save_source(source_obj)
                synced_count += 1
            logger.info(f"Synced {synced_count} source records into database.")
            return synced_count
        except Exception as e:
            raise RepositoryError(f"Failed to sync sources config to database: {e}", original_exception=e)

    def get_active_sources(self) -> List[Source]:
        """Retrieves all enabled sources from database."""
        return self.search(where_clause="(enabled IS TRUE OR enabled = True)")

    def get_sources_by_method(self, method: str) -> List[Source]:
        """Retrieves active sources matching a specific collection method."""
        return self.search(where_clause="collection_method = ? AND (enabled IS TRUE OR enabled = True)", params=(method,))

    def get_by_id(self, source_id: str) -> Optional[Source]:
        """Alias for read_by_id to retrieve a source by ID."""
        return self.read_by_id(source_id)


