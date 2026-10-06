# lint-policy

Shared pre-commit policy hooks for agentic Python repositories. This repo is
the single source of truth for the rules agents must follow. Each project
references it at a pinned revision and keeps its own configuration and
baseline.

## Hooks

| Hook id | Rule |
|---|---|
| `no-comments` | No `#` comments in Python. Docstrings only. Shebangs, encoding cookies, and registered tool directives are allowed. |
| `require-docstrings` | Every module, class, and function in the source roots has a docstring. Tests are exempt by default. |
| `line-limits` | Files stay below 300 lines. Functions stay below 30 lines excluding their docstrings. |
| `numeric-guards` | A raising `isinstance(value, int)` guard must also exclude `bool`. |
| `suppression-ratchet` | Every `noqa`, `type: ignore`, `pyright: ignore`, and `nosec` directive carries ` - reason: ...` and a baseline entry. |
| `top-level-order` | Imports and module-level assignments belong at the top of the file. |
| `reinvention-guard` | Hand-rolled counter, defaultdict, dict copy, `mktemp`, mean, and retry shapes are rejected with the replacement named. |

All hooks run repository-wide on every commit and push. None of them inspect
only the changed files, because the baseline checks are global.

## Install in a repository

1. Add the hook block to `.pre-commit-config.yaml`:

   ```yaml
     - repo: https://github.com/mallochio/lint-policy
       rev: v0.2.0
       hooks:
         - id: no-comments
         - id: require-docstrings
         - id: line-limits
         - id: numeric-guards
         - id: suppression-ratchet
         - id: top-level-order
         - id: reinvention-guard
   ```

2. Configure roots when they are not `src`, `scripts`, and `tests`. Put the
   table in `pyproject.toml`, or in a standalone `.lintpolicy.toml` with the
   same keys at top level:

   ```toml
   [tool.lintpolicy]
   source-roots = ["foundation-gemini/src"]
   test-roots = ["foundation-gemini/src/tests"]
   ```

3. Record the current debt once:

   ```bash
   uvx --from git+https://github.com/mallochio/lint-policy lintpolicy-baseline --write
   ```

4. Run the hooks:

   ```bash
   uv run pre-commit run --all-files
   ```

5. Add the policy block to `AGENTS.md`, from `docs/AGENTS-snippet.md`.

See `docs/rollout.md` for the migration plan for repositories with existing
debt and for CI access to the private hook repo.

## Configuration reference

| Key | Default | Effect |
|---|---|---|
| `source-roots` | `["src", "scripts"]` | Production roots. |
| `test-roots` | `["tests"]` | Test roots. |
| `baseline` | `.lintpolicy-baseline.json` | Baseline file name, relative to the repo root. |
| `comments.roots` | source + test | Roots scanned by `no-comments`. |
| `comments.allow` | `noqa`, `type: ignore`, `pyright: ignore`, `pragma: no cover`, `fmt:`, `ruff:`, `nosec` | Directive prefixes allowed as hash comments. |
| `docstrings.roots` | source | Roots scanned by `require-docstrings`. |
| `<tool>.exclude` | `[]` | fnmatch patterns against repo-relative paths, for example `["**/tests/**", "**/test_*.py"]` to keep tests out of the docstring check. |
| `limits.roots` | source + test | Roots scanned by `line-limits`. |
| `limits.file-lines` | `300` | A file fails at this many lines or more. |
| `limits.function-lines` | `30` | A function fails at this many lines or more, excluding its docstring. |
| `suppressions.roots` | source + test | Roots scanned by `suppression-ratchet`. |
| `suppressions.require-reason` | `true` | A new directive without ` - reason: ...` fails. |
| `top-level.roots` | source + test | Roots scanned by `top-level-order`. |
| `reinvention.roots` | source + test | Roots scanned by `reinvention-guard`. |
| `numeric.roots` | source | Roots scanned by `numeric-guards`. |

Every section accepts a `roots` key that replaces the default. Examples live
in `templates/lintpolicy.toml`.

## Baseline ratchet

The baseline records existing debt, so new violations fail immediately while
old ones do not block unrelated work.

- A violation that is not in the baseline fails.
- A violation that grows past its baseline value fails.
- A baseline entry that no longer matches anything fails as stale. This is
  what forces the baseline to shrink: after a cleanup, run
  `lintpolicy-baseline --write` and commit the smaller file.
- `lintpolicy-baseline --check` fails when the committed baseline differs
  from the tree, which is useful in CI.

Baseline values for `line-limits` are measurements, not counts: the file line
count and the function line count. They ratchet the same way.

## Counting rules

- A file fails at 300 lines or more. File length is the number of physical
  lines.
- A function fails at 30 lines or more, counted from the `def` line to the
  last line of the body, minus its docstring lines. Decorators are not
  counted.
- Docstring and comment text do not count against a function, because
  comments are banned and docstrings are excluded by design.

## Ordering rules

The import region of a file covers its docstring, imports, import fallback
blocks (`try`/`except` and conditional blocks whose bodies hold only
imports), `if TYPE_CHECKING:` blocks, and an `__all__` assignment. An import
outside that region, or any import inside a function or class, fails.

A module-level assignment after the first class or function definition
fails. Assignments inside a `__main__` guard are exempt, because that block
is the program entry point.

## Reinvention rules

`reinvention-guard` flags shapes that agents rewrite by hand and names the
library replacement:

- `d[k] = d.get(k, 0) + 1` -> `collections.Counter`
- `if k not in d: d[k] = []` -> `collections.defaultdict` or `dict.setdefault`
- `for k, v in src.items(): dst[k] = v` -> `dst.update(src)`
- `tempfile.mktemp` -> `NamedTemporaryFile`, `TemporaryDirectory`, or `mkstemp`
- `sum(values) / len(values)` -> `statistics.fmean`
- `time.sleep` inside an `except` in a loop -> `tenacity`, `backoff`, or the repo helper

Algorithm-level duplication of a library cannot be detected syntactically.
Cover that case with the `AGENTS.md` rule and review. The Ruff families
`FURB`, `PTH`, `SIM`, `C4`, `PERF`, `DTZ`, and `PIE` catch many further
reinvented idioms; see `templates/pyproject-fragment.toml`.

## Companion checks

`templates/` holds the recommended pieces for a target repository:

- `pre-commit-block.yaml`: the hook block to paste.
- `lintpolicy.toml`: annotated configuration example.
- `pyproject-fragment.toml`: ruff, complexipy, pytest, and coverage settings.
- `ci-parity.sh`: scoped pre-commit script for the pre-push stage.
- `ruff_new_code.sh`: changed-line Ruff gate using ondivi.
- `docvet-block.yaml`: docstring freshness hook block.
- `AGENTS-snippet.md`: the policy block to paste into `AGENTS.md`.
- `docs/tooling.md`: survey of off-the-shelf tools and what to adopt.

## Development

```bash
just install
just checks
just tests
```
