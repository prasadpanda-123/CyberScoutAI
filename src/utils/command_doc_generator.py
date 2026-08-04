"""
Automatic CLI Command Documentation Generator for CyberScout AI.

Introspects argparse parser definitions to automatically generate:
1. commands.txt  - Plain text command reference grouped by categories
2. commands.md   - GitHub-flavored Markdown reference with tables and workflow guides
"""

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.core.constants import PROJECT_ROOT
from src.core.logging import get_logger

logger = get_logger(__name__)

# Category mapping definitions
CATEGORY_MAPPINGS = {
    "version": ["--version"],
    "system": ["--health", "--config-check", "--db-check"],
    "automation": ["--run-once", "--daemon", "--dry-run", "--scheduler-status", "--metrics"],
    "email": ["--email-test"],
    "dashboard": ["--dashboard", "--web"],
    "configuration": ["--validate-config", "--validate-sources", "--provider-health", "--config-report"],
    "environment": ["--env-status", "--github-status"],
    "documentation": ["--generate-command-docs"],
    "help": ["--help", "-h"],
}

CATEGORY_HEADERS = {
    "version": "VERSION",
    "system": "SYSTEM",
    "automation": "AUTOMATION",
    "email": "EMAIL",
    "dashboard": "DASHBOARD",
    "configuration": "CONFIGURATION",
    "environment": "ENVIRONMENT",
    "documentation": "DOCUMENTATION",
    "help": "HELP",
}


def introspect_parser(parser: argparse.ArgumentParser) -> List[Dict[str, str]]:
    """
    Introspects argparse actions and extracts flags, option strings, and help strings.

    Args:
        parser: Initialized argparse.ArgumentParser.

    Returns:
        List of dictionaries containing option details.
    """
    entries = []
    for action in parser._actions:
        if not action.option_strings:
            continue
        
        long_flag = next((opt for opt in action.option_strings if opt.startswith("--")), action.option_strings[0])
        short_flag = next((opt for opt in action.option_strings if opt.startswith("-") and not opt.startswith("--")), None)
        
        flags_str = ", ".join(action.option_strings)
        help_str = action.help or "No description provided."

        # Assign category based on flags
        category = "system"
        for cat, flags in CATEGORY_MAPPINGS.items():
            if any(opt in flags for opt in action.option_strings):
                category = cat
                break

        entries.append({
            "category": category,
            "long_flag": long_flag,
            "short_flag": short_flag,
            "flags_str": flags_str,
            "help": help_str,
            "command": f"python main.py {long_flag}",
        })

    return entries


def generate_commands_txt(entries: List[Dict[str, str]], root_dir: Optional[Path] = None) -> Path:
    """
    Generates commands.txt plain text reference.

    Args:
        entries: Extracted parser entries.
        root_dir: Target output directory.

    Returns:
        Path object to created commands.txt file.
    """
    out_dir = root_dir or PROJECT_ROOT
    target_path = out_dir / "commands.txt"

    lines = [
        "===========================================================================",
        "CyberScout AI CLI Reference",
        "===========================================================================",
        "",
        "VERSION",
        "",
        "python main.py --version",
        "    Show application version",
        "",
        "===========================================================================",
        "SYSTEM",
        "===========================================================================",
        "",
        "python main.py",
        "    Start default application bootstrap and graceful shutdown",
        "",
    ]

    grouped: Dict[str, List[Dict[str, str]]] = {}
    for entry in entries:
        cat = entry["category"]
        grouped.setdefault(cat, []).append(entry)

    for cat_key in ["system", "automation", "email", "dashboard", "configuration", "environment", "documentation", "help"]:
        if cat_key not in grouped:
            continue

        cat_title = CATEGORY_HEADERS.get(cat_key, cat_key.upper())
        if cat_key != "system":
            lines.append("===========================================================================")
            lines.append(cat_title)
            lines.append("===========================================================================")
            lines.append("")

        for item in grouped[cat_key]:
            lines.append(f"{item['command']}")
            lines.append(f"    {item['help']}")
            lines.append("")

    content = "\n".join(lines) + "\n"
    target_path.write_text(content, encoding="utf-8")
    logger.info(f"Successfully generated '{target_path}'.")
    return target_path


