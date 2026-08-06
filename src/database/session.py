"""
SQLAlchemy Session Lifecycle Management for CyberScout AI.
"""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session, sessionmaker, scoped_session

from src.database.engine import get_engine
from src.core.logging import get_logger

logger = get_logger(__name__)

_session_factory = None


def get_session_factory(engine=None):
    """
    Returns scoped session factory for given engine (or default singleton engine).
    """
    global _session_factory
    if engine is not None:
        return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)
    return _session_factory


@contextmanager
def get_db_session(engine=None) -> Generator[Session, None, None]:
    """
    Context manager providing a transactional SQLAlchemy Session.
    Automatically commits on success or rolls back on exception.
    """
    factory = get_session_factory(engine=engine)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session transaction failed, changes rolled back: {e}")
        raise
    finally:
        session.close()
