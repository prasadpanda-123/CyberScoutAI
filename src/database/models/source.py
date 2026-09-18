"""
SQLAlchemy ORM Model for Sources table.
"""

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from src.database.base import Base


class SourceModel(Base):
    __tablename__ = "Sources"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    collection_method = Column(String, nullable=False)
    default_category = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")
    enabled = Column(Boolean, default=True)
    official = Column(Boolean, default=False)
    trust_score = Column(Float, default=1.0)
    maintenance_level = Column(String, nullable=True)
    update_frequency = Column(String, nullable=True)
    max_requests_per_run = Column(Integer, nullable=True)
    request_delay_ms = Column(Integer, nullable=True)

    # Phase 2 Registry & Health Metadata
    canonical_url = Column(String, nullable=True)
    organization = Column(String, nullable=True)
    country_scope = Column(String, nullable=True, default="GLOBAL")
    language = Column(String, nullable=True, default="en")
    source_family = Column(String, nullable=True, default="other")
    opportunity_types = Column(Text, nullable=True)
    collector_type = Column(String, nullable=True, default="rss")
    access_method = Column(String, nullable=True, default="rss")
    trust_tier = Column(String, nullable=True, default="tier_2")
    requires_auth = Column(Boolean, default=False)
    rate_limit_policy = Column(Text, nullable=True)
    robots_policy = Column(String, default="respect")
    terms_review_status = Column(String, default="pending_review")
    parser_version = Column(String, default="1.0.0")
    health_status = Column(String, default="healthy")
    last_success_at = Column(DateTime, nullable=True)
    last_failure_at = Column(DateTime, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    last_item_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "collection_method": self.collection_method,
            "default_category": self.default_category,
            "status": self.status,
            "enabled": bool(self.enabled) if self.enabled is not None else True,
            "official": bool(self.official) if self.official is not None else False,
            "trust_score": self.trust_score or 1.0,
            "maintenance_level": self.maintenance_level,
            "update_frequency": self.update_frequency,
            "max_requests_per_run": self.max_requests_per_run,
            "request_delay_ms": self.request_delay_ms,
            "canonical_url": self.canonical_url,
            "organization": self.organization,
            "country_scope": self.country_scope,
            "language": self.language,
            "source_family": self.source_family,
            "opportunity_types": self.opportunity_types.split(",") if self.opportunity_types else [],
            "collector_type": self.collector_type,
            "access_method": self.access_method,
            "trust_tier": self.trust_tier,
            "requires_auth": bool(self.requires_auth),
            "robots_policy": self.robots_policy,
            "terms_review_status": self.terms_review_status,
            "parser_version": self.parser_version,
            "health_status": self.health_status,
            "last_success_at": str(self.last_success_at) if self.last_success_at else None,
            "last_failure_at": str(self.last_failure_at) if self.last_failure_at else None,
            "last_checked_at": str(self.last_checked_at) if self.last_checked_at else None,
            "last_item_count": self.last_item_count or 0,
            "failure_count": self.failure_count or 0,
            "success_count": self.success_count or 0,
        }
