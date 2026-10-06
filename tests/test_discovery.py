"""Behavior tests for file discovery and exclusions."""

from __future__ import annotations

from pathlib import Path

from lintpolicy.discovery import iter_python_files, path_matches
from support import write_python


def test_exclude_patterns_match_nested_and_root_paths() -> None:
    assert path_matches("ground/tests/test_a.py", ["**/tests/**"])
    assert path_matches("tests/test_a.py", ["**/tests/**"])
    assert path_matches("workflows/test_run.py", ["**/test_*.py"])
    assert path_matches("workflows/run_test.py", ["**/*_test.py"])
    assert not path_matches("workflows/run.py", ["**/test_*.py", "**/tests/**"])


def test_iter_python_files_applies_exclusions(tmp_path: Path) -> None:
    write_python(tmp_path, "src/a.py", "")
    write_python(tmp_path, "src/pkg/tests/test_a.py", "")
    write_python(tmp_path, "tests/test_b.py", "")
    write_python(tmp_path, "workflows/test_c.py", "")
    roots = ["src", "tests", "workflows"]
    exclude = ["**/tests/**", "**/test_*.py"]
    found = {path.relative_to(tmp_path).as_posix() for path in iter_python_files(tmp_path, roots, exclude)}
    assert found == {"src/a.py"}
