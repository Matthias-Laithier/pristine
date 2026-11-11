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

pristine checks code structure, supported defect patterns, and project tooling. A short guide covers decisions that need judgment; an executable check catalog describes what the scanner actually detects. Use it alongside your formatter, linter, type checker, and tests.

## Quick start

```sh
uv tool install --python 3.15 git+https://github.com/Matthias-Laithier/pristine
```

```sh
pristine guide
pristine checks --json
pristine check src tests
pristine project .
pristine audit .
```

For an agent's `AGENTS.md` or `CLAUDE.md`:

```
Before coding, run pristine guide. Run pristine check on touched directories and pristine project on the root, then the project's gate before finishing. Report failures, meaningful exceptions, and unverified behavior.
```

**Breaking change in 0.9.0:** `rule`, `rules`, and `growth` are removed. Use `guide` for principles and `checks [--json]` for mechanical coverage. Rule documents were archived outside the package and removed; check IDs remain stable finding identifiers, not a prose compliance checklist.

## Checks and reports

`pristine checks` lists enabled file, path, and project checks from executable metadata. Its JSON form contains `rule_id`, `title`, `checked_by`, and `summary`. Coverage varies by language and pattern: a clean scan is not assurance about all defects or security properties.

`check` uses tree-sitter grammars, downloaded on first use, and isolated workers. A crashed or timed-out worker leaves its current file unchecked while the scan continues. `--jobs N` caps processes; the default is half the CPU cores. Discovery respects git ignores and skips vendored, generated, and data files where appropriate; the secret scan also includes discovered data and lockfiles. Unsupported formats, missing paths, and verification failures remain visible.

Text groups findings by file, ranked by distinct check IDs then path. JSON retains full paths and lines and includes ranked `triage` evidence. `--max N` caps displayed findings, not totals or file overviews. `--exclude <glob>` skips matching paths. Use command `--help` for options.

`project` recognizes Python, JavaScript/TypeScript, Go, and Rust repositories. It reads the root Makefile, manifests, lockfiles, and supported static-tool configurations without running the project's gate. Python's annotation capability requires strict mypy or Ruff's ANN001/002/003/201/202/204/205/206 rules; inference alone is insufficient. Recognized suppressions disable that capability, and unsupported overrides or incomplete source scope produce verification findings.

Exit codes: **0** complete without errors (warnings may remain), **1** error findings, **2** invalid usage, **3** incomplete verification. Incomplete verification takes priority over findings. Complete verification refers only to the checks performed.

## Python and TypeScript coverage

Every language-applicable source check has Python and JS/TS detection, including TSX. TypeScript adds settings reads, known dropped promise operations, async blocking calls, concurrent fan-out, log interpolation, composition patterns, function clones, model settings, and test-quality patterns. Detectors use language-specific evidence and exemptions. This is check-family coverage, not identical recall or whole-program verification.

CR-22's naive-datetime check is Python-specific. JavaScript `Date` already represents an instant. Generic floating promises need type-aware `@typescript-eslint/no-floating-promises`; pristine detects only recognized promise-producing APIs. Import cycles resolve known local edges, not arbitrary TypeScript path aliases. Untyped JavaScript mutation, custom test frameworks, and arbitrary client aliases are not inferred. Use `pristine checks` for each detector's precise scope.

## Installation and native tools

