"""
Collector Factory for CyberScout AI Collection Framework.
"""

from typing import Optional, Type

from src.collectors.base import BaseCollector
from src.collectors.context import CollectorContext
from src.collectors.registry import CollectorRegistry
from src.core.exceptions import CollectorError
from src.core.logging import get_logger

logger = get_logger(__name__)


class CollectorFactory:
    """
    Factory for instantiating concrete BaseCollector instances.
    """

    def __init__(self, registry: Optional[CollectorRegistry] = None, context: Optional[CollectorContext] = None):
        self.registry = registry or CollectorRegistry()
        self.context = context or CollectorContext.create_default()

    def create_collector(self, class_name: str, source_id: str) -> BaseCollector:
        """
        Instantiates a BaseCollector subclass by class name.

        Args:
            class_name: Name of registered collector class.
            source_id: Target source identifier.

        Returns:
            Instantiated BaseCollector object.
        """
        cls_type = self.registry.get_collector_class(class_name)
        if not cls_type:
            raise CollectorError(f"Collector class '{class_name}' is not registered.")

        collector_obj = cls_type(source_id=source_id)
        collector_obj.initialize()
        return collector_obj
