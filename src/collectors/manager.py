"""
Collector Manager for CyberScout AI Collection Framework.

Orchestrates execution of SearchPlan tasks across collectors with exception isolation,
metrics tracking, and logging. Failure in one task or collector never stops the pipeline.
"""

import socket
import ssl
import time
from typing import Dict, List, Optional
import urllib.error

from src.collectors.base import BaseCollector
from src.collectors.context import CollectorContext
from src.collectors.exceptions import CollectorError, HTTPClientError, RateLimitError
from src.collectors.factory import CollectorFactory
from src.collectors.metrics import CollectorMetrics
from src.collectors.registry import CollectorRegistry
from src.collectors.result import CollectorResult
from src.core.logging import get_logger
from src.intelligence.planner_models import SearchPlan, SearchTask

logger = get_logger(__name__)


class CollectorManager:
    """
    Central orchestrator for executing collection tasks safely and reliably.
    """

    def __init__(
        self,
        registry: Optional[CollectorRegistry] = None,
        factory: Optional[CollectorFactory] = None,
        context: Optional[CollectorContext] = None,
    ):
        self.registry = registry or CollectorRegistry()
        self.context = context or CollectorContext.create_default()
        self.factory = factory or CollectorFactory(registry=self.registry, context=self.context)
        self.metrics = CollectorMetrics()

    def execute_task(self, task: SearchTask, collector: Optional[BaseCollector] = None) -> CollectorResult:
        """
        Executes a single SearchTask with complete exception isolation.
        Handles timeouts, HTTP errors, SSL errors, and collector exceptions without failing the pipeline.

        Args:
            task: Planned SearchTask instance.
            collector: Optional pre-instantiated BaseCollector.

        Returns:
            Standardized CollectorResult instance.
        """
        start_time = time.time()
        source_id = task.source_id
        method = task.collection_method or "rss"
        url = task.target_url

        if not collector:
            preferred_collector_name = task.metadata.get("preferred_collector")
            if not preferred_collector_name or preferred_collector_name == "GenericCollector":
                if method == "rss":
                    preferred_collector_name = "GenericRSSCollector"
                elif method == "html":
                    preferred_collector_name = "HtmlScraperCollector"
                elif source_id == "github_search":
                    preferred_collector_name = "GithubSearchCollector"
                elif source_id == "ctftime":
                    preferred_collector_name = "CtftimeCollector"
                else:
                    preferred_collector_name = "GenericRSSCollector"

            try:
                collector = self.factory.create_collector(preferred_collector_name, source_id=source_id)
            except Exception as e:
                logger.warning(f"Could not instantiate collector '{preferred_collector_name}' for provider '{source_id}': {e}. Using fallback.")

        if not collector:
            duration = time.time() - start_time
            self.metrics.record_provider_result(source_id, method, success=False)
            return CollectorResult(
                source_id=source_id,
                status="failed",
                items=[],
                errors=[f"Failed to resolve collector for provider '{source_id}'."],
                metrics=self.metrics.to_dict(),
                duration_seconds=duration,
            )

        try:
            logger.info(f"CollectorManager executing task on provider '{source_id}' ({collector.collector_name}) | URL: '{url}'...")
            result = collector.collect(task)
            duration = time.time() - start_time
            result.duration_seconds = duration

            if result.status == "success":
                self.metrics.record_provider_result(source_id, method, success=True, item_count=result.item_count)
            else:
                self.metrics.record_provider_result(source_id, method, success=False)

            result.metrics = self.metrics.to_dict()
            logger.info(f"Provider '{source_id}' completed with status '{result.status}' ({result.item_count} items collected in {duration:.2f}s).")
            return result

        except (TimeoutError, socket.timeout) as err_timeout:
            duration = time.time() - start_time
            self.metrics.record_provider_result(source_id, method, success=False, is_timeout=True)
            logger.error(f"[PIPELINE RESILIENCE WARNING] Provider '{source_id}' timed out after {duration:.2f}s (URL: '{url}'): {err_timeout}. Continuing pipeline.")
            return CollectorResult(
                source_id=source_id,
                status="failed",
                items=[],
                errors=[f"Timeout error: {err_timeout}"],
                metrics=self.metrics.to_dict(),
                duration_seconds=duration,
            )

        except urllib.error.HTTPError as err_http:
            duration = time.time() - start_time
            self.metrics.record_provider_result(source_id, method, success=False)
            logger.error(f"[PIPELINE RESILIENCE WARNING] Provider '{source_id}' HTTP {err_http.code} error after {duration:.2f}s (URL: '{url}'): {err_http.reason}. Continuing pipeline.")
            return CollectorResult(
                source_id=source_id,
                status="failed",
                items=[],
                errors=[f"HTTP {err_http.code} error: {err_http.reason}"],
                metrics=self.metrics.to_dict(),
                duration_seconds=duration,
            )

        except (urllib.error.URLError, socket.gaierror) as err_net:
            duration = time.time() - start_time
            self.metrics.record_provider_result(source_id, method, success=False)
            logger.error(f"[PIPELINE RESILIENCE WARNING] Provider '{source_id}' Network/DNS failure after {duration:.2f}s (URL: '{url}'): {err_net}. Continuing pipeline.")
            return CollectorResult(
                source_id=source_id,
                status="failed",
                items=[],
                errors=[f"Network/DNS error: {err_net}"],
                metrics=self.metrics.to_dict(),
                duration_seconds=duration,
            )

        except ssl.SSLError as err_ssl:
            duration = time.time() - start_time
            self.metrics.record_provider_result(source_id, method, success=False)
            logger.error(f"[PIPELINE RESILIENCE WARNING] Provider '{source_id}' SSL verification error after {duration:.2f}s (URL: '{url}'): {err_ssl}. Continuing pipeline.")
            return CollectorResult(
                source_id=source_id,
                status="failed",
                items=[],
                errors=[f"SSL error: {err_ssl}"],
                metrics=self.metrics.to_dict(),
                duration_seconds=duration,
            )

        except (CollectorError, Exception) as err_gen:
            duration = time.time() - start_time
            self.metrics.record_provider_result(source_id, method, success=False)
            logger.error(f"[PIPELINE RESILIENCE WARNING] Isolated exception executing provider '{source_id}' (URL: '{url}'): {err_gen}. Continuing pipeline.")
            return CollectorResult(
                source_id=source_id,
                status="failed",
                items=[],
                errors=[f"Collector exception: {str(err_gen)}"],
                metrics=self.metrics.to_dict(),
                duration_seconds=duration,
            )

    def execute_plan(self, plan: SearchPlan) -> List[CollectorResult]:
        """
        Executes all SearchTasks in a SearchPlan sequentially with complete exception isolation.

        Args:
            plan: Master SearchPlan generated by SearchPlanner.

        Returns:
            List of CollectorResult instances.
        """
        start_time = time.time()
        results: List[CollectorResult] = []
        logger.info(f"CollectorManager starting plan execution ({plan.total_tasks} tasks)...")

        for task in plan.tasks:
            try:
                res = self.execute_task(task)
                results.append(res)
            except Exception as task_err:
                logger.error(f"[CRITICAL TASK ISOLATION] Unhandled exception in execute_task for task '{task.task_id}': {task_err}. Skipping task and continuing pipeline.")
                results.append(CollectorResult(
                    source_id=task.source_id,
                    status="failed",
                    errors=[str(task_err)],
                ))

        total_duration = time.time() - start_time
        self.metrics.execution_duration_seconds = total_duration
        logger.info(
            f"CollectorManager completed plan execution in {total_duration:.2f}s | "
            f"Providers Attempted: {self.metrics.providers_attempted} | "
            f"Succeeded: {self.metrics.providers_succeeded} | "
            f"Failed: {self.metrics.providers_failed} | "
            f"Items Collected: {self.metrics.total_items_collected}"
        )
        return results
