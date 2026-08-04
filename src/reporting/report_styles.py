"""
Style rules, color themes, and formatting helpers for python-docx report generation.
"""

from typing import Any


class ReportStyles:
    """Design System tokens and style constants for DOCX documents."""

    # Color Palette (HEX)
    COLOR_PRIMARY_HEX = "0F172A"       # Dark Slate / Navy
    COLOR_SECONDARY_HEX = "0EA5E9"     # Cyber Sky Blue
    COLOR_ACCENT_HEX = "10B981"        # Emerald Verified
    COLOR_DARK_TEXT_HEX = "1E293B"     # Slate Text
    COLOR_MUTED_TEXT_HEX = "64748B"    # Muted Gray
    COLOR_LIGHT_BG_HEX = "F8FAFC"      # Soft Gray Shading
    COLOR_BORDER_HEX = "E2E8F0"        # Light Border

    # Fonts
    FONT_FAMILY_PRIMARY = "Segoe UI"
    FONT_FAMILY_SECONDARY = "Calibri"

    @staticmethod
    def set_cell_background(cell: Any, hex_color: str) -> None:
        """Sets cell background shading color via XML parsing."""
        try:
            from docx.oxml import parse_xml
            from docx.oxml.ns import nsdecls
            shading_xml = f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>'
            cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))
        except Exception:
            pass

    @staticmethod
    def set_cell_margins(cell: Any, top: int = 100, bottom: int = 100, left: int = 150, right: int = 150) -> None:
        """Sets table cell padding margins via XML attributes."""
        try:
            from docx.oxml import parse_xml
            from docx.oxml.ns import nsdecls
            tcPr = cell._tc.get_or_add_tcPr()
            margins_xml = f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>'
            tcPr.append(parse_xml(margins_xml))
        except Exception:
            pass
