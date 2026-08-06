"""
Automated Idempotent Data Migration Service (SQLite -> PostgreSQL).

Copies existing records from local SQLite file into target PostgreSQL database
without creating duplicates (Phase 7).
"""

from pathlib import Path
import sqlite3
from typing import Optional
from sqlalchemy import select, inspect
from sqlalchemy.orm import Session

from src.core.constants import DATA_DIR, DEFAULT_DB_NAME
from src.core.logging import get_logger
from src.database.engine import get_db_url, create_db_engine
from src.database.base import Base
from src.database.models import (
    OpportunityModel,
    SourceModel,
    UserModel,
    AuditLogModel,
    SearchHistoryModel,
    EmailHistoryModel,
    SchedulerStateModel,
    AppLogModel,
    PreferenceModel,
    StatisticModel,
    KeywordModel,
)

logger = get_logger(__name__)


class DatabaseDataMigrator:
    """
    Idempotent Data Migration Coordinator.
    """

    def __init__(self, sqlite_path: Optional[Path] = None, target_engine=None):
        self.sqlite_path = sqlite_path or (DATA_DIR / DEFAULT_DB_NAME)
        self.target_engine = target_engine

    def migrate_if_needed(self) -> None:
        """
        Executes idempotent migration if SQLite database exists and target engine is configured.
        """
        if not self.sqlite_path.exists():
            logger.info(f"No SQLite database found at '{self.sqlite_path}' for data migration.")
            return

        if self.target_engine is None:
            from src.database.engine import get_engine
            self.target_engine = get_engine()

        # Ensure schema tables exist on target engine
        Base.metadata.create_all(bind=self.target_engine)

        url_str, dialect = get_db_url()
        if dialect == "sqlite" and str(self.sqlite_path.resolve()) in url_str:
            logger.debug("Source SQLite database is identical to target SQLite engine. No migration needed.")
            return

        logger.info(f"Starting data migration from SQLite '{self.sqlite_path}' to target database ({dialect}).")

        try:
            sqlite_conn = sqlite3.connect(str(self.sqlite_path))
            sqlite_conn.row_factory = sqlite3.Row

            with Session(self.target_engine) as session:
                self._migrate_table(sqlite_conn, session, "Sources", SourceModel, "id")
                self._migrate_table(sqlite_conn, session, "Users", UserModel, "id")
                self._migrate_table(sqlite_conn, session, "Opportunities", OpportunityModel, "id")
                self._migrate_table(sqlite_conn, session, "SearchHistory", SearchHistoryModel, "run_id")
                self._migrate_table(sqlite_conn, session, "EmailHistory", EmailHistoryModel, "id")
                self._migrate_table(sqlite_conn, session, "scheduler_state", SchedulerStateModel, "id")
                self._migrate_table(sqlite_conn, session, "AppLogs", AppLogModel, "id")
                self._migrate_table(sqlite_conn, session, "AuditLogs", AuditLogModel, "id")
                self._migrate_table(sqlite_conn, session, "Preferences", PreferenceModel, "id")
                self._migrate_table(sqlite_conn, session, "Statistics", StatisticModel, "id")
                self._migrate_table(sqlite_conn, session, "Keywords", KeywordModel, "id")
                session.commit()

            sqlite_conn.close()
            logger.info("Data migration completed successfully.")
        except Exception as e:
            logger.error(f"Error during data migration: {e}")

    def _migrate_table(self, sqlite_conn: sqlite3.Connection, session: Session, table_name: str, model_cls, pk_field: str) -> None:
        """Migrates records from a SQLite table into target session idempotently."""
        try:
            cursor = sqlite_conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name};")
            rows = cursor.fetchall()
            cursor.close()

            if not rows:
                return

            migrated_count = 0
            model_columns = {c.name for c in inspect(model_cls).columns}

            for row in rows:
                row_dict = dict(row)
                pk_val = row_dict.get(pk_field)
                if pk_val is not None:
                    # Check if already present on target
                    existing = session.query(model_cls).filter(getattr(model_cls, pk_field) == pk_val).first()
                    if existing:
                        continue

                filtered_data = {k: v for k, v in row_dict.items() if k in model_columns}
                obj = model_cls(**filtered_data)
                session.add(obj)
                migrated_count += 1

            session.flush()
            if migrated_count > 0:
                logger.info(f"Migrated {migrated_count} records into '{table_name}'.")
        except Exception as e:
            logger.warning(f"Skipped table '{table_name}' migration due to info: {e}")
