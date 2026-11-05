# TL-3 Automate Formatting and Static Analysis

Every project automates the mechanical code-quality checks its ecosystem supports. Configure a formatter, a linter with the rule sets that back up the rules of this guide, and a type checker in its strict mode when the language or ecosystem provides a mature, applicable checker. Run these tools through `make check`, and verify formatting without rewriting files in the check target.

Human review decides behavior, design, and domain correctness. It never spends attention on spacing, import order, unreachable code, or other rules a tool can enforce consistently. Tool configuration lives in version control, and local execution and CI use the same configuration.

The type checker runs in its strict mode: `strict = true` for mypy, `typeCheckingMode = "strict"` for pyright, `"strict": true` in `tsconfig.json`, and the equivalent for other checkers. A default mode accepts unannotated definitions and implicit `Any`, the gaps [CR-21](cr-21-never-escape-the-type-checker.md) forbids. ty has no strict mode, as of version 0.0.96 released on 2026-11-02. Its closest setting is `all = "error"` under `[tool.ty.rules]`, which turns on the rules that default to warn or ignore.

The linter enables the rule sets that enforce the detail of a rule better than pristine does:
- Python with ruff: `S` for security, backing [BS-3](bs-3-bound-every-external-call.md) and [BS-10](bs-10-untrusted-values-never-change-the-structure-of-a-query-command-markup-or-path.md). `ASYNC` for [BS-13](bs-13-async-code-never-blocks-the-event-loop.md). `DTZ` for the datetimes of [CR-22](cr-22-instants-are-aware-utc-money-is-exact-quantities-name-their-unit.md). `G` for the logging format and `T20` for `print`, both backing [BS-15](bs-15-log-diagnosable-events-never-personal-data.md).
- TypeScript: the `strict-type-checked` configuration of typescript-eslint, which includes `no-floating-promises` and `no-explicit-any`, plus `react-hooks` and `jsx-a11y` in React projects.

[CR-21](cr-21-never-escape-the-type-checker.md) owns the escape hatches that silence the checker. This rule owns configuring and running the checker and the linter.

Generated and vendored code may be excluded when their producer owns their shape. A checker that cannot understand required framework behavior may receive the narrowest targeted suppression. A command-line program ignores `T20` only in the module that writes its user-facing output, following the exception of [BS-15](bs-15-log-diagnosable-events-never-personal-data.md). Never disable a rule project-wide to avoid fixing one site, and never add a tool that produces unactionable noise.

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

`pyproject.toml`:

```toml
[tool.ruff.lint]
extend-select = ["S", "ASYNC", "DTZ", "G", "T20"]

[tool.mypy]
strict = true
```

One fast command applies the formatter, the linter, the type checker, and the tests of the project with versioned configuration. Strict mode rejects an unannotated function, and the lint sets catch a naive datetime or a blocking call in a coroutine before review. See [TL-2](tl-2-make-check-is-fast-make-check-all-runs-everything.md).
