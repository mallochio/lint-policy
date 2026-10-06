"""Discover the Python files that policy checks apply to."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "notebooks",
        "venv",
    }
)


def iter_python_files(root: Path, roots: Sequence[str]) -> Iterator[Path]:
    """Yield Python files under each configured root."""
    for relative in roots:
        base = root / relative
        if base.is_file() and base.suffix == ".py":
            yield base
            continue
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if _is_skipped(base, path):
                continue
            yield path


def relative_path(path: Path, root: Path) -> str:
    """Return the repository-relative POSIX path, or the absolute path."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _is_skipped(base: Path, path: Path) -> bool:
    """Return whether a discovered file sits under a skipped directory."""
    parts = path.relative_to(base).parts[:-1]
    return any(part in SKIP_DIR_NAMES for part in parts)
