"""Detect hand-rolled implementations of well-known library idioms.

Each detector recognizes a high-frequency shape that agents rewrite by hand
and names the battle-hardened replacement. Algorithm-level duplication of an
external library is semantic and stays a review question.
"""

from __future__ import annotations

import ast

SLEEP_CALLS = {"time.sleep", "asyncio.sleep", "sleep"}
EMPTY_CONSTRUCTORS = {"list", "dict", "set"}


def detect(node: ast.AST) -> str | None:
    """Return the replacement message for one hand-rolled shape, if any."""
    if isinstance(node, ast.Assign):
        return _counter_bump(node)
    if isinstance(node, ast.If):
        return _defaultdict_init(node)
    if isinstance(node, ast.For):
        return _dict_copy_loop(node) or _retry_loop(node)
    if isinstance(node, ast.While):
        return _retry_loop(node)
    if isinstance(node, ast.Call):
        return _mktemp(node)
    if isinstance(node, ast.BinOp):
        return _mean_division(node)
    return None


def _counter_bump(node: ast.Assign) -> str | None:
    """Flag ``d[key] = d.get(key, 0) + 1``."""
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Subscript):
        return None
    lookup = _counter_lookup(node.value)
    if lookup is None:
        return None
    owner, key = lookup
    target = node.targets[0]
    if ast.unparse(target.value) != owner or ast.unparse(target.slice) != key:
        return None
    return f"hand-rolled counter on {owner}; use collections.Counter"


def _counter_lookup(value: ast.expr) -> tuple[str, str] | None:
    """Return the owner and key of a ``d.get(key, 0) + 1`` expression."""
    if not isinstance(value, ast.BinOp) or not isinstance(value.op, ast.Add):
        return None
    for candidate, constant in ((value.left, value.right), (value.right, value.left)):
        if isinstance(constant, ast.Constant) and constant.value == 1:
            found = _zero_default_get(candidate)
            if found is not None:
                return found
    return None


def _zero_default_get(candidate: ast.expr) -> tuple[str, str] | None:
    """Return the owner and key of a ``d.get(key, 0)`` call, or None."""
    if not isinstance(candidate, ast.Call) or candidate.keywords or len(candidate.args) != 2:
        return None
    func = candidate.func
    if not isinstance(func, ast.Attribute) or func.attr != "get":
        return None
    default = candidate.args[1]
    if isinstance(default, ast.Constant) and default.value == 0:
        return ast.unparse(func.value), ast.unparse(candidate.args[0])
    return None


def _defaultdict_init(node: ast.If) -> str | None:
    """Flag ``if key not in mapping: mapping[key] = []``."""
    key, mapping = _not_in_pair(node.test)
    if key is None or not isinstance(mapping, ast.Name) or len(node.body) != 1:
        return None
    assign = node.body[0]
    if not isinstance(assign, ast.Assign) or len(assign.targets) != 1:
        return None
    target = assign.targets[0]
    if not isinstance(target, ast.Subscript):
        return None
    if ast.unparse(target.value) != mapping.id or ast.unparse(target.slice) != key:
        return None
    if not _is_empty_container(assign.value):
        return None
    return f"hand-rolled defaultdict init for {mapping.id}; use collections.defaultdict or dict.setdefault"


def _not_in_pair(test: ast.expr) -> tuple[str | None, ast.expr | None]:
    """Return the key text and container from a ``key not in mapping`` test."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return None, None
    if not isinstance(test.ops[0], ast.NotIn):
        return None, None
    return ast.unparse(test.left), test.comparators[0]


def _is_empty_container(value: ast.expr) -> bool:
    """Return whether a value is an empty list, dict, set, or constructor."""
    if isinstance(value, ast.List):
        return not value.elts
    if isinstance(value, ast.Dict):
        return not value.keys
    if isinstance(value, ast.Set):
        return not value.elts
    if isinstance(value, ast.Call) and not value.args and not value.keywords:
        return isinstance(value.func, ast.Name) and value.func.id in EMPTY_CONSTRUCTORS
    return False


def _dict_copy_loop(node: ast.For) -> str | None:
    """Flag ``for key, value in src.items(): dst[key] = value``."""
    if not isinstance(node.target, ast.Tuple) or len(node.target.elts) != 2:
        return None
    key, value = node.target.elts
    if not (isinstance(key, ast.Name) and isinstance(value, ast.Name)):
        return None
    source = _items_source(node.iter)
    if source is None or len(node.body) != 1:
        return None
    assign = node.body[0]
    if not isinstance(assign, ast.Assign) or len(assign.targets) != 1:
        return None
    target = assign.targets[0]
    if not isinstance(target, ast.Subscript):
        return None
    if ast.unparse(target.slice) != key.id:
        return None
    if ast.unparse(assign.value) != value.id:
        return None
    return f"hand-rolled dict copy; use {ast.unparse(target.value)}.update({source})"


def _items_source(iterable: ast.expr) -> str | None:
    """Return the receiver of an ``.items()`` call, if any."""
    if not isinstance(iterable, ast.Call) or not isinstance(iterable.func, ast.Attribute):
        return None
    if iterable.func.attr != "items" or iterable.args or iterable.keywords:
        return None
    return ast.unparse(iterable.func.value)


def _retry_loop(node: ast.For | ast.While) -> str | None:
    """Flag a sleep inside an except block inside a loop."""
    for child in ast.walk(node):
        if not isinstance(child, ast.Try):
            continue
        if any(_handler_sleeps(handler) for handler in child.handlers):
            return "sleep inside an except block in a loop looks like a hand-rolled retry; use tenacity, backoff, or an existing helper"
    return None


def _handler_sleeps(handler: ast.ExceptHandler) -> bool:
    """Return whether an except handler calls sleep somewhere."""
    return any(_is_sleep_call(node) for node in ast.walk(handler) if isinstance(node, ast.Call))


def _is_sleep_call(node: ast.Call) -> bool:
    """Return whether a call is a known sleep function."""
    return ast.unparse(node.func) in SLEEP_CALLS


def _mktemp(node: ast.Call) -> str | None:
    """Flag ``tempfile.mktemp``."""
    if ast.unparse(node.func) != "tempfile.mktemp":
        return None
    return "tempfile.mktemp is racy; use tempfile.NamedTemporaryFile, TemporaryDirectory, or mkstemp"


def _mean_division(node: ast.BinOp) -> str | None:
    """Flag ``sum(values) / len(values)``."""
    if not isinstance(node.op, ast.Div):
        return None
    numerator = _single_argument_call(node.left, "sum")
    denominator = _single_argument_call(node.right, "len")
    if numerator is None or denominator is None:
        return None
    if ast.unparse(numerator) != ast.unparse(denominator):
        return None
    return "hand-rolled mean; use statistics.fmean or statistics.mean"


def _single_argument_call(node: ast.expr, name: str) -> ast.expr | None:
    """Return the single positional argument of ``name(...)``, if any."""
    if not isinstance(node, ast.Call) or node.keywords or len(node.args) != 1:
        return None
    if ast.unparse(node.func) != name:
        return None
    return node.args[0]
