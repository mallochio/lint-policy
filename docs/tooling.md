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
| `complexipy` | Cognitive complexity per function | Limit 15. Nesting raises the score, so it catches deep code that cyclomatic complexity rates as simple. Runs as the `cognitive-complexity` hook from `templates/design-gates-block.yaml`. |
| `import-linter` | Layer order, forbidden imports, import cycles, independent packages | Needs a contract per repository; see `templates/importlinter-fragment.toml`. Runs as the `import-layers` hook. This repo enforces its own contract in `pyproject.toml`. |
| Ruff `PLR0913`, `SLF001` | Parameter count over 5, access to private members | `PLR0913` is the only parameter limit in the stack. `SLF001` stops code from reaching into another module's internals, which `import-linter` cannot see. Tests are exempt from `SLF001`. |

## Overlap between the design gates

Measured on synthetic functions and on this repo.

| Shape | Ruff `C901` | Other Ruff rule | `complexipy` |
|---|---|---|---|
| Flat chain of ten `elif` branches | 11 | `PLR0911` (11 returns) | 10 |
| Eight levels of nested loops and ifs | 9 | `PLR1702` (8 blocks) | 37 |
| Seven parameters | clean | `PLR0913` (7 arguments) | 0 |

- `complexipy` and `C901` agree on flat code. They diverge on nesting, where
  `complexipy` scores four times higher. Keep `C901` for fast editor feedback
  and let `complexipy` carry the nesting limit.
- `PLR1702` (nesting depth) and `PLR0914` (locals) are preview rules and
  duplicate what `complexipy` penalises. They are not adopted.
- `PLR0913` does not overlap with either tool.
- `import-linter` checks which modules import which. `SLF001` checks attribute
  access. Neither covers the other.
- The function length hook and `PLR0915` (statements) overlap. `PLR0915` stays
  in the template because it is cheap.

## Optional

- `refurb` — the standalone tool behind Ruff's `FURB`. Runs on mypy's engine
  and catches patterns Ruff has not ported. Add only if Ruff leaves gaps.
- `lizard` — polyglot function length, cyclomatic complexity, and clone
  detection. Useful for the TypeScript app in SignalFoundry; Python limits
  stay with `line-limits`.
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
- `tach` — layers and explicit public interfaces per module, written in Rust.
  It overlaps `import-linter` on layers. Choose one; `import-linter` is the
  more mature and has independence and forbidden-import contracts.
- `vulture` — dead code. Its unique value (unused functions and fields) only
  appears at 60% confidence, where it flagged dataclass fields in this repo
  and would need a whitelist. Ruff `F401` and `F841` cover the high-confidence
  cases. Revisit if dead helpers become a problem.
- Ruff `PLR2004` (magic numbers) — four hits in this repo, mostly line counts
  and arities. The readability gain does not justify the noise.
- Full pylint — overlaps Ruff. Only `duplicate-code` (R0801) and
  `too-many-lines` (C0302) are unique; `prylint` or `lizard` can cover both.

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
