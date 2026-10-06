"""Require suppression directives to carry a reason and a baseline entry.

Existing directives are grandfathered through the baseline. A directive that
is not in the baseline fails, so an agent cannot add `# noqa` or
`# type: ignore` without a deliberate, reviewable baseline change.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from lintpolicy.baseline import Baseline
from lintpolicy.config import Config, load_config
from lintpolicy.directives import iter_comments, normalize, starts_with_directive
from lintpolicy.discovery import iter_python_files, relative_path
from lintpolicy.reporting import Finding, report


@dataclass(frozen=True)
class SuppressionScan:
    """Directive entries with their locations."""

    entries: dict[str, str | None]
    locations: dict[str, tuple[str, int]]


def scan(config: Config) -> SuppressionScan:
    """Collect suppression directives from the configured roots."""
    entries: dict[str, str | None] = {}
    locations: dict[str, tuple[str, int]] = {}
    for path in iter_python_files(config.root, config.suppression_roots, config.suppression_exclude):
        relative = relative_path(path, config.root)
        _collect_file(relative, path, config.comment_allow, entries, locations)
    return SuppressionScan(entries, locations)


def _collect_file(
    relative: str,
    path: Path,
    allow: Sequence[str],
    entries: dict[str, str | None],
    locations: dict[str, tuple[str, int]],
) -> None:
    """Collect directives from one file into the entries map."""
    try:
        raw = path.read_bytes()
    except OSError:
        return
    for comment, line in iter_comments(raw):
        body = comment[1:].strip()
        if not starts_with_directive(body, allow):
            continue
        key = _unique_key(relative, normalize(body), entries)
        entries[key] = _reason(body)
        locations[key] = (relative, line)


def _unique_key(relative: str, body: str, entries: dict[str, str | None]) -> str:
    """Return a stable key for one directive occurrence."""
    base = f"{relative}|{body}"
    occurrence = 1
    key = base
    while key in entries:
        occurrence += 1
        key = f"{base}#{occurrence}"
    return key


def _reason(body: str) -> str | None:
    """Return the text after the first ' - ' separator, if present."""
    if " - " not in body:
        return None
    text = body.split(" - ", 1)[1].strip()
    return text or None


def _new_finding(result: SuppressionScan, key: str, require_reason: bool) -> Finding:
    """Build the finding for an unregistered directive."""
    relative, line = result.locations[key]
    if require_reason and result.entries[key] is None:
        message = "new suppression needs a reason: add ' - reason: <why>' and register it in the baseline"
    else:
        message = "new suppression is not registered: add it to the baseline"
    return Finding(relative, line, message)


def main() -> int:
    """Run the suppression policy on the configured roots."""
    config = load_config()
    result = scan(config)
    baseline = Baseline.load(config.baseline_path).section("suppressions")
    missing = [key for key in sorted(result.entries) if key not in baseline]
    stale = [
        f"suppressions: baseline entry is stale, remove it: {key}"
        for key in sorted(baseline)
        if key not in result.entries
    ]
    findings = [_new_finding(result, key, config.suppression_require_reason) for key in missing]
    return report("suppressions", findings, stale)
