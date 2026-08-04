"""
Automation Engine orchestrator for CyberScout AI.
"""

from typing import Any, Dict, Optional

from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.automation.lifecycle import LifecyclePublisher
from src.automation.pipeline import PipelineRunner
from src.automation.scheduler import SchedulerService
from src.automation.state import RuntimeState

logger = get_logger(__name__)


class AutomationEngine:
    """
    Main manager orchestrating schedules, state tracking, and scan pipeline runner execution.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        pipeline_runner: Optional[PipelineRunner] = None,
        scheduler_service: Optional[SchedulerService] = None,
        lifecycle_publisher: Optional[LifecyclePublisher] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.pipeline_runner = pipeline_runner or PipelineRunner(db_manager=self.db_manager)
        self.scheduler_service = scheduler_service or SchedulerService()
        self.lifecycle_publisher = lifecycle_publisher or LifecyclePublisher()
        self.state = RuntimeState.IDLE
        self.last_run_result: Dict[str, Any] = {}

    def start(self) -> None:
        """Starts engine schedules."""
        self.state = RuntimeState.RUNNING
        self.lifecycle_publisher.publish_event("Pipeline Started", "Automation engine started successfully.")
        self.scheduler_service.add_job("Master Pipeline Scan", self.run_once)
        self.scheduler_service.start()

    def stop(self) -> None:
        """Stops engine schedules."""
        self.state = RuntimeState.STOPPING
        self.scheduler_service.stop()
        self.state = RuntimeState.STOPPED
        self.lifecycle_publisher.publish_event("Pipeline Finished", "Automation engine stopped successfully.")

    def run_once(self, dry_run: bool = False) -> Dict[str, Any]:
        """Runs a single scan pipeline iteration."""
        prev_state = self.state
        self.state = RuntimeState.RUNNING
        try:
            self.lifecycle_publisher.publish_event("Collection Started", "Starting automated pipeline collection...")
            result = self.pipeline_runner.run_pipeline(dry_run=dry_run)
            self.last_run_result = result
            self.state = prev_state if prev_state != RuntimeState.IDLE else RuntimeState.SLEEPING
            self.lifecycle_publisher.publish_event("Collection Completed", "Automated pipeline collection run finished.")
            return result
        except Exception as e:
            self.state = RuntimeState.ERROR
            logger.error(f"Error running automated pipeline: {e}")
            self.lifecycle_publisher.publish_event("Pipeline Failed", f"Automated pipeline execution aborted: {e}")
            raise

    def run_forever(self, dry_run: bool = False) -> None:
        """Runs scheduler forever in daemon loop blocking mode."""
        self.start()
        logger.info("Running daemon execution loop forever. Press CTRL+C to terminate.")
        try:
            while True:
                import time
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Termination signal caught in blocking run loop.")
            self.stop()

    def status(self) -> Dict[str, Any]:
        """Returns details about scheduler states and last pipeline execution results."""
        sched_status = self.scheduler_service.get_status()
        return {
            "state": self.state.value,
            "scheduler": sched_status,
            "last_run_result": self.last_run_result,
        }
