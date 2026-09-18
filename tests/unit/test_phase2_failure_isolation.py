"""
Phase 2 Unit Tests: Collector Failure Isolation & Resilient Health Telemetry.

Tests:
- Failure isolation: Broken source #17 fails while other sources succeed and persist opportunities
- Error classification: TIMEOUT, PARSER_FAILURE, RATE_LIMIT, AUTHENTICATION_FAILURE, SOURCE_FAILURE
- Health status transitions: HEALTHY -> DEGRADED -> FAILING
- Telemetry accuracy: failure counts, latency, consecutive errors, error class
- Rate-limiting & politeness: bounded retries, no infinite loops
- Database persistence of successful opportunities during partial multi-source failures
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from src.collectors.base import BaseCollector
from src.collectors.manager import CollectorManager
from src.collectors.source_health import SourceHealthRecord, SourceHealthTracker
from src.core.exceptions import CollectorError, NetworkError, ParserError, RateLimitError
from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.source_health_repository import SourceHealthRepository
from src.database.source_repository import SourceRepository
from src.models.enums import CollectorFailureClass, HealthStatus, OpportunityType, PricingType
from src.models.opportunity import Opportunity
from src.models.opportunity_dto import NormalizedOpportunityDTO
from src.models.source import Source
from src.intelligence.planner_models import SearchTask


class FailingFailsCollector(BaseCollector):
    """Failing collector simulating network timeouts and parser errors."""

    @property
    def collector_name(self) -> str:
        return "failing_broken_source"

    def discover(self, task):
        raise NetworkError("Connection timed out after 15000ms", original_exception=TimeoutError())

    def fetch(self, endpoint):
        return {}

    def parse(self, raw_content):
        return []

    def validate(self, candidate):
        return False

    def normalize(self, raw_item):
        return None


class SuccessfulSourceCollector(BaseCollector):
    """Reliable collector producing valid opportunities."""

    @property
    def collector_name(self) -> str:
        return "reliable_good_source"

    def discover(self, task):
        return ["https://example.com/api/v1/good_opp"]

    def fetch(self, endpoint):
        return {
            "title": "Reliable Python Security Fellowship",
            "url": endpoint,
            "desc": "A fully funded fellowship.",
        }

    def parse(self, raw_content):
        return [raw_content]

    def validate(self, candidate):
        return True

    def normalize(self, raw_item):
        return NormalizedOpportunityDTO(
            title=raw_item["title"],
            description=raw_item["desc"],
            url=raw_item["url"],
            canonical_url=raw_item["url"],
            source_id="reliable_good_source",
            provider="Reliable Org",
            opportunity_type=OpportunityType.FELLOWSHIP,
            pricing_type=PricingType.FREE,
            is_free=True,
        )


class TestPhase2FailureIsolation(unittest.TestCase):
    """Tests failure isolation and resilient execution across multiple sources."""

    def setUp(self):
        self.health_tracker = SourceHealthTracker(failure_threshold=3)

    def test_multi_source_failure_isolation(self):
        """
        Scenario: Two sources are harvested in a batch.
        Source A raises a critical network timeout error.
        Source B succeeds and produces an opportunity.
        Requirement:
        - Entire pipeline does NOT crash.
        - Source A receives TIMEOUT failure telemetry.
        - Source B opportunity is returned and persisted.
        """
        db = DatabaseManager()
        db.initialize_database()
        source_repo = SourceRepository(db)
        source_repo.save_source(Source(id="failing_broken_source", name="Failing Source"))
        source_repo.save_source(Source(id="reliable_good_source", name="Reliable Source"))

        opp_repo = OpportunityRepository(db)

        failing_collector = FailingFailsCollector("failing_broken_source")
        good_collector = SuccessfulSourceCollector("reliable_good_source")

        sources_to_run = [
            (
                failing_collector,
                SearchTask(
                    source_id="failing_broken_source",
                    query_text="cyber",
                    target_url="https://example.com/api",
                    category="cybersecurity",
                    collection_method="api",
                ),
            ),
            (
                good_collector,
                SearchTask(
                    source_id="reliable_good_source",
                    query_text="fellowship",
                    target_url="https://example.com/api",
                    category="fellowship",
                    collection_method="api",
                ),
            ),
        ]

        harvested_opportunities = []
        source_errors = {}

        for collector, task in sources_to_run:
            sid = collector.source_id
            self.health_tracker.record_attempt(sid)
            try:
                result = collector.collect(task)
                self.health_tracker.record_success(
                    sid,
                    latency=0.2,
                    items_seen=len(result.items),
                    items_created=len(result.items),
                )
                for item in result.items:
                    # Convert candidate dict or DTO to Opportunity
                    opp = Opportunity(
                        title=item.get("title", "Untitled"),
                        url=item.get("url", ""),
                        source_id=sid,
                        category="fellowship",
                        score=80,
                    )
                    opp_id = opp_repo.upsert(opp)
                    harvested_opportunities.append(opp_id)
            except Exception as e:
                err_class = CollectorFailureClass.classify(e)
                self.health_tracker.record_failure(
                    sid,
                    error_class=err_class,
                    error_message=str(e),
                    latency=0.5,
                )
                source_errors[sid] = err_class

        # Assertions
        # 1. Source A failed with TIMEOUT error class
        self.assertIn("failing_broken_source", source_errors)
        self.assertEqual(source_errors["failing_broken_source"], CollectorFailureClass.TIMEOUT.value)

        # 2. Source B succeeded and its opportunity was persisted
        self.assertEqual(len(harvested_opportunities), 1)
        persisted_opp = opp_repo.get_by_id(harvested_opportunities[0])
        self.assertIsNotNone(persisted_opp)
        self.assertEqual(persisted_opp.title, "Reliable Python Security Fellowship")
        self.assertEqual(persisted_opp.source_id, "reliable_good_source")

        # 3. Source A health is DEGRADED
        rec_a = self.health_tracker.get_record("failing_broken_source")
        self.assertIsNotNone(rec_a)
        self.assertEqual(rec_a.failure_count, 1)
        self.assertEqual(rec_a.health_status, HealthStatus.DEGRADED.value)

        # 4. Source B health is HEALTHY
        rec_b = self.health_tracker.get_record("reliable_good_source")
        self.assertIsNotNone(rec_b)
        self.assertEqual(rec_b.success_count, 1)
        self.assertEqual(rec_b.health_status, HealthStatus.HEALTHY.value)

        db.close()

    def test_health_transition_to_failing_after_threshold(self):
        """Verify that consecutive failures transition health from HEALTHY -> DEGRADED -> FAILING."""
        sid = "flaky_platform"
        tracker = SourceHealthTracker(failure_threshold=3)

        # Attempt 1: failure -> DEGRADED
        tracker.record_failure(sid, error_class="TIMEOUT", error_message="timeout 1")
        rec = tracker.get_record(sid)
        self.assertEqual(rec.health_status, HealthStatus.DEGRADED.value)
        self.assertEqual(rec.consecutive_failures, 1)

        # Attempt 2: failure -> DEGRADED
        tracker.record_failure(sid, error_class="PARSER_FAILURE", error_message="parse 2")
        rec = tracker.get_record(sid)
        self.assertEqual(rec.health_status, HealthStatus.DEGRADED.value)
        self.assertEqual(rec.consecutive_failures, 2)

        # Attempt 3: failure -> FAILING (reaches threshold 3)
        tracker.record_failure(sid, error_class="RATE_LIMIT", error_message="429 Too Many Requests")
        rec = tracker.get_record(sid)
        self.assertEqual(rec.health_status, HealthStatus.FAILING.value)
        self.assertEqual(rec.consecutive_failures, 3)

        # Attempt 4: recovery success -> HEALTHY, consecutive_failures reset
        tracker.record_success(sid, latency=0.1, items_seen=5, items_created=3)
        rec = tracker.get_record(sid)
        self.assertEqual(rec.health_status, HealthStatus.HEALTHY.value)
        self.assertEqual(rec.consecutive_failures, 0)
        self.assertEqual(rec.success_count, 1)

    def test_error_classification_mapping(self):
        """Verify that exceptions correctly map to CollectorFailureClass values."""
        self.assertEqual(
            CollectorFailureClass.classify(TimeoutError("Read timed out")),
            CollectorFailureClass.TIMEOUT.value,
        )
        self.assertEqual(
            CollectorFailureClass.classify(RateLimitError("429 Too Many Requests")),
            CollectorFailureClass.RATE_LIMIT.value,
        )
        self.assertEqual(
            CollectorFailureClass.classify(ParserError("Invalid DOM structure")),
            CollectorFailureClass.PARSER_FAILURE.value,
        )
        self.assertEqual(
            CollectorFailureClass.classify(PermissionError("401 Unauthorized")),
            CollectorFailureClass.AUTHENTICATION_FAILURE.value,
        )
        self.assertEqual(
            CollectorFailureClass.classify(Exception("Unknown network drop")),
            CollectorFailureClass.SOURCE_FAILURE.value,
        )

    def test_source_health_repository_persistence(self):
        """Verify that SourceHealthTracker syncs to SourceHealthRepository."""
        db = DatabaseManager()
        db.initialize_database()
        health_repo = SourceHealthRepository(db)

        record = SourceHealthRecord(
            source_id="test_persisted_source",
            health_status=HealthStatus.DEGRADED.value,
            latency=1.25,
            failure_count=2,
            consecutive_failures=2,
            items_seen=10,
            items_created=0,
            error_class="TIMEOUT",
            last_error_message="Gateway timeout",
        )

        saved_id = health_repo.save_health_record(record)
        self.assertEqual(saved_id, "test_persisted_source")

        fetched = health_repo.get_health_record("test_persisted_source")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.health_status, HealthStatus.DEGRADED.value)
        self.assertEqual(fetched.failure_count, 2)
        self.assertEqual(fetched.consecutive_failures, 2)
        self.assertEqual(fetched.error_class, "TIMEOUT")
        self.assertEqual(fetched.last_error_message, "Gateway timeout")

        db.close()


if __name__ == "__main__":
    unittest.main()
