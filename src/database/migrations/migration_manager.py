"""
Database Migration Manager for CyberScout AI.

Manages schema versions, migration history, and sequential upgrades.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.database.connection import DatabaseManager
from src.core.exceptions import MigrationError
from src.core.logging import get_logger

logger = get_logger(__name__)


class Migration:
    """Represents a single database migration definition."""

    def __init__(self, version: int, description: str, sql: str):
        self.version = version
        self.description = description
        self.sql = sql


# Registry of system migrations
MIGRATIONS: List[Migration] = [
    Migration(
        version=1,
        description="Initial baseline schema creation",
        sql="""
        -- Baseline schema is initialized by DatabaseManager._create_schema
        SELECT 1;
        """,
    ),
    Migration(
        version=2,
        description="Knowledge Base & Historical Intelligence Schema v2",
        sql="""
        CREATE TABLE IF NOT EXISTS trend_snapshots (
            id TEXT PRIMARY KEY,
            snapshot_date TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS provider_statistics (
            provider_name TEXT PRIMARY KEY,
            total_opportunities INTEGER DEFAULT 0,
            active_opportunities INTEGER DEFAULT 0,
            average_score REAL DEFAULT 0.0,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS opportunity_history (
            id TEXT PRIMARY KEY,
            opportunity_id TEXT NOT NULL,
            change_type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS retention_logs (
            id TEXT PRIMARY KEY,
            action_taken TEXT NOT NULL,
            records_affected INTEGER DEFAULT 0,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    ),
    Migration(
        version=3,
        description="Phase 11.5 Quality Intelligence Schema Extension",
        sql="""
        SELECT 1;
        """,
    ),
    Migration(
        version=4,
        description="Phase 12 Production Data Intelligence Schema Extension",
        sql="""
        CREATE TABLE IF NOT EXISTS trend_statistics (
            id TEXT PRIMARY KEY,
            window_days INTEGER DEFAULT 30,
            metric_category TEXT NOT NULL,
            metric_key TEXT NOT NULL,
            metric_value INTEGER DEFAULT 0,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS historical_changes (
            id TEXT PRIMARY KEY,
            opportunity_id TEXT NOT NULL,
            change_type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS link_validation (
            url TEXT PRIMARY KEY,
            status_code INTEGER DEFAULT 200,
            ssl_valid INTEGER DEFAULT 1,
            content_type TEXT,
            response_time REAL DEFAULT 0.0,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS quality_metrics_daily (
            date DATE PRIMARY KEY,
            total_collected INTEGER DEFAULT 0,
            total_accepted INTEGER DEFAULT 0,
            total_rejected INTEGER DEFAULT 0,
            total_duplicates INTEGER DEFAULT 0,
            total_expired INTEGER DEFAULT 0,
            avg_confidence REAL DEFAULT 0.0,
            avg_quality REAL DEFAULT 0.0,
            avg_freshness REAL DEFAULT 100.0
        );
        """,
    ),
    Migration(
        version=5,
        description="Phase 12.3 Scheduler State Table Creation",
        sql="""
        CREATE TABLE IF NOT EXISTS scheduler_state (
            id INTEGER PRIMARY KEY DEFAULT 1,
            last_email_sent TEXT,
            last_pipeline_run TEXT,
            updated_at TEXT
        );
        """,
    ),
    Migration(
        version=6,
        description="External Scheduler Webhook Request Idempotency & Tracking Table",
        sql="""
        CREATE TABLE IF NOT EXISTS scheduler_webhook_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE NOT NULL,
            timestamp INTEGER NOT NULL,
            received_at TIMESTAMP NOT NULL,
            status TEXT NOT NULL DEFAULT 'accepted',
            source TEXT NOT NULL DEFAULT 'google_apps_script',
            execution_details TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_webhook_req_id ON scheduler_webhook_requests(request_id);
        """,
    ),
    Migration(
        version=7,
        description="Phase 2 ScanJobs Operational Job State & Concurrency Table",
        sql="""
        CREATE TABLE IF NOT EXISTS "ScanJobs" (
            job_id VARCHAR(64) PRIMARY KEY,
            job_type VARCHAR(32) NOT NULL DEFAULT 'full_scan',
            status VARCHAR(32) NOT NULL DEFAULT 'queued',
            progress REAL NOT NULL DEFAULT 0.0,
            current_collector VARCHAR(128) NOT NULL DEFAULT 'Initializing',
            opportunities_found INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMP NULL,
            finished_at TIMESTAMP NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            dry_run BOOLEAN NOT NULL DEFAULT FALSE,
            errors TEXT NULL,
            result TEXT NULL,
            created_by_admin_id VARCHAR(64) NULL
        );
        CREATE INDEX IF NOT EXISTS idx_scanjobs_status ON "ScanJobs"(status);
        CREATE INDEX IF NOT EXISTS idx_scanjobs_created_at ON "ScanJobs"(created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_scan_job ON "ScanJobs" (job_type)
            WHERE status IN ('queued', 'running', 'collecting', 'processing', 'saving');
        """,
    ),
    Migration(
        version=8,
        description="Phase 3 Pending MFA & OTP State Centralization Table",
        sql="""
        CREATE TABLE IF NOT EXISTS "PendingMfa" (
            token VARCHAR(64) PRIMARY KEY,
            state_type VARCHAR(32) NOT NULL DEFAULT 'admin_login_mfa',
            account_id INTEGER NOT NULL,
            username VARCHAR(128) NOT NULL,
            email VARCHAR(255) NOT NULL,
            role VARCHAR(64) NULL,
            otp_hash VARCHAR(64) NOT NULL,
            new_password_hash TEXT NULL,
            next_url TEXT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            expires_at INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_resend_at INTEGER NULL
        );
        CREATE INDEX IF NOT EXISTS ix_pending_mfa_account_state ON "PendingMfa"(account_id, state_type);
        CREATE INDEX IF NOT EXISTS ix_pending_mfa_expires_at ON "PendingMfa"(expires_at);
        """,
    ),
    Migration(
        version=9,
        description="Server-Side Sessions & Opaque Cookie Minimization Table",
        sql="""
        CREATE TABLE IF NOT EXISTS "ServerSessions" (
            session_hash VARCHAR(64) PRIMARY KEY,
            session_data TEXT NOT NULL DEFAULT '{}',
            account_id VARCHAR(64) NULL,
            account_type VARCHAR(16) NOT NULL DEFAULT 'anonymous',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            revoked_at TIMESTAMP NULL
        );
        CREATE INDEX IF NOT EXISTS ix_server_sessions_expires_at ON "ServerSessions"(expires_at);
        CREATE INDEX IF NOT EXISTS ix_server_sessions_account ON "ServerSessions"(account_id, account_type);
        """,
    ),
    Migration(
        version=10,
        description="Phase 2 Source Registry, Health & Granular Opportunity Pricing Schema Extension",
        sql="""
        CREATE TABLE IF NOT EXISTS "SourceHealth" (
            source_id VARCHAR(128) PRIMARY KEY,
            health_status VARCHAR(32) NOT NULL DEFAULT 'HEALTHY',
            last_attempt TIMESTAMP NULL,
            last_success TIMESTAMP NULL,
            last_failure TIMESTAMP NULL,
            failure_count INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            items_seen INTEGER NOT NULL DEFAULT 0,
            items_created INTEGER NOT NULL DEFAULT 0,
            items_updated INTEGER NOT NULL DEFAULT 0,
            items_rejected INTEGER NOT NULL DEFAULT 0,
            latency REAL NOT NULL DEFAULT 0.0,
            error_class VARCHAR(64) NULL,
            parser_version VARCHAR(32) NOT NULL DEFAULT '1.0.0',
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            details TEXT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_source_health_status ON "SourceHealth"(health_status);
        """,
    ),
    Migration(
        version=11,
        description="Phase 2.1 Idempotent Harvesting & Layered Identity Hardening",
        sql="""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_opportunities_source_ext_id
        ON "Opportunities" (source_id, source_external_id)
        WHERE source_external_id IS NOT NULL AND source_external_id != '';

        CREATE INDEX IF NOT EXISTS ix_opportunities_identity_fingerprint
        ON "Opportunities" (identity_fingerprint);
        """,
    ),
    Migration(
        version=12,
        description="Phase 4 SSR-First Discovery, PostgreSQL Full-Text Search & Saved Opportunities",
        sql="""
        CREATE TABLE IF NOT EXISTS "SavedOpportunities" (
            id VARCHAR(128) PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES "Users"(id) ON DELETE CASCADE,
            opportunity_id VARCHAR(128) NOT NULL REFERENCES "Opportunities"(id) ON DELETE CASCADE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_saved_user_opportunity UNIQUE (user_id, opportunity_id)
        );
        CREATE INDEX IF NOT EXISTS ix_saved_user_id ON "SavedOpportunities" (user_id);
        CREATE INDEX IF NOT EXISTS ix_saved_opp_id ON "SavedOpportunities" (opportunity_id);
        """,
    ),
    Migration(
        version=13,
        description="Phase 5 Intelligent Opportunity Ranking, Personalization & User Preferences",
        sql="""
        CREATE TABLE IF NOT EXISTS "UserPreferences" (
            id VARCHAR(128) PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE REFERENCES "Users"(id) ON DELETE CASCADE,
            skills TEXT DEFAULT '[]',
            interests TEXT DEFAULT '[]',
            preferred_categories TEXT DEFAULT '[]',
            preferred_types TEXT DEFAULT '[]',
            prefers_remote BOOLEAN NULL,
            preferred_location VARCHAR(128) NULL,
            experience_level VARCHAR(64) NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS "UserSearchHistory" (
            id VARCHAR(128) PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES "Users"(id) ON DELETE CASCADE,
            query_text VARCHAR(255) NOT NULL,
            filters_json TEXT DEFAULT '{}',
            searched_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
    ),
    Migration(
        version=14,
        description="Phase 6 Industrial Data Quality, Opportunity Lifecycle, Quarantine & Freshness Intelligence",
        sql="""
        SELECT 1;
        """,
    ),
    Migration(
        version=15,
        description="Phase 7 Intelligent Alerting, Change Detection & User Notification Engine",
        sql="""
        CREATE TABLE IF NOT EXISTS "NotificationOutbox" (
            id VARCHAR(128) PRIMARY KEY,
            user_id INTEGER NOT NULL,
            opportunity_id VARCHAR(128) NOT NULL,
            event_type VARCHAR(32) NOT NULL,
            notification_type VARCHAR(32) NOT NULL DEFAULT 'email',
            delivery_mode VARCHAR(32) NOT NULL DEFAULT 'digest',
            change_fingerprint VARCHAR(64) NOT NULL DEFAULT '',
            deduplication_key VARCHAR(255) NOT NULL UNIQUE,
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            read_at TIMESTAMP NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            last_error TEXT NULL,
            provider_message_id VARCHAR(255) NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            queued_at TIMESTAMP NULL,
            sent_at TIMESTAMP NULL,
            failed_at TIMESTAMP NULL,
            metadata_json TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS ix_notif_outbox_user_id ON "NotificationOutbox"(user_id);
        CREATE INDEX IF NOT EXISTS ix_notif_outbox_opp_id ON "NotificationOutbox"(opportunity_id);
        CREATE INDEX IF NOT EXISTS ix_notif_outbox_status ON "NotificationOutbox"(status);
        CREATE INDEX IF NOT EXISTS ix_notif_outbox_created_at ON "NotificationOutbox"(created_at);
        """,
    ),
    Migration(
        version=16,
        description="Phase 12 Canonical User ID UUID Migration",
        sql="""
        -- Executed via specialized MigrationManager._apply_v16_canonical_user_uuid_migration
        SELECT 1;
        """,
    ),
]


QUALITY_COLUMNS = [
    ("confidence_score", "REAL DEFAULT 0.0"),
    ("quality_score", "REAL DEFAULT 0.0"),
    ("is_rejected", "INTEGER DEFAULT 0"),
    ("rejection_reason", "TEXT DEFAULT ''"),
    ("quality_flags", "TEXT DEFAULT ''"),
    ("topic_score", "REAL DEFAULT 0.0"),
    ("keyword_score", "REAL DEFAULT 0.0"),
    ("spam_score", "REAL DEFAULT 0.0"),
]

PRODUCTION_COLUMNS = [
    ("freshness_score", "REAL DEFAULT 100.0"),
    ("provider_score", "REAL DEFAULT 100.0"),
    ("link_status", "TEXT DEFAULT 'valid'"),
    ("verification_status", "TEXT DEFAULT 'verified'"),
    ("last_verified", "TIMESTAMP"),
    ("expired", "INTEGER DEFAULT 0"),
    ("archived", "INTEGER DEFAULT 0"),
]

PHASE2_SOURCE_COLUMNS = [
    ("canonical_url", "TEXT"),
    ("organization", "VARCHAR(255)"),
    ("country_scope", "VARCHAR(64) DEFAULT 'GLOBAL'"),
    ("language", "VARCHAR(16) DEFAULT 'en'"),
    ("source_family", "VARCHAR(64) DEFAULT 'OTHER'"),
    ("opportunity_types", "TEXT"),
    ("collector_type", "VARCHAR(64) DEFAULT 'rss'"),
    ("access_method", "VARCHAR(64) DEFAULT 'manual_review'"),
    ("trust_tier", "VARCHAR(16) DEFAULT 'TIER_2'"),
    ("requires_auth", "BOOLEAN DEFAULT FALSE"),
    ("rate_limit_policy", "TEXT"),
    ("robots_policy", "VARCHAR(32) DEFAULT 'allow'"),
    ("terms_review_status", "VARCHAR(32) DEFAULT 'pending'"),
    ("parser_version", "VARCHAR(32) DEFAULT '1.0.0'"),
    ("health_status", "VARCHAR(32) DEFAULT 'HEALTHY'"),
    ("last_success_at", "TIMESTAMP"),
    ("last_failure_at", "TIMESTAMP"),
    ("last_checked_at", "TIMESTAMP"),
    ("last_item_count", "INTEGER DEFAULT 0"),
    ("last_new_item_count", "INTEGER DEFAULT 0"),
    ("last_updated_item_count", "INTEGER DEFAULT 0"),
    ("failure_count", "INTEGER DEFAULT 0"),
    ("success_count", "INTEGER DEFAULT 0"),
]

PHASE2_OPPORTUNITY_COLUMNS = [
    ("opportunity_type", "VARCHAR(64)"),
    ("pricing_type", "VARCHAR(32) DEFAULT 'UNKNOWN'"),
    ("price_amount", "REAL"),
    ("application_fee", "REAL"),
    ("certificate_fee", "REAL"),
    ("is_free", "BOOLEAN"),
    ("free_conditions", "TEXT"),
    ("stipend_type", "VARCHAR(32) DEFAULT 'UNKNOWN'"),
    ("stipend_amount", "REAL"),
    ("stipend_currency", "VARCHAR(16)"),
    ("certificate_available", "VARCHAR(16) DEFAULT 'UNKNOWN'"),
    ("certificate_cost", "VARCHAR(16) DEFAULT 'UNKNOWN'"),
    ("eligibility", "TEXT"),
    ("requirements", "TEXT"),
]

PHASE2_1_OPPORTUNITY_COLUMNS = [
    ("source_external_id", "VARCHAR(255)"),
    ("canonical_url", "TEXT"),
    ("identity_fingerprint", "VARCHAR(64)"),
    ("first_seen_at", "TIMESTAMP WITH TIME ZONE"),
    ("last_seen_at", "TIMESTAMP WITH TIME ZONE"),
    ("last_changed_at", "TIMESTAMP WITH TIME ZONE"),
    ("last_harvested_at", "TIMESTAMP WITH TIME ZONE"),
]

PHASE6_OPPORTUNITY_COLUMNS = [
    ("lifecycle_status", "VARCHAR(32) NOT NULL DEFAULT 'active'"),
    ("quality_status", "VARCHAR(32) NOT NULL DEFAULT 'passed'"),
    ("completeness_score", "REAL NOT NULL DEFAULT 1.0"),
    ("quarantine_reason", "TEXT"),
    ("stale_at", "TIMESTAMP WITH TIME ZONE"),
    ("absence_count", "INTEGER NOT NULL DEFAULT 0"),
]

PHASE7_USER_PREFERENCE_COLUMNS = [
    ("email_notifications_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("in_app_notifications_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("notify_new_opportunities", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("notify_meaningful_updates", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("notify_reopened_opportunities", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("delivery_mode", "VARCHAR(32) NOT NULL DEFAULT 'digest'"),
    ("digest_frequency", "VARCHAR(32) NOT NULL DEFAULT 'daily'"),
    ("quiet_hours_enabled", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("quiet_hours_start", "VARCHAR(5) NOT NULL DEFAULT '22:00'"),
    ("quiet_hours_end", "VARCHAR(5) NOT NULL DEFAULT '08:00'"),
    ("timezone", "VARCHAR(64) NOT NULL DEFAULT 'UTC'"),
    ("min_score_threshold", "REAL NOT NULL DEFAULT 0.0"),
]



class MigrationManager:
    """
    Tracks and executes database schema migrations.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def initialize_metadata_tables(self) -> None:
        """
        Ensures that metadata tables required by the migration framework
        (specifically 'schema_version') exist before any migration operations execute.
        """
        sql = """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP NOT NULL,
            description TEXT
        );
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.executescript(sql)
            conn.commit()
        finally:
            cursor.close()

    def get_current_version(self) -> int:
        """Returns highest applied schema version, or 0 if uninitialized."""
        self.initialize_metadata_tables()
        sql = "SELECT MAX(version) as current_version FROM schema_version;"
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            cursor.close()
            if row:
                val = row[0] if not hasattr(row, "get") else row.get("current_version", row[0])
                if val is not None:
                    return int(val)
            return 0
        except Exception:
            return 0

    def _get_existing_columns(self, table_name: str) -> List[str]:
        """Returns list of existing column names in a table."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            if self.db_manager.get_engine().dialect.name == "postgresql":
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND LOWER(table_name) = LOWER(%s);",
                    (table_name,),
                )
                return [r[0] for r in cursor.fetchall()]
            cursor.execute(f"PRAGMA table_info({table_name});")
            return [row[1] for row in cursor.fetchall()]
        except Exception:
            return []
        finally:
            cursor.close()

    def _apply_v3_quality_columns(self) -> None:
        """Safely adds Phase 11.5 quality columns if they don't exist."""
        existing = self._get_existing_columns("Opportunities")
        if not existing:
            return
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            for col_name, col_def in QUALITY_COLUMNS:
                if col_name.lower() not in [c.lower() for c in existing]:
                    cursor.execute(f"ALTER TABLE Opportunities ADD COLUMN {col_name} {col_def};")
                    logger.info(f"Added column '{col_name}' to Opportunities table.")
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to add quality columns: {e}", original_exception=e)
        finally:
            cursor.close()

    def _apply_v4_production_columns(self) -> None:
        """Safely adds Phase 12 production columns if they don't exist."""
        existing = self._get_existing_columns("Opportunities")
        if not existing:
            return
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            for col_name, col_def in PRODUCTION_COLUMNS:
                if col_name.lower() not in [c.lower() for c in existing]:
                    cursor.execute(f"ALTER TABLE Opportunities ADD COLUMN {col_name} {col_def};")
                    logger.info(f"Added column '{col_name}' to Opportunities table.")
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to add production columns: {e}", original_exception=e)
        finally:
            cursor.close()

    def _apply_v10_source_columns(self) -> None:
        """Safely adds Phase 2 Source registry columns if they don't exist."""
        existing = self._get_existing_columns("Sources")
        if not existing:
            return
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            existing_lower = [c.lower() for c in existing]
            for col_name, col_def in PHASE2_SOURCE_COLUMNS:
                if col_name.lower() not in existing_lower:
                    cursor.execute(f'ALTER TABLE "Sources" ADD COLUMN {col_name} {col_def};')
                    logger.info(f"Added column '{col_name}' to Sources table.")
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to add Phase 2 source columns: {e}", original_exception=e)
        finally:
            cursor.close()

    def _apply_v10_opportunity_pricing_columns(self) -> None:
        """Safely adds Phase 2 Opportunity pricing and classification columns if they don't exist."""
        existing = self._get_existing_columns("Opportunities")
        if not existing:
            return
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            existing_lower = [c.lower() for c in existing]
            for col_name, col_def in PHASE2_OPPORTUNITY_COLUMNS:
                if col_name.lower() not in existing_lower:
                    cursor.execute(f'ALTER TABLE "Opportunities" ADD COLUMN {col_name} {col_def};')
                    logger.info(f"Added column '{col_name}' to Opportunities table.")
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to add Phase 2 opportunity columns: {e}", original_exception=e)
        finally:
            cursor.close()

    def _apply_v11_idempotent_columns(self) -> None:
        """Safely adds Phase 2.1 Opportunity identity and harvesting state columns if they don't exist."""
        existing = self._get_existing_columns("Opportunities")
        if not existing:
            return
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            existing_lower = [c.lower() for c in existing]
            for col_name, col_def in PHASE2_1_OPPORTUNITY_COLUMNS:
                if col_name.lower() not in existing_lower:
                    cursor.execute(f'ALTER TABLE "Opportunities" ADD COLUMN {col_name} {col_def};')
                    logger.info(f"Added column '{col_name}' to Opportunities table.")

            # Create partial unique index on (source_id, source_external_id)
            cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_opportunities_source_ext_id
            ON "Opportunities" (source_id, source_external_id)
            WHERE source_external_id IS NOT NULL AND source_external_id != '';
            """)
            # Create index on identity_fingerprint
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_opportunities_identity_fingerprint
            ON "Opportunities" (identity_fingerprint);
            """)

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to apply Phase 2.1 columns/indexes: {e}", original_exception=e)
        finally:
            cursor.close()

    def _apply_v12_fts_and_saved_opportunities(self) -> None:
        """Safely adds Phase 4 PostgreSQL Full-Text Search tsvector column, GIN index, filter indexes, and SavedOpportunities table."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            # 1. Add search_vector generated column to Opportunities if not exists
            existing = self._get_existing_columns("Opportunities")
            existing_lower = [c.lower() for c in existing] if existing else []
            if "search_vector" not in existing_lower:
                try:
                    cursor.execute("""
                    ALTER TABLE "Opportunities" ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (
                        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(company, '') || ' ' || coalesce(provider, '')), 'B') ||
                        setweight(to_tsvector('english', coalesce(category, '') || ' ' || coalesce(opportunity_type, '') || ' ' || coalesce(tags, '')), 'C') ||
                        setweight(to_tsvector('english', coalesce(description, '') || ' ' || coalesce(eligibility, '') || ' ' || coalesce(location, '')), 'D')
                    ) STORED;
                    """)
                    logger.info("Added 'search_vector' generated tsvector column to Opportunities.")
                except Exception as e:
                    logger.warning(f"Notice adding search_vector generated column: {e}")

            # 2. Add GIN index on search_vector
            try:
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS ix_opportunities_search_vector 
                ON "Opportunities" USING GIN (search_vector);
                """)
            except Exception as e:
                logger.warning(f"Notice creating ix_opportunities_search_vector GIN index: {e}")

            # 3. Add B-tree indexes on frequently queried opportunity filter columns
            filter_indexes = [
                ("ix_opportunities_opp_type", 'CREATE INDEX IF NOT EXISTS ix_opportunities_opp_type ON "Opportunities" (opportunity_type);'),
                ("ix_opportunities_remote", 'CREATE INDEX IF NOT EXISTS ix_opportunities_remote ON "Opportunities" (remote);'),
                ("ix_opportunities_is_free", 'CREATE INDEX IF NOT EXISTS ix_opportunities_is_free ON "Opportunities" (is_free);'),
                ("ix_opportunities_pricing_type", 'CREATE INDEX IF NOT EXISTS ix_opportunities_pricing_type ON "Opportunities" (pricing_type);'),
                ("ix_opportunities_source_id", 'CREATE INDEX IF NOT EXISTS ix_opportunities_source_id ON "Opportunities" (source_id);'),
                ("ix_opportunities_difficulty", 'CREATE INDEX IF NOT EXISTS ix_opportunities_difficulty ON "Opportunities" (difficulty);'),
            ]
            for idx_name, idx_sql in filter_indexes:
                try:
                    cursor.execute(idx_sql)
                except Exception as ie:
                    logger.warning(f"Notice creating filter index {idx_name}: {ie}")

            # 4. Create SavedOpportunities table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS "SavedOpportunities" (
                id VARCHAR(128) PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES "Users"(id) ON DELETE CASCADE,
                opportunity_id VARCHAR(128) NOT NULL REFERENCES "Opportunities"(id) ON DELETE CASCADE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_saved_user_opportunity UNIQUE (user_id, opportunity_id)
            );
            CREATE INDEX IF NOT EXISTS ix_saved_user_id ON "SavedOpportunities" (user_id);
            CREATE INDEX IF NOT EXISTS ix_saved_opp_id ON "SavedOpportunities" (opportunity_id);
            """)

            conn.commit()
            logger.info("Successfully applied Phase 4 FTS, indexes, and SavedOpportunities table.")
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to apply Phase 4 FTS and SavedOpportunities schema: {e}", original_exception=e)
        finally:
            cursor.close()

    def _apply_v13_user_preferences_and_history(self) -> None:
        """Safely creates UserPreferences and UserSearchHistory tables for Phase 5 personalization with RLS."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            # 1. Create UserPreferences table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS "UserPreferences" (
                id VARCHAR(128) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                user_id INTEGER NOT NULL UNIQUE REFERENCES "Users"(id) ON DELETE CASCADE,
                skills TEXT DEFAULT '[]',
                interests TEXT DEFAULT '[]',
                preferred_categories TEXT DEFAULT '[]',
                preferred_types TEXT DEFAULT '[]',
                prefers_remote BOOLEAN NULL,
                preferred_location VARCHAR(128) NULL,
                experience_level VARCHAR(64) NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS ix_user_preferences_user_id ON "UserPreferences" (user_id);
            """)

            # 2. Create UserSearchHistory table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS "UserSearchHistory" (
                id VARCHAR(128) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                user_id INTEGER NOT NULL REFERENCES "Users"(id) ON DELETE CASCADE,
                query_text VARCHAR(255) NOT NULL,
                filters_json TEXT DEFAULT '{}',
                searched_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS ix_user_search_history_user_id ON "UserSearchHistory" (user_id);
            """)

            # 3. Enable and FORCE RLS
            for tbl in ['"UserPreferences"', '"UserSearchHistory"']:
                try:
                    cursor.execute(f'ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;')
                    cursor.execute(f'ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;')
                except Exception as rls_e:
                    logger.warning(f"Notice enabling RLS on {tbl}: {rls_e}")

            # 4. Create base policies
            policies = [
                ('UserPreferences', 'userpreferences_policy', 'CREATE POLICY userpreferences_policy ON "UserPreferences" FOR ALL USING (true) WITH CHECK (true);'),
                ('UserSearchHistory', 'usersearchhistory_policy', 'CREATE POLICY usersearchhistory_policy ON "UserSearchHistory" FOR ALL USING (true) WITH CHECK (true);')
            ]
            for tablename, policyname, sql in policies:
                try:
                    cursor.execute("""
                        SELECT 1 FROM pg_policies 
                        WHERE LOWER(tablename) = LOWER(%s) AND LOWER(policyname) = LOWER(%s);
                    """, (tablename, policyname))
                    if not cursor.fetchone():
                        cursor.execute(sql)
                except Exception as pe:
                    logger.warning(f"Notice on policy {tablename}.{policyname}: {pe}")

            conn.commit()
            logger.info("Successfully applied Phase 5 UserPreferences and UserSearchHistory schema with RLS.")
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to apply Phase 5 personalization schema: {e}", original_exception=e)
        finally:
            cursor.close()

    def _apply_v14_data_quality_and_lifecycle(self) -> None:
        """Applies Phase 6 Data Quality, Lifecycle, Quarantine & Freshness columns and indexes."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            # 1. Add columns to Opportunities if not present
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND LOWER(table_name) = 'opportunities';"
            )
            existing_cols = {row[0].lower() for row in cursor.fetchall()}

            for col_name, col_type in PHASE6_OPPORTUNITY_COLUMNS:
                if col_name.lower() not in existing_cols:
                    try:
                        cursor.execute(f'ALTER TABLE "Opportunities" ADD COLUMN {col_name} {col_type};')
                        logger.info(f"Added column {col_name} to Opportunities.")
                    except Exception as ce:
                        logger.warning(f"Notice adding column {col_name}: {ce}")

            # 2. Add B-tree indexes
            indexes = [
                ("ix_opportunities_lifecycle_status", 'CREATE INDEX IF NOT EXISTS ix_opportunities_lifecycle_status ON "Opportunities" (lifecycle_status);'),
                ("ix_opportunities_quality_status", 'CREATE INDEX IF NOT EXISTS ix_opportunities_quality_status ON "Opportunities" (quality_status);'),
                ("ix_opportunities_last_harvested", 'CREATE INDEX IF NOT EXISTS ix_opportunities_last_harvested ON "Opportunities" (last_harvested_at);'),
            ]
            for idx_name, idx_sql in indexes:
                try:
                    cursor.execute(idx_sql)
                except Exception as ie:
                    logger.warning(f"Notice creating index {idx_name}: {ie}")

            # 3. Synchronize lifecycle_status with existing deadlines and status
            try:
                cursor.execute("""
                    UPDATE "Opportunities"
                    SET lifecycle_status = 'expired'
                    WHERE (deadline < CURRENT_DATE OR status = 'expired')
                      AND lifecycle_status = 'active';
                """)
                cursor.execute("""
                    UPDATE "Opportunities"
                    SET lifecycle_status = 'closing_soon'
                    WHERE deadline >= CURRENT_DATE 
                      AND deadline <= (CURRENT_DATE + INTERVAL '3 days')
                      AND lifecycle_status = 'active';
                """)
            except Exception as se:
                logger.warning(f"Notice synchronizing lifecycle status: {se}")

            conn.commit()
            logger.info("Successfully applied Phase 6 data quality, lifecycle, and freshness schema extension.")
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to apply Phase 6 schema extension: {e}", original_exception=e)
        finally:
            cursor.close()

    def _apply_v15_notification_outbox_and_preferences(self) -> None:
        """Applies Phase 7 NotificationOutbox table, UserPreferences extension, indexes and RLS."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            # 1. Create NotificationOutbox table if not exists
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS "NotificationOutbox" (
                id VARCHAR(128) PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES "Users"(id) ON DELETE CASCADE,
                opportunity_id VARCHAR(128) NOT NULL REFERENCES "Opportunities"(id) ON DELETE CASCADE,
                event_type VARCHAR(32) NOT NULL,
                notification_type VARCHAR(32) NOT NULL DEFAULT 'email',
                delivery_mode VARCHAR(32) NOT NULL DEFAULT 'digest',
                change_fingerprint VARCHAR(64) NOT NULL DEFAULT '',
                deduplication_key VARCHAR(255) NOT NULL UNIQUE,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                is_read BOOLEAN NOT NULL DEFAULT FALSE,
                read_at TIMESTAMP WITH TIME ZONE NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                last_error TEXT NULL,
                provider_message_id VARCHAR(255) NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                queued_at TIMESTAMP WITH TIME ZONE NULL,
                sent_at TIMESTAMP WITH TIME ZONE NULL,
                failed_at TIMESTAMP WITH TIME ZONE NULL,
                metadata_json TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS ix_notif_outbox_user_id ON "NotificationOutbox"(user_id);
            CREATE INDEX IF NOT EXISTS ix_notif_outbox_opp_id ON "NotificationOutbox"(opportunity_id);
            CREATE INDEX IF NOT EXISTS ix_notif_outbox_status ON "NotificationOutbox"(status);
            CREATE INDEX IF NOT EXISTS ix_notif_outbox_created_at ON "NotificationOutbox"(created_at);
            CREATE INDEX IF NOT EXISTS ix_notif_outbox_pending ON "NotificationOutbox"(status, delivery_mode) WHERE status = 'pending';
            """)

            # 2. Add Phase 7 columns to UserPreferences
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND LOWER(table_name) = 'userpreferences';"
            )
            existing_cols = {row[0].lower() for row in cursor.fetchall()}

            for col_name, col_type in PHASE7_USER_PREFERENCE_COLUMNS:
                if col_name.lower() not in existing_cols:
                    try:
                        cursor.execute(f'ALTER TABLE "UserPreferences" ADD COLUMN {col_name} {col_type};')
                        logger.info(f"Added column {col_name} to UserPreferences.")
                    except Exception as ce:
                        logger.warning(f"Notice adding column {col_name} to UserPreferences: {ce}")

            # 3. Enable and FORCE RLS on NotificationOutbox
            try:
                cursor.execute('ALTER TABLE "NotificationOutbox" ENABLE ROW LEVEL SECURITY;')
                cursor.execute('ALTER TABLE "NotificationOutbox" FORCE ROW LEVEL SECURITY;')
            except Exception as rls_e:
                logger.warning(f"Notice enabling RLS on NotificationOutbox: {rls_e}")

            # 4. Create base RLS policy
            try:
                cursor.execute("""
                    SELECT 1 FROM pg_policies 
                    WHERE LOWER(tablename) = 'notificationoutbox' AND LOWER(policyname) = 'notification_outbox_policy';
                """)
                if not cursor.fetchone():
                    cursor.execute('CREATE POLICY notification_outbox_policy ON "NotificationOutbox" FOR ALL USING (true) WITH CHECK (true);')
            except Exception as pe:
                logger.warning(f"Notice on policy notification_outbox_policy: {pe}")

            conn.commit()
            logger.info("Successfully applied Phase 7 NotificationOutbox and UserPreferences schema with RLS.")
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to apply Phase 7 notification outbox schema: {e}", original_exception=e)
        finally:
            cursor.close()

    def _apply_v16_canonical_user_uuid_migration(self) -> None:
        """
        Phase 12 Canonical User ID UUID Migration.
        Migrates Users.id from integer sequence to native PostgreSQL UUID (gen_random_uuid()).
        Migrates all referencing foreign keys across SavedOpportunities, UserPreferences,
        UserSearchHistory, NotificationOutbox, and AuditLogs without data loss.
        Re-establishes all indexes, constraints, and Row Level Security (RLS) policies.
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            # Check if Users.id is already UUID
            cursor.execute("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                  AND table_name = 'Users' 
                  AND column_name = 'id';
            """)
            col_info = cursor.fetchone()
            if col_info and col_info[0].lower() == "uuid":
                logger.info("Users.id is already of type UUID. Migration v16 is already satisfied.")
                return

            logger.info("Executing Phase 12 Canonical User ID UUID Migration transaction...")

            # 1. Add temporary uuid_id to Users and generate unique UUIDs for all existing records
            cursor.execute("""
                ALTER TABLE "Users" ADD COLUMN IF NOT EXISTS uuid_id UUID DEFAULT gen_random_uuid();
                UPDATE "Users" SET uuid_id = gen_random_uuid() WHERE uuid_id IS NULL;
                ALTER TABLE "Users" ALTER COLUMN uuid_id SET NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS uq_users_uuid_id ON "Users"(uuid_id);
            """)

            # 2. Add temporary user_uuid columns to referencing tables
            cursor.execute("""
                ALTER TABLE "SavedOpportunities" ADD COLUMN IF NOT EXISTS user_uuid UUID;
                ALTER TABLE "UserPreferences" ADD COLUMN IF NOT EXISTS user_uuid UUID;
                ALTER TABLE "UserSearchHistory" ADD COLUMN IF NOT EXISTS user_uuid UUID;
                ALTER TABLE "NotificationOutbox" ADD COLUMN IF NOT EXISTS user_uuid UUID;
                ALTER TABLE "AuditLogs" ADD COLUMN IF NOT EXISTS user_uuid UUID;
            """)

            # 3. Backfill dependent tables using old integer user_id mapping to Users.uuid_id
            cursor.execute("""
                UPDATE "SavedOpportunities" s 
                SET user_uuid = u.uuid_id 
                FROM "Users" u 
                WHERE s.user_id = u.id AND s.user_uuid IS NULL;

                UPDATE "UserPreferences" p 
                SET user_uuid = u.uuid_id 
                FROM "Users" u 
                WHERE p.user_id = u.id AND p.user_uuid IS NULL;

                UPDATE "UserSearchHistory" h 
                SET user_uuid = u.uuid_id 
                FROM "Users" u 
                WHERE h.user_id = u.id AND h.user_uuid IS NULL;

                UPDATE "NotificationOutbox" n 
                SET user_uuid = u.uuid_id 
                FROM "Users" u 
                WHERE n.user_id = u.id AND n.user_uuid IS NULL;

                UPDATE "AuditLogs" a 
                SET user_uuid = u.uuid_id 
                FROM "Users" u 
                WHERE a.user_id = u.id AND a.user_uuid IS NULL;
            """)

            # 4. Data verification checkpoint: ensure zero NULLs for tables where user_id was NOT NULL
            for tbl in ["SavedOpportunities", "UserPreferences", "UserSearchHistory", "NotificationOutbox"]:
                cursor.execute(f'SELECT COUNT(*) FROM "{tbl}" WHERE user_uuid IS NULL;')
                missing = cursor.fetchone()[0]
                if missing > 0:
                    raise MigrationError(f"Critical data integrity failure: {missing} records in {tbl} have NULL user_uuid after backfill!")

            # 5. Drop existing foreign key constraints on referencing tables
            fk_drops = [
                ('SavedOpportunities', 'SavedOpportunities_user_id_fkey'),
                ('UserPreferences', 'UserPreferences_user_id_fkey'),
                ('UserSearchHistory', 'UserSearchHistory_user_id_fkey'),
                ('NotificationOutbox', 'NotificationOutbox_user_id_fkey'),
                ('AuditLogs', 'fk_auditlogs_user_id'),
            ]
            for tbl, fk_name in fk_drops:
                cursor.execute(f"""
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = '{fk_name}') THEN
                            ALTER TABLE "{tbl}" DROP CONSTRAINT "{fk_name}";
                        END IF;
                    END $$;
                """)

            # 6. Drop old integer user_id columns and promote user_uuid -> user_id
            cursor.execute("""
                -- SavedOpportunities
                ALTER TABLE "SavedOpportunities" DROP CONSTRAINT IF EXISTS uq_saved_user_opportunity;
                ALTER TABLE "SavedOpportunities" DROP COLUMN user_id;
                ALTER TABLE "SavedOpportunities" RENAME COLUMN user_uuid TO user_id;
                ALTER TABLE "SavedOpportunities" ALTER COLUMN user_id SET NOT NULL;
                ALTER TABLE "SavedOpportunities" ADD CONSTRAINT uq_saved_user_opportunity UNIQUE (user_id, opportunity_id);

                -- UserPreferences
                ALTER TABLE "UserPreferences" DROP CONSTRAINT IF EXISTS "UserPreferences_user_id_key";
                ALTER TABLE "UserPreferences" DROP COLUMN user_id;
                ALTER TABLE "UserPreferences" RENAME COLUMN user_uuid TO user_id;
                ALTER TABLE "UserPreferences" ALTER COLUMN user_id SET NOT NULL;
                ALTER TABLE "UserPreferences" ADD CONSTRAINT uq_user_preferences_user_id UNIQUE (user_id);

                -- UserSearchHistory
                ALTER TABLE "UserSearchHistory" DROP COLUMN user_id;
                ALTER TABLE "UserSearchHistory" RENAME COLUMN user_uuid TO user_id;
                ALTER TABLE "UserSearchHistory" ALTER COLUMN user_id SET NOT NULL;

                -- NotificationOutbox
                ALTER TABLE "NotificationOutbox" DROP COLUMN user_id;
                ALTER TABLE "NotificationOutbox" RENAME COLUMN user_uuid TO user_id;
                ALTER TABLE "NotificationOutbox" ALTER COLUMN user_id SET NOT NULL;

                -- AuditLogs
                ALTER TABLE "AuditLogs" DROP COLUMN user_id;
                ALTER TABLE "AuditLogs" RENAME COLUMN user_uuid TO user_id;
            """)

            # 7. Migrate Users primary key: drop old integer PK, drop column id, rename uuid_id -> id
            cursor.execute("""
                ALTER TABLE "Users" DROP CONSTRAINT "Users_pkey";
                ALTER TABLE "Users" DROP COLUMN id;
                ALTER TABLE "Users" RENAME COLUMN uuid_id TO id;
                ALTER TABLE "Users" ALTER COLUMN id SET DEFAULT gen_random_uuid();
                ALTER TABLE "Users" ADD CONSTRAINT "Users_pkey" PRIMARY KEY (id);
                DROP INDEX IF EXISTS uq_users_uuid_id;
            """)

            # 8. Re-establish foreign keys referencing Users(id) [UUID]
            cursor.execute("""
                ALTER TABLE "SavedOpportunities"
                    ADD CONSTRAINT "SavedOpportunities_user_id_fkey"
                    FOREIGN KEY (user_id) REFERENCES "Users"(id) ON DELETE CASCADE;

                ALTER TABLE "UserPreferences"
                    ADD CONSTRAINT "UserPreferences_user_id_fkey"
                    FOREIGN KEY (user_id) REFERENCES "Users"(id) ON DELETE CASCADE;

                ALTER TABLE "UserSearchHistory"
                    ADD CONSTRAINT "UserSearchHistory_user_id_fkey"
                    FOREIGN KEY (user_id) REFERENCES "Users"(id) ON DELETE CASCADE;

                ALTER TABLE "NotificationOutbox"
                    ADD CONSTRAINT "NotificationOutbox_user_id_fkey"
                    FOREIGN KEY (user_id) REFERENCES "Users"(id) ON DELETE CASCADE;

                ALTER TABLE "AuditLogs"
                    ADD CONSTRAINT "fk_auditlogs_user_id"
                    FOREIGN KEY (user_id) REFERENCES "Users"(id) ON DELETE SET NULL;
            """)

            # 9. Recreate indexes on user_id columns
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS ix_saved_user_id ON "SavedOpportunities" (user_id);
                CREATE INDEX IF NOT EXISTS ix_user_preferences_user_id ON "UserPreferences" (user_id);
                CREATE INDEX IF NOT EXISTS ix_user_search_history_user_id ON "UserSearchHistory" (user_id);
                CREATE INDEX IF NOT EXISTS ix_notif_outbox_user_id ON "NotificationOutbox" (user_id);
                CREATE INDEX IF NOT EXISTS ix_auditlogs_user_id ON "AuditLogs" (user_id);
            """)

            # 10. Re-verify Row Level Security (RLS)
            for tbl in ['"Users"', '"SavedOpportunities"', '"UserPreferences"', '"UserSearchHistory"', '"NotificationOutbox"', '"AuditLogs"']:
                try:
                    cursor.execute(f'ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;')
                    cursor.execute(f'ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;')
                except Exception as rls_err:
                    logger.warning(f"RLS re-enable notice for {tbl}: {rls_err}")

            conn.commit()
            logger.info("Phase 12 Canonical User ID UUID Migration successfully executed and committed.")
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to execute Phase 12 UUID migration: {e}", original_exception=e)
        finally:
            cursor.close()

    def apply_migrations(self) -> int:
        """
        Applies any pending migrations in sequential order.

        Returns:
            Number of newly applied migrations.
        """
        if self.db_manager.get_engine().dialect.name == "postgresql":
            self.initialize_metadata_tables()
            current_version = self.get_current_version()
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            applied_count = 0
            try:
                if current_version < 4:
                    for v, desc in [
                        (1, "Baseline PostgreSQL Schema"),
                        (2, "Knowledge Base & Source Registry"),
                        (3, "Opportunity Quality & Verification"),
                        (4, "Production Architecture & Audit Logs"),
                    ]:
                        cursor.execute(
                            "INSERT INTO schema_version (version, applied_at, description) VALUES (%s, NOW(), %s) ON CONFLICT (version) DO NOTHING;",
                            (v, desc),
                        )
                    conn.commit()

                # Safely apply v10 on PostgreSQL if needed
                self._apply_v10_source_columns()
                self._apply_v10_opportunity_pricing_columns()

                # Ensure SourceHealth table exists
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS "SourceHealth" (
                    source_id VARCHAR(128) PRIMARY KEY,
                    health_status VARCHAR(32) NOT NULL DEFAULT 'HEALTHY',
                    last_attempt TIMESTAMP NULL,
                    last_success TIMESTAMP NULL,
                    last_failure TIMESTAMP NULL,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    items_seen INTEGER NOT NULL DEFAULT 0,
                    items_created INTEGER NOT NULL DEFAULT 0,
                    items_updated INTEGER NOT NULL DEFAULT 0,
                    items_rejected INTEGER NOT NULL DEFAULT 0,
                    latency REAL NOT NULL DEFAULT 0.0,
                    error_class VARCHAR(64) NULL,
                    parser_version VARCHAR(32) NOT NULL DEFAULT '1.0.0',
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    details TEXT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_source_health_status ON "SourceHealth"(health_status);
                """)
                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at, description) VALUES (%s, NOW(), %s) ON CONFLICT (version) DO NOTHING;",
                    (10, "Phase 2 Source Registry, Health & Granular Opportunity Pricing Schema Extension"),
                )
                conn.commit()

                # Safely apply v11 on PostgreSQL
                self._apply_v11_idempotent_columns()
                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at, description) VALUES (%s, NOW(), %s) ON CONFLICT (version) DO NOTHING;",
                    (11, "Phase 2.1 Idempotent Harvesting & Layered Identity Hardening"),
                )
                conn.commit()

                # Safely apply v12 on PostgreSQL (FTS, GIN, Facet Indexes, SavedOpportunities)
                self._apply_v12_fts_and_saved_opportunities()
                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at, description) VALUES (%s, NOW(), %s) ON CONFLICT (version) DO NOTHING;",
                    (12, "Phase 4 SSR-First Discovery, PostgreSQL Full-Text Search & Saved Opportunities"),
                )
                conn.commit()

                # Safely apply v13 on PostgreSQL (Personalization, UserPreferences, UserSearchHistory)
                self._apply_v13_user_preferences_and_history()
                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at, description) VALUES (%s, NOW(), %s) ON CONFLICT (version) DO NOTHING;",
                    (13, "Phase 5 Intelligent Opportunity Ranking, Personalization & User Preferences"),
                )
                conn.commit()

                # Safely apply v14 on PostgreSQL (Phase 6 Data Quality, Lifecycle, Quarantine & Freshness)
                self._apply_v14_data_quality_and_lifecycle()
                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at, description) VALUES (%s, NOW(), %s) ON CONFLICT (version) DO NOTHING;",
                    (14, "Phase 6 Industrial Data Quality, Opportunity Lifecycle, Quarantine & Freshness Intelligence"),
                )
                conn.commit()

                # Safely apply v15 on PostgreSQL (Phase 7 Notification Outbox, UserPreferences notification columns, RLS)
                self._apply_v15_notification_outbox_and_preferences()
                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at, description) VALUES (%s, NOW(), %s) ON CONFLICT (version) DO NOTHING;",
                    (15, "Phase 7 Intelligent Alerting, Change Detection & User Notification Engine"),
                )
                conn.commit()

                # Safely apply v16 on PostgreSQL (Phase 12 Canonical User ID UUID Migration)
                if current_version < 16:
                    self._apply_v16_canonical_user_uuid_migration()
                    cursor.execute(
                        "INSERT INTO schema_version (version, applied_at, description) VALUES (%s, NOW(), %s) ON CONFLICT (version) DO NOTHING;",
                        (16, "Phase 12 Canonical User ID UUID Migration"),
                    )
                    conn.commit()
                    applied_count += 1
            finally:
                cursor.close()
            return applied_count

        conn = self.db_manager.get_connection()
        self.initialize_metadata_tables()
        current_version = self.get_current_version()
        applied_count = 0

        for migration in MIGRATIONS:
            if migration.version > current_version:
                logger.info(f"Applying migration v{migration.version}: {migration.description}...")
                try:
                    now = datetime.now(timezone.utc).isoformat()

                    if migration.version == 3:
                        self._apply_v3_quality_columns()
                    elif migration.version == 4:
                        self._apply_v4_production_columns()
                    elif migration.version == 10:
                        self._apply_v10_source_columns()
                        self._apply_v10_opportunity_pricing_columns()
                    elif migration.version == 14:
                        for col_name, col_type in PHASE6_OPPORTUNITY_COLUMNS:
                            try:
                                with self.db_manager.transaction() as cur:
                                    cur.execute(f'ALTER TABLE Opportunities ADD COLUMN {col_name} {col_type};')
                            except Exception:
                                pass
                    elif migration.version == 15:
                        for col_name, col_type in PHASE7_USER_PREFERENCE_COLUMNS:
                            try:
                                with self.db_manager.transaction() as cur:
                                    cur.execute(f'ALTER TABLE UserPreferences ADD COLUMN {col_name} {col_type};')
                            except Exception:
                                pass

                    with self.db_manager.transaction() as cursor:
                        cursor.executescript(migration.sql)
                        cursor.execute(
                            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?);",
                            (migration.version, now, migration.description),
                        )
                    applied_count += 1
                except Exception as e:
                    raise MigrationError(f"Migration v{migration.version} failed: {e}", original_exception=e)

        return applied_count


if __name__ == "__main__":
    import sys
    mgr = MigrationManager()
    try:
        count = mgr.apply_migrations()
        ver = mgr.get_current_version()
        print(f"PostgreSQL migrations completed successfully. Applied: {count} migration(s). Current schema version: {ver}")
        sys.exit(0)
    except Exception as exc:
        print(f"Migration execution failed: {exc}", file=sys.stderr)
        sys.exit(1)

