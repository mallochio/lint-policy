"""Require a docstring on every module, class, and function in source roots.

Tests are out of scope by default because ``docstring_roots`` defaults to the
source roots. ``@overload`` stubs and property setters and deleters are exempt,
because a docstring on the implementation or getter covers them.
"""

from __future__ import annotations

import ast
from pathlib import Path

from lintpolicy.baseline import Baseline, over_budget_keys, verify_counts
from lintpolicy.config import Config, load_config
from lintpolicy.discovery import iter_python_files, relative_path
from lintpolicy.reporting import Finding, Scan, report
from lintpolicy.structure import nested_blocks

EXEMPT_DECORATORS = {"overload", "typing.overload"}
EXEMPT_DECORATOR_SUFFIXES = (".setter", ".deleter")


def scan(config: Config) -> Scan:
    """Return docstring findings and per-file counts."""
    findings: list[Finding] = []
    counts: dict[str, int] = {}
    for path in iter_python_files(config.root, config.docstring_roots, config.docstring_exclude):
        relative = relative_path(path, config.root)
        file_findings = check_file(relative, path)
        if not file_findings:
            continue
        findings.extend(file_findings)
        counts[relative] = len(file_findings)
    return Scan(tuple(findings), counts)


def check_file(relative: str, path: Path) -> list[Finding]:
    """Return missing docstrings in one file."""
    tree = _parse(path)
    if tree is None:
        return [Finding(relative, 1, "unable to parse for the docstring check")]
    findings = _missing_definitions(relative, tree)
    if ast.get_docstring(tree, clean=False) is None:
        findings.append(Finding(relative, 1, "module docstring is required"))
    return findings


def _parse(path: Path) -> ast.Module | None:
    """Parse a Python file, or return None when that fails."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None


def _missing_definitions(relative: str, tree: ast.Module) -> list[Finding]:
    """Return findings for definitions without a docstring."""
    findings: list[Finding] = []
    _visit_block(relative, tree.body, [], findings)
    return findings


def _visit_block(relative: str, block: list[ast.stmt], stack: list[str], findings: list[Finding]) -> None:
    """Walk one statement block and record missing docstrings."""
    for node in block:
        if isinstance(node, ast.ClassDef):
            _record(relative, node, "class", [*stack, node.name], findings)
            _visit_block(relative, node.body, [*stack, node.name], findings)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _record(relative, node, "function", [*stack, node.name], findings)
            _visit_block(relative, node.body, [*stack, node.name], findings)
        else:
            for nested in nested_blocks(node):
                _visit_block(relative, nested, stack, findings)


def _record(
    relative: str,
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    kind: str,
    name_parts: list[str],
    findings: list[Finding],
) -> None:
    """Record a missing docstring for one class or function."""
    if ast.get_docstring(node, clean=False) is not None:
        return
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_exempt(node):
        return
    name = ".".join(name_parts)
    findings.append(Finding(relative, node.lineno, f"missing {kind} docstring: {name}"))


def _is_exempt(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return whether overload stubs and accessors are exempt."""
    for decorator in node.decorator_list:
        name = _decorator_name(decorator)
        if name in EXEMPT_DECORATORS:
            return True
        if name.endswith(EXEMPT_DECORATOR_SUFFIXES):
            return True
    return False


def _decorator_name(decorator: ast.expr) -> str:
    """Return the dotted name of a decorator expression."""
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    return ast.unparse(decorator)


def main() -> int:
    """Run the docstring policy on the configured roots."""
    config = load_config()
    result = scan(config)
    budgets = Baseline.load(config.baseline_path).section("docstrings")
    over, stale = verify_counts("docstrings", result.counts, budgets)
    unbudgeted = over_budget_keys(result.counts, budgets)
    findings = [finding for finding in result.findings if finding.path in unbudgeted]
    return report("docstrings", findings, [*over, *stale])
