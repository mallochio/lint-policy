"""Behavior tests for the numeric guard policy."""

from __future__ import annotations

from pathlib import Path

from lintpolicy.config import load_config
from lintpolicy.numeric import scan
from support import write_python

GUARD = (
    '"""Module."""\n\n\ndef check(value):\n    """Validate."""\n'
    '    if not isinstance(value, int):\n        raise TypeError("need int")\n    return value\n'
)


def test_int_guard_that_accepts_bool_is_rejected(tmp_path: Path) -> None:
    write_python(tmp_path, "src/a.py", GUARD)
    result = scan(load_config(tmp_path))
    assert result.counts == {"src/a.py": 1}
    assert "accepts bool" in result.findings[0].message


def test_bool_exclusion_passes(tmp_path: Path) -> None:
    source = GUARD.replace(
        "if not isinstance(value, int):",
        "if not isinstance(value, int) or isinstance(value, bool):",
    )
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert result.findings == ()
    assert result.counts == {}


def test_int_or_float_guard_is_covered(tmp_path: Path) -> None:
    source = GUARD.replace("isinstance(value, int)", "isinstance(value, int | float)")
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    assert result.counts == {"src/a.py": 1}
