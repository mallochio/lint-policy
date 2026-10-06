"""Cap file length and function length.

A file fails when it has ``file-lines`` lines or more. A function fails when
its span from the ``def`` line to the end of the body, excluding docstring
lines, is ``function-lines`` lines or more. Decorators are not counted.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from lintpolicy.baseline import Baseline, verify_counts
from lintpolicy.config import Config, load_config
from lintpolicy.discovery import iter_python_files, relative_path
from lintpolicy.reporting import Finding, Scan, report
from lintpolicy.structure import is_docstring, nested_blocks


@dataclass(frozen=True)
class FunctionSpan:
    """One function definition and its measured length."""

    qualname: str
    line: int
    length: int


def scan(config: Config) -> Scan:
    """Return limit findings and measurement counts."""
    findings: list[Finding] = []
    counts: dict[str, int] = {}
    for path in iter_python_files(config.root, config.limit_roots, config.limit_exclude):
        relative = relative_path(path, config.root)
        _measure_file(relative, path, config, findings, counts)
    return Scan(tuple(findings), counts)


def _measure_file(
    relative: str,
    path: Path,
    config: Config,
    findings: list[Finding],
    counts: dict[str, int],
) -> None:
    """Measure one file and record its violations."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return
    file_lines = len(source.splitlines())
    if file_lines >= config.file_line_limit:
        counts[f"file:{relative}"] = file_lines
        message = f"file has {file_lines} lines; the limit is {config.file_line_limit}"
        findings.append(Finding(relative, 1, message))
    seen: dict[str, int] = {}
    for span in function_spans(tree):
        if span.length < config.function_line_limit:
            continue
        key = _unique_key(relative, span.qualname, seen)
        counts[key] = span.length
        message = (
            f"function {span.qualname} spans {span.length} lines excluding its docstring; "
            f"the limit is {config.function_line_limit}"
        )
        findings.append(Finding(relative, span.line, message))


def _unique_key(relative: str, qualname: str, seen: dict[str, int]) -> str:
    """Return a stable measurement key for one function."""
    base = f"function:{relative}:{qualname}"
    occurrence = seen.get(base, 0) + 1
    seen[base] = occurrence
    return base if occurrence == 1 else f"{base}#{occurrence}"


def function_spans(tree: ast.Module) -> Iterator[FunctionSpan]:
    """Yield every function definition with its measured length."""
    yield from _walk_block(tree.body, [])


def _walk_block(block: list[ast.stmt], stack: list[str]) -> Iterator[FunctionSpan]:
    """Yield function spans in one statement block."""
    for node in block:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualname = ".".join([*stack, node.name])
            yield FunctionSpan(qualname, node.lineno, _length(node))
            yield from _walk_block(node.body, [*stack, node.name])
        elif isinstance(node, ast.ClassDef):
            yield from _walk_block(node.body, [*stack, node.name])
        else:
            for nested in nested_blocks(node):
                yield from _walk_block(nested, stack)


def _length(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return the def-to-end line count minus the docstring lines."""
    end = node.end_lineno or node.lineno
    return end - node.lineno + 1 - _docstring_lines(node)


def _docstring_lines(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return the line count of a leading docstring statement."""
    if not node.body:
        return 0
    first = node.body[0]
    if not is_docstring(first):
        return 0
    return (first.end_lineno or first.lineno) - first.lineno + 1


def main() -> int:
    """Run the size policy on the configured roots."""
    config = load_config()
    result = scan(config)
    budgets = Baseline.load(config.baseline_path).section("limits")
    over, stale = verify_counts("limits", result.counts, budgets)
    return report("limits", result.findings, [*over, *stale])
