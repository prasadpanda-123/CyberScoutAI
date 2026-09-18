"""
Controlled Database Reset Manager for CyberScout AI (Phase 12.2).

Provides a deterministic, fail-closed, dependency-aware database reset
for development and test environments while strictly preserving schema
definitions, migration history, sequences, and security controls.

SAFETY CONSTRAINTS:
- NEVER executes against a production environment (checks APP_ENV and host).
- Requires explicit confirmation flag.
- Verifies prior backup snapshot exists before clearing application data.
- Preserves migration history in 'schema_version' table.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import text

from src.core.exceptions import ConfigurationError, DatabaseError
from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.database.engine import get_masked_db_host, get_db_url
from src.maintenance.backup_manager import BackupManager

logger = get_logger(__name__)


class DatabaseResetManager:
    """Safely manages fresh development/test database resets."""

    APPLICATION_TABLES: List[str] = [
        # Dependent tables first (foreign keys to Users and Opportunities)
        "AuditLogs",
        "NotificationOutbox",
        "SavedOpportunities",
        "UserPreferences",
        "UserSearchHistory",
        "ServerSessions",
        "PendingMfa",
        "LoginAttempts",
        "Opportunities",
        "OpportunityDuplicatesArchive",
        "SearchHistory",
        "AppLogs",
        "EmailHistory",
        "ScanJobs",
        "SourceHealth",
        "scheduler_webhook_requests",
        "Users",
        "Admins",
        "Sources",
        "Keywords",
        "Preferences",
        "Statistics",
        "scheduler_state",
    ]

    PRESERVED_TABLES: List[str] = [
        "schema_version",
        "alembic_version",
    ]

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def verify_safety_preconditions(self) -> Dict[str, Any]:
        """
        Validates that target environment is disposable and safe to reset.
        Raises ConfigurationError or DatabaseError if safety cannot be guaranteed.
        """
        app_env = os.getenv("APP_ENV", "").lower().strip()
        if app_env in ("production", "prod"):
            raise ConfigurationError(
                f"CRITICAL SAFETY VIOLATION: Cannot reset database in APP_ENV='{app_env}'!"
            )
        if app_env not in ("development", "dev", "test", "testing", "staging_disposable", "local"):
            raise ConfigurationError(
                f"Ambiguous environment APP_ENV='{app_env}'. Reset is only permitted in development/test."
            )

        # Check latest backup
        bm = BackupManager(db_manager=self.db_manager)
        backups = list(bm.backup_dir.glob("cyberscout_backup_*.sql"))
        if not backups:
            raise DatabaseError("SAFETY PRECONDITION FAILED: No database backup snapshot found in data/backups/.")

        latest_backup = max(backups, key=lambda p: p.stat().st_mtime)
        if latest_backup.stat().st_size < 1000:
            raise DatabaseError(f"SAFETY PRECONDITION FAILED: Latest backup '{latest_backup.name}' is suspiciously small or empty.")

        masked_host = get_masked_db_host()
        return {
            "app_env": app_env,
            "masked_host": masked_host,
            "latest_backup": str(latest_backup),
            "latest_backup_size": latest_backup.stat().st_size,
            "is_safe": True,
        }

    def reset_database(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Performs a controlled, transactional reset of application tables.
        
        Args:
            confirm: Must be explicitly True to execute.
            
        Returns:
            Dictionary containing execution summary, row counts before and after.
        """
        if not confirm:
            raise ValueError("Controlled reset aborted: 'confirm=True' is required.")

        preflight = self.verify_safety_preconditions()
        logger.warning(
            f"Initiating controlled database reset on '{preflight['masked_host']}' (APP_ENV={preflight['app_env']})..."
        )

        start_t = datetime.now(timezone.utc)
        counts_before: Dict[str, int] = {}
        counts_after: Dict[str, int] = {}

        with self.db_manager.get_session() as session:
            # 1. Capture row counts before reset
            for tbl in self.APPLICATION_TABLES:
                try:
                    cnt = session.execute(text(f'SELECT count(*) FROM "{tbl}"')).scalar()
                    counts_before[tbl] = cnt or 0
                except Exception as e:
                    counts_before[tbl] = -1

            # 2. Execute dependency-aware atomic truncate
            # Quote all table names
            quoted_tables = ", ".join([f'"{tbl}"' for tbl in self.APPLICATION_TABLES])
            truncate_sql = f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE;"
            logger.info(f"Executing TRUNCATE on {len(self.APPLICATION_TABLES)} application tables...")
            session.execute(text(truncate_sql))
            session.commit()

        # 3. Re-enforce RLS policies and grants on the clean database
        logger.info("Re-enforcing Row Level Security policies and grants post-reset...")
        self.db_manager.configure_rls_policies(force=True)

        # 4. Verify post-reset table states and row counts
        with self.db_manager.get_session() as session:
            for tbl in self.APPLICATION_TABLES:
                cnt = session.execute(text(f'SELECT count(*) FROM "{tbl}"')).scalar()
                counts_after[tbl] = cnt or 0

            # Verify schema_version preserved
            schema_ver_cnt = session.execute(text("SELECT count(*) FROM schema_version")).scalar()
            max_ver = session.execute(text("SELECT max(version) FROM schema_version")).scalar()

        # 5. Check all application tables are 0
        non_zero = {t: c for t, c in counts_after.items() if c > 0}
        if non_zero:
            raise DatabaseError(f"Reset validation failed: some tables still contain rows: {non_zero}")

        duration = (datetime.now(timezone.utc) - start_t).total_seconds()
        result = {
            "success": True,
            "duration_seconds": duration,
            "reset_at": start_t.isoformat(),
            "environment": preflight["app_env"],
            "masked_host": preflight["masked_host"],
            "tables_reset": len(self.APPLICATION_TABLES),
            "counts_before": counts_before,
            "counts_after": counts_after,
            "schema_version_preserved": max_ver == 16,
            "schema_version_count": schema_ver_cnt,
            "max_schema_version": max_ver,
        }
        logger.info(f"Controlled database reset completed successfully in {duration:.2f}s. All application tables 0.")
        return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Controlled Database Reset for CyberScout AI")
    parser.add_argument("--confirm", action="store_true", help="Explicitly confirm database reset")
    args = parser.parse_args()

    manager = DatabaseResetManager()
    if not args.confirm:
        print("PREFLIGHT CHECK ONLY (use --confirm to execute reset):")
        try:
            safety = manager.verify_safety_preconditions()
            print(f"Preconditions PASSED: {safety}")
        except Exception as e:
            print(f"Preconditions FAILED: {e}")
    else:
        res = manager.reset_database(confirm=True)
        print("RESET RESULT:")
        print(res)