def generate_commands_md(entries: List[Dict[str, str]], root_dir: Optional[Path] = None) -> Path:
    """
    Generates commands.md GitHub Markdown reference with tables and workflows.

    Args:
        entries: Extracted parser entries.
        root_dir: Target output directory.

    Returns:
        Path object to created commands.md file.
    """
    out_dir = root_dir or PROJECT_ROOT
    target_path = out_dir / "commands.md"

    lines = [
        "# CyberScout AI — CLI Command Reference & Workflow Guide",
        "",
        "> Complete command reference and operational workflow guide for CyberScout AI.",
        "",
        "---",
        "",
        "## 📌 Quick Reference Table",
        "",
        "| Category | Command | Description |",
        "|---|---|---|",
        "| **SYSTEM** | `python main.py` | Run default application bootstrap & shutdown |",
    ]

    grouped: Dict[str, List[Dict[str, str]]] = {}
    for entry in entries:
        cat = entry["category"]
        grouped.setdefault(cat, []).append(entry)

    for entry in entries:
        cat_title = CATEGORY_HEADERS.get(entry["category"], entry["category"].upper())
        lines.append(f"| **{cat_title}** | `{entry['command']}` | {entry['help']} |")

    lines.extend([
        "",
        "---",
        "",
        "## 🛠️ Common Operational Workflows",
        "",
        "### 1. Fresh Installation Workflow",
        "```bash",
        "# Clone repository & set up environment",
        "git clone https://github.com/CyberScoutAI/cyberscout-ai.git",
        "cd CyberScoutAI",
        "python -m venv venv",
        "source venv/bin/activate  # Or venv\\Scripts\\activate on Windows",
        "pip install -r requirements.txt",
        "",
        "# Verify configuration and database setup",
        "python main.py --env-status",
        "python main.py --health",
        "```",
        "",
        "### 2. Daily Pipeline Scan Workflow",
        "```bash",
        "# Run a single collection & ranking iteration",
        "python main.py --run-once",
        "",
        "# Run single iteration in dry-run mode (skip DB writes & email)",
        "python main.py --run-once --dry-run",
        "```",
        "",
        "### 3. Health & Environment Diagnostic Check",
        "```bash",
        "# Check complete subsystem health",
        "python main.py --health",
        "",
        "# Check local .env setup",
        "python main.py --env-status",
        "",
        "# Check GitHub API rate limit status",
        "python main.py --github-status",
        "```",
        "",
        "### 4. System Debugging Workflow",
        "```bash",
        "# Verify YAML configuration files",
        "python main.py --validate-config",
        "",
        "# Audit source definitions & capability mappings",
        "python main.py --validate-sources",
        "",
        "# Check provider DNS reachability",
        "python main.py --provider-health",
        "```",
        "",
        "### 5. Web Dashboard Launch Workflow",
        "```bash",
        "# Launch browser control center on http://127.0.0.1:5000",
        "python main.py --dashboard",
        "```",
        "",
        "### 6. Continuous Automation Daemon",
        "```bash",
        "# Start background scheduler loop",
        "python main.py --daemon",
        "```",
        "",
        "### 7. Email Digest Testing Workflow",
        "```bash",
        "# Send test email digest report",
        "python main.py --email-test",
        "```",
        "",
        "### 8. CLI Command Documentation Generator",
        "```bash",
        "# Automatically regenerate commands.txt and commands.md",
        "python main.py --generate-command-docs",
        "```",
    ])

    content = "\n".join(lines) + "\n"
    target_path.write_text(content, encoding="utf-8")
    logger.info(f"Successfully generated '{target_path}'.")
    return target_path


def generate_all_command_docs(parser: argparse.ArgumentParser, root_dir: Optional[Path] = None) -> Tuple[Path, Path]:
    """
    Introspects parser and generates both commands.txt and commands.md.

    Args:
        parser: argparse.ArgumentParser object.
        root_dir: Target output directory.

    Returns:
        Tuple of (path_txt, path_md).
    """
    entries = introspect_parser(parser)
    txt_path = generate_commands_txt(entries, root_dir=root_dir)
    md_path = generate_commands_md(entries, root_dir=root_dir)
    return txt_path, md_path
