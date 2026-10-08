# Tooling survey

Off-the-shelf packages evaluated against the policy hooks in this repo. The
goal is to own as little custom code as possible and to adopt a package
whenever it implements a rule exactly.

## Adopt now

| Tool | Covers | Notes |
|---|---|---|
| Ruff `FURB` (refurb) | Reinvented stdlib idioms: reimplemented operators, read-whole-file, repeated append, prefix/suffix slices | 36 refurb checks ported into Ruff, all autofixable. The closest thing to an off-the-shelf "do not reinvent the wheel" linter. |
| Ruff `PTH`, `SIM`, `C4`, `PERF`, `DTZ`, `PIE` | Hand-rolled paths, control flow, comprehensions, loops, datetimes | Mostly enabled in the target repos already. Contained in `templates/pyproject-fragment.toml`. |
| Ruff `E402`, `PLC0415` | Imports after code, imports inside functions | `E402` is already active in most repos; `PLC0415` is the pylint equivalent. Our `top-level-order` hook adds the globals rule and the baseline. |
| Ruff `RUF100`, `PGH003`, `PGH004` | Unused `noqa`, blanket `type: ignore`, blanket `noqa` | Supersedes the `flake8-noqa` plugin without adding flake8. |
| `ondivi` | Changed-lines baseline for any linter (Ruff, flake8, pylint, mypy) | Phase in the Ruff families above in repos with existing debt without a `noqa` dump. Pin `ondivi==0.7.3`. Uses `git diff` against the merge base, so violations within the diff context window of a change are also flagged. |
| `docvet` | Stale docstrings (freshness), plus presence and enrichment reporting | Gate `freshness` only, and run the hook with `args: ["--staged"]` plus `pass_filenames: false`. Diff mode inspects the git diff; with file arguments it reads an empty unstaged diff and passes vacuously. It reported zero findings across all four repos. Enrichment findings are far too many to gate (534 on cerberus); they stay warnings. Pin `v1.16.0`. |
| `complexipy` | Python cognitive complexity (nesting-aware) | Complements Ruff `C901` / `PLR0912` (cyclomatic / branch density). Config lives in `templates/pyproject-fragment.toml` (`max-complexity-allowed = 20`). Official pre-commit hook (`complexipy-pre-commit`), PyPI wheels, snapshots, and a Python API. Already wired in mantis and the thermo-nuclear cleanup standard. |

## Optional

- `refurb` — the standalone tool behind Ruff's `FURB`. Runs on mypy's engine
  and catches patterns Ruff has not ported. Add only if Ruff leaves gaps.
- `lizard` — polyglot function length, cyclomatic complexity, and clone
  detection. Useful for the TypeScript app in SignalFoundry; Python limits
  stay with `line-limits`. For polyglot cognitive + cyclomatic gates, prefer
  evaluating `cccc` (below) over lizard's cyclomatic-only heuristic.
- `cccc` — Rust CLI for cognitive and cyclomatic complexity across many
  languages (Python via tree-sitter, plus TS/JS, Go, Rust, and others). Strong
  for mixed-language trees and CI caching (`cccc-action`). Keep as a
  polyglot/TS option; do not replace `complexipy` for Python-only policy
  (see skipped note).
- `flake8-max-function-length` — exact function-length rule that excludes
  docstrings by default. Use it instead of our function limit only if a plugin
  is preferred over our hook; it has no file length and no baseline.
- `prylint` — a fast, byte-identical pylint port in Rust. Could run
  `too-many-lines` (C0302) or `duplicate-code` (R0801) without pylint's cost,
  including the O(n^2) duplicate check. Young project; evaluate before use.

## Considered and skipped

- `nocomment-linter` — bans Python comments and is built for coding agents,
  with a directive allowlist close to ours. Our `no-comments` hook adds the
  committed baseline and directive registration and keeps the rule inside this
  package, so the extra dependency buys little.
- `interrogate` / `docstr-coverage` — docstring coverage percentages. Our hook
  is stricter (every definition, per-file ratchet); percentage gates hide
  debt. `docvet` supersedes both.
- `flake8-noqa` — needs flake8; the useful checks are in Ruff as `RUF100`,
  `PGH003`, and `PGH004`.
- `wemake-python-styleguide` — the strongest design-limit linter (module
  members, locals, expression counts, try body). Adopting it wholesale would
  flood the repos and overlap Ruff; cherry-picking through flake8 is more
  machinery than the current hooks justify.
- Full pylint — overlaps Ruff. Only `duplicate-code` (R0801) and
  `too-many-lines` (C0302) are unique; `prylint` or `lizard` can cover both.
- `cccc` as a `complexipy` replacement — skipped for this Python policy.
  Side-by-side on Sonar-style fixtures (nested `if`, `elif`/`else`,
  `match`, logical runs, `sum_of_primes`) both tools report the same
  cognitive scores. The only Python deltas found were multi-site recursion
  and comprehension nesting (cccc stricter by 1). That is not a meaningful
  cognitive-complexity win for Python-only repos. `complexipy` already
  matches the stack: `pyproject.toml` config, official pre-commit hook,
  PyPI install, snapshot grandfathering, and the ≤20 house standard used by
  mantis and repo-cleanup-crew. `cccc` is younger, installs as a
  cargo/binary (no first-party pre-commit repo), and uses `cccc.toml`.
  Revisit `cccc` when a target repo needs one cognitive gate across Python
  and TypeScript, not for a better Python cognitive metric.

## Custom rules that stay ours

No off-the-shelf package found for:

- `numeric-guards` — raising numeric `isinstance` guards that accept bool.
- `reinvention-guard` patterns not in refurb: counter bumps, `mktemp`, retry
  loops, `sum/len` means.
- `suppression-ratchet` — a reason plus a committed baseline entry.
- `top-level-order` — module-level assignments after the first definition.
- File length at 300 with a committed baseline. Pylint `too-many-lines` needs
  pylint; this hook is exact and ratcheted.

## Pattern engines

`semgrep` and `ast-grep` express custom rules as YAML patterns in many
languages, with agent-oriented rule-writing support. They are the right move
if the custom rule set grows past a handful or must cover TypeScript. They are
heavier than the stdlib-only hooks here, so they stay a future option.
