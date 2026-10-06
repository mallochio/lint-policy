"""Analyze numeric guards and boolean control flow."""

from __future__ import annotations

import ast
from collections.abc import Sequence

from lintpolicy.numeric.ast_utils import (
    aggregate_element,
    exact_bool_value,
    is_bool_isinstance,
    numeric_subject,
    parents,
    previous_statements,
    statement_blocks,
    suite_outcomes,
    subject_binding,
    target_binds_subject,
    target_writes_subject,
    writes_subject,
)


def scan_tree(tree: ast.AST) -> list[tuple[int, str]]:
    """Return source lines and messages for unsafe numeric guards."""
    parent_map = parents(tree)
    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        subject = numeric_subject(node)
        if subject is None or not isinstance(node, ast.Call):
            continue
        guard = _raising_guard(node, parent_map)
        if guard is None:
            continue
        subject_key = ast.unparse(subject)
        subject_scope = subject_binding(node, subject, parent_map)
        if _guard_rejects_bool(guard, subject_key, parent_map, subject_scope):
            continue
        if isinstance(guard, ast.If) and _preceding_excludes_bool(guard, subject_key, parent_map, subject_scope):
            continue
        rendered = ast.unparse(node)
        message = f"{rendered} accepts bool; exclude bool in the same guard (bool is a subclass of int)"
        findings.append((node.lineno, message))
    return findings


def _raising_guard(node: ast.AST, parent_map: dict[ast.AST, ast.AST]) -> ast.If | None:
    """Find the nearest if guard whose control flow can raise for all paths."""
    current = node
    while current in parent_map:
        parent = parent_map[current]
        if isinstance(parent, ast.If) and parent.test is current:
            if _block_raises(parent.body) or _block_raises(parent.orelse) or _later_sibling_raises(parent, parent_map):
                return parent
            return None
        if isinstance(parent, ast.stmt):
            return None
        current = parent
    return None


def _later_sibling_raises(guard: ast.If, parent_map: dict[ast.AST, ast.AST]) -> bool:
    """Return whether statements after a guard in its block always raise."""
    parent = parent_map.get(guard)
    if parent is None:
        return False
    for block in statement_blocks(parent):
        if guard in block:
            return _block_raises(block[block.index(guard) + 1 :])
    return False


def _block_raises(statements: Sequence[ast.stmt]) -> bool:
    """Return whether every path through a statement suite raises."""
    return suite_outcomes(statements) == frozenset({"raise"})


def _guard_rejects_bool(
    guard: ast.If,
    subject_key: str,
    parent_map: dict[ast.AST, ast.AST],
    subject_scope: ast.comprehension | None,
) -> bool:
    """Return whether all paths for a bool subject raise inside the guard."""
    truth_values = _truth_values_for_bool(guard.test, subject_key, subject_scope, parent_map)
    parent = parent_map.get(guard)
    suffix: Sequence[ast.stmt] = ()
    if parent is not None:
        for block in statement_blocks(parent):
            if guard in block:
                suffix = block[block.index(guard) + 1 :]
                break
    outcomes: set[str] = set()
    if True in truth_values:
        outcomes.update(_continued_outcomes(guard.body, suffix))
    if False in truth_values:
        outcomes.update(_continued_outcomes(guard.orelse, suffix))
    return outcomes == {"raise"}


def _continued_outcomes(branch: Sequence[ast.stmt], suffix: Sequence[ast.stmt]) -> frozenset[str]:
    """Include later statements for control paths that leave a branch normally."""
    outcomes = suite_outcomes(branch)
    if "fallthrough" not in outcomes:
        return outcomes
    return (outcomes - {"fallthrough"}) | suite_outcomes(suffix)


def _truth_values_for_bool(
    node: ast.AST,
    subject_key: str,
    subject_scope: ast.comprehension | None,
    parent_map: dict[ast.AST, ast.AST],
) -> frozenset[bool]:
    """Approximate possible truth values when the subject is a bool."""
    known = _known_bool_value(node, subject_key)
    if known is not None:
        return frozenset({known})
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return frozenset(
            not value for value in _truth_values_for_bool(node.operand, subject_key, subject_scope, parent_map)
        )
    if isinstance(node, ast.BoolOp):
        return _bool_op_values(node, subject_key, subject_scope, parent_map)
    aggregate = aggregate_element(node)
    if aggregate is None:
        return _unknown_bool_values()
    name, element, comprehension = aggregate
    if _shadows_subject(comprehension, subject_key) and not _matching_aggregate_scope(
        comprehension, subject_key, subject_scope
    ):
        return _unknown_bool_values()
    values = _truth_values_for_bool(element, subject_key, subject_scope, parent_map)
    if _matching_aggregate_scope(comprehension, subject_key, subject_scope):
        return _aggregate_with_checked_element(name, values)
    return _aggregate_with_unknown_length(name, values)


def _unknown_bool_values() -> frozenset[bool]:
    """Return both possible truth values."""
    return frozenset({True, False})


def _matching_aggregate_scope(
    comprehension: ast.expr,
    subject_key: str,
    subject_scope: ast.comprehension | None,
) -> bool:
    """Return whether the comprehension iterates over the subject binding."""
    return subject_scope is not None and any(
        generator is subject_scope and target_binds_subject(generator.target, subject_key)
        for generator in comprehension.generators
    )


