"""Reject explanatory hash comments in Python sources.

Docstrings are not comments. Allowed hash comments are a shebang on line 1,
a PEP 263 encoding cookie, and tooling directives listed in the configuration.
A comment that carries prose followed by a directive is reported so the prose
can be deleted.
"""

from __future__ import annotations

import re
import tokenize
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path

from lintpolicy.baseline import Baseline, over_budget_keys, verify_counts
from lintpolicy.config import Config, load_config
from lintpolicy.directives import extract_directive, starts_with_directive
from lintpolicy.discovery import iter_python_files, relative_path
from lintpolicy.reporting import Finding, Scan, report

_ENCODING_COOKIE = re.compile(r"^[ \t\f]*#.*?coding[:=][ \t]*[-_.a-zA-Z0-9]+")


def scan(config: Config) -> Scan:
    """Return comment findings and per-file counts."""
    findings: list[Finding] = []
    counts: dict[str, int] = {}
    for path in iter_python_files(config.root, config.comment_roots, config.comment_exclude):
        relative = relative_path(path, config.root)
        file_findings = check_file(relative, path, config.comment_allow)
        if not file_findings:
            continue
        findings.extend(file_findings)
        counts[relative] = len(file_findings)
    return Scan(tuple(findings), counts)


def check_file(relative: str, path: Path, allow: Sequence[str]) -> list[Finding]:
    """Return disallowed comments in one file."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [Finding(relative, 1, f"unable to read: {exc}")]
    return disallowed_comments_bytes(raw, relative, allow)


def disallowed_comments_bytes(raw: bytes, filename: str, allow: Sequence[str]) -> list[Finding]:
    """Return disallowed comments in one encoded Python source."""
    findings: list[Finding] = []
    cookie_lines = _cookie_line_numbers(raw)
    try:
        for token in tokenize.tokenize(BytesIO(raw).readline):
            if token.type != tokenize.COMMENT:
                continue
            kept = retained_comment(
                token.string,
                token.start[0],
                allow=allow,
                line=token.line,
                cookie_lines=cookie_lines,
            )
            if kept == token.string:
                continue
            message = f"disallowed comment: {token.string.strip()}; move the note into a docstring or delete it"
            findings.append(Finding(filename, token.start[0], message))
    except (SyntaxError, tokenize.TokenError, UnicodeError, ValueError) as exc:
        return [Finding(filename, 1, f"unable to tokenize: {exc}")]
    return findings


def retained_comment(
    comment: str,
    line_no: int,
    *,
    allow: Sequence[str],
    line: str = "",
    cookie_lines: frozenset[int] = frozenset({1, 2}),
) -> str | None:
    """Return the hash comment to keep, or None when it must be removed."""
    if line_no == 1 and comment.startswith("#!"):
        return comment
    if _is_encoding_cookie(line_no, line if line else comment, cookie_lines):
        return comment
    body = comment[1:].lstrip()
    if starts_with_directive(body, allow):
        return comment
    return extract_directive(comment, allow)


def _cookie_line_numbers(raw: bytes) -> frozenset[int]:
    """Return the line numbers where Python honors a PEP 263 cookie."""
    lines = raw.split(b"\n")[:2]
    numbers: set[int] = set()
    if not lines:
        return frozenset()
    if _matches_cookie(lines[0]):
        numbers.add(1)
    if len(lines) > 1 and (lines[0].strip() == b"" or lines[0].lstrip().startswith(b"#")):
        if _matches_cookie(lines[1]):
            numbers.add(2)
    return frozenset(numbers)


def _matches_cookie(line: bytes) -> bool:
    """Return whether one physical line is a PEP 263 cookie declaration."""
    return _ENCODING_COOKIE.match(line.decode("utf-8", "replace")) is not None


def _is_encoding_cookie(line_no: int, line: str, cookie_lines: frozenset[int]) -> bool:
    """Return whether this comment is a cookie Python would honor."""
    return line_no in cookie_lines and _ENCODING_COOKIE.match(line) is not None


def main() -> int:
    """Run the comment policy on the configured roots."""
    config = load_config()
    result = scan(config)
    budgets = Baseline.load(config.baseline_path).section("comments")
    over, stale = verify_counts("comments", result.counts, budgets)
    unbudgeted = over_budget_keys(result.counts, budgets)
    findings = [finding for finding in result.findings if finding.path in unbudgeted]
    return report("comments", findings, [*over, *stale])
