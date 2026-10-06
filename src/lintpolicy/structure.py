"""Shared AST block traversal helpers."""

from __future__ import annotations

import ast
from collections.abc import Iterator


def nested_blocks(node: ast.AST) -> Iterator[list[ast.stmt]]:
    """Yield statement blocks nested inside a non-definition node."""
    if isinstance(node, ast.Try):
        for handler in node.handlers:
            yield handler.body
    if isinstance(node, ast.Match):
        for case in node.cases:
            yield case.body
    for _name, value in ast.iter_fields(node):
        if isinstance(value, list) and value and all(isinstance(item, ast.stmt) for item in value):
            yield value


def is_docstring(node: ast.stmt) -> bool:
    """Return whether a statement is a string expression."""
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
