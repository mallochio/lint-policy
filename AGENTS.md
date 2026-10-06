# Agent Instructions

This repository is the shared lint policy for agentic Python repositories.
Follow the policy here before you change any hook.

## Commands

- `just install` installs the package and both pre-commit hook stages.
- `just checks` runs every hook on every file.
- `just tests` runs the test suite.
- `just baseline` regenerates the baseline after a cleanup.
- `just baseline-check` verifies the committed baseline matches the tree.

## Rules

- No `#` comments in Python. Docstrings only. The hooks in this repo enforce
  the same rules they provide to other repositories.
- Every module, class, and function in `src/` needs a docstring.
- Files stay below 300 lines. Functions stay below 30 lines excluding their
  docstrings. Decorators do not count.
- Do not add suppression directives. Fix the code or the check instead.
- Keep test functions small and test files short. Tests are exempt from
  docstrings, not from the comment ban or the line limits.
- When a hook reports a stale baseline entry, remove the entry and rerun
  `just baseline` rather than weakening the check.
