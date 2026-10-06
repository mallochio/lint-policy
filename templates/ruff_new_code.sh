#!/usr/bin/env bash
set -euo pipefail

if git rev-parse --verify origin/main >/dev/null 2>&1; then
  base="$(git merge-base HEAD origin/main)"
elif git rev-parse --verify main >/dev/null 2>&1; then
  base="$(git merge-base HEAD main)"
else
  echo "[ruff-new] no main branch found; skipping new-code lint"
  exit 0
fi

report="$(mktemp)"
trap 'rm -f "$report"' EXIT

uv run ruff check . --output-format=concise > "$report" || true
uvx --from ondivi==0.7.3 ondivi --fromfile "$report" --baseline "$base"