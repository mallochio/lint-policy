"""Behavior tests for the reinvention policy."""

from __future__ import annotations

from pathlib import Path

from lintpolicy.check_reinvention import scan
from lintpolicy.config import load_config
from support import write_python


def _messages(tmp_path: Path, source: str) -> list[str]:
    write_python(tmp_path, "src/a.py", source)
    result = scan(load_config(tmp_path))
    return [finding.message for finding in result.findings]


def test_counter_bump_is_flagged(tmp_path: Path) -> None:
    source = '"""Module."""\n\n\ndef bump(counts, key):\n    """Bump."""\n    counts[key] = counts.get(key, 0) + 1\n'
    assert "use collections.Counter" in _messages(tmp_path, source)[0]


def test_defaultdict_init_is_flagged(tmp_path: Path) -> None:
    source = (
        '"""Module."""\n\n\ndef group(rows, key):\n    """Group."""\n    groups = {}\n'
        "    for row in rows:\n        if key not in groups:\n            groups[key] = []\n"
        "        groups[key].append(row)\n    return groups\n"
    )
    messages = _messages(tmp_path, source)
    assert len(messages) == 1
    assert "collections.defaultdict" in messages[0]


def test_dict_copy_loop_is_flagged(tmp_path: Path) -> None:
    source = (
        '"""Module."""\n\n\ndef merge(dst, src):\n    """Merge."""\n'
        "    for key, value in src.items():\n        dst[key] = value\n    return dst\n"
    )
    assert "use dst.update(src)" in _messages(tmp_path, source)[0]


def test_mktemp_is_flagged(tmp_path: Path) -> None:
    source = '"""Module."""\n\nimport tempfile\n\n\ndef path():\n    """Path."""\n    return tempfile.mktemp()\n'
    assert "tempfile.mktemp is racy" in _messages(tmp_path, source)[0]


def test_mean_division_is_flagged(tmp_path: Path) -> None:
    source = '"""Module."""\n\n\ndef average(values):\n    """Average."""\n    return sum(values) / len(values)\n'
    assert "use statistics.fmean" in _messages(tmp_path, source)[0]


def test_retry_loop_is_flagged(tmp_path: Path) -> None:
    source = (
        '"""Module."""\n\nimport time\n\n\ndef fetch(load):\n    """Fetch."""\n'
        "    for _ in range(3):\n        try:\n            return load()\n"
        "        except ValueError:\n            time.sleep(1)\n"
    )
    assert "hand-rolled retry" in _messages(tmp_path, source)[0]


def test_unrelated_mean_arguments_pass(tmp_path: Path) -> None:
    source = '"""Module."""\n\n\ndef ratio(values, rows):\n    """Ratio."""\n    return sum(values) / len(rows)\n'
    assert _messages(tmp_path, source) == []


def test_dict_copy_with_extra_body_passes(tmp_path: Path) -> None:
    source = (
        '"""Module."""\n\n\ndef merge(dst, src, count):\n    """Merge."""\n'
        "    for key, value in src.items():\n        dst[key] = value\n        count += 1\n    return count\n"
    )
    assert _messages(tmp_path, source) == []
