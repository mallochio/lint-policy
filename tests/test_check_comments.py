"""Behavior tests for the comment policy."""

from __future__ import annotations

from pathlib import Path

from lintpolicy.check_comments import main, scan
from lintpolicy.config import load_config
from lintpolicy.make_baseline import collect
from support import write_baseline, write_python


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


def test_baselined_prose_comment_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_python(tmp_path, "src/a.py", '"""Module."""\n\nvalue = 1  # explains the value\n')
    write_baseline(tmp_path, "comments", {"src/a.py": 1})
    assert main() == 1
    assert "disallowed comment" in capsys.readouterr().out


def test_noqa_line_passes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_python(tmp_path, "src/a.py", '"""Module."""\nimport os  # noqa: E402\n')
    write_baseline(tmp_path, "comments", {})
    assert main() == 0


def test_nonempty_comments_section_is_rejected(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_python(tmp_path, "src/a.py", '"""Module."""\nvalue = 1\n')
    write_baseline(tmp_path, "comments", {"src/old.py": 2})
    assert main() == 1
    assert "remove the comments section" in capsys.readouterr().err


def test_baseline_adopt_omits_comment_counts(tmp_path: Path) -> None:
    write_python(tmp_path, "src/a.py", '"""Module."""\n\nvalue = 1  # explains the value\n')
    assert not collect(load_config(tmp_path)).get("comments")
