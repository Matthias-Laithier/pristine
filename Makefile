.PHONY: dev install check check-all format format-check lint typecheck test selfcheck dead-code audit

dev:
	uv run pristine check src tests

install:
	uv sync --locked

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

check: format-check lint typecheck test selfcheck dead-code

check-all: check
	gitleaks git --redact --no-banner .
	$(MAKE) audit

format-check:
	uv run ruff format --check src tests

lint:
	uv run ruff check src tests

typecheck:
	uv run ty check src tests

test:
	uv run pytest -q

selfcheck:
	uv run pristine check src tests Makefile

dead-code:
	uv run vulture src tests --min-confidence 100

audit:
	uv run pip-audit --skip-editable
