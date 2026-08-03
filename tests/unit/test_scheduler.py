"""
Unit tests for Scheduler & Application Lifecycle (Phase 1.4).
"""

import unittest

from src.scheduler.base_job import BaseJob
from src.scheduler.events import LifecycleEvent, EventBus
from src.scheduler.manager import SchedulerManager
from src.scheduler.registry import JobRegistry
from src.scheduler.retry import retry_with_backoff


class MockSuccessJob(BaseJob):
    """Mock job that completes successfully."""

    def __init__(self, job_id: str = "mock_success", job_name: str = "Mock Success Job"):
        self._job_id = job_id
        self._job_name = job_name
        self.executed = False
        self.cleaned_up = False

    @property
    def job_id(self) -> str:
        return self._job_id

    @property
    def job_name(self) -> str:
        return self._job_name

    def validate(self) -> bool:
        return True

    def execute(self) -> bool:
        self.executed = True
        return True

    def cleanup(self) -> None:
        self.cleaned_up = True


class MockFailingJob(BaseJob):
    """Mock job that raises an exception during execution."""

    def __init__(self, job_id: str = "mock_fail", job_name: str = "Mock Failing Job"):
        self._job_id = job_id
        self._job_name = job_name
        self.attempts = 0

    @property
    def job_id(self) -> str:
        return self._job_id

    @property
    def job_name(self) -> str:
        return self._job_name

    def validate(self) -> bool:
        return True

    def execute(self) -> bool:
        self.attempts += 1
        raise ValueError("Simulated job execution error")

    def cleanup(self) -> None:
        pass


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.registry = JobRegistry()
        self.scheduler = SchedulerManager(registry=self.registry)

    def test_job_registration_and_registry(self):
        job = MockSuccessJob()
        self.assertTrue(self.scheduler.register_job(job))
        self.assertEqual(len(self.registry.list_jobs()), 1)
        self.assertTrue(self.registry.is_enabled("mock_success"))

        self.registry.disable_job("mock_success")
        self.assertFalse(self.registry.is_enabled("mock_success"))

    def test_job_execution_and_lifecycle_events(self):
        job = MockSuccessJob()
        self.scheduler.register_job(job)

        events_fired = []

        def event_callback(event_name, data):
            events_fired.append(event_name)

        bus = EventBus()
        bus.subscribe(LifecycleEvent.JOB_STARTING, event_callback)
        bus.subscribe(LifecycleEvent.JOB_SUCCESS, event_callback)

        bus.publish(LifecycleEvent.JOB_STARTING, {"job_id": job.job_id})
        bus.publish(LifecycleEvent.JOB_SUCCESS, {"job_id": job.job_id})

        self.assertIn("job_starting", events_fired)
        self.assertIn("job_success", events_fired)

        success = self.scheduler.run_job("mock_success")
        self.assertTrue(success)
        self.assertTrue(job.executed)
        self.assertTrue(job.cleaned_up)

        metrics = self.scheduler.get_job_metrics("mock_success")
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.status, "success")
        self.assertEqual(metrics.success_count, 1)

    def test_pause_and_resume_job(self):
        job = MockSuccessJob()
        self.scheduler.register_job(job)

        self.scheduler.pause_job("mock_success")
        self.assertTrue(self.scheduler.is_paused("mock_success"))

        # Running paused job should return False and not execute
        result = self.scheduler.run_job("mock_success")
        self.assertFalse(result)

        self.scheduler.resume_job("mock_success")
        self.assertFalse(self.scheduler.is_paused("mock_success"))

    def test_retry_framework(self):
        attempts = 0

        @retry_with_backoff(max_retries=2, initial_delay=0.01)
        def failing_func():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise ValueError("Temporary failure")
            return "ok"

        result = failing_func()
        self.assertEqual(result, "ok")
        self.assertEqual(attempts, 2)

    def test_graceful_shutdown(self):
        self.scheduler.shutdown()
        self.assertFalse(self.scheduler.is_running)


if __name__ == "__main__":
    unittest.main()
