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

    if not raw_url:
        if "PYTEST_CURRENT_TEST" in os.environ or os.getenv("APP_ENV") in ("test", "testing") or os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
            raw_url = os.getenv("TEST_DATABASE_URL", "").strip()

    if not raw_url:
        logger.error("DATABASE_URL environment variable is missing.")
        raise DatabaseConnectionError("DATABASE_URL (or TEST_DATABASE_URL for tests) environment variable is required. SQLite is not supported.")

    if raw_url.startswith("sqlite"):
        logger.error("Unsupported database backend: SQLite is not supported.")
        raise DatabaseConnectionError("Unsupported database backend: SQLite is not supported. CyberScout AI requires PostgreSQL.")

    # Convert legacy postgres:// to postgresql:// if present (Render/Heroku convention)
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql://", 1)

    # Automatically transform direct Supabase hostnames (db.<ref>.supabase.co:5432) or Session Pooler port 5432 to Transaction Pooler port 6543 for IPv4 compatibility
    try:
        parsed = urllib.parse.urlparse(raw_url)
        host = parsed.hostname or ""
        user = parsed.username or "postgres"
        password = parsed.password or ""
        dbname = parsed.path.lstrip("/") or "postgres"

        if "supabase.co" in host or "supabase.com" in host:
            if host.startswith("db."):
                project_ref = host.split(".")[1] if len(host.split(".")) > 1 else ""
                pooler_host = os.getenv("SUPABASE_POOLER_HOST", "pooler.supabase.com")
                pooler_port = int(os.getenv("SUPABASE_POOLER_PORT", "6543"))
                pooler_user = user if "." in user else f"{user}.{project_ref}"

                user_pass = f"{pooler_user}:{urllib.parse.quote(password)}" if password else pooler_user
                raw_url = f"postgresql://{user_pass}@{pooler_host}:{pooler_port}/{dbname}"
                logger.info(f"Auto-normalized direct Supabase host '{host}' to Transaction Pooler '{pooler_host}:{pooler_port}'.")
            elif parsed.port == 5432 or ":5432" in raw_url:
                pooler_port = int(os.getenv("SUPABASE_POOLER_PORT", "6543"))
                raw_url = raw_url.replace(":5432", f":{pooler_port}", 1)
                logger.info(f"Auto-normalized Supabase Pooler port from 5432 (Session mode) to {pooler_port} (Transaction mode).")
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
    Factory creating a SQLAlchemy Engine configured for PostgreSQL.
    Enables connection pooling, pool_pre_ping, pool_recycle, and future mode.
    """
    connection_url = get_db_url(custom_url=custom_url)

    if connection_url.startswith("sqlite"):
        raise DatabaseConnectionError("Unsupported database backend: SQLite is not supported. CyberScout AI requires PostgreSQL.")

    try:
        parsed = urllib.parse.urlparse(connection_url)
        host = parsed.hostname or "unknown"
        port = parsed.port or 5432
        dbname = parsed.path.lstrip("/") or "postgres"
        query_params = urllib.parse.parse_qs(parsed.query)
        sslmode = query_params.get("sslmode", ["require"])[0]
        masked_h = f"{host[:2]}***{host[-4:]}" if len(host) > 6 else host
        logger.info(
            f"PostgreSQL Configured — Host: {masked_h}, Port: {port}, Database: {dbname}, SSLMode: {sslmode}"
        )
    except Exception:
        pass

    logger.info("Initializing PostgreSQL SQLAlchemy Database Engine.")
    return create_engine(
        connection_url,
        isolation_level="READ COMMITTED",
        pool_size=3,
        max_overflow=5,
        pool_pre_ping=False,
        pool_recycle=45,
        connect_args={
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
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
