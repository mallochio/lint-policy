"""Require imports and module-level assignments at the top of a file.

The import region covers the module docstring, imports, import fallback
blocks (``try``/``except`` or conditional blocks whose bodies hold only
imports), ``if TYPE_CHECKING:`` blocks, and an ``__all__`` assignment. An
import outside that region, or any import inside a function or class, fails.

A module-level assignment that appears after the first class or function
definition fails. Assignments nested in a ``__main__`` guard are exempt.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Sequence
from pathlib import Path

from lintpolicy.baseline import Baseline, verify_counts
from lintpolicy.config import Config, load_config
from lintpolicy.discovery import iter_python_files, relative_path
from lintpolicy.reporting import Finding, Scan, report
from lintpolicy.structure import is_docstring, nested_blocks


def scan(config: Config) -> Scan:
    """Return ordering findings and per-file counts."""
    findings: list[Finding] = []
    counts: dict[str, int] = {}
    for path in iter_python_files(config.root, config.toplevel_roots, config.toplevel_exclude):
        relative = relative_path(path, config.root)
        file_findings = check_file(relative, path)
        if not file_findings:
            continue
        findings.extend(file_findings)
        counts[relative] = len(file_findings)
    return Scan(tuple(findings), counts)


def check_file(relative: str, path: Path) -> list[Finding]:
    """Return ordering findings for one file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []
    body = tree.body
    region_end = _import_region_end(body)
    findings = _late_imports(relative, body, region_end)
    findings.extend(_definition_imports(relative, body, []))
    findings.extend(_late_assignments(relative, body))
    return findings


def _import_region_end(body: Sequence[ast.stmt]) -> int:
    """Return the index of the first statement outside the import region."""
    for index, stmt in enumerate(body):
        if not _in_import_region(stmt):
            return index
    return len(body)


def _in_import_region(stmt: ast.stmt) -> bool:
    """Return whether a statement belongs to the top import region."""
    if is_docstring(stmt) or isinstance(stmt, (ast.Import, ast.ImportFrom)):
        return True
    if _is_all_assignment(stmt):
        return True
    if isinstance(stmt, ast.If) and _is_type_checking(stmt.test):
        return _holds_only_imports(stmt.body)
    if isinstance(stmt, ast.If):
        return _holds_only_imports(stmt.body) and _holds_only_imports(stmt.orelse)
    if isinstance(stmt, ast.Try):
        return _holds_only_imports(stmt.body) and all(_holds_only_imports(h.body) for h in stmt.handlers)
    return False


def _holds_only_imports(block: Sequence[ast.stmt]) -> bool:
    """Return whether every statement is part of the import region."""
    return all(_in_import_region(stmt) for stmt in block)


def _is_all_assignment(stmt: ast.stmt) -> bool:
    """Return whether a statement assigns to ``__all__``."""
    if isinstance(stmt, ast.Assign):
        return any(isinstance(target, ast.Name) and target.id == "__all__" for target in stmt.targets)
    if isinstance(stmt, ast.AnnAssign):
        return isinstance(stmt.target, ast.Name) and stmt.target.id == "__all__"
    return False


def _is_type_checking(test: ast.expr) -> bool:
    """Return whether an if test is ``TYPE_CHECKING``."""
    return isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"


def _late_imports(relative: str, body: Sequence[ast.stmt], region_end: int) -> list[Finding]:
    """Return imports that appear after the import region."""
    findings: list[Finding] = []
    for stmt in body[region_end:]:
        for imported in _imports_outside_definitions(stmt):
            message = f"import is not at the top of the file: {_render(imported)}; move it into the import region"
            findings.append(Finding(relative, imported.lineno, message))
    return findings


def _definition_imports(relative: str, block: Sequence[ast.stmt], stack: list[str]) -> list[Finding]:
    """Return imports that appear inside a function or class body."""
    findings: list[Finding] = []
    for node in block:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            qualname = ".".join([*stack, node.name])
            findings.extend(_imports_in_definition(relative, node, kind, qualname))
            findings.extend(_definition_imports(relative, node.body, [*stack, node.name]))
        else:
            for nested in nested_blocks(node):
                findings.extend(_definition_imports(relative, nested, stack))
    return findings


def _imports_in_definition(relative: str, node: ast.stmt, kind: str, qualname: str) -> list[Finding]:
    """Return imports found directly under one definition."""
    findings: list[Finding] = []
    for stmt in node.body:
        for imported in _imports_outside_definitions(stmt):
            message = f"import is inside {kind} {qualname}: {_render(imported)}; move it to the top of the file"
            findings.append(Finding(relative, imported.lineno, message))
    return findings


def _imports_outside_definitions(node: ast.AST) -> Iterator[ast.Import | ast.ImportFrom]:
    """Yield imports under a node without descending into nested definitions."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        yield node
        return
    for child in ast.iter_child_nodes(node):
        yield from _imports_outside_definitions(child)


def _late_assignments(relative: str, body: Sequence[ast.stmt]) -> list[Finding]:
    """Return module-level assignments after the first definition."""
    first_definition = _first_definition(body)
    findings: list[Finding] = []
    for stmt in body[first_definition:]:
        name = _assigned_name(stmt)
        if name is None:
            continue
        message = f"module-level assignment after the first definition: {name}; move it to the top"
        findings.append(Finding(relative, stmt.lineno, message))
    return findings


def _first_definition(body: Sequence[ast.stmt]) -> int:
    """Return the index of the first class or function definition."""
    for index, stmt in enumerate(body):
        if isinstance(stmt, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            return index
    return len(body)


def _assigned_name(stmt: ast.stmt) -> str | None:
    """Return one assigned plain name, or None when this is not an assignment."""
    if isinstance(stmt, ast.Assign):
        targets = stmt.targets
    elif isinstance(stmt, (ast.AnnAssign, ast.AugAssign)):
        targets = [stmt.target]
    else:
        return None
    for target in targets:
        name = _plain_name(target)
        if name is not None:
            return name
    return None


def _plain_name(target: ast.expr) -> str | None:
    """Return a plain name from an assignment target, if any."""
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            name = _plain_name(element)
            if name is not None:
                return name
    return None


def _render(node: ast.AST) -> str:
    """Render one import statement inside a message."""
    return ast.unparse(node)


def main() -> int:
    """Run the ordering policy on the configured roots."""
    config = load_config()
    result = scan(config)
    budgets = Baseline.load(config.baseline_path).section("top_level")
    over, stale = verify_counts("top_level", result.counts, budgets)
    return report("top_level", result.findings, [*over, *stale])
