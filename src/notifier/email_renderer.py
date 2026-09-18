"""
Modern Email Renderer for CyberScout AI (Phase 7).

Generates professional, responsive, table-based HTML email notifications
with inline styling, strict XSS escaping, safe protocol filtering, and plain-text fallback.
"""

from datetime import datetime, timezone
import html
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.core.logging import get_logger
from src.models.opportunity import Opportunity

logger = get_logger(__name__)

DANGEROUS_PROTOCOLS = (
    "javascript:",
    "data:",
    "vbscript:",
    "file:",
    "blob:",
    "about:",
)


class ModernEmailRenderer:
    """
    Renders high-polish, responsive HTML bulletins and plain-text fallbacks
    for immediate alerts and daily digest batches.
    """

    @classmethod
    def sanitize_url(cls, url: Optional[str]) -> str:
        """
        Validates URL scheme and protocols to prevent XSS and protocol smuggling.
        Only allows HTTP and HTTPS protocols.
        """
        if not url:
            return "#"
        clean = str(url).strip()
        lower = clean.lower()
        if any(lower.startswith(p) for p in DANGEROUS_PROTOCOLS):
            return "#"
        try:
            parsed = urlparse(clean)
            if parsed.scheme not in ("http", "https"):
                return "#"
            if not parsed.netloc or "." not in parsed.netloc:
                return "#"
            return clean
        except Exception:
            return "#"

    _sanitize_url = sanitize_url

    @classmethod
    def safe_text(cls, val: Any, max_len: Optional[int] = None) -> str:
        """Escapes HTML entities and truncates string safely."""
        if val is None:
            return ""
        s = re.sub(r"\s+", " ", str(val)).strip()
        if max_len and len(s) > max_len:
            s = s[:max_len] + "..."
        return html.escape(s)

    _clean_text = safe_text
    clean_text = safe_text

    @classmethod
    def render_immediate(
        cls,
        card: Any,
        recipient_name: str = "User",
        recipient_email: str = "user@example.com",
        app_url: str = "http://localhost:5000",
    ) -> Tuple[str, str]:
        """Renders an immediate notification alert bulletin for a single opportunity card."""
        title = getattr(card, "title", "Opportunity")
        event_type = getattr(card, "event_type", "NEW")
        if hasattr(event_type, "value"):
            event_type = event_type.value
        event_type_str = str(event_type).upper()

        digest_title = f"{event_type_str} Opportunity: {title}"
        period_label = f"Immediate {event_type_str} Alert"
        match_map = {}
        card_id = getattr(card, "opportunity_id", None) or getattr(card, "id", "")
        match_reasons = getattr(card, "match_reasons", []) or []
        if card_id and match_reasons:
            match_map[card_id] = match_reasons

        return cls.render_digest(
            opportunities=[card],
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            digest_title=digest_title,
            period_label=period_label,
            app_url=app_url,
            match_reasons_map=match_map,
        )

    @classmethod
    def render_digest(
        cls,
        opportunities: List[Any],
        recipient_email: str = "user@example.com",
        recipient_name: Optional[str] = None,
        digest_title: str = "New Opportunities For You",
        period_label: str = "Daily Digest",
        app_url: str = "http://localhost:5000",
        match_reasons_map: Optional[Dict[str, List[str]]] = None,
    ) -> Tuple[str, str]:
        """
        Renders a complete HTML email and plain-text fallback.

        Args:
            opportunities: List of Opportunity records or NotificationCardDTOs.
            recipient_email: Destination recipient email.
            recipient_name: Optional display name for recipient.
            digest_title: Primary banner heading.
            period_label: Frequency subtext.
            app_url: Base domain URL for web links.
            match_reasons_map: Mapping of opp.id to list of match reason strings.

        Returns:
            Tuple of (html_body, plain_text_body).
        """
        opps = opportunities or []
        reasons_map = match_reasons_map or {}
        now_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # -------------------------------------------------------------
        # 1. Plain-Text Alternative Generation
        # -------------------------------------------------------------
        plain_lines = [
            "===========================================================",
            "CYBERSCOUT AI",
            "Intelligent Cybersecurity Opportunity Discovery",
            "===========================================================",
            "",
            f"🎯 {digest_title.upper()}",
            f"{len(opps)} new opportunities matched to your interests ({period_label} • {now_str})",
            "",
            "-----------------------------------------------------------",
        ]

        for idx, opp in enumerate(opps, 1):
            title = getattr(opp, "title", "Opportunity")
            org = getattr(opp, "provider", None) or getattr(opp, "company", None) or getattr(opp, "organization", None) or "Cybersecurity Organization"
            mode = "Remote" if getattr(opp, "remote", False) else "In-Person / On-Site"
            
            pricing_str = getattr(opp, "pricing", None)
            if pricing_str:
                cost = pricing_str
            elif getattr(opp, "is_free", False) or getattr(opp, "price_amount", None) == 0:
                cost = "Free"
            elif getattr(opp, "price_amount", None):
                cost = f"${opp.price_amount:,.2f}"
            else:
                cost = "Free" if "free" in str(getattr(opp, "pricing_type", "")).lower() else "View Details"

            stipend_str = getattr(opp, "stipend", None)
            if stipend_str:
                stipend_text = stipend_str
            elif getattr(opp, "stipend_amount", None):
                stipend_text = f"${opp.stipend_amount:,.2f}"
            else:
                stipend_text = None

            opp_url = getattr(opp, "view_url", None) or getattr(opp, "url", "#")
            cta_url = cls.sanitize_url(opp_url)
            deadline = getattr(opp, "deadline", None)
            deadline_str = str(deadline)[:10] if deadline else "Ongoing / Rolling"

            plain_lines.append(f"{idx}. {title}")
            plain_lines.append(f"   Source: {org}")
            plain_lines.append(f"   Deadline: {deadline_str}")
            plain_lines.append(f"   Cost: {cost}")
            if stipend_text:
                plain_lines.append(f"   Stipend: {stipend_text}")
            plain_lines.append(f"   Mode: {mode}")
            plain_lines.append(f"   View: {cta_url}")
            plain_lines.append("")

        plain_lines.extend([
            "-----------------------------------------------------------",
            "CyberScout AI — Notification Settings: " + f"{app_url}/notifications",
            f"Generated: {now_iso}",
        ])
        plain_text = "\n".join(plain_lines)

        # -------------------------------------------------------------
        # 2. Modern HTML Table-Based Generation
        # -------------------------------------------------------------
        cards_html: List[str] = []
        for opp in opps:
            opp_id = getattr(opp, "id", None) or getattr(opp, "opportunity_id", "")
            title = cls.safe_text(getattr(opp, "title", "Opportunity"))
            org = cls.safe_text(getattr(opp, "provider", None) or getattr(opp, "company", None) or getattr(opp, "organization", None) or "Cybersecurity Organization")
            cat = cls.safe_text(getattr(opp, "category", "Opportunity")).capitalize()
            op_type = cls.safe_text(getattr(opp, "opportunity_type", "") or "").replace("_", " ").capitalize()
            desc = cls.safe_text(getattr(opp, "description", "") or "", max_len=180)
            
            pricing_str = getattr(opp, "pricing", None)
            if pricing_str:
                cost_text = cls.safe_text(pricing_str)
                cost_color = "#16a34a" if "free" in pricing_str.lower() else "#0f172a"
            elif getattr(opp, "is_free", False) or getattr(opp, "price_amount", None) == 0:
                cost_text = "Free"
                cost_color = "#16a34a"
            elif getattr(opp, "price_amount", None):
                cost_text = f"${opp.price_amount:,.2f}"
                cost_color = "#0f172a"
            else:
                cost_text = "Free" if "free" in str(getattr(opp, "pricing_type", "")).lower() else "View Details"
                cost_color = "#16a34a" if cost_text == "Free" else "#475569"

            stipend_val = getattr(opp, "stipend", None)
            if stipend_val:
                stipend_text = cls.safe_text(stipend_val)
            elif getattr(opp, "stipend_amount", None):
                stipend_text = f"${opp.stipend_amount:,.2f}"
            else:
                stipend_text = None

            mode = "Remote" if getattr(opp, "remote", False) else "In-Person"
            mode_badge_bg = "#ecfdf5" if mode == "Remote" else "#f1f5f9"
            mode_badge_fg = "#047857" if mode == "Remote" else "#475569"

            deadline = getattr(opp, "deadline", None)
            deadline_str = str(deadline)[:10] if deadline else "Ongoing / Rolling"

            is_urgent = False
            if deadline and hasattr(deadline, "strftime"):
                days_left = (deadline - datetime.now(timezone.utc)).days
                if 0 <= days_left <= 7:
                    is_urgent = True

            opp_url = getattr(opp, "view_url", None) or getattr(opp, "url", "#")
            cta_url = cls.sanitize_url(opp_url)

            # Match reasons
            reasons = reasons_map.get(opp_id) or getattr(opp, "match_reasons", []) or []
            reasons_html = ""
            if reasons:
                reasons_items = "".join(f'<div style="font-size: 11px; color: #0369a1; padding: 2px 0;">&check; {cls.safe_text(r)}</div>' for r in reasons[:3])
                reasons_html = f"""
                <div style="background-color: #f0f9ff; border-left: 3px solid #0284c7; padding: 6px 10px; margin-top: 8px; border-radius: 0 4px 4px 0;">
                    <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: #0284c7; margin-bottom: 2px;">Why this matches you</div>
                    {reasons_items}
                </div>
                """

            urgent_badge = ""
            if is_urgent:
                urgent_badge = """
                <span style="display: inline-block; padding: 2px 8px; font-size: 10px; font-weight: 700; border-radius: 4px; background-color: #fef2f2; color: #dc2626; text-transform: uppercase; margin-left: 6px;">
                    🔥 Closing Soon
                </span>
                """

            # Opportunity card table
            cards_html.append(f"""
            <!-- Opportunity Card -->
            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 16px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <tr>
                    <td style="padding: 16px 20px;">
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                            <tr>
                                <td>
                                    <span style="display: inline-block; padding: 2px 8px; font-size: 10px; font-weight: 700; border-radius: 4px; background-color: #f0fdf4; color: #166534; text-transform: uppercase;">
                                        {cat}
                                    </span>
                                    {f'<span style="display: inline-block; padding: 2px 8px; font-size: 10px; font-weight: 700; border-radius: 4px; background-color: #eff6ff; color: #1d4ed8; text-transform: uppercase; margin-left: 6px;">{op_type}</span>' if op_type else ''}
                                    <span style="display: inline-block; padding: 2px 8px; font-size: 10px; font-weight: 700; border-radius: 4px; background-color: {mode_badge_bg}; color: {mode_badge_fg}; text-transform: uppercase; margin-left: 6px;">
                                        {mode}
                                    </span>
                                    {urgent_badge}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding-top: 8px;">
                                    <h3 style="margin: 0 0 4px 0; font-size: 16px; font-weight: 700; line-height: 1.3; color: #0f172a;">
                                        <a href="{cta_url}" target="_blank" rel="noopener noreferrer" style="color: #0284c7; text-decoration: none;">
                                            {title}
                                        </a>
                                    </h3>
                                    <div style="font-size: 12px; font-weight: 600; color: #64748b;">
                                        {org}
                                    </div>
                                </td>
                            </tr>
                            {f'<tr><td style="padding-top: 6px; font-size: 12px; line-height: 1.5; color: #475569;">{desc}</td></tr>' if desc else ''}
                            <tr>
                                <td style="padding-top: 12px;">
                                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="font-size: 12px; color: #334155; border-top: 1px solid #f1f5f9; padding-top: 8px;">
                                        <tr>
                                            <td width="50%" style="padding: 2px 0;">
                                                <span style="color: #94a3b8; font-size: 11px;">Deadline:</span> <strong style="color: {'#dc2626' if is_urgent else '#334155'};">{deadline_str}</strong>
                                            </td>
                                            <td width="50%" align="right" style="padding: 2px 0;">
                                                <span style="color: #94a3b8; font-size: 11px;">Cost:</span> <strong style="color: {cost_color};">{cost_text}</strong>
                                            </td>
                                        </tr>
                                        {f'<tr><td colspan="2" style="padding: 2px 0;"><span style="color: #94a3b8; font-size: 11px;">Stipend:</span> <strong style="color: #047857;">{stipend_text}</strong></td></tr>' if stipend_text else ''}
                                    </table>
                                </td>
                            </tr>
                            {f'<tr><td style="padding-top: 4px;">{reasons_html}</td></tr>' if reasons_html else ''}
                            <tr>
                                <td style="padding-top: 14px;" align="right">
                                    <a href="{cta_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #0284c7; color: #ffffff; font-size: 12px; font-weight: 700; text-decoration: none; padding: 8px 16px; border-radius: 6px; letter-spacing: 0.3px;">
                                        VIEW OPPORTUNITY &rarr;
                                    </a>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
            """)

        cards_body = "\n".join(cards_html) if cards_html else """
        <div style="padding: 24px; text-align: center; background-color: #ffffff; border-radius: 8px; border: 1px dashed #cbd5e1; color: #64748b; font-size: 13px;">
            No new opportunities match your current filter threshold today.
        </div>
        """

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CYBERSCOUT AI — {cls.safe_text(digest_title)}</title>
    <style>
        @media only screen and (max-width: 620px) {{
            .main-table {{ width: 100% !important; }}
            .content-padding {{ padding: 12px !important; }}
        }}
    </style>
