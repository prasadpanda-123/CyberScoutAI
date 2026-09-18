"""
Migration v3: Opportunity URL Hash Uniqueness & Safe Duplicate Archival.

1. Safely archives historical duplicate records (status = 'duplicate') into OpportunityDuplicatesArchive.
2. Removes duplicate-status rows from Opportunities table without deleting any unique or active data.
3. Creates a database-level UNIQUE index on Opportunities(url_hash).
"""

from typing import Any, Dict
from src.core.logging import get_logger
from src.database.connection import DatabaseManager

logger = get_logger(__name__)


def run_migration(db_manager: DatabaseManager = None) -> Dict[str, Any]:
    """Executes migration v3 safely and idempotently."""
    db = db_manager or DatabaseManager()
    conn = db.get_connection()
    cursor = conn.cursor()
    stats = {
        "archived_count": 0,
        "purged_count": 0,
        "remaining_active": 0,
        "unique_index_created": False,
    }

    try:
        # Step 1: Create archive table for duplicates if not exists
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS "OpportunityDuplicatesArchive" (
                id VARCHAR PRIMARY KEY,
                title VARCHAR,
                description TEXT,
                url TEXT,
                url_hash VARCHAR,
                source_id VARCHAR,
                category VARCHAR,
                provider VARCHAR,
                company VARCHAR,
                location VARCHAR,
                remote BOOLEAN,
                paid BOOLEAN,
                certificate BOOLEAN,
                price_raw VARCHAR,
                price_normalized VARCHAR,
                currency VARCHAR,
                deadline DATE,
                published_date DATE,
                discovered_date DATE,
                duration VARCHAR,
                difficulty VARCHAR,
                tags TEXT,
                beginner_friendly BOOLEAN,
                score INTEGER,
                score_breakdown TEXT,
                confidence_score FLOAT,
                quality_score FLOAT,
                is_rejected BOOLEAN,
                rejection_reason TEXT,
                quality_flags TEXT,
                topic_score FLOAT,
                keyword_score FLOAT,
                spam_score FLOAT,
                status VARCHAR,
                duplicate_of_id VARCHAR,
                run_id VARCHAR,
                raw_data TEXT,
                expired INTEGER,
                archived INTEGER,
                last_seen TIMESTAMP,
                archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # Step 2: Copy duplicate rows to archive table (ignore if already archived)
        cursor.execute(
            """
            INSERT INTO "OpportunityDuplicatesArchive" (
                id, title, description, url, url_hash, source_id, category,
                provider, company, location, remote, paid, certificate,
                price_raw, price_normalized, currency, deadline, published_date,
                discovered_date, duration, difficulty, tags, beginner_friendly,
                score, score_breakdown, confidence_score, quality_score,
                is_rejected, rejection_reason, quality_flags, topic_score,
                keyword_score, spam_score, status, duplicate_of_id, run_id,
                raw_data, expired, archived, last_seen
            )
            SELECT 
                id, title, description, url, url_hash, source_id, category,
                provider, company, location, remote, paid, certificate,
                price_raw, price_normalized, currency, deadline, published_date,
                discovered_date, duration, difficulty, tags, beginner_friendly,
                score, score_breakdown, confidence_score, quality_score,
                is_rejected, rejection_reason, quality_flags, topic_score,
                keyword_score, spam_score, status, duplicate_of_id, run_id,
                raw_data, expired, archived, last_seen
            FROM "Opportunities"
            WHERE status = 'duplicate'
            ON CONFLICT (id) DO NOTHING;
            """
        )
        stats["archived_count"] = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0

        # Step 3: Purge duplicate status records from Opportunities table
        cursor.execute("DELETE FROM \"Opportunities\" WHERE status = 'duplicate';")
        stats["purged_count"] = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0

        # Step 4: Verify remaining rows count
        cursor.execute('SELECT COUNT(*) FROM "Opportunities";')
        stats["remaining_active"] = cursor.fetchone()[0]

        # Step 5: Create UNIQUE index on url_hash
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_opportunities_url_hash ON "Opportunities" (url_hash);')
        stats["unique_index_created"] = True

        conn.commit()
        logger.info(f"Migration v3 completed: {stats}")
        return stats
    except Exception as e:
        conn.rollback()
        logger.error(f"Migration v3 failed: {e}")
        raise
    finally:
        cursor.close()


if __name__ == "__main__":
    res = run_migration()
    print("Migration v3 result:", res)
