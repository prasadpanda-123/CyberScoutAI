"""
RSS/XML Feed Parser Diagnostics and Recovery Subsystem for CyberScout AI.

Tracks feed health, detects malformed XML payloads, identifies HTML/JSON content-type mismatches,
saves error response dumps under logs/rss_errors/, and generates diagnostic reports.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from src.core.constants import PROJECT_ROOT
from src.core.logging import get_logger

logger = get_logger(__name__)

# Directory where malformed RSS response dumps are stored
RSS_ERRORS_DIR = PROJECT_ROOT / "logs" / "rss_errors"


@dataclass
class RSSErrorRecord:
    """Represents a detailed XML parsing failure diagnostic record."""
    source_id: str
    collector_name: str
    target_url: str
    http_status: int
    content_type: str
    response_size: int
    line_number: Optional[int]
    column_number: Optional[int]
    parser_exception: str
    snippet: str
    timestamp: str
    file_saved: Optional[str]
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RSSDiagnosticsManager:
    """
    Central Manager for RSS feed diagnostics, error tracking, and response dump persistence.
    """

    _instance: Optional["RSSDiagnosticsManager"] = None
    _error_records: List[RSSErrorRecord] = []
    _feed_stats: Dict[str, Dict[str, Any]] = {}

    def __new__(cls) -> "RSSDiagnosticsManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._error_records = []
            cls._instance._feed_stats = {}
            RSS_ERRORS_DIR.mkdir(parents=True, exist_ok=True)
        return cls._instance

    def log_parser_error(
        self,
        source_id: str,
        collector_name: str,
        target_url: str,
        http_status: int,
        content_type: str,
        payload: str,
        exception_msg: str,
        line: Optional[int] = None,
        col: Optional[int] = None,
        recommendation: Optional[str] = None,
    ) -> RSSErrorRecord:
        """
        Logs a detailed RSS/XML parsing failure, saves response dump to disk, and tracks diagnostics.

        Args:
            source_id: Source ID string.
            collector_name: Name of collector.
            target_url: Feed target URL.
            http_status: HTTP status code.
            content_type: Content-Type header string.
            payload: Raw response body string.
            exception_msg: Exception message.
            line: Line number of XML error.
            col: Column number of XML error.
            recommendation: Recommended fix or collector.

        Returns:
            RSSErrorRecord dataclass instance.
        """
        now = datetime.now(timezone.utc)
        ts_str = now.strftime("%Y%m%d_%H%M%S")
        iso_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        snippet = payload[:300].strip().replace("\n", " ").replace("\r", "") if payload else ""
        size = len(payload.encode("utf-8")) if payload else 0

        # Auto-determine recommendation if not provided
        if not recommendation:
            lower_payload = payload.lower() if payload else ""
            lower_ct = content_type.lower() if content_type else ""

            if "text/html" in lower_ct or "<!doctype html" in lower_payload or "<html" in lower_payload or "just a moment..." in lower_payload:
                recommendation = "Recommend switching to 'HtmlScraperCollector' (Response is HTML/Cloudflare)."
            elif "application/json" in lower_ct or (payload and payload.strip().startswith(("{", "["))):
                recommendation = "Recommend switching to API/JSON Collector (Response is JSON)."
            elif "404" in exception_msg or http_status == 404:
                recommendation = "Feed endpoint returned 404 Not Found. Update source URL."
            else:
                recommendation = "Malformed XML markup. Attempt lxml recovery or fix feed XML escaping."

        # Save dump to disk under logs/rss_errors/
        file_saved_path: Optional[str] = None
        try:
            RSS_ERRORS_DIR.mkdir(parents=True, exist_ok=True)
            clean_sid = re.sub(r"[^\w\-]", "_", source_id)
            dump_filename = f"rss_error_{ts_str}_{clean_sid}.xml"
            dump_file = RSS_ERRORS_DIR / dump_filename
            dump_file.write_text(payload or "", encoding="utf-8")
            file_saved_path = str(dump_file)
        except Exception as fe:
            logger.warning(f"Could not save malformed RSS response dump: {fe}")

        record = RSSErrorRecord(
            source_id=source_id,
            collector_name=collector_name,
            target_url=target_url,
            http_status=http_status,
            content_type=content_type or "unknown",
            response_size=size,
            line_number=line,
            column_number=col,
            parser_exception=exception_msg,
            snippet=snippet,
            timestamp=iso_str,
            file_saved=file_saved_path,
            recommendation=recommendation,
        )

        self._error_records.append(record)

        # Update feed stats
        self._feed_stats[source_id] = {
            "status": "Broken",
            "last_error": exception_msg,
            "last_error_time": iso_str,
            "target_url": target_url,
            "recommendation": recommendation,
        }

        # Detailed structured log line eliminating vague warning
        loc_str = f"line {line}, col {col}" if line and col else "unknown position"
        logger.warning(
            f"[RSS XML PARSE ERROR] Provider '{source_id}' ({collector_name}) | "
            f"URL: '{target_url}' | HTTP {http_status} | Content-Type: '{content_type}' | "
            f"Error at {loc_str}: {exception_msg} | Fix: {recommendation}"
        )

        return record

    def record_success(self, source_id: str, target_url: str, response_time_sec: float = 0.5) -> None:
        """Records a successful feed collection run."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        existing = self._feed_stats.get(source_id, {})
        existing.update({
            "status": "Healthy",
            "last_success_time": now_str,
            "target_url": target_url,
            "last_response_time": response_time_sec,
        })
        self._feed_stats[source_id] = existing

    def get_all_records(self) -> List[RSSErrorRecord]:
        """Returns all recorded RSS error records."""
        return list(self._error_records)

    def get_feed_diagnostics_summary(self) -> Dict[str, Any]:
        """Returns summary dictionary of feed diagnostics for Web Dashboard and CLI."""
        total_errors = len(RSSDiagnosticsManager._error_records)
        stats = RSSDiagnosticsManager._feed_stats

        healthy_count = sum(1 for s in stats.values() if s.get("status") == "Healthy")
        broken_count = sum(1 for s in stats.values() if s.get("status") == "Broken")

        resp_times = [s["last_response_time"] for s in stats.values() if "last_response_time" in s]
        avg_resp_time = round(sum(resp_times) / len(resp_times), 3) if resp_times else 0.0

        return {
            "total_parser_errors": total_errors,
            "healthy_feeds_count": healthy_count,
            "broken_feeds_count": broken_count,
            "average_response_time_sec": avg_resp_time,
            "feed_stats": stats,
            "recent_errors": [r.to_dict() for r in RSSDiagnosticsManager._error_records[-20:]],
        }
