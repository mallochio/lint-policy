"""AST helpers for recognizing numeric guards and subject bindings."""

from __future__ import annotations

import ast
from collections.abc import Sequence

INT_ONLY = frozenset({"int"})
INT_OR_FLOAT = frozenset({"int", "float"})


def parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """Map each AST node to its direct parent."""
    result: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            result[child] = node
    return result


def numeric_subject(node: ast.AST) -> ast.expr | None:
    """Return the subject of a supported numeric isinstance call."""
    if not isinstance(node, ast.Call) or node.keywords or len(node.args) != 2:
        return None
    if not isinstance(node.func, ast.Name) or node.func.id != "isinstance":
        return None
    if type_names(node.args[1]) not in {INT_ONLY, INT_OR_FLOAT}:
        return None
    return node.args[0]


def type_names(node: ast.AST) -> frozenset[str] | None:
    """Return recognized type names from a name, tuple, or union expression."""
    if isinstance(node, ast.Name):
        return frozenset({node.id})
    if isinstance(node, ast.Tuple):
        return merge_type_names(node.elts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = type_names(node.left)
        right = type_names(node.right)
        return None if left is None or right is None else left | right
    return None


def merge_type_names(elements: Sequence[ast.expr]) -> frozenset[str] | None:
    """Merge type names from each tuple element, rejecting unknown expressions."""
    names: set[str] = set()
    for element in elements:
        part = type_names(element)
        if part is None:
            return None
        names.update(part)
    return frozenset(names)


def subject_binding(
    node: ast.AST,
    subject: ast.expr,
    parent_map: dict[ast.AST, ast.AST],
) -> ast.comprehension | None:
    """Find the active comprehension generator that binds the subject."""
    subject_key = ast.unparse(subject)
    current = node
    while current in parent_map:
        parent = parent_map[current]
        if isinstance(parent, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
            for generator in reversed(active_generators(parent, node)):
                if target_binds_subject(generator.target, subject_key):
                    return generator
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return None
        current = parent
    return None


def active_generators(comprehension: ast.AST, node: ast.AST) -> list[ast.comprehension]:
    """Return generators active at a node inside a comprehension."""
    generators = comprehension.generators
    if contains_node(comprehension.elt, node):
        return generators
    for index, generator in enumerate(generators):
        if contains_node(generator.iter, node):
            return generators[:index]
        if any(contains_node(test, node) for test in generator.ifs):
            return generators[: index + 1]
    return []


def contains_node(container: ast.AST, target: ast.AST) -> bool:
    """Return whether an AST subtree contains the target node by identity."""
    return any(node is target for node in ast.walk(container))


def target_binds_subject(target: ast.expr, subject_key: str) -> bool:
    """Return whether a comprehension target binds a name in the subject."""
    subject = ast.parse(subject_key, mode="eval").body
    names = {node.id for node in ast.walk(subject) if isinstance(node, ast.Name)}
    return any(isinstance(node, ast.Name) and node.id in names for node in ast.walk(target))


def subject_has_name(subject_key: str, name: str) -> bool:
    """Return whether a subject expression contains the named identifier."""
    subject = ast.parse(subject_key, mode="eval").body
    return any(isinstance(node, ast.Name) and node.id == name for node in ast.walk(subject))


def target_writes_subject(target: ast.expr, subject_key: str) -> bool:
    """Return whether an assignment target may overwrite the subject."""
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(target_writes_subject(element, subject_key) for element in target.elts)
    subject = ast.parse(subject_key, mode="eval").body
    target_load = as_load(target)
    if ast.dump(target_load, include_attributes=False) == ast.dump(subject, include_attributes=False):
        return True
    target_path = expression_path(target_load)
    subject_path = expression_path(subject)
    if target_path is not None and subject_path is not None and subject_path[: len(target_path)] == target_path:
        return True
    return isinstance(target_load, ast.Name) and subject_has_name(subject_key, target_load.id)


def expression_path(node: ast.expr) -> tuple[tuple[str, str], ...] | None:
    """Return a stable name, attribute, and subscript path for an expression."""
    if isinstance(node, ast.Name):
        return (("name", node.id),)
    if isinstance(node, ast.Attribute):
        base = expression_path(node.value)
        return None if base is None else base + (("attribute", node.attr),)
    if isinstance(node, ast.Subscript):
        base = expression_path(node.value)
        return None if base is None else base + (("subscript", ast.dump(node.slice, include_attributes=False)),)
    return None


def as_load(node: ast.expr) -> ast.expr:
    """Reparse an expression in load context for assignment comparisons."""
    return ast.parse(ast.unparse(node), mode="eval").body


def scope_nodes(node: ast.AST):
    """Yield nodes in one scope without descending into nested scopes."""
    yield node
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
        return
    for child in ast.iter_child_nodes(node):
        yield from scope_nodes(child)


def writes_subject(statement: ast.stmt, subject_key: str) -> bool:
    """Return whether a statement rebinds a name used by the subject."""
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return subject_has_name(subject_key, statement.name)
    return any(writes_subject_node(node, subject_key) for node in scope_nodes(statement))


def writes_subject_node(node: ast.AST, subject_key: str) -> bool:
    """Check one node for a binding or assignment that changes the subject."""
    if node_binds_subject(node, subject_key):
        return True
    return any(target_writes_subject(target, subject_key) for target in write_targets(node))


def node_binds_subject(node: ast.AST, subject_key: str) -> bool:
    """Return whether a declaration or import binds a name in the subject."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return subject_has_name(subject_key, node.name)
    return (
        handler_binds_subject(node, subject_key)
        or pattern_binds_subject(node, subject_key)
        or import_binds_subject(node, subject_key)
    )


def handler_binds_subject(node: ast.AST, subject_key: str) -> bool:
    """Check whether an exception handler binds a name in the subject."""
    return isinstance(node, ast.ExceptHandler) and node.name is not None and subject_has_name(subject_key, node.name)


def pattern_binds_subject(node: ast.AST, subject_key: str) -> bool:
    """Check whether a match pattern binds a name in the subject."""
    if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name is not None:
        return subject_has_name(subject_key, node.name)
    return isinstance(node, ast.MatchMapping) and node.rest is not None and subject_has_name(subject_key, node.rest)


def import_binds_subject(node: ast.AST, subject_key: str) -> bool:
    """Check whether an import binds a name in the subject."""
    if isinstance(node, ast.Import):
        names = (alias.asname or alias.name.split(".")[0] for alias in node.names)
        return any(subject_has_name(subject_key, name) for name in names)
    if isinstance(node, ast.ImportFrom):
        if any(alias.name == "*" for alias in node.names):
            return True
        names = (alias.asname or alias.name for alias in node.names)
        return any(subject_has_name(subject_key, name) for name in names)
    return False


def write_targets(node: ast.AST) -> list[ast.expr]:
    """Return assignment targets directly written by a node."""
    if isinstance(node, (ast.Assign, ast.Delete)):
        return node.targets
    if isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.For, ast.AsyncFor)):
        return [node.target]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [item.optional_vars for item in node.items if item.optional_vars is not None]
    return []


def aggregate_element(node: ast.AST) -> tuple[str, ast.expr, ast.expr] | None:
    """Return the element and comprehension for a supported all or any call."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return None
    if node.func.id not in {"all", "any"} or len(node.args) != 1:
        return None
    iterable = node.args[0]
    if isinstance(iterable, (ast.GeneratorExp, ast.ListComp)):
        return node.func.id, iterable.elt, iterable
    return None


def exact_bool_value(node: ast.AST, subject_key: str) -> bool | None:
    """Return a known result for an exact type comparison with bool."""
    if (
        not isinstance(node, ast.Compare)
        or len(node.ops) != 1
        or not isinstance(node.ops[0], (ast.Is, ast.IsNot, ast.Eq, ast.NotEq))
        or len(node.comparators) != 1
    ):
        return None
    operands = ((node.left, node.comparators[0]), (node.comparators[0], node.left))
    for call, other in operands:
        if not isinstance(other, ast.Name) or other.id != "bool":
            continue
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "type"
            and len(call.args) == 1
            and ast.unparse(call.args[0]) == subject_key
        ):
            return isinstance(node.ops[0], (ast.Is, ast.Eq))
    return None


def is_bool_isinstance(node: ast.AST, subject_key: str) -> bool:
    """Return whether a call tests the same subject against bool."""
    if not isinstance(node, ast.Call) or node.keywords or len(node.args) != 2:
        return False
    if not isinstance(node.func, ast.Name) or node.func.id != "isinstance":
        return False
    return type_names(node.args[1]) == frozenset({"bool"}) and ast.unparse(node.args[0]) == subject_key


def previous_statements(guard: ast.stmt, parent_map: dict[ast.AST, ast.AST]) -> Sequence[ast.stmt]:
    """Return statements before a guard in the same parent block."""
    parent = parent_map.get(guard)
    if parent is None:
        return ()
    for block in statement_blocks(parent):
        if guard in block:
            return block[: block.index(guard)]
    return ()


def statement_blocks(parent: ast.AST) -> list[list[ast.stmt]]:
    """Return the statement suites directly owned by a parent node."""
    blocks: list[list[ast.stmt]] = []
    for name in ("body", "orelse", "finalbody"):
        block = getattr(parent, name, None)
        if isinstance(block, list):
            blocks.append(block)
    if isinstance(parent, ast.Try):
        blocks.extend(handler.body for handler in parent.handlers)
    return blocks


def suite_outcomes(statements: Sequence[ast.stmt]) -> frozenset[str]:
    """Compute raise, exit, and fallthrough outcomes for a statement suite."""
    outcomes = frozenset({"fallthrough"})
    for statement in statements:
        if "fallthrough" not in outcomes:
            break
        outcomes = (outcomes - {"fallthrough"}) | statement_outcomes(statement)
    return outcomes


def statement_outcomes(statement: ast.stmt) -> frozenset[str]:
    """Compute control-flow outcomes for one statement."""
    if isinstance(statement, ast.Raise):
        return frozenset({"raise"})
    if isinstance(statement, (ast.Return, ast.Break, ast.Continue)):
        return frozenset({"exit"})
    if isinstance(statement, ast.If):
        alternate = statement.orelse or [ast.Pass()]
        return suite_outcomes(statement.body) | suite_outcomes(alternate)
    return frozenset({"fallthrough"})
