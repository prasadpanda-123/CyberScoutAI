"""
Search Intelligence Query Builder for CyberScout AI.

Combines keywords.yaml + sources.yaml to construct ready-to-fetch queries,
API parameters, and target RSS/HTML endpoints for collectors.
"""

from typing import Any, Dict, List, Optional
import urllib.parse

from src.core.config import config
from src.core.logging import get_logger

logger = get_logger(__name__)


class SearchQuery:
    """
    Represents a constructed search query or collection target URL for a source.
    """

    def __init__(
        self,
        source_id: str,
        collection_method: str,
        target_url: str,
        query_params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        category: str = "other",
    ):
        self.source_id = source_id
        self.collection_method = collection_method
        self.target_url = target_url
        self.query_params = query_params or {}
        self.headers = headers or {}
        self.category = category

    def full_url(self) -> str:
        """Returns target URL with encoded query parameters appended."""
        if not self.query_params:
            return self.target_url
        encoded = urllib.parse.urlencode(self.query_params)
        delimiter = "&" if "?" in self.target_url else "?"
        return f"{self.target_url}{delimiter}{encoded}"

    def to_dict(self) -> Dict[str, Any]:
        """Converts SearchQuery to dictionary representation."""
        return {
            "source_id": self.source_id,
            "collection_method": self.collection_method,
            "target_url": self.full_url(),
            "category": self.category,
        }

    def __repr__(self) -> str:
        return f"<SearchQuery source='{self.source_id}' method='{self.collection_method}' url='{self.full_url()}'>"


class QueryBuilder:
    """
    Builds concrete SearchQuery targets for registered sources.
    """

    def __init__(
        self,
        sources_config: Optional[Dict[str, Any]] = None,
        keywords_config: Optional[Dict[str, Any]] = None,
    ):
        self.sources_config = sources_config or config.get("sources", {})
        self.keywords_config = keywords_config or config.get("keywords", {})

    def build_all_queries(self) -> List[SearchQuery]:
        """
        Builds search queries for all enabled sources in config.

        Returns:
            List of SearchQuery target objects.
        """
        queries: List[SearchQuery] = []
        sources = self._extract_sources_list()

        for source in sources:
            if not isinstance(source, dict) or not source.get("enabled", True):
                continue

            query = self.build_query_for_source(source)
            if query:
                queries.append(query)

        logger.info(f"Generated {len(queries)} search intelligence targets.")
        return queries

    def build_query_for_source(self, source: Dict[str, Any]) -> Optional[SearchQuery]:
        """Builds SearchQuery target for a single source dictionary."""
        source_id = source.get("id", "unknown")
        method = source.get("collection_method", source.get("type", "rss"))
        category = source.get("default_category", "other")
        base_url = source.get("url") or source.get("rss_url") or source.get("base_url")

        if not base_url:
            return None

        # Build method-specific target
        if method == "rss":
            return SearchQuery(
                source_id=source_id,
                collection_method="rss",
                target_url=base_url,
                category=category,
            )
        elif method == "api":
            params = source.get("query_params", {})
            return SearchQuery(
                source_id=source_id,
                collection_method="api",
                target_url=base_url,
                query_params=params,
                category=category,
            )
        else:
            return SearchQuery(
                source_id=source_id,
                collection_method=method,
                target_url=base_url,
                category=category,
            )

    def _extract_sources_list(self) -> List[Dict[str, Any]]:
        """Safely extracts sources list from config structure."""
        if isinstance(self.sources_config, dict):
            if "sources" in self.sources_config and isinstance(self.sources_config["sources"], list):
                return self.sources_config["sources"]
            return [{"id": k, **v} if isinstance(v, dict) else {"id": k} for k, v in self.sources_config.items()]
        elif isinstance(self.sources_config, list):
            return self.sources_config
        return []


def main() -> None:
    """CLI tool for testing search query generation."""
    qb = QueryBuilder()
    queries = qb.build_all_queries()
    print("=" * 60)
    print(f"CyberScout AI — Search Intelligence Query Builder")
    print(f"Generated {len(queries)} active search targets:")
    print("=" * 60)
    for q in queries:
        print(f"[{q.source_id.upper()}] ({q.collection_method}) -> {q.full_url()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
