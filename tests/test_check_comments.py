"""Behavior tests for the comment policy."""

from __future__ import annotations

from pathlib import Path

from lintpolicy.check_comments import scan
from lintpolicy.config import load_config
from support import write_python


def test_explanatory_comment_is_rejected(tmp_path: Path) -> None:
    write_python(tmp_path, "src/a.py", '"""Module."""\n\nvalue = 1  # explains the value\n')
    result = scan(load_config(tmp_path))
    assert [finding.line for finding in result.findings] == [3]
    assert result.counts == {"src/a.py": 1}


def test_shebang_and_directives_are_allowed(tmp_path: Path) -> None:
    source = '#!/usr/bin/env python\n"""Module."""\nimport os  # noqa: E402\n'
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert result.findings == ()
    assert result.counts == {}


def test_docstrings_are_not_comments(tmp_path: Path) -> None:
    source = '"""Module docstring."""\n\n\ndef run() -> None:\n    """Run it."""\n    return None\n'
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert result.findings == ()
    assert result.counts == {}


def test_prose_before_directive_is_rejected(tmp_path: Path) -> None:
    write_python(tmp_path, "src/a.py", '"""Module."""\nimport os  # needed here # noqa: E402\n')
    result = scan(load_config(tmp_path))
    assert len(result.findings) == 1
    assert " # noqa: E402" in result.findings[0].message


def test_tests_root_comments_are_rejected(tmp_path: Path) -> None:
    write_python(tmp_path, "tests/test_a.py", '"""Tests."""\n\nvalue = 1  # TODO remove\n')
    result = scan(load_config(tmp_path))
    assert result.counts == {"tests/test_a.py": 1}
