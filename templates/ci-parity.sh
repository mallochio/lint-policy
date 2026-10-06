#!/usr/bin/env bash
set -euo pipefail

resolve_merge_base() {
  if git rev-parse --verify origin/main >/dev/null 2>&1; then
    git merge-base HEAD origin/main
    return
  fi
  if git rev-parse --verify main >/dev/null 2>&1; then
    git merge-base HEAD main
    return
  fi
  return 1
}

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" = "main" ]; then
  echo "[ci-parity] On main: running pre-commit --all-files (matches push CI)"
  exec uv run pre-commit run --all-files --show-diff-on-failure
fi

if ! base="$(resolve_merge_base)"; then
  echo "[ci-parity] Could not resolve merge base with main; skipping scoped check."
  exit 0
fi

echo "[ci-parity] Running pre-commit scoped to ${base}..HEAD (matches PR CI)"
exec uv run pre-commit run --show-diff-on-failure --from-ref "$base" --to-ref HEAD
