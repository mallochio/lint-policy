# Code Policy (agent block)

Paste this block into a target repository's `AGENTS.md`.

---

## Code Policy

- No `#` comments in Python. Docstrings only. Allowed hash comments are a
  shebang, a PEP 263 encoding cookie, and registered tool directives.
- Every module, class, and function in the source roots needs a docstring.
  Docstrings follow Google style. Tests are exempt from docstrings.
- Files stay below 300 lines. Functions stay below 30 lines excluding their
  docstrings. Decorators do not count.
- Keep cognitive complexity per function at 15 or less and functions to five
  parameters or fewer. Respect the `import-linter` layers: import downward
  only, and do not access private members of other modules.
- Imports and module-level assignments belong at the top of the file. No
  imports inside functions or classes. A module-level assignment after the
  first class or function definition fails.
- Before writing an implementation, check the standard library, an existing
  dependency, and existing repo helpers. The `reinvention-guard` hook flags
  common hand-rolled idioms; algorithm-level duplication is a review
  concern and must be justified in the PR.
- No new `# noqa`, `# type: ignore`, `# pyright: ignore`, or `# nosec`
  directives. A directive needs ` - reason: <why>` and a baseline entry that a
  reviewer can see in the diff.
- Fix the code, not the check. Baseline entries can only shrink. When
  `lintpolicy` reports a stale entry, remove the entry and run
  `uvx --from git+https://github.com/mallochio/lint-policy lintpolicy-baseline --write`.
- Run `just checks-ci` before pushing, and report any check that cannot run.
