"""
Template Loader for CyberScout AI.
"""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.core.constants import PROJECT_ROOT
from src.notifier.exceptions import TemplateError


class TemplateLoader:
    """
    Loads templates securely from templates/ directory.
    """

    def __init__(self, template_dir: Path = PROJECT_ROOT / "templates"):
        self.template_dir = template_dir
        if not self.template_dir.exists():
            self.template_dir.mkdir(parents=True, exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def load_template(self, name: str):
        """Loads target Jinja template by name."""
        try:
            return self.env.get_template(name)
        except Exception as e:
            raise TemplateError(f"Could not load template '{name}': {e}", original_exception=e)
