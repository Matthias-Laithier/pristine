# TL-3 Automate Formatting and Static Analysis

Every project automates the mechanical code-quality checks its ecosystem supports. Configure a formatter and a linter. Configure type checking when the language or ecosystem provides a mature, applicable checker. Run these tools through `make check`, and verify formatting without rewriting files in the check target.

Human review decides behavior, design, and domain correctness. It never spends attention on spacing, import order, unreachable code, or other rules a tool can enforce consistently. Tool configuration lives in version control, and local execution and CI use the same configuration.

Generated and vendored code may be excluded when their producer owns their shape. A checker that cannot understand required framework behavior may receive the narrowest targeted suppression. Never disable a rule project-wide to avoid fixing one site, and never add a tool that produces unactionable noise.

## Bad

```make
check:
	pytest
```

Formatting and static defects depend on reviewers noticing them, and different contributors apply different standards.

## Good

```make
.PHONY: check format-check lint typecheck test

check: format-check lint typecheck test

format-check:
	ruff format --check .

lint:
	ruff check .

typecheck:
	mypy .

test:
	pytest -m "not slow"
```

One fast command applies the formatter, the linter, the type checker, and the tests of the project with versioned configuration. See [TL-2](tl-2-make-check-is-fast-make-check-all-runs-everything.md).
