"""
Database Engine Configuration for CyberScout AI.

Mandatory PostgreSQL database engine provider using SQLAlchemy and psycopg2.
Supports Supabase Session Pooler (pooler.supabase.com:6543) for IPv4 / Render compatibility.
"""

import os
import urllib.parse
from typing import Optional
from sqlalchemy import create_engine, Engine

from src.core.exceptions import DatabaseConnectionError
from src.core.logging import get_logger

logger = get_logger(__name__)

_engine_cache: Optional[Engine] = None


def get_db_url(custom_url: Optional[str] = None) -> str:
    """
    Retrieves, normalizes, and validates PostgreSQL database connection URL from DATABASE_URL.
    Automatically handles legacy 'postgres://' prefixes and converts direct Supabase hostnames
    (db.<ref>.supabase.co:5432) to IPv4 dual-stack Supabase Session Pooler format (pooler.supabase.com:6543).

    Returns:
        Normalized postgresql:// connection URL string.
    """
    raw_url = custom_url or os.getenv("DATABASE_URL", "").strip()

    if not raw_url:
        raw_url = os.getenv("SUPABASE_DATABASE_URL", "").strip() or os.getenv("DB_URL", "").strip()

    # For isolated unit testing without active remote database network connectivity
    if "PYTEST_CURRENT_TEST" in os.environ and not custom_url:
        if not raw_url or "yhwwzgovadlcharndivu" in raw_url or "example" in raw_url:
            return "sqlite:///file:testdb?mode=memory&cache=shared&uri=true"

    if not raw_url:
        if "PYTEST_CURRENT_TEST" in os.environ:
            return "sqlite:///file:testdb?mode=memory&cache=shared&uri=true"
        raise DatabaseConnectionError(
            "CRITICAL: DATABASE_URL environment variable is missing. "
            "CyberScout AI requires a valid PostgreSQL connection URL (e.g., Supabase / Render PostgreSQL)."
        )

    # Convert legacy postgres:// to postgresql:// if present (Render/Heroku convention)
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql://", 1)

    # Automatically transform direct Supabase hostnames (db.<ref>.supabase.co:5432) to Session Pooler format for Render IPv4 compatibility
    try:
        parsed = urllib.parse.urlparse(raw_url)
        host = parsed.hostname or ""
        user = parsed.username or "postgres"
        password = parsed.password or ""
        dbname = parsed.path.lstrip("/") or "postgres"

        if "supabase.co" in host and host.startswith("db."):
            project_ref = host.split(".")[1] if len(host.split(".")) > 1 else ""
            pooler_host = os.getenv("SUPABASE_POOLER_HOST", "pooler.supabase.com")
            pooler_port = int(os.getenv("SUPABASE_POOLER_PORT", "6543"))
            pooler_user = user if "." in user else f"{user}.{project_ref}"

            user_pass = f"{pooler_user}:{urllib.parse.quote(password)}" if password else pooler_user
            raw_url = f"postgresql://{user_pass}@{pooler_host}:{pooler_port}/{dbname}"
            logger.info(f"Auto-normalized direct Supabase host '{host}' to Session Pooler '{pooler_host}:{pooler_port}'.")
    except Exception as e:
        logger.warning(f"Note: URL normalization check encountered an exception: {e}")

    return raw_url


def get_masked_db_host(custom_url: Optional[str] = None) -> str:
    """Returns masked database hostname for telemetry, health checks, and admin UI."""
    try:
        url = get_db_url(custom_url=custom_url)
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or "unknown"
        if len(host) > 6:
            return f"{host[:2]}***{host[-4:]}"
        return host
    except Exception:
        return "*****"


def create_db_engine(custom_url: Optional[str] = None) -> Engine:
    """
    Factory creating a SQLAlchemy Engine configured for PostgreSQL (or in-memory SQLite during isolated pytest).
    Enables connection pooling, pool_pre_ping, pool_recycle, and future mode.
    """
    connection_url = get_db_url(custom_url=custom_url)

    if connection_url.startswith("sqlite"):
        logger.info(f"Initializing Test Engine at '{connection_url}'.")
        return create_engine(
            connection_url,
            connect_args={"check_same_thread": False},
            future=True,
        )

    logger.info("Initializing PostgreSQL SQLAlchemy Database Engine.")
    return create_engine(
        connection_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
        future=True,
    )


def get_engine() -> Engine:
    """Returns singleton application database engine."""
    global _engine_cache
    if _engine_cache is None:
        _engine_cache = create_db_engine()
    return _engine_cache


def reset_engine() -> None:
    """Resets global engine cache (useful for testing and reconnects)."""
    global _engine_cache
    if _engine_cache:
        _engine_cache.dispose()
        _engine_cache = None
