# Changelog

## 0.4.4

Explanatory `#` comments are never baselined.

- Every prose `#` comment in the configured roots fails. Shebangs, PEP 263
  encoding cookies, and the directive allow-list (`noqa`, `type: ignore`,
  `pyright: ignore`, `pragma: no cover`, `fmt:`, `ruff:`, `nosec`) are unchanged.
- A non-empty `comments` section in the baseline fails with a message to remove it.
- `lintpolicy-baseline` no longer writes comment counts.
