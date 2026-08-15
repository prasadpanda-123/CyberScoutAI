"""
SQLAlchemy ORM Model for Admins table.
"""

import datetime
from sqlalchemy import Column, DateTime, Integer, String

from src.database.base import Base


class AdminModel(Base):
    __tablename__ = "Admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="Admin")
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
