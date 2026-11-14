"""
Promotion Repository for CyberScout AI (Phase F).

Manages transactional candidate promotion into production Opportunities,
schema synchronization for promotion status columns, deduplication lookups,
and persistent daily report delivery tracking.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.core.exceptions import DatabaseError, RepositoryError
from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.discovery.discovery_models import DiscoveredCandidate
from src.discovery.promotion_models import DailyReportMetadata, EmailDeliveryRecord, PromotionStatus
from src.models.opportunity import Opportunity

logger = get_logger(__name__)

DDL_DAILY_REPORT_DELIVERY = """
CREATE TABLE IF NOT EXISTS "DailyReportDelivery" (
    id VARCHAR(64) PRIMARY KEY,
    report_date DATE NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    report_identifier VARCHAR(100) UNIQUE NOT NULL,
    opportunity_ids TEXT,
    attachment_path TEXT,
    attachment_checksum VARCHAR(64),
    delivery_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    attempt_count INT DEFAULT 0,
    max_attempts INT DEFAULT 3,
    provider_message_id VARCHAR(255),
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    delivered_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS "ix_daily_report_delivery_date" ON "DailyReportDelivery" ("report_date");
CREATE UNIQUE INDEX IF NOT EXISTS "uq_daily_report_date_recipient" ON "DailyReportDelivery" ("report_date", "recipient");
"""


class PromotionRepository:
    """
    DAO handling atomic transactional promotion of verified DiscoveredCandidates
    into production Opportunities, and tracking daily report delivery idempotency.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        opp_repo: Optional[OpportunityRepository] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.opp_repo = opp_repo or OpportunityRepository(db_manager=self.db_manager)
        self._schema_ensured = False

    def ensure_schema(self) -> bool:
        """
        Idempotently adds promotion tracking columns to DiscoveredCandidates
        and creates DailyReportDelivery table if not present.
        """
        if self._schema_ensured:
            return True

        try:
            with self.db_manager.transaction() as cursor:
                # 1. Non-destructive columns on DiscoveredCandidates
                if self.db_manager.get_engine().dialect.name == "postgresql":
                    cursor.execute(
                        'ALTER TABLE "DiscoveredCandidates" ADD COLUMN IF NOT EXISTS promoted_to_opportunity_id VARCHAR(64);'
                    )
                    cursor.execute(
                        'ALTER TABLE "DiscoveredCandidates" ADD COLUMN IF NOT EXISTS promoted_at TIMESTAMP WITH TIME ZONE;'
                    )
                    cursor.execute(
                        'ALTER TABLE "DiscoveredCandidates" ADD COLUMN IF NOT EXISTS promotion_status VARCHAR(32) DEFAULT \'unpromoted\';'
                    )
                    # 2. DailyReportDelivery table
                    cursor.execute(DDL_DAILY_REPORT_DELIVERY)
                else:
                    # SQLite test fallback
                    cursor.execute(
                        "CREATE TABLE IF NOT EXISTS DailyReportDelivery ("
                        "id TEXT PRIMARY KEY, report_date TEXT NOT NULL, recipient TEXT NOT NULL, "
                        "report_identifier TEXT UNIQUE NOT NULL, opportunity_ids TEXT, attachment_path TEXT, "
                        "attachment_checksum TEXT, delivery_status TEXT DEFAULT 'pending', "
                        "attempt_count INT DEFAULT 0, max_attempts INT DEFAULT 3, provider_message_id TEXT, "
                        "last_error TEXT, created_at TEXT, delivered_at TEXT);"
                    )
            self._schema_ensured = True
            logger.debug("Promotion schema and DailyReportDelivery verified.")
            return True
        except Exception as e:
            logger.warning(f"Could not verify promotion schema: {e}")
            return False

    def get_approved_candidates_for_promotion(
        self,
        run_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Queries staged candidates in DiscoveredCandidates that have passed Phase E Free-Only gate
        and are pending production promotion.
        """
        self.ensure_schema()
        limit_val = max(1, min(limit, 200))

        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            if run_id:
                sql = """
                SELECT * FROM "DiscoveredCandidates"
                WHERE free_only_decision = 'APPROVED'
                  AND pricing_verification_status = 'VERIFIED_FREE'
                  AND (promotion_status IS NULL OR promotion_status = 'unpromoted')
                  AND (promoted_to_opportunity_id IS NULL OR promoted_to_opportunity_id = '')
                  AND discovery_run_id = %s
                ORDER BY score DESC, discovered_at ASC
                LIMIT %s;
                """
                cursor.execute(sql, (run_id, limit_val))
            else:
                sql = """
                SELECT * FROM "DiscoveredCandidates"
                WHERE free_only_decision = 'APPROVED'
                  AND pricing_verification_status = 'VERIFIED_FREE'
                  AND (promotion_status IS NULL OR promotion_status = 'unpromoted')
                  AND (promoted_to_opportunity_id IS NULL OR promoted_to_opportunity_id = '')
                ORDER BY score DESC, discovered_at ASC
                LIMIT %s;
                """
                cursor.execute(sql, (limit_val,))

            cols = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(cols, row)) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching approved candidates for promotion: {e}")
            return []
        finally:
            cursor.close()

    def get_existing_production_opportunities(self, limit: int = 500) -> List[Opportunity]:
        """Fetches active production opportunities for deduplication matching."""
        try:
            return self.opp_repo.get_active_opportunities(limit=limit)
        except Exception as e:
            logger.error(f"Error fetching existing production opportunities: {e}")
            return []

    def promote_candidate_transactional(
        self,
        candidate_id: str,
        opportunity: Opportunity,
        is_update: bool = False,
        update_fields: Optional[List[str]] = None,
    ) -> str:
        """
        Atomically executes production promotion inside a single database transaction:
        1. Inserts new Opportunity into Opportunities OR updates existing Opportunity fields.
        2. Updates DiscoveredCandidates staging record with promoted_to_opportunity_id,
           promoted_at, and promotion_status.
        If either fails, the entire transaction rolls back cleanly.

        Args:
            candidate_id: Primary key of DiscoveredCandidate.
            opportunity: Opportunity entity to persist.
            is_update: True if updating an existing record, False if new insertion.
            update_fields: Specific field names to update if is_update=True.

        Returns:
            opportunity_id string on success.
        """
        self.ensure_schema()
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.db_manager.transaction() as cursor:
            # Step 1: Insert or Update Opportunities table
            if not is_update:
                # New Opportunity insert
                opp_dict = self.opp_repo._entity_to_dict(opportunity)
                # Check actual columns in Opportunities table to prevent missing column errors
                available_cols = self.opp_repo._get_table_columns()
                if available_cols:
                    filtered_dict = {k: v for k, v in opp_dict.items() if k.lower() in available_cols}
                else:
                    filtered_dict = opp_dict

                cols = list(filtered_dict.keys())
                placeholders = ["%s" if self.db_manager.get_engine().dialect.name == "postgresql" else "?" for _ in cols]
                col_names_joined = ", ".join([f'"{c}"' if c in ("id", "user_id") else c for c in cols])
                sql_opp = f'INSERT INTO "Opportunities" ({col_names_joined}) VALUES ({", ".join(placeholders)});'
                cursor.execute(sql_opp, tuple(filtered_dict.values()))
            else:
                # Existing Opportunity update (only changed fields, preserving first_seen_at and id)
                update_items = update_fields or ["last_seen_at", "last_harvested_at"]
                if "last_seen_at" not in update_items:
                    update_items.append("last_seen_at")
                if "last_harvested_at" not in update_items:
                    update_items.append("last_harvested_at")

                opp_dict = self.opp_repo._entity_to_dict(opportunity)
                available_cols = self.opp_repo._get_table_columns()
                valid_updates = [k for k in update_items if not available_cols or k.lower() in available_cols]

                if valid_updates:
                    ph = "%s" if self.db_manager.get_engine().dialect.name == "postgresql" else "?"
                    set_clause = ", ".join([f'"{k}" = {ph}' if k in ("id", "user_id") else f"{k} = {ph}" for k in valid_updates])
                    sql_upd = f'UPDATE "Opportunities" SET {set_clause} WHERE id = {ph};'
                    params = [opp_dict.get(k) for k in valid_updates] + [opportunity.id]
                    cursor.execute(sql_upd, tuple(params))

            # Step 2: Update candidate record in DiscoveredCandidates staging table
            new_status = PromotionStatus.UPDATED.value if is_update else PromotionStatus.PROMOTED.value
            ph = "%s" if self.db_manager.get_engine().dialect.name == "postgresql" else "?"
            sql_cand = f"""
            UPDATE "DiscoveredCandidates" SET
                promoted_to_opportunity_id = {ph},
                promoted_at = CURRENT_TIMESTAMP,
                promotion_status = {ph},
                processing_status = 'promoted'
            WHERE id = {ph};
            """
            cursor.execute(sql_cand, (opportunity.id, new_status, candidate_id))

        logger.info(
            f"Successfully promoted candidate '{candidate_id}' -> Opportunity '{opportunity.id}' "
            f"({'UPDATED' if is_update else 'PROMOTED'})."
        )
        return opportunity.id

    def mark_candidate_promotion_status(
        self,
        candidate_id: str,
        status: PromotionStatus,
        reason: str = "",
    ) -> None:
        """Updates candidate record with non-promoted status (e.g. SKIPPED, BLOCKED)."""
        self.ensure_schema()
        ph = "%s" if self.db_manager.get_engine().dialect.name == "postgresql" else "?"
        sql = f"""
        UPDATE "DiscoveredCandidates" SET
            promotion_status = {ph},
            processing_status = {ph}
        WHERE id = {ph};
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (status.value, status.value, candidate_id))
        except Exception as e:
            logger.warning(f"Could not update candidate '{candidate_id}' status: {e}")

    def get_daily_summary_counts(
        self,
        report_date: str,
        run_id: Optional[str] = None,
        strict: bool = False,
    ) -> DailyReportMetadata:
        """Compiles discovery, extraction, classification, verification, and promotion metrics."""
        if not self.ensure_schema() and strict:
            raise RepositoryError("Could not verify the daily summary schema.")
        metadata = DailyReportMetadata(report_date=report_date)

        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            # Total active opportunities
            cursor.execute('SELECT COUNT(*) FROM "Opportunities" WHERE status = \'active\';')
            row = cursor.fetchone()
            metadata.total_active_production = row[0] if row else 0

            # DiscoveredCandidates metrics
            filter_clause = "WHERE DATE(discovered_at) = %s" if self.db_manager.get_engine().dialect.name == "postgresql" else "WHERE substr(discovered_at, 1, 10) = ?"
            params: Tuple[Any, ...] = (report_date,)
            if run_id:
                filter_clause = "WHERE discovery_run_id = %s" if self.db_manager.get_engine().dialect.name == "postgresql" else "WHERE discovery_run_id = ?"
                params = (run_id,)

            cursor.execute(f'SELECT COUNT(*) FROM "DiscoveredCandidates" {filter_clause};', params)
            metadata.total_discovered = (cursor.fetchone() or [0])[0]

            cursor.execute(f'SELECT COUNT(*) FROM "DiscoveredCandidates" {filter_clause} AND extraction_status = \'completed\';', params)
            metadata.total_extracted = (cursor.fetchone() or [0])[0]

            cursor.execute(f'SELECT COUNT(*) FROM "DiscoveredCandidates" {filter_clause} AND classification_status = \'success\';', params)
            metadata.total_classified = (cursor.fetchone() or [0])[0]

            cursor.execute(f'SELECT COUNT(*) FROM "DiscoveredCandidates" {filter_clause} AND free_only_decision = \'APPROVED\';', params)
            metadata.total_approved = (cursor.fetchone() or [0])[0]

            cursor.execute(f'SELECT COUNT(*) FROM "DiscoveredCandidates" {filter_clause} AND free_only_decision = \'REJECTED\';', params)
            metadata.total_rejected = (cursor.fetchone() or [0])[0]

            cursor.execute(f'SELECT COUNT(*) FROM "DiscoveredCandidates" {filter_clause} AND free_only_decision = \'QUARANTINED\';', params)
            metadata.total_quarantined = (cursor.fetchone() or [0])[0]

            cursor.execute(f'SELECT COUNT(*) FROM "DiscoveredCandidates" {filter_clause} AND promotion_status = \'promoted\';', params)
            metadata.newly_promoted_count = (cursor.fetchone() or [0])[0]

            cursor.execute(f'SELECT COUNT(*) FROM "DiscoveredCandidates" {filter_clause} AND promotion_status = \'updated\';', params)
            metadata.existing_updated_count = (cursor.fetchone() or [0])[0]

        except Exception as e:
            logger.error(f"Error compiling daily summary counts: {e}")
            if strict:
                raise RepositoryError("Could not compile daily summary counts.") from e
        finally:
            cursor.close()

        return metadata

    # -------------------------------------------------------------------------
    # DAILY REPORT DELIVERY IDEMPOTENCY & AUDIT
    # -------------------------------------------------------------------------
    def get_delivery_record(self, report_date: str, recipient: str) -> Optional[EmailDeliveryRecord]:
        """Queries delivery record by report_date and recipient to check if already sent."""
        self.ensure_schema()
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            sql = """
            SELECT * FROM "DailyReportDelivery"
            WHERE report_date = %s AND recipient = %s
            LIMIT 1;
            """
            cursor.execute(sql, (report_date, recipient))
            row = cursor.fetchone()
            if not row:
                return None
            cols = [desc[0] for desc in cursor.description]
            d = dict(zip(cols, row))
            opp_ids = []
            if d.get("opportunity_ids"):
                try:
                    opp_ids = json.loads(d["opportunity_ids"])
                except Exception:
                    pass
            return EmailDeliveryRecord(
                report_date=str(d["report_date"]),
                recipient=d["recipient"],
                report_identifier=d["report_identifier"],
                opportunity_ids=opp_ids,
                attachment_path=d.get("attachment_path"),
                attachment_checksum=d.get("attachment_checksum"),
                delivery_status=d.get("delivery_status", "pending"),
                attempt_count=int(d.get("attempt_count", 0)),
                max_attempts=int(d.get("max_attempts", 3)),
                provider_message_id=d.get("provider_message_id"),
                last_error=d.get("last_error"),
                created_at=str(d.get("created_at", "")),
                delivered_at=str(d["delivered_at"]) if d.get("delivered_at") else None,
            )
        except Exception as e:
            logger.error(f"Error fetching delivery record: {e}")
            return None
        finally:
            cursor.close()

    def record_delivery_attempt(self, record: EmailDeliveryRecord) -> str:
        """
        Inserts or updates initial pending delivery attempt record.
        Enforces database uniqueness on (report_date, recipient).
        """
        self.ensure_schema()
        rec_id = f"del_{record.report_date.replace('-', '')}_{uuid.uuid4().hex[:8]}"
        sql = """
        INSERT INTO "DailyReportDelivery" (
            id, report_date, recipient, report_identifier,
            opportunity_ids, attachment_path, attachment_checksum,
            delivery_status, attempt_count, max_attempts, created_at
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, CURRENT_TIMESTAMP
        )
        ON CONFLICT (report_identifier) DO UPDATE SET
            attempt_count = "DailyReportDelivery".attempt_count + 1,
            last_error = EXCLUDED.last_error
        RETURNING id;
        """
        with self.db_manager.transaction() as cursor:
            cursor.execute(
                sql,
                (
                    rec_id,
                    record.report_date,
                    record.recipient,
                    record.report_identifier,
                    json.dumps(record.opportunity_ids),
                    record.attachment_path,
                    record.attachment_checksum,
                    record.delivery_status,
                    record.attempt_count + 1,
                    record.max_attempts,
                ),
            )
            row = cursor.fetchone()
            return str(row[0]) if row else rec_id

    def update_delivery_success(
        self,
        report_identifier: str,
        provider_message_id: str,
    ) -> None:
        """Updates delivery record to 'sent' upon successful Brevo response."""
        sql = """
        UPDATE "DailyReportDelivery" SET
            delivery_status = 'sent',
            provider_message_id = %s,
            delivered_at = CURRENT_TIMESTAMP,
            last_error = NULL
        WHERE report_identifier = %s;
        """
        with self.db_manager.transaction() as cursor:
            cursor.execute(sql, (provider_message_id, report_identifier))

    def update_delivery_failure(
        self,
        report_identifier: str,
        error_message: str,
    ) -> None:
        """Updates delivery record with failure details."""
        sql = """
        UPDATE "DailyReportDelivery" SET
            delivery_status = 'failed',
            last_error = %s
        WHERE report_identifier = %s;
        """
        with self.db_manager.transaction() as cursor:
            cursor.execute(sql, (error_message, report_identifier))

