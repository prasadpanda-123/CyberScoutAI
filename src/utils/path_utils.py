"""
Path manipulation, security, and resolution utilities for CyberScout AI.
"""

from pathlib import Path
from typing import Union

from src.core.constants import PROJECT_ROOT


def ensure_dir(dir_path: Union[str, Path]) -> Path:
    """
    Ensures that a directory exists, creating parent directories if necessary.

    Args:
        dir_path: Directory path.

    Returns:
        Path object of the created/verified directory.
    """
    path = Path(dir_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_relative_path(path: Union[str, Path]) -> Path:
    """
    Returns path relative to project root if possible, or original path.

    Args:
        path: Input file path.

    Returns:
        Path object relative to PROJECT_ROOT.
    """
    p = Path(path).resolve()
    try:
        return p.relative_to(PROJECT_ROOT)
    except ValueError:
        return p


def is_safe_path(target_path: Union[str, Path], base_dir: Union[str, Path] = PROJECT_ROOT) -> bool:
    """
    Validates whether a target path stays safely within base_dir (prevents directory traversal).

    Args:
        target_path: Candidate file or directory path.
        base_dir: Root container directory. Defaults to PROJECT_ROOT.

    Returns:
        True if path is inside base_dir, False if path attempts traversal.
    """
    try:
        resolved_target = Path(target_path).resolve()
        resolved_base = Path(base_dir).resolve()
        return resolved_target.is_relative_to(resolved_base)
    except Exception:
        return False
