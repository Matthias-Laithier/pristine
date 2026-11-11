# Working on pristine

[README.md](README.md) covers installation and usage. Before coding, run `pristine guide`; use `pristine checks [--json]` for executable coverage. Run the relevant checks while working and the project gate before finishing. Report failures, meaningful exceptions, and unverified behavior.

## Architecture

- `checks/` groups file and path checks by concern: `core/`, `boundaries/`, `composition/`, and `testing/`, split into cohesive subtopics. Each module or package defines a `CHECK` descriptor beside its implementation. `checks/definitions.py` owns the contracts; `checks/registry.py` explicitly imports and lists checks in ID order. Thresholds and detected patterns live in code. Checks share helpers through neutral modules.
- File checks receive one parsed file. Path checks receive discovered paths once in the main process and never parse with tree-sitter.
- `project/` inspects root tooling configuration without executing the project's gate. Its inspection registry connects checks to repository loading, command parsing, and static-tool configuration readers.
- `catalog/` renders the seven-principle guide and executable check catalog. File/path descriptors live with their code; project metadata describes enabled project checks. IDs identify findings and remain stable, without per-ID prose documents.
- `files/` owns discovery and classification; `syntax/` owns tree-sitter parsing and shared syntax helpers; `clients/` and `imports/` own external-client recognition and import-edge readers.
- `engine/` inspects files in isolated workers. `services/` owns process, git, scanner, grammar, and verified native-tool boundaries.
- `reports/` owns findings, per-file outcomes, worker JSON-line encoding, and aggregation; `cli/` owns arguments and text/JSON presentation. `cli/main.py` is the console entry point.
- `audit/` validates native OSV evidence and advisory results. Keep extraction, lookup, and verification gaps distinct from security conclusions.

## Runtime contracts

- Workers run at most `--jobs N` processes, half the CPU cores by default, and emit one JSON line per completed file. A crash or timeout leaves only the current file unchecked; replacement workers continue the scan.
- Grammar downloads share the worker budget and announce first use on stderr. Discovery respects exclusions and leaves out vendored directories. Missing paths are report evidence, not an aborted run.
- Text and JSON describe the same report. `--max N` caps displayed findings while totals and triage retain full counts. Complete verification covers only enabled detected patterns; unsupported inputs and failed boundaries remain explicit verification gaps.
- Native tools prefer exactly compatible installed binaries, otherwise verified pinned releases in a private cache. Provisioning and scanner failures are incomplete verification, never clean scans. Preserve input/output limits, finite deadlines, integrity checks, and advisory source evidence.

## Changing checks

1. Define the check and its precise descriptor together, then register it explicitly in ID order. Metadata names actual languages, patterns, and exemptions; it does not claim whole-field coverage.
2. Test observable behavior and boundaries through `run_pristine` in `tests/conftest.py`. `tests/checks/` mirrors implementation concerns; catalog tests verify executable metadata and CLI behavior. Keep tests deterministic, with independent expected results.
3. For new detection behavior, run it on several real repositories and inspect every finding. Favor precision over recall; uncertain cases remain unverified rather than becoming false positives.

## Quality gate and pins

- `make check` checks formatting, lint, types, tests, and pristine's own source/tests/Makefile; it must pass with zero findings. `pristine project .` must also report zero findings.
- Run `make check-all` before pushing; it adds a gitleaks history scan. CI syncs locked dependencies, caches grammars, and runs this gate.
- Tests parse real grammars, so first use needs network access. Native scanner tests replay reviewed responses and fake process/download boundaries; live advisory lookup and release downloads stay outside the gate.
- Keep `tree-sitter<0.26`: 0.26.0 segfaulted or bus-faulted on TSX/TypeScript trees, while 0.25.2 parsed them cleanly. Lift the pin only after large-codebase validation.
- Native compatibility is pinned to gitleaks 8.30.1 and OSV-Scanner 2.7.0. Update hashes, boundary tests, and compatibility evidence together when changing these releases.
- Keep lint exceptions narrow in `pyproject.toml`: test assertions, bounded argument-list subprocess calls at service/test boundaries, and CLI output. Each exception must match intended behavior, not hide a defect.
- Commits use one-line conventional messages, `type(scope): summary`, and pass `make check`.
