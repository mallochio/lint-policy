"""Helpers for lintpolicy behavior tests."""

from __future__ import annotations

import json
from pathlib import Path


def write_python(root: Path, relative: str, source: str) -> Path:
    """Write a Python file under root and return its path."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def write_config(root: Path, text: str) -> Path:
    """Write a standalone lintpolicy config and return its path."""
    path = root / ".lintpolicy.toml"
    path.write_text(text, encoding="utf-8")
    return path


def write_baseline(root: Path, section: str, budgets: dict[str, int]) -> Path:
    """Write a minimal baseline file for one tool section."""
    path = root / ".lintpolicy-baseline.json"
    path.write_text(json.dumps({"version": 1, section: budgets}), encoding="utf-8")
    return path
