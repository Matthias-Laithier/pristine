# TL-4 Keep Dependencies Minimal, Declared, and Audited

Every dependency has a present use, an explicit declaration, and an owner who can explain why the standard library or the existing dependencies do not satisfy the requirement. Remove unused packages and development tools in the change that makes them obsolete. Keep runtime, development, and optional dependencies in their correct scopes. Install from the lockfile in frozen mode, and pin the runtime version.

Deployable applications commit the lockfile of their ecosystem and build from it reproducibly. Every install from a lockfile runs in frozen mode: `uv sync --locked`, `npm ci`, `pnpm install --frozen-lockfile`, `go mod download`. A lockfile that a plain install silently rewrites protects nothing. Reusable libraries declare compatible ranges for their direct dependencies and use a lockfile for their own development and tests when the ecosystem supports one. Never edit generated lockfiles by hand.

The runtime version is pinned: `.python-version` or `requires-python` in `pyproject.toml`, `engines` in `package.json`, the `go` directive in `go.mod`. Local development, CI, and production then run the same interpreter or toolchain, and the frozen lockfile resolves against the runtime it was locked for.

Run the available vulnerability and obsolete-dependency checks regularly, and through `make check-all` when they are deterministic enough for the complete gate. A reported vulnerability requires an assessment. A blind upgrade is no answer. Record temporary pins, ignored advisories, forks, and postponed upgrades with their reason and their removal condition.

Transitive dependencies belong to the direct package that selected them. Declare a transitive package directly only when application code imports it or the project must constrain it for a documented compatibility or security reason. [CR-2](cr-2-do-not-reinvent.md) owns whether to adopt a dependency. This rule owns it after adoption.

## Bad

```toml
[project]
requires-python = ">=3.13,<3.14"
dependencies = [
    "requests",
    "python-dateutil",
    "pytz",
]
```

The application uses `requests` and relies on the standard library for dates and time zones. The two unused packages still expand installation, updates, and vulnerability review.

## Good

```toml
[project]
requires-python = ">=3.13,<3.14"
dependencies = [
    "requests>=2.32,<3",
]
```

The manifest declares only the direct package the application uses. Its generated lockfile records the exact deployable dependency graph, and `requires-python` pins the interpreter it runs on.
