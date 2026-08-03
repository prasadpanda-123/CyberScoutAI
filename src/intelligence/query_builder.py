"""
Dynamic Search Query Builder for CyberScout AI Search Intelligence Layer.

Integrates KeywordEngine and SearchTemplateEngine to construct dynamic,
non-hardcoded search queries tailored to target opportunity categories.
"""

from typing import Any, Dict, List, Optional
from src.core.logging import get_logger
from src.intelligence.keyword_engine import KeywordEngine
from src.intelligence.template_engine import SearchTemplateEngine
from src.models.search_models import SearchQuery

logger = get_logger(__name__)


class QueryBuilder:
    """
    Constructs dynamic search queries combining keywords, synonyms, and search templates.
    """

    def __init__(
        self,
        keyword_engine: Optional[KeywordEngine] = None,
        template_engine: Optional[SearchTemplateEngine] = None,
        sources_config: Optional[Dict[str, Any]] = None,
    ):
        self.keyword_engine = keyword_engine or KeywordEngine()
        self.template_engine = template_engine or SearchTemplateEngine()
        self.sources_config = sources_config or {}

    def generate_queries(
        self,
        category: Optional[str] = None,
        include_synonyms: bool = True,
        max_queries: int = 50,
    ) -> List[SearchQuery]:
        """
        Generates dynamic SearchQuery objects for specified category and keywords.

        Args:
            category: Optional opportunity category filter (e.g. 'internship', 'ctf').
            include_synonyms: Whether to expand terms with synonyms.
            max_queries: Maximum number of queries to generate.

        Returns:
            List of unique, populated SearchQuery dataclass instances.
        """
        keywords = (
            self.keyword_engine.get_expanded_keywords(category)
            if include_synonyms
            else self.keyword_engine.get_keywords_by_category(category)
            if category
            else self.keyword_engine.get_all_keywords()
        )

        queries: List[SearchQuery] = []
        seen_strings = set()

        for kw in keywords:
            rendered_strings = self.template_engine.render_queries(kw, category=category)
            for q_str in rendered_strings:
                q_clean = q_str.strip()
                if q_clean and q_clean.lower() not in seen_strings:
                    seen_strings.add(q_clean.lower())
                    sq = SearchQuery(
                        query_text=q_clean,
                        category=category or "other",
                        keywords=[kw],
                    )
                    queries.append(sq)
                    if len(queries) >= max_queries:
                        break

            if len(queries) >= max_queries:
                break

        logger.info(f"QueryBuilder generated {len(queries)} dynamic search queries (category='{category}').")
        return queries

    def build_all_queries(self) -> List[SearchQuery]:
        """
        Backward compatibility helper for building queries directly from loaded sources_config.
        """
        queries: List[SearchQuery] = []
        sources = self.sources_config.get("sources", [])
        for src in sources:
            if not isinstance(src, dict) or not src.get("enabled", True):
                continue
            sq = SearchQuery(
                source_id=src.get("id", "custom"),
                collection_method=src.get("collection_method", "rss"),
                target_url=src.get("url", ""),
                query_params=src.get("query_params", {}),
                category=src.get("default_category", "other"),
            )
            queries.append(sq)
        return queries
