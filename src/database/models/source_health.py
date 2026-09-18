"""
SQLAlchemy ORM Model for SourceHealth table.

Tracks persistent per-source run telemetry, latencies, items harvested, and failure classifications.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from src.database.base import Base


class SourceHealthModel(Base):
    __tablename__ = "SourceHealth"

    source_id = Column(String(128), ForeignKey("Sources.id"), primary_key=True)
    health_status = Column(String(32), nullable=False, default="HEALTHY", index=True)
    last_attempt = Column(DateTime, nullable=True)
    last_success = Column(DateTime, nullable=True)
    last_failure = Column(DateTime, nullable=True)
    failure_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    items_seen = Column(Integer, nullable=False, default=0)
    items_created = Column(Integer, nullable=False, default=0)
    items_updated = Column(Integer, nullable=False, default=0)
    items_rejected = Column(Integer, nullable=False, default=0)
    latency = Column(Float, nullable=False, default=0.0)
    error_class = Column(String(64), nullable=True)
    parser_version = Column(String(32), nullable=False, default="1.0.0")
    consecutive_failures = Column(Integer, nullable=False, default=0)
    details = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "health_status": self.health_status,
            "last_attempt": str(self.last_attempt) if self.last_attempt else None,
            "last_success": str(self.last_success) if self.last_success else None,
            "last_failure": str(self.last_failure) if self.last_failure else None,
            "failure_count": self.failure_count or 0,
            "success_count": self.success_count or 0,
            "items_seen": self.items_seen or 0,
            "items_created": self.items_created or 0,
            "items_updated": self.items_updated or 0,
            "items_rejected": self.items_rejected or 0,
            "latency": self.latency or 0.0,
            "error_class": self.error_class,
            "parser_version": self.parser_version,
            "consecutive_failures": self.consecutive_failures or 0,
            "details": self.details,
            "updated_at": str(self.updated_at) if self.updated_at else None,
        }
