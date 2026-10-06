"""Behavior tests for the top-level ordering policy."""

from __future__ import annotations

from pathlib import Path

from lintpolicy.check_toplevel import scan
from lintpolicy.config import load_config
from support import write_python


def test_import_after_code_is_rejected(tmp_path: Path) -> None:
    write_python(tmp_path, "src/a.py", '"""Module."""\n\nVALUE = 1\n\nimport os\n')
    result = scan(load_config(tmp_path))
    assert result.counts == {"src/a.py": 1}
    assert "import is not at the top" in result.findings[0].message


def test_import_region_allows_common_patterns(tmp_path: Path) -> None:
    source = (
        '"""Module."""\n\nfrom __future__ import annotations\n\nimport os\n\n'
        "try:\n    import ujson as json\nexcept ImportError:\n    import json\n\n"
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n    from collections.abc import Sequence\n\n"
        '__all__ = ["os"]\n\nVALUE = 1\n'
    )
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert result.findings == ()


def test_function_import_is_rejected(tmp_path: Path) -> None:
    source = '"""Module."""\n\n\ndef run():\n    """Run."""\n    import torch\n    return torch\n'
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert len(result.findings) == 1
    assert "inside function run" in result.findings[0].message


def test_assignment_after_definition_is_rejected(tmp_path: Path) -> None:
    source = '"""Module."""\n\n\ndef run():\n    """Run."""\n    return 1\n\n_CACHE = {}\n'
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert len(result.findings) == 1
    assert "after the first definition" in result.findings[0].message


def test_assignment_before_definitions_passes(tmp_path: Path) -> None:
    source = '"""Module."""\n\n_CACHE = {}\n\n\ndef run():\n    """Run."""\n    return _CACHE\n'
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert result.findings == ()


def test_main_guard_assignment_is_exempt(tmp_path: Path) -> None:
    source = (
        '"""Module."""\n\n\ndef run():\n    """Run."""\n    return 1\n\n'
        'if __name__ == "__main__":\n    result = run()\n    print(result)\n'
    )
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert result.findings == ()


def test_tests_root_is_scanned(tmp_path: Path) -> None:
    write_python(tmp_path, "tests/test_a.py", '"""Tests."""\n\nVALUE = 1\n\nimport os\n')
    result = scan(load_config(tmp_path))
    assert result.counts == {"tests/test_a.py": 1}
