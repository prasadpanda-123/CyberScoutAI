"""
Notification Client Facade for CyberScout AI.
"""

from pathlib import Path
import time
from typing import Any, Dict, Optional
import uuid

from src.database.connection import DatabaseManager
from src.notifier.digest_builder import DigestBuilder
from src.notifier.history import HistoryTracker
from src.notifier.html_renderer import HTMLRenderer
from src.notifier.metrics import NotifierMetrics
from src.notifier.smtp_sender import SMTPSender
from src.notifier.template_loader import TemplateLoader


class EmailClient:
    """
    Unified manager client coordinating reporting, rendering, delivering daily digest alerts.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        config_path: Optional[Path] = None,
        template_loader: Optional[TemplateLoader] = None,
        html_renderer: Optional[HTMLRenderer] = None,
        digest_builder: Optional[DigestBuilder] = None,
        smtp_sender: Optional[SMTPSender] = None,
        history_tracker: Optional[HistoryTracker] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.config_path = config_path
        self.template_loader = template_loader or TemplateLoader()
        self.html_renderer = html_renderer or HTMLRenderer(template_loader=self.template_loader)
        self.digest_builder = digest_builder or DigestBuilder(db_manager=self.db_manager, config_path=self.config_path)
        self.smtp_sender = smtp_sender or SMTPSender(config_path=self.config_path)
        self.history_tracker = history_tracker or HistoryTracker(db_manager=self.db_manager)
        self.metrics = NotifierMetrics()

    def send_daily_digest(self) -> Dict[str, Any]:
        """
        Retrieves active data, builds daily digest, renders HTML/Text, and delivers email.

        Returns:
            Outcome summary dictionary containing status and delivery logs.
        """
        # 1. Compile Report Digest Data Model
        digest = self.digest_builder.build_digest()
        if digest.total_opportunities == 0:
            return {"status": "skipped", "message": "No active opportunities found to send."}

        # 2. Render Template contents
        render_start = time.time()
        html, text = self.html_renderer.render_report(digest)
        self.metrics.record_render(time.time() - render_start)

        # 3. Transmit via SMTP transport
        send_start = time.time()
        subject = f"CyberScout AI Digest - {digest.date}"
        run_id = f"email-run-{int(time.time())}"

        try:
            msg_id = self.smtp_sender.send_email(
                html_content=html,
                plain_content=text,
                subject=subject,
            )
            send_duration = time.time() - send_start
            self.metrics.record_sent(send_duration)

            # 4. Record delivery histories for every processed item
            for category_items in digest.categories.values():
                for opp in category_items:
                    self.history_tracker.log_delivery(opp.id, email_run_id=run_id)

            return {
                "status": "success",
                "message_id": msg_id,
                "opportunities_sent": digest.total_opportunities,
                "metrics": self.metrics.get_summary(),
            }

        except Exception as e:
            self.metrics.record_failed()
            return {
                "status": "failed",
                "error": str(e),
                "metrics": self.metrics.get_summary(),
            }
