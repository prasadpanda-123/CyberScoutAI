"""
SQLAlchemy ORM Model for Sources table.
"""

from sqlalchemy import Boolean, Column, Float, Integer, String, Text

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
        }
