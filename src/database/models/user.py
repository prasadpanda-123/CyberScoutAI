"""
SQLAlchemy ORM Models for Users and AuditLogs tables.
"""

import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, func

from src.database.base import Base


class UserModel(Base):
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="Viewer")
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active == 1,
            "created_at": str(self.created_at) if self.created_at else None,
            "last_login": str(self.last_login) if self.last_login else None,
        }


class AuditLogModel(Base):
    __tablename__ = "AuditLogs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow, index=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String, nullable=True)
    event_type = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    source_ip = Column(String, nullable=True)
    status = Column(String, nullable=False)
    details = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": str(self.timestamp) if self.timestamp else None,
            "user_id": self.user_id,
            "username": self.username,
            "event_type": self.event_type,
            "action": self.action,
            "source_ip": self.source_ip,
            "status": self.status,
            "details": self.details,
        }
