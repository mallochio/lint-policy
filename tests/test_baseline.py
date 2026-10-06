"""Behavior tests for baseline verification."""

from __future__ import annotations

from pathlib import Path

from lintpolicy.baseline import Baseline, over_budget_keys, save, verify_counts


def test_new_finding_fails() -> None:
    over, stale = verify_counts("comments", {"a.py": 2, "b.py": 1}, {"b.py": 1})
    assert over == ["comments: new finding in a.py; fix it or register it in the baseline"]
    assert stale == []


def test_growth_is_reported() -> None:
    over, stale = verify_counts("comments", {"a.py": 3}, {"a.py": 2})
    assert over == ["comments: a.py grew to 3, baseline allows 2"]
    assert stale == []


def test_stale_entry_is_reported() -> None:
    over, stale = verify_counts("comments", {}, {"a.py": 2})
    assert over == []
    assert "stale" in stale[0]


def test_round_trip(tmp_path: Path) -> None:
    save(tmp_path / "baseline.json", {"version": 1, "comments": {"a.py": 1}})
    loaded = Baseline.load(tmp_path / "baseline.json")
    assert loaded.section("comments") == {"a.py": 1}
    assert loaded.section("missing") == {}
    assert Baseline.load(tmp_path / "absent.json").section("comments") == {}


def test_over_budget_keys_flags_missing_and_grown() -> None:
    assert over_budget_keys({"a.py": 2}, {"a.py": 1}) == {"a.py"}
    assert over_budget_keys({"a.py": 1}, {}) == {"a.py"}
    assert over_budget_keys({"a.py": 1}, {"a.py": 1}) == set()
    assert over_budget_keys({}, {"a.py": 1}) == set()
