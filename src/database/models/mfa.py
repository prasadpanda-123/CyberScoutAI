"""
SQLAlchemy ORM Model for Pending MFA and OTP Verification States.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from src.database.base import Base


class PendingMfaModel(Base):
    """
    Persistent state for pending multi-factor authentication (MFA) and OTP verification transactions.
    Replaces process-local memory stores, enabling stateless multi-worker WSGI deployments.
    """
    __tablename__ = "PendingMfa"

    token = Column(String(64), primary_key=True)
    state_type = Column(String(32), nullable=False, default="admin_login_mfa", index=True)
    account_id = Column(Integer, nullable=False)
    username = Column(String(128), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(64), nullable=True)
    otp_hash = Column(String(64), nullable=False)
    new_password_hash = Column(Text, nullable=True)
    next_url = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    expires_at = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_resend_at = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_pending_mfa_account_state", "account_id", "state_type"),
        Index("ix_pending_mfa_expires_at", "expires_at"),
    )