def _aggregate_with_checked_element(name: str, values: frozenset[bool]) -> frozenset[bool]:
    """Evaluate all or any when the iterable checks the same bound subject."""
    if name == "any" and values == frozenset({True}):
        return values
    if name == "all" and values == frozenset({False}):
        return values
    return _unknown_bool_values()


def _aggregate_with_unknown_length(name: str, values: frozenset[bool]) -> frozenset[bool]:
    """Evaluate all or any when the iterable length is not proven."""
    if name == "any" and values == frozenset({True}):
        return _unknown_bool_values()
    if name == "any" and values == frozenset({False}):
        return values
    if name == "all" and values == frozenset({True}):
        return values
    return _unknown_bool_values()


def _known_bool_value(node: ast.AST, subject_key: str) -> bool | None:
    """Return a known truth value for supported bool and numeric checks."""
    if is_bool_isinstance(node, subject_key):
        return True
    exact = exact_bool_value(node, subject_key)
    if exact is not None:
        return exact
    subject = numeric_subject(node)
    if subject is not None and ast.unparse(subject) == subject_key:
        return True
    return None


def _bool_op_values(
    node: ast.BoolOp,
    subject_key: str,
    subject_scope: ast.comprehension | None,
    parent_map: dict[ast.AST, ast.AST],
) -> frozenset[bool]:
    """Compute possible bool results of a boolean operator."""
    is_and = isinstance(node.op, ast.And)
    outcomes = frozenset({is_and})
    for value in node.values:
        right = _truth_values_for_bool(value, subject_key, subject_scope, parent_map)
        operation = (lambda left, item: left and item) if is_and else (lambda left, item: left or item)
        outcomes = frozenset(operation(left, item) for left in outcomes for item in right)
    return outcomes


def _shadows_subject(comprehension: ast.expr, subject_key: str) -> bool:
    """Return whether a comprehension target shadows the subject's names."""
    return any(target_binds_subject(generator.target, subject_key) for generator in comprehension.generators)


def _preceding_excludes_bool(
    guard: ast.If,
    subject_key: str,
    parent_map: dict[ast.AST, ast.AST],
    subject_scope: ast.comprehension | None,
) -> bool:
    """Return whether an earlier statement or enclosing branch excludes bool."""
    current: ast.stmt = guard
    while True:
        parent = parent_map.get(current)
        previous = _previous_sibling_exclusion(current, subject_key, subject_scope, parent_map)
        if previous is not None:
            return previous
        if isinstance(parent, ast.If) and _enclosing_branch_excludes_bool(
            current, parent, subject_key, subject_scope, parent_map
        ):
            return True
        if _parent_rebinds_subject(parent, subject_key) or _scope_boundary(parent):
            return False
        current = parent


def _previous_sibling_exclusion(
    current: ast.stmt,
    subject_key: str,
    subject_scope: ast.comprehension | None,
    parent_map: dict[ast.AST, ast.AST],
) -> bool | None:
    """Find the nearest preceding exclusion unless the subject was reassigned."""
    for statement in reversed(previous_statements(current, parent_map)):
        if writes_subject(statement, subject_key):
            return False
        if _statement_excludes_bool(statement, subject_key, subject_scope, parent_map):
            return True
    return None


def _parent_rebinds_subject(parent: ast.AST | None, subject_key: str) -> bool:
    """Return whether a loop or with statement rebinds the subject."""
    if isinstance(parent, (ast.For, ast.AsyncFor)):
        return target_writes_subject(parent.target, subject_key)
    if isinstance(parent, (ast.With, ast.AsyncWith)):
        return any(
            item.optional_vars is not None and target_writes_subject(item.optional_vars, subject_key)
            for item in parent.items
        )
    return False


def _scope_boundary(parent: ast.AST | None) -> bool:
    """Return whether walking to an earlier statement must stop."""
    return not isinstance(parent, ast.stmt) or isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))


def _enclosing_branch_excludes_bool(
    current: ast.stmt,
    parent: ast.If,
    subject_key: str,
    subject_scope: ast.comprehension | None,
    parent_map: dict[ast.AST, ast.AST],
) -> bool:
    """Check whether the current branch follows a known bool exclusion."""
    values = _truth_values_for_bool(parent.test, subject_key, subject_scope, parent_map)
    return (current in parent.body and values == frozenset({False})) or (
        current in parent.orelse and values == frozenset({True})
    )


def _statement_excludes_bool(
    statement: ast.stmt,
    subject_key: str,
    subject_scope: ast.comprehension | None,
    parent_map: dict[ast.AST, ast.AST],
) -> bool:
    """Return whether an if statement exits all bool paths from its body."""
    if not isinstance(statement, ast.If):
        return False
    if _truth_values_for_bool(statement.test, subject_key, subject_scope, parent_map) != frozenset({True}):
        return False
    return _block_exits(statement.body)


def _block_exits(statements: Sequence[ast.stmt]) -> bool:
    """Return whether no path falls through a statement suite."""
    return "fallthrough" not in suite_outcomes(statements)
