"""Behavior tests for the file and function line limits."""

from __future__ import annotations

from pathlib import Path

from lintpolicy.check_limits import main, scan
from lintpolicy.config import load_config
from support import write_baseline, write_python


def _function_source(code_lines: int, docstring_lines: int) -> str:
    """Build a module whose function has the requested body sizes."""
    lines = ['"""Module."""', "", "", "def run() -> None:"]
    if docstring_lines:
        body = ['"""Summarize the run.'] + ["Detail line."] * (docstring_lines - 2) + ['"""']
        lines.extend("    " + item for item in body)
    lines.extend(f"    value_{index} = {index}" for index in range(code_lines))
    return "\n".join(lines) + "\n"


def test_file_at_limit_fails(tmp_path: Path) -> None:
    source = '"""Module."""\n' + "value = 1\n" * 299
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert result.counts == {"file:src/a.py": 300}
    assert "300 lines" in result.findings[0].message


def test_file_below_limit_passes(tmp_path: Path) -> None:
    source = '"""Module."""\n' + "value = 1\n" * 298
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert result.findings == ()
    assert result.counts == {}


def test_function_docstring_is_excluded(tmp_path: Path) -> None:
    source = _function_source(code_lines=25, docstring_lines=5)
    write_python(tmp_path, "src/a.py", source)
    assert len(source.splitlines()) >= 30
    result = scan(load_config(tmp_path))
    assert result.counts == {}


def test_function_without_docstring_at_limit_fails(tmp_path: Path) -> None:
    write_python(tmp_path, "src/a.py", _function_source(code_lines=29, docstring_lines=0))
    result = scan(load_config(tmp_path))
    assert result.counts == {"function:src/a.py:run": 30}


def test_decorators_do_not_count(tmp_path: Path) -> None:
    source = '"""Module."""\n\n\n' + "@wrapper\n" * 5 + "def run() -> None:\n" + "    value = 1\n" * 27
    write_python(tmp_path, "src/a.py", source)
    assert len(source.splitlines()) >= 30
    result = scan(load_config(tmp_path))
    assert result.counts == {}


def test_tests_root_is_scanned(tmp_path: Path) -> None:
    write_python(tmp_path, "tests/test_a.py", _function_source(code_lines=29, docstring_lines=0))
    result = scan(load_config(tmp_path))
    assert result.counts == {"function:tests/test_a.py:run": 30}


def test_baseline_covered_function_limit_passes_main(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_python(tmp_path, "src/a.py", _function_source(code_lines=29, docstring_lines=0))
    write_baseline(tmp_path, "limits", {"function:src/a.py:run": 30})
    assert main() == 0
