"""
File I/O utilities for CyberScout AI.
"""

import json
from pathlib import Path
from typing import Any, Union

from src.core.exceptions import ValidationError


def read_json_file(file_path: Union[str, Path]) -> Any:
    """
    Reads and parses a JSON file with error validation.

    Args:
        file_path: Path to JSON file.

    Returns:
        Parsed JSON data object.
    """
    path = Path(file_path)
    if not path.exists():
        raise ValidationError(f"JSON file not found at '{file_path}'.")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON content in '{file_path}': {e}", original_exception=e)
    except Exception as e:
        raise ValidationError(f"Failed to read JSON file '{file_path}': {e}", original_exception=e)


def write_json_file(file_path: Union[str, Path], data: Any, indent: int = 2) -> None:
    """
    Writes data object to a formatted JSON file with parent directory auto-creation.

    Args:
        file_path: Path to target file.
        data: Data object to serialize.
        indent: Indentation level.
    """
    path = Path(file_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
    except Exception as e:
        raise ValidationError(f"Failed to write JSON file '{file_path}': {e}", original_exception=e)
