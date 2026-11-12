<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/soap-bar-dark.svg">
    <img src="assets/brand/soap-bar-light.svg" alt="pristine" width="400">
  </picture>
</p>

<p align="center">Predictable code structure and defect checks for AI coding agents.</p>

<p align="center">
  <a href="https://github.com/Matthias-Laithier/pristine/actions/workflows/check.yml"><img src="https://github.com/Matthias-Laithier/pristine/actions/workflows/check.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/Matthias-Laithier/pristine/releases/latest"><img src="https://img.shields.io/github/v/release/Matthias-Laithier/pristine" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Matthias-Laithier/pristine" alt="License"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.15%2B-blue" alt="Python 3.15+"></a>
</p>

Pristine checks code structure and defect patterns in Python, JavaScript and TypeScript. Findings include a stable ID, location and fix. A seven-bullet guide handles decisions that need judgment.

## Quick start

```sh
uv tool install --python 3.15 git+https://github.com/Matthias-Laithier/pristine
```

```sh
pristine guide
pristine checks
pristine check src tests
pristine project .
```

Add to `AGENTS.md` or `CLAUDE.md`:

```
Before coding, run pristine guide. Run pristine check on touched directories and pristine project on the root, then the project's gate before finishing. Report failures, meaningful exceptions, and unverified behavior.
```

## What it checks

35 source checks cover file and function size, nesting, comments, placement, imports, mutation, external calls, injection patterns, async work and tests. Four project check families inspect the Makefile, verification gates, static tools and reproducible dependencies. `pristine checks --json` lists exact coverage from the implementations.

Check IDs are grouped as `STR` (structure), `DEP` (dependencies), `SAFE` (safety), `TEST` (tests) and `PROJ` (project). JSON uses `check_id`, `by_check` and `distinct_checks`. Version 0.12.0 replaces the old IDs and JSON field names without compatibility aliases.

Supported source: `.py`, `.pyi`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`, `.mts`, `.cts`. Other languages are reported as unsupported. Python and Prisma SQL migrations retain history checks.

Checks favor precision over recall. A clean scan establishes only the advertised patterns. Use Pristine alongside your formatter, linter, type checker and tests. Generic floating promises need type-aware ESLint; TypeScript path aliases, untyped JavaScript mutation and custom test frameworks remain outside the detected patterns.

## Reports

Use `--json` for structured results, `--max N` to limit displayed findings, and `--exclude <glob>` to skip paths. Totals retain every finding. Workers run in isolation, with half the CPU cores by default; `--jobs N` sets the limit. Grammars download on first use. Discovery respects git ignores and skips vendored and generated code.

Exit codes: **0** completed without errors, **1** error findings, **2** invalid usage, **3** incomplete verification. Warnings alone return 0. Scanner failures take priority over findings and never produce a clean verdict.

<details>
<summary>Project-check coverage</summary>

`pristine project` inspects configuration without executing the project's gate. Python annotation coverage requires strict mypy or Ruff's ANN001/002/003/201/202/204/205/206 rules. Unsupported configurations, overrides and incomplete source scope produce verification findings. It complements the project's formatter, linter, type checker and tests.

</details>

## Dependency audit

Optional known-advisory lookup through [OSV-Scanner](https://github.com/google/osv-scanner):

```sh
pristine audit .
pristine audit path/to/uv.lock --json --max 10
```

Supports one `uv.lock`, or a directory containing it. Online lookup sends package identities to OSV. Results cover native-extracted PyPI package/version advisory matches; they establish neither exploitability nor the absence of vulnerabilities. Reported fixed versions are advisory context, not upgrade recommendations.

<details>
<summary>Native tools and verification limits</summary>

OSV-Scanner 2.7.0 uses a compatible installed binary or a verified official release cached in `~/.pristine-native-tools`. macOS/Linux on arm64 and x86_64 are supported. First use requires network access; the cached binary is rechecked for integrity. No global installation or audited-project dependency installation occurs. Failed provisioning or unsafe caches produce incomplete verification.

Audit input/output is capped at 8 MiB with a 300-second deadline. Downloads have a 64 MiB cap and finite deadline. Leaf symlinks are refused. Verification requires matching source evidence and a positive package count. Unknown diagnostics, skips, filters and contradictory exits remain failures. Advisory freshness, installed dependencies, package origins and reachability are outside the audit scope.

Requires [uv](https://docs.astral.sh/uv/) and Python 3.15+. The PyPI package named `pristine` is unrelated. `tree-sitter<0.26` avoids known parser crashes. Live advisory lookups and release downloads stay outside the test gate.

</details>

## Performance

| Repository at revision | Language | Files | Lines | Time |
| --- | --- | ---: | ---: | ---: |
| [requests](https://github.com/psf/requests/tree/3c7baaa05ab4aa49cc819ce3a819d260de19c157) | Python | 37 | 12,032 | 0.638 s |
| [HTTPX](https://github.com/encode/httpx/tree/b5addb64f0161ff6bfe94c124ef76f6a1fba5254) | Python | 60 | 17,753 | 0.495 s |
| [ky](https://github.com/sindresorhus/ky/tree/3541888878c4d303a8bc2ad61815f4e048f55a5d) | TypeScript | 98 | 36,231 | 0.515 s |
| [Zod](https://github.com/colinhacks/zod/tree/19c40d2072288b4cafec851e9d056a72a88e5973) | TypeScript | 520 | 92,471 | 1.466 s |

## Contributing

See [AGENTS.md](AGENTS.md) for architecture, check metadata, tests, and the quality gate.

## License

[MIT](LICENSE)
