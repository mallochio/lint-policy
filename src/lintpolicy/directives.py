"""Detect tooling directives in Python comment text."""

from __future__ import annotations

import re
import tokenize
from collections.abc import Iterator, Sequence
from io import BytesIO


def normalize(text: str) -> str:
    """Collapse whitespace so directive prefixes match reliably."""
    collapsed = re.sub(r"\s+", " ", text.strip()).lower()
    return re.sub(r"\s*:\s*", ": ", collapsed).strip()


def starts_with_directive(body: str, allow: Sequence[str]) -> bool:
    """Return whether comment text is only a tooling directive."""
    normalized = normalize(body)
    for prefix in allow:
        needle = normalize(prefix)
        if not normalized.startswith(needle):
            continue
        rest = normalized[len(needle) :]
        if rest == "" or rest[0] in " :[" or rest.startswith(" - "):
            return True
    return False


def extract_directive(comment: str, allow: Sequence[str]) -> str | None:
    """Return the directive portion of a comment, or None."""
    position = comment.find("#", 1)
    while position != -1:
        candidate = comment[position + 1 :].lstrip()
        if starts_with_directive(candidate, allow):
            return "# " + candidate
        position = comment.find("#", position + 1)
    return None


def iter_comments(raw: bytes) -> Iterator[tuple[str, int]]:
    """Yield comment text and line number pairs from encoded source."""
    try:
        for token in tokenize.tokenize(BytesIO(raw).readline):
            if token.type == tokenize.COMMENT:
                yield token.string, token.start[0]
    except (SyntaxError, tokenize.TokenError, UnicodeError, ValueError):
        return
