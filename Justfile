install:
	uv sync
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push

checks:
	uv run pre-commit run --all-files

tests:
	uv run pytest

baseline:
	uv run lintpolicy-baseline --write

baseline-check:
	uv run lintpolicy-baseline --check

report:
	uv run lintpolicy-baseline
