# TL-2 `make check` Is Fast, `make check-all` Runs Everything

`make check` runs every fast mechanical check: the linter, the typechecker, fast tests, format verification, and anything else that should run before every push. A fast mechanical check that exists in the project and is missing from `check` is a defect: the gate lies by omission. [TL-3](tl-3-automate-formatting-and-static-analysis.md) defines the required code-quality checks. `make check-all` runs `check` first, then every remaining mechanical check, such as slow integration, end-to-end, load, and dependency checks.

`make check-all` includes `make check` and every remaining mechanical check, such as slow integration, end-to-end, load, and applicable dependency checks. A check that exists in the project and is in neither target is a defect. See [TL-4](tl-4-keep-dependencies-minimal-declared-and-audited.md).

Evals of model quality are the exception. They are nondeterministic measurements and no pass or fail gate, so they live in `make eval`, outside `check` and `check-all` (see [TST-8](tst-8-model-quality-is-measured-by-evals-code-by-deterministic-tests.md)).

`check` is the fast local verdict of the project. `check-all` is the complete verdict. CI runs `make check-all` verbatim and never re-implements it in pipeline config, so local and CI verification share one implementation.

`check` is fast enough to run before every push. A slow `make check` is a skipped gate, and a skipped gate protects nothing. The fast test suite does its part by staying minimal (see [TST-3](tst-3-minimal-test-count.md)).

## Bad

```make
check:
	pytest -m "not slow"

check-all:
	pytest -m slow
```

`make check` is green while the linter and the typechecker would both fail, and `make check-all` runs the slow tests without the fast gate. The fast gate says healthy, no target gives the complete verdict, and review finds what tooling should have found.

## Good

```make
.PHONY: check check-all format-check lint typecheck test slow-test

check: format-check lint typecheck test

check-all: check slow-test

format-check:
	ruff format --check .

lint:
	ruff check .

typecheck:
	mypy .

test:
	pytest -m "not slow"

slow-test:
	pytest -m slow
```

The verification step in the CI job:

```yaml
- run: make check-all
```

The fast gate stays cheap enough for every push. The complete gate runs through one command locally and in CI, and no mechanical check escapes to review.
