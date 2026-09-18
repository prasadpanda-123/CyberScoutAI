"""
SQLAlchemy ORM Model for ScanJobs operational execution state.
"""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text, text

from src.database.base import Base


class ScanJobModel(Base):
    """
    Persistent operational execution record for background scan jobs.
    Enforces cross-worker concurrency locking and status tracking in PostgreSQL.
    """
    __tablename__ = "ScanJobs"

    job_id = Column(String(64), primary_key=True)
    job_type = Column(String(32), nullable=False, default="full_scan")
    status = Column(String(32), nullable=False, default="queued", index=True)
    progress = Column(Float, nullable=False, default=0.0)
    current_collector = Column(String(128), nullable=False, default="Initializing")
    opportunities_found = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    dry_run = Column(Boolean, nullable=False, default=False)
    errors = Column(Text, nullable=True)  # JSON-serialized list[str]
    result = Column(Text, nullable=True)  # JSON-serialized dict
    created_by_admin_id = Column(String(64), nullable=True)

    __table_args__ = (
        Index(
            "uq_active_scan_job",
            "job_type",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running', 'collecting', 'processing', 'saving')"),
            sqlite_where=text("status IN ('queued', 'running', 'collecting', 'processing', 'saving')"),
        ),
    )