</head>
<body style="margin: 0; padding: 0; background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #334155;">
    <!-- Container -->
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #0b1120; padding: 24px 0;">
        <tr>
            <td align="center">
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="600" class="main-table" style="background-color: #f8fafc; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.3);">
                    <!-- Brand Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #0a0e1a 0%, #0f172a 100%); padding: 24px 28px; border-bottom: 2px solid #0284c7;">
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                <tr>
                                    <td>
                                        <div style="font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">
                                            <span style="color: #38bdf8;">CYBERSCOUT</span> AI
                                        </div>
                                        <div style="font-size: 11px; color: #94a3b8; font-weight: 500; margin-top: 2px;">
                                            Intelligent Opportunity Discovery
                                        </div>
                                    </td>
                                    <td align="right">
                                        <span style="display: inline-block; padding: 4px 10px; font-size: 10px; font-weight: 700; border-radius: 20px; background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); text-transform: uppercase;">
                                            {cls.safe_text(period_label)}
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Digest Summary Banner -->
                    <tr>
                        <td style="padding: 20px 28px; background-color: #ffffff; border-bottom: 1px solid #e2e8f0;">
                            <h2 style="margin: 0 0 4px 0; font-size: 18px; font-weight: 800; color: #0f172a;">
                                🎯 {cls.safe_text(digest_title)}
                            </h2>
                            <p style="margin: 0; font-size: 13px; color: #64748b;">
                                <strong>{len(opps)} new opportunities matched to your interests</strong> &bull; {now_str}
                            </p>
                        </td>
                    </tr>

                    <!-- Opportunity Cards List -->
                    <tr>
                        <td class="content-padding" style="padding: 20px 28px; background-color: #f8fafc;">
                            {cards_body}
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #0f172a; padding: 20px 28px; color: #64748b; font-size: 11px; line-height: 1.6; text-align: center; border-top: 1px solid #1e293b;">
                            <div style="margin-bottom: 8px;">
                                <a href="{app_url}/notifications" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; text-decoration: none; font-weight: 600; margin: 0 8px;">Notification Settings</a> &bull;
                                <a href="{app_url}/profile" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; text-decoration: none; font-weight: 600; margin: 0 8px;">Career Profile</a> &bull;
                                <a href="{app_url}/opportunities" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; text-decoration: none; font-weight: 600; margin: 0 8px;">All Opportunities</a>
                            </div>
                            <div>
                                Generated on {now_iso} by CyberScout AI.
                            </div>
                            <div style="margin-top: 4px; color: #475569;">
                                This bulletin was dispatched to {cls.safe_text(recipient_email)} according to your verified preferences.
                            </div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

        return html_content, plain_text
