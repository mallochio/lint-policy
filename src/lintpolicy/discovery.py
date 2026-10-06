"""Discover the Python files that policy checks apply to."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from fnmatch import fnmatchcase
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


def iter_python_files(root: Path, roots: Sequence[str], exclude: Sequence[str] = ()) -> Iterator[Path]:
    """Yield Python files under each configured root, minus exclusions."""
    for relative in roots:
        base = root / relative
        if base.is_file() and base.suffix == ".py":
            if not _excluded(base, root, exclude):
                yield base
            continue
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if _is_skipped(base, path) or _excluded(path, root, exclude):
                continue
            yield path


def path_matches(relative: str, patterns: Sequence[str]) -> bool:
    """Return whether a repo-relative POSIX path matches an exclude pattern."""
    for pattern in patterns:
        if fnmatchcase(relative, pattern):
            return True
        if pattern.startswith("**/") and fnmatchcase(relative, pattern[3:]):
            return True
        if pattern.endswith("/**") and fnmatchcase(relative, pattern[:-3]):
            return True
    return False


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


def _excluded(path: Path, root: Path, patterns: Sequence[str]) -> bool:
    """Return whether a discovered file matches an exclusion pattern."""
    if not patterns:
        return False
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return False
    return path_matches(relative, patterns)
