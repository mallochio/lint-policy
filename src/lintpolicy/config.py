"""Load lintpolicy configuration for a target repository.

Configuration lives in ``pyproject.toml`` under ``[tool.lintpolicy]`` or in a
standalone ``.lintpolicy.toml`` with the same keys at top level. Every key is
optional; defaults target a standard ``src``/``scripts``/``tests`` layout.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_ALLOWED_DIRECTIVES: tuple[str, ...] = (
    "noqa",
    "type: ignore",
    "pyright: ignore",
    "pragma: no cover",
    "fmt:",
    "ruff:",
    "nosec",
)
DEFAULT_SOURCE_ROOTS: tuple[str, ...] = ("src", "scripts")
DEFAULT_TEST_ROOTS: tuple[str, ...] = ("tests",)
DEFAULT_BASELINE_NAME = ".lintpolicy-baseline.json"
DEFAULT_FILE_LINES = 300
DEFAULT_FUNCTION_LINES = 30


@dataclass(frozen=True)
class Config:
    """Resolved lintpolicy configuration for one repository."""

    root: Path
    source_roots: tuple[str, ...]
    test_roots: tuple[str, ...]
    baseline_path: Path
    comment_roots: tuple[str, ...]
    comment_allow: tuple[str, ...]
    docstring_roots: tuple[str, ...]
    limit_roots: tuple[str, ...]
    file_line_limit: int
    function_line_limit: int
    suppression_roots: tuple[str, ...]
    suppression_require_reason: bool
    toplevel_roots: tuple[str, ...]
    reinvention_roots: tuple[str, ...]
    numeric_roots: tuple[str, ...]


def load_config(start: Path | None = None) -> Config:
    """Load configuration using the repository root as the base."""
    root = (start or Path.cwd()).resolve()
    table = _load_table(root)
    source = _string_tuple(table, "source-roots", DEFAULT_SOURCE_ROOTS)
    tests = _string_tuple(table, "test-roots", DEFAULT_TEST_ROOTS)
    comments = _section(table, "comments")
    docstrings = _section(table, "docstrings")
    limits = _section(table, "limits")
    suppressions = _section(table, "suppressions")
    top_level = _section(table, "top-level")
    reinvention = _section(table, "reinvention")
    numeric = _section(table, "numeric")
    return Config(
        root=root,
        source_roots=source,
        test_roots=tests,
        baseline_path=root / _string(table, "baseline", DEFAULT_BASELINE_NAME),
        comment_roots=tuple(_roots(comments, source + tests)),
        comment_allow=_string_tuple(comments, "allow", DEFAULT_ALLOWED_DIRECTIVES),
        docstring_roots=tuple(_roots(docstrings, source)),
        limit_roots=tuple(_roots(limits, source + tests)),
        file_line_limit=_int(limits, "file-lines", DEFAULT_FILE_LINES),
        function_line_limit=_int(limits, "function-lines", DEFAULT_FUNCTION_LINES),
        suppression_roots=tuple(_roots(suppressions, source + tests)),
        suppression_require_reason=_bool(suppressions, "require-reason", True),
        toplevel_roots=tuple(_roots(top_level, source + tests)),
        reinvention_roots=tuple(_roots(reinvention, source + tests)),
        numeric_roots=tuple(_roots(numeric, source)),
    )


def _load_table(root: Path) -> dict[str, Any]:
    """Return the lintpolicy table from pyproject or the standalone file."""
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        table = data.get("tool", {}).get("lintpolicy")
        if isinstance(table, dict):
            return table
    standalone = root / ".lintpolicy.toml"
    if standalone.is_file():
        return tomllib.loads(standalone.read_text(encoding="utf-8"))
    return {}


def _section(table: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a nested configuration section, or an empty mapping."""
    value = table.get(key)
    return value if isinstance(value, dict) else {}


def _roots(section: dict[str, Any], fallback: tuple[str, ...]) -> list[str]:
    """Return the section roots, or the fallback roots."""
    value = section.get("roots")
    if value is None:
        return list(fallback)
    return [str(item) for item in value]


def _string(table: dict[str, Any], key: str, fallback: str) -> str:
    """Return a string configuration value, or the fallback."""
    value = table.get(key)
    return value if isinstance(value, str) else fallback


def _string_tuple(table: dict[str, Any], key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    """Return a string-list configuration value, or the fallback."""
    value = table.get(key)
    if value is None:
        return fallback
    return tuple(str(item) for item in value)


def _int(section: dict[str, Any], key: str, fallback: int) -> int:
    """Return an integer configuration value, or the fallback."""
    value = section.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return fallback


def _bool(section: dict[str, Any], key: str, fallback: bool) -> bool:
    """Return a boolean configuration value, or the fallback."""
    value = section.get(key)
    return value if isinstance(value, bool) else fallback
