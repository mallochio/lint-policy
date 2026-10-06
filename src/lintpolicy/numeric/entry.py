"""Run the configured numeric guard scan and report baseline status."""

from __future__ import annotations

import ast

from lintpolicy.baseline import Baseline, over_budget_keys, verify_counts
from lintpolicy.config import Config, load_config
from lintpolicy.discovery import iter_python_files, relative_path
from lintpolicy.numeric.analysis import scan_tree
from lintpolicy.reporting import Finding, Scan, report


def scan(config: Config) -> Scan:
    """Scan configured Python roots and return numeric guard findings."""
    findings: list[Finding] = []
    counts: dict[str, int] = {}
    for path in iter_python_files(config.root, config.numeric_roots, config.numeric_exclude):
        relative = relative_path(path, config.root)
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
            file_findings = [Finding(relative, line, message) for line, message in scan_tree(tree)]
        except SyntaxError as error:
            file_findings = [Finding(relative, error.lineno or 1, f"syntax error: {error.msg}")]
        findings.extend(file_findings)
        if file_findings:
            counts[relative] = len(file_findings)
    return Scan(tuple(findings), counts)


def main() -> int:
    """Run the scan, verify its baseline budgets, and report the result."""
    config = load_config()
    result = scan(config)
    budgets = Baseline.load(config.baseline_path).section("numeric")
    over, stale = verify_counts("numeric", result.counts, budgets)
    unbudgeted = over_budget_keys(result.counts, budgets)
    findings = [finding for finding in result.findings if finding.path in unbudgeted]
    return report("numeric", findings, [*over, *stale])
