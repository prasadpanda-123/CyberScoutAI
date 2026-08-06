"""
SQLAlchemy ORM Model for Opportunities table.
"""

import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
)
from sqlalchemy.orm import relationship

from src.database.base import Base


class OpportunityModel(Base):
    __tablename__ = "Opportunities"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    url = Column(Text, nullable=False)
    url_hash = Column(String, nullable=False, index=True)
    source_id = Column(String, ForeignKey("Sources.id"), nullable=False)
    category = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=True)
    company = Column(String, nullable=True)
    location = Column(String, nullable=True)
    remote = Column(Boolean, default=False)
    paid = Column(Boolean, nullable=True)
    certificate = Column(Boolean, default=False)
    price_raw = Column(String, nullable=True)
    price_normalized = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    deadline = Column(Date, nullable=True, index=True)
    published_date = Column(Date, nullable=True)
    discovered_date = Column(Date, nullable=False, index=True)
    duration = Column(String, nullable=True)
    difficulty = Column(String, default="unknown")
    tags = Column(Text, nullable=True)
    beginner_friendly = Column(Boolean, nullable=True)
    score = Column(Integer, default=0, index=True)
    score_breakdown = Column(Text, nullable=True)
    confidence_score = Column(Float, default=0.0)
    quality_score = Column(Float, default=0.0)
    is_rejected = Column(Boolean, default=False)
    rejection_reason = Column(Text, nullable=True)
    quality_flags = Column(Text, nullable=True)
    topic_score = Column(Float, default=0.0)
    keyword_score = Column(Float, default=0.0)
    spam_score = Column(Float, default=0.0)
    status = Column(String, nullable=False, default="active", index=True)
    duplicate_of_id = Column(String, ForeignKey("Opportunities.id"), nullable=True)
    run_id = Column(String, ForeignKey("SearchHistory.run_id"), nullable=True)
    raw_data = Column(Text, nullable=True)
    last_seen = Column(DateTime, nullable=True)

    # Relationships
    source = relationship("SourceModel", foreign_keys=[source_id])
    duplicate_of = relationship("OpportunityModel", remote_side=[id])

    def to_dict(self) -> dict:
        """Converts model instance to dictionary representation."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "url_hash": self.url_hash,
            "source_id": self.source_id,
            "category": self.category,
            "provider": self.provider,
            "company": self.company,
            "location": self.location,
            "remote": bool(self.remote) if self.remote is not None else False,
            "paid": self.paid,
            "certificate": bool(self.certificate) if self.certificate is not None else False,
            "price_raw": self.price_raw,
            "price_normalized": self.price_normalized,
            "currency": self.currency,
            "deadline": str(self.deadline) if self.deadline else None,
            "published_date": str(self.published_date) if self.published_date else None,
            "discovered_date": str(self.discovered_date) if self.discovered_date else None,
            "duration": self.duration,
            "difficulty": self.difficulty,
            "tags": self.tags.split(",") if isinstance(self.tags, str) and self.tags else (self.tags or []),
            "beginner_friendly": self.beginner_friendly,
            "score": self.score or 0,
            "score_breakdown": self.score_breakdown,
            "confidence_score": self.confidence_score or 0.0,
            "quality_score": self.quality_score or 0.0,
            "is_rejected": bool(self.is_rejected) if self.is_rejected is not None else False,
            "rejection_reason": self.rejection_reason,
            "quality_flags": self.quality_flags,
            "topic_score": self.topic_score or 0.0,
            "keyword_score": self.keyword_score or 0.0,
            "spam_score": self.spam_score or 0.0,
            "status": self.status,
            "duplicate_of_id": self.duplicate_of_id,
            "run_id": self.run_id,
            "raw_data": self.raw_data,
            "last_seen": str(self.last_seen) if self.last_seen else None,
        }