Install with [uv](https://docs.astral.sh/uv/), which obtains Python 3.15+ when needed. The `pristine` package on PyPI is unrelated. `tree-sitter` remains below 0.26 because 0.26.0 crashed while walking TSX and TypeScript trees.

Native scanners prefer exactly compatible installed executables: [gitleaks](https://github.com/gitleaks/gitleaks) **8.30.1** and [OSV-Scanner](https://github.com/google/osv-scanner) **2.7.0**. Otherwise pristine downloads a pinned official release, verifies committed hashes, and caches it privately in `~/.pristine-native-tools`. Other installed versions are untouched. Provisioning supports macOS/Linux on arm64/aarch64 and x86_64 and needs HTTPS access to GitHub release assets on first use. Warm use rechecks executable integrity without downloading again.

Provisioning, network, corrupt-cache, and unsafe-cache failures mean incomplete verification, never a clean scan. For a damaged cache, remove its affected private entry and retry. Downloads have a 64 MiB cap and finite deadline. No administrator access, package-manager operation, global PATH change, project-owned static-tool installation, or audited-project dependency installation is performed.

## Optional dependency audit

```sh
pristine audit .
pristine audit path/to/uv.lock --json --max 10
```

`PATH` is required: one `uv.lock` or a directory's root `uv.lock`. Coverage is limited to the PyPI package/version records OSV-Scanner extracts. There is no recursive discovery, manifest resolution, source scanning, reachability analysis, package-origin assurance, or dependency installation. Unsupported inputs and platforms cannot produce a clean result.

The target becomes an absolute path; leaf symlinks are refused and ancestors resolved. A complete scan requires exactly one matching source and a positive extraction count consistent with native JSON package evidence. Input and combined scanner output are capped at 8 MiB, with a 300-second scan deadline. Native warnings, errors, filters, skips, contradictory exits, and unknown diagnostics or output shapes fail closed, even when advisories are found. Experimental extraction flags are tied to the pinned scanner version.

Online lookup sends package identities to OSV. Results describe known advisory matches at scan time, not guaranteed freshness, exploitability, or absence of undisclosed vulnerabilities. `aliases` includes native group and advisory aliases; `fixed_versions` gives contextual advisory releases, not applicable upgrade recommendations. Missing fixed-version evidence is explicit.

Text and JSON retain source evidence, verification problems, full counts, and scope. JSON includes `scope`, `verification_status`, `summary`, `findings`, `sources`, and `problems`. `--max N` is a positive integer and caps only advisory rows; `summary.omitted` counts the rest. Counts refer to native advisory records, not distinct vulnerabilities inferred from aliases. A complete scan without findings means no known advisory matches. Audit uses the same exit codes; incomplete verification takes priority over vulnerabilities.

Tests replay reviewed native responses and fake process/download boundaries. Live advisory lookup and release downloads stay outside `make check` and CI tests. Audit supplements source and project checks; it does not replace the project gate or human judgment.

## Performance

Historical wall time before the 0.9.0 checker repairs, on open-source repositories at the linked revisions, using Python 3.15.2 on an Apple silicon laptop with the default 9 workers (half the cores). Times are medians of 5 runs after a warmup, with cached grammars and bytecode. Files and lines count successfully analyzed code files. Time covers the full repository scan. These measurements have not been rerun for 0.9.0.

| Repository | Language | Files | Lines | Time |
| --- | --- | ---: | ---: | ---: |
| [requests](https://github.com/psf/requests/tree/3c7baaa05ab4aa49cc819ce3a819d260de19c157) | Python | 48 | 12,490 | 1.2 s |
| [ky](https://github.com/sindresorhus/ky/tree/3541888878c4d303a8bc2ad61815f4e048f55a5d) | TypeScript | 98 | 36,231 | 1.0 s |
| [cobra](https://github.com/spf13/cobra/tree/adbc8813901bba65827259daa8e22ff94ec1f30e) | Go | 38 | 16,810 | 0.6 s |
| [fd](https://github.com/sharkdp/fd/tree/24d90b28d25438af2a8f2e7f7e46d03d6828da94) | Rust | 33 | 9,598 | 0.5 s |
| [gson](https://github.com/google/gson/tree/65df6e5a99747f73d386f3a61d887a0257255e0f) | Java | 270 | 58,076 | 1.1 s |
| [Newtonsoft.Json](https://github.com/JamesNK/Newtonsoft.Json/tree/52fa3aef1f2cadcd3a3f874251eddc98d3efbbaa) | C# | 884 | 144,617 | 3.7 s |

## Contributing

See [AGENTS.md](AGENTS.md) for architecture, check metadata, tests, and the quality gate.

## License

[MIT](LICENSE)
