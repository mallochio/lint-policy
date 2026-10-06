"""Generate or refresh the committed policy baseline."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from lintpolicy import (
    check_comments,
    check_docstrings,
    check_limits,
    check_reinvention,
    check_suppressions,
    check_toplevel,
)
from lintpolicy.baseline import BASELINE_VERSION, save
from lintpolicy.config import Config, load_config
from lintpolicy.numeric import scan as scan_numeric


def collect(config: Config) -> dict:
    """Measure the current tree and return baseline data."""
    return {
        "version": BASELINE_VERSION,
        "comments": check_comments.scan(config).counts,
        "docstrings": check_docstrings.scan(config).counts,
        "limits": check_limits.scan(config).counts,
        "numeric": scan_numeric(config).counts,
        "suppressions": check_suppressions.scan(config).entries,
        "top_level": check_toplevel.scan(config).counts,
        "reinvention": check_reinvention.scan(config).counts,
    }


def render(data: dict) -> str:
    """Render baseline data in the committed format."""
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the baseline command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the baseline file")
    parser.add_argument("--check", action="store_true", help="fail when the committed file differs")
    args = parser.parse_args(argv)
    config = load_config()
    data = collect(config)
    if args.write:
        save(config.baseline_path, data)
        print(f"baseline written: {config.baseline_path}")
        return 0
    rendered = render(data)
    if args.check:
        return _check(config, rendered)
    print(rendered, end="")
    return 0


def _check(config: Config, rendered: str) -> int:
    """Compare the committed baseline text with the rendered baseline."""
    current = ""
    if config.baseline_path.is_file():
        current = config.baseline_path.read_text(encoding="utf-8")
    if current == rendered:
        print("baseline: ok")
        return 0
    print("baseline differs; run lintpolicy-baseline --write and review the diff", file=sys.stderr)
    return 1
