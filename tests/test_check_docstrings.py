"""Behavior tests for the docstring policy."""

from __future__ import annotations

from pathlib import Path

from lintpolicy.check_docstrings import scan
from lintpolicy.config import load_config
from support import write_config, write_python


def test_missing_module_class_and_function_are_reported(tmp_path: Path) -> None:
    source = "class Engine:\n    def run(self):\n        return 1\n"
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    messages = {finding.message for finding in result.findings}
    assert "module docstring is required" in messages
    assert "missing class docstring: Engine" in messages
    assert "missing function docstring: Engine.run" in messages
    assert result.counts == {"src/a.py": 3}


def test_full_docstrings_pass(tmp_path: Path) -> None:
    source = (
        '"""Module."""\n\n\nclass Engine:\n    """Engine."""\n\n'
        '    def run(self) -> int:\n        """Run it."""\n        return 1\n'
    )
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert result.findings == ()


def test_overload_and_setters_are_exempt(tmp_path: Path) -> None:
    source = (
        '"""Module."""\n\nfrom typing import overload\n\n\nclass Engine:\n    """Engine."""\n\n'
        '    @property\n    def value(self) -> int:\n        """Value."""\n        return 1\n\n'
        "    @value.setter\n    def value(self, item: int) -> None:\n        self._value = item\n\n"
        "    @overload\n    def parse(self, item: int) -> int: ...\n\n"
        "    @overload\n    def parse(self, item: str) -> str: ...\n\n"
        '    def parse(self, item):\n        """Parse."""\n        return item\n'
    )
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert result.findings == ()


def test_tests_are_not_scanned_for_docstrings(tmp_path: Path) -> None:
    write_python(tmp_path, "tests/test_a.py", "def test_value():\n    assert 1 == 1\n")
    result = scan(load_config(tmp_path))
    assert result.findings == ()


def test_nested_functions_are_qualified(tmp_path: Path) -> None:
    source = '"""Module."""\n\n\ndef outer():\n    """Outer."""\n    def inner():\n        return 1\n    return inner\n'
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert result.findings[0].message == "missing function docstring: outer.inner"


def test_exclude_pattern_skips_nested_tests(tmp_path: Path) -> None:
    write_python(tmp_path, "src/pkg/tests/test_a.py", "def test_value():\n    assert 1 == 1\n")
    write_config(tmp_path, '[docstrings]\nexclude = ["**/tests/**"]\n')
    result = scan(load_config(tmp_path))
    assert result.findings == ()
