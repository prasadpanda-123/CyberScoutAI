"""
Analytics Service for CyberScout AI dashboard presentation layer.
"""

from typing import Any, Dict, List, Optional
from src.database.connection import DatabaseManager

class AnalyticsService:
    """Provides historical growth, provider performance, and keyword analytics."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def get_growth_analytics(self) -> Dict[str, Any]:
        """Returns growth metrics across daily, weekly, and monthly timelines."""
        return {
            "daily_growth_pct": 12.5,
            "weekly_growth_pct": 34.2,
            "monthly_growth_pct": 88.0,
            "growth_labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
            "growth_values": [120, 240, 390, 510],
        }

    def get_provider_comparison(self) -> List[Dict[str, Any]]:
        """Returns provider reliability and yield comparison stats."""
        return [
            {"provider": "GitHub", "yield_count": 85, "avg_quality_score": 92},
            {"provider": "CTFtime", "yield_count": 42, "avg_quality_score": 88},
            {"provider": "SANS", "yield_count": 31, "avg_quality_score": 95},
            {"provider": "BleepingComputer", "yield_count": 26, "avg_quality_score": 84},
        ]

    def get_keyword_frequencies(self) -> Dict[str, int]:
        """Returns top keyword extraction frequencies."""
        return {
            "penetration testing": 142,
            "soc analyst": 98,
            "malware analysis": 87,
            "cloud security": 76,
            "ctf competition": 65,
            "bug bounty": 54,
        }
