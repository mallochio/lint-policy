"""Behavior tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

from lintpolicy.config import DEFAULT_FILE_LINES, load_config
from support import write_config


def test_defaults_target_src_and_tests(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert config.source_roots == ("src", "scripts")
    assert config.test_roots == ("tests",)
    assert config.file_line_limit == DEFAULT_FILE_LINES
    assert config.function_line_limit == 30
    assert config.docstring_roots == ("src", "scripts")


def test_standalone_config_overrides_roots_and_limits(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """
source-roots = ["pkg"]
test-roots = ["pkg/tests"]

[limits]
file-lines = 120
function-lines = 20
""",
    )
    config = load_config(tmp_path)
    assert config.source_roots == ("pkg",)
    assert config.file_line_limit == 120
    assert config.function_line_limit == 20
    assert config.limit_roots == ("pkg", "pkg/tests")


def test_pyproject_table_wins_over_standalone(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.lintpolicy]\nsource-roots = ["app"]\n', encoding="utf-8")
    write_config(tmp_path, 'source-roots = ["pkg"]\n')
    config = load_config(tmp_path)
    assert config.source_roots == ("app",)


def test_section_excludes_are_loaded(tmp_path: Path) -> None:
    write_config(tmp_path, '[docstrings]\nexclude = ["**/tests/**"]\n')
    config = load_config(tmp_path)
    assert config.docstring_exclude == ("**/tests/**",)
    assert config.comment_exclude == ()
