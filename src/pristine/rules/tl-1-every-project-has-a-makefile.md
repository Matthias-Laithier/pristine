# TL-1 Every Project Has a Makefile

Every project has a Makefile, whatever the stack. Python, Node, Go, Rust, or a mixed monorepo all share the same front door. `make` is the one convention that crosses every ecosystem: it is on every Unix machine and every CI image. `package.json` scripts exist only in Node projects, `just` and Taskfile need installs, and README paragraphs are prose nobody re-reads.

The Makefile lives at the repository root. A project with several components, such as a backend, a frontend, and a worker, has one root Makefile and no Makefile per component, so the front door is one place. The contract targets always run the whole project: `make dev` starts every component that has something to run, `make check` runs the fast checks of every component, and `make check-all` runs every check. What runs inside a component is an implementation detail. The front door is the root.

The contract has three mandatory targets, in every project, with no exceptions:
- `make dev` runs the project in development mode: dev server, watchers, hot reload, whatever running means for the project. For a library, running means the test watcher or an example harness.
- `make check` is the fast verification gate, defined in [TL-2](tl-2-make-check-is-fast-make-check-all-runs-everything.md).
- `make check-all` is the complete verification gate, slow tests included, defined in [TL-2](tl-2-make-check-is-fast-make-check-all-runs-everything.md).

Two targets join by condition:
- `build` joins exactly when the project produces artifacts, such as compiled binaries, a bundled frontend, or container images. A project with no build step has no build target.
- `install` is optional and common: it takes a fresh clone to running by installing the dependencies and preparing the environment.

Other targets are free, such as `test`, `lint`, `fmt`, `clean`, and `deploy`. The verification gates compose mechanical targets: fast targets belong to `check`, slow targets belong to `check-all`. Operational targets such as `clean` and `deploy` stay independent. The rule mandates the front door and leaves the rest of the Makefile free.

An agent landing on the repository types `make dev` and `make check` before reading anything else. CI runs `make check-all`. The same verbs work on every project, and that is the entire point.

## Bad

```make
.PHONY: run_server qa full_qa format-check lint typecheck test slow-test

run_server:
	uvicorn main:app --reload

qa: format-check lint typecheck test

full_qa: qa slow-test

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

Same actions, invented verbs. The next project says `start`, `verify`, and `verify_all`, and every contributor starts at the README. An agent typing `make check` gets `No rule to make target`.

## Good

```make
.PHONY: dev check check-all format-check lint typecheck test slow-test

dev:
	uvicorn main:app --reload

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

The commands and dependencies are unchanged. Only the public target names changed, and they follow the shared contract: `make dev`, `make check`, and `make check-all`.
