"""Read, verify, and write the committed policy baseline.

The baseline is the ratchet for existing debt. It records, per tool, the
current set of violations or measurements. A violation that is not in the
baseline fails immediately. A baseline entry that no longer matches anything
in the tree also fails, so the baseline can only shrink.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

BASELINE_VERSION = 1


@dataclass(frozen=True)
class Baseline:
    """Parsed baseline data."""

    data: dict

    @classmethod
    def load(cls, path: Path) -> Baseline:
        """Load the baseline, or return an empty one when the file is absent."""
        if not path.is_file():
            return cls({})
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def section(self, tool: str) -> dict:
        """Return one tool section, or an empty mapping."""
        value = self.data.get(tool)
        return value if isinstance(value, dict) else {}


def save(path: Path, data: dict) -> None:
    """Write baseline data as sorted, newline-terminated JSON."""
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def over_budget_keys(actual: Mapping[str, int], budgets: Mapping[str, int]) -> set[str]:
    """Return keys that exceed their baseline budget or have no entry."""
    return {key for key, value in actual.items() if value > budgets.get(key, 0)}


def verify_counts(tool: str, actual: Mapping[str, int], budgets: Mapping[str, int]) -> tuple[list[str], list[str]]:
    """Return over-budget and stale messages for one count-based tool."""
    over: list[str] = []
    for key in sorted(over_budget_keys(actual, budgets)):
        budget = budgets.get(key)
        if budget is None:
            over.append(f"{tool}: new finding in {key}; fix it or register it in the baseline")
        else:
            over.append(f"{tool}: {key} grew to {actual[key]}, baseline allows {budget}")
    stale = [f"{tool}: baseline entry is stale, remove it: {key}" for key in sorted(budgets) if actual.get(key, 0) == 0]
    return over, stale
