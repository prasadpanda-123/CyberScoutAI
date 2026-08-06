"""
Database Engine Configuration for CyberScout AI.

Supports dual-dialect connection management:
- Uses PostgreSQL when DATABASE_URL environment variable is present.
- Automatically falls back to SQLite for local development when DATABASE_URL is absent.
"""

import os
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, Engine
from sqlalchemy.pool import StaticPool

from src.core.constants import DATA_DIR, DEFAULT_DB_NAME
from src.core.logging import get_logger

logger = get_logger(__name__)

_engine_cache: Optional[Engine] = None


def get_db_url(custom_url: Optional[str] = None, db_path: Optional[Path] = None) -> tuple[str, str]:
    """
    Determines database connection URL and dialect mode.

    Returns:
        Tuple of (connection_url, dialect_name)
    """
    raw_url = custom_url or os.getenv("DATABASE_URL", "").strip()
    if raw_url:
        # Convert legacy postgres:// to postgresql:// if present (Render/Heroku convention)
        if raw_url.startswith("postgres://"):
            raw_url = raw_url.replace("postgres://", "postgresql://", 1)
        return raw_url, "postgresql"

    # Default fallback: SQLite
    target_path = db_path or (DATA_DIR / DEFAULT_DB_NAME)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite_url = f"sqlite:///{target_path.as_posix()}"
    return sqlite_url, "sqlite"


def create_db_engine(custom_url: Optional[str] = None, db_path: Optional[Path] = None) -> Engine:
    """
    Factory creating a SQLAlchemy Engine tailored to PostgreSQL or SQLite fallback.
    """
    connection_url, dialect = get_db_url(custom_url=custom_url, db_path=db_path)

    if dialect == "postgresql":
        logger.info("Initializing PostgreSQL SQLAlchemy Database Engine.")
        engine = create_engine(
            connection_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800,
            future=True,
        )
    else:
        logger.info(f"Initializing SQLite Fallback SQLAlchemy Engine at '{connection_url}'.")
        connect_args = {"check_same_thread": False}
        if ":memory:" in connection_url:
            engine = create_engine(
                connection_url,
                connect_args=connect_args,
                poolclass=StaticPool,
                future=True,
            )
        else:
            engine = create_engine(
                connection_url,
                connect_args=connect_args,
                future=True,
            )

    return engine


def get_engine() -> Engine:
    """
    Returns singleton application database engine.
    """
    global _engine_cache
    if _engine_cache is None:
        _engine_cache = create_db_engine()
    return _engine_cache


def reset_engine() -> None:
    """Resets global engine cache (useful for testing)."""
    global _engine_cache
    if _engine_cache:
        _engine_cache.dispose()
        _engine_cache = None
