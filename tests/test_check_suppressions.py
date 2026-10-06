"""Behavior tests for the suppression ratchet."""

from __future__ import annotations

import json
from pathlib import Path

from lintpolicy.check_suppressions import main, scan
from lintpolicy.config import load_config
from support import write_python

REASON_BODY = "noqa: e402 - reason: lazy import"


def _write_baseline(root: Path, suppressions: dict) -> None:
    data = {"version": 1, "suppressions": suppressions}
    (root / ".lintpolicy-baseline.json").write_text(json.dumps(data), encoding="utf-8")


def test_directive_entries_capture_reason(tmp_path: Path) -> None:
    write_python(tmp_path, "src/a.py", '"""Module."""\nimport os  # noqa: E402 - reason: lazy import\n')
    result = scan(load_config(tmp_path))
    assert list(result.entries.values()) == ["reason: lazy import"]


def test_plain_comment_is_not_a_suppression(tmp_path: Path) -> None:
    write_python(tmp_path, "src/a.py", '"""Module."""\nvalue = 1  # note\n')
    result = scan(load_config(tmp_path))
    assert result.entries == {}


def test_registered_directive_passes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_python(tmp_path, "src/a.py", '"""Module."""\nimport os  # noqa: E402 - reason: lazy import\n')
    _write_baseline(tmp_path, {f"src/a.py|{REASON_BODY}": "reason: lazy import"})
    assert main() == 0


def test_unregistered_directive_with_reason_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_python(tmp_path, "src/a.py", '"""Module."""\nimport os  # noqa: E402 - reason: lazy import\n')
    _write_baseline(tmp_path, {})
    assert main() == 1
    assert "is not registered" in capsys.readouterr().out


def test_unregistered_directive_without_reason_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_python(tmp_path, "src/a.py", '"""Module."""\nimport os  # noqa: E402\n')
    assert main() == 1
    assert "needs a reason" in capsys.readouterr().out


def test_stale_baseline_entry_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_python(tmp_path, "src/a.py", '"""Module."""\nvalue = 1\n')
    _write_baseline(tmp_path, {"src/old.py|noqa: e402": None})
    assert main() == 1
    assert "stale" in capsys.readouterr().err
