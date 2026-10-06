# Rollout

How to bring an existing repository under the shared policy without blocking
all work on day one.

## 1. Prepare the policy repo

Tag a release in `mallochio/lint-policy` and pin that tag as `rev` in every
target repository. Private repositories need credentials in CI for
pre-commit to clone the hook repo.

## 2. Configure the target repository

Add the hook block from `templates/pre-commit-block.yaml`. Set roots in
`[tool.lintpolicy]` when the layout is not `src`/`scripts`/`tests`. See
`templates/lintpolicy.toml` for an annotated example.

## 3. Record the baseline

```bash
uvx --from git+https://github.com/mallochio/lint-policy lintpolicy-baseline --write
uv run pre-commit run --all-files
```

The first run should pass, because every current violation is in the
baseline. Commit the baseline together with the hook block. The baseline diff
is the review artifact: reviewers can see exactly what debt is being
grandfathered.

## 4. Fix in waves

Fix one package or file at a time:

1. Remove the violations.
2. Run `lintpolicy-baseline --write`.
3. Commit the smaller baseline with the fix.

The hooks fail on stale entries, so the baseline cannot silently keep debt
that was already removed. Prefer waves that end in one reviewable PR each.

Recommended wave order:

1. Delete dead suppression directives that reference rules that are not
   enabled. This is free progress.
2. Delete explanatory comments and fold their content into docstrings.
3. Add docstrings, largest gaps first.
4. Move imports and module-level assignments to the top of each file.
5. Split files at 300 lines and functions at 30 lines, guided by `line-limits`
   output.
6. Register or remove the remaining suppressions.

## 5. Tighten

When a tool's baseline section is empty, the ratchet is at zero for that
tool. Keep it there: any new violation fails. To check that the repository
still matches its baseline, run:

```bash
uvx --from git+https://github.com/mallochio/lint-policy lintpolicy-baseline --check
```
