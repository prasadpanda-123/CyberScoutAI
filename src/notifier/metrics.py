"""
Notifier Operational Metrics Tracker for CyberScout AI.
"""

from typing import Any, Dict


class NotifierMetrics:
    """
    Logs notification operational speeds and outcome performance values.
    """

    def __init__(self):
        self.emails_sent = 0
        self.emails_failed = 0
        self.total_send_duration = 0.0
        self.total_render_duration = 0.0

    def record_sent(self, duration: float) -> None:
        """Records a successful email dispatch."""
        self.emails_sent += 1
        self.total_send_duration += duration

    def record_failed(self) -> None:
        """Records a failed dispatch attempt."""
        self.emails_failed += 1

    def record_render(self, duration: float) -> None:
        """Records a report compilation render time."""
        self.total_render_duration += duration

    def get_summary(self) -> Dict[str, Any]:
        """Returns delivery statistics summaries."""
        total = self.emails_sent + self.emails_failed
        rate = (self.emails_sent / total * 100.0) if total > 0 else 0.0
        avg_send = (self.total_send_duration / self.emails_sent) if self.emails_sent > 0 else 0.0
        avg_render = (self.total_render_duration / total) if total > 0 else 0.0

        return {
            "emails_sent": self.emails_sent,
            "emails_failed": self.emails_failed,
            "delivery_rate": round(rate, 2),
            "average_send_time": round(avg_send, 4),
            "average_render_time": round(avg_render, 4),
        }
