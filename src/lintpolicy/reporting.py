"""Shared finding types and terminal reporting."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Finding:
    """One policy violation."""

    path: str
    line: int
    message: str


@dataclass(frozen=True)
class Scan:
    """Findings plus measurement keys for the baseline ratchet."""

    findings: tuple[Finding, ...]
    counts: dict[str, int] = field(default_factory=dict)


def report(tool: str, findings: Sequence[Finding], errors: Sequence[str]) -> int:
    """Print findings and errors, and return a process status."""
    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.message}")
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    total = len(findings) + len(errors)
    if total:
        print(f"{tool}: {total} violation(s)", file=sys.stderr)
        return 1
    print(f"{tool}: ok")
    return 0
