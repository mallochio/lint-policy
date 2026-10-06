"""Flag hand-rolled implementations of well-known idioms.

See ``lintpolicy.reinvention_rules`` for the detected shapes. Algorithm-level
duplication of an external library cannot be detected syntactically; this
hook covers the high-frequency idiom shapes and names the replacement.
"""

from __future__ import annotations

import ast
from pathlib import Path

from lintpolicy.baseline import Baseline, over_budget_keys, verify_counts
from lintpolicy.config import Config, load_config
from lintpolicy.discovery import iter_python_files, relative_path
from lintpolicy.reporting import Finding, Scan, report
from lintpolicy.reinvention_rules import detect


def scan(config: Config) -> Scan:
    """Return reinvention findings and per-file counts."""
    findings: list[Finding] = []
    counts: dict[str, int] = {}
    for path in iter_python_files(config.root, config.reinvention_roots, config.reinvention_exclude):
        relative = relative_path(path, config.root)
        file_findings = check_file(relative, path)
        if not file_findings:
            continue
        findings.extend(file_findings)
        counts[relative] = len(file_findings)
    return Scan(tuple(findings), counts)


def check_file(relative: str, path: Path) -> list[Finding]:
    """Return reinvention findings for one file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []
    findings: list[Finding] = []
    for node in ast.walk(tree):
        message = detect(node)
        if message is not None:
            findings.append(Finding(relative, node.lineno, message))
    return findings


def main() -> int:
    """Run the reinvention policy on the configured roots."""
    config = load_config()
    result = scan(config)
    budgets = Baseline.load(config.baseline_path).section("reinvention")
    over, stale = verify_counts("reinvention", result.counts, budgets)
    unbudgeted = over_budget_keys(result.counts, budgets)
    findings = [finding for finding in result.findings if finding.path in unbudgeted]
    return report("reinvention", findings, [*over, *stale])
