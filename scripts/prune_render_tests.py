from __future__ import annotations

import os
import shutil
from pathlib import Path


def prune_tests(project_root: Path) -> int:
    root = project_root.resolve()
    required_files = ("Procfile", "requirements.txt", "wsgi.py")
    if root == Path(root.anchor) or not all((root / name).is_file() for name in required_files):
        raise RuntimeError("Refusing to prune tests outside the project root.")

    tests_dir = root / "tests"
    if not tests_dir.exists():
        return 0
    if tests_dir.is_symlink() or tests_dir.resolve().parent != root:
        raise RuntimeError("Refusing to prune a tests path outside the project root.")

    removed_count = sum(path.is_file() for path in tests_dir.rglob("*"))
    shutil.rmtree(tests_dir)
    return removed_count


def main() -> int:
    if os.environ.get("RENDER") != "true":
        raise SystemExit("Test pruning is allowed only in a Render build environment.")

    root = Path(__file__).resolve().parent.parent
    removed_count = prune_tests(root)
    print(f"Removed {removed_count} test files from the Render build artifact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
