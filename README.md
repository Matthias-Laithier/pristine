<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/soap-bar-dark.svg">
    <img src="assets/brand/soap-bar-light.svg" alt="pristine" width="400">
  </picture>
</p>

<p align="center">Opinionated coding rules for AI agents, with a CLI that serves them and checks the mechanical ones.</p>

<p align="center">
  <a href="https://github.com/Matthias-Laithier/pristine/actions/workflows/check.yml"><img src="https://github.com/Matthias-Laithier/pristine/actions/workflows/check.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/Matthias-Laithier/pristine/releases/latest"><img src="https://img.shields.io/github/v/release/Matthias-Laithier/pristine" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Matthias-Laithier/pristine" alt="License"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.15%2B-blue" alt="Python 3.15+"></a>
</p>

pristine is a rulebook of 63 coding rules written for AI coding agents. Each rule has a stable ID, a short statement, its exceptions, and examples where they help. The CLI prints the rules to the agent and checks the ones a parser can decide, so every finding names a rule and its fix.

Linters such as ruff and eslint cover syntax, formatting, and known bug patterns. pristine covers structure, trust boundaries, composability, testing, and project tooling.

## Quick start

```sh
uv tool install git+https://github.com/Matthias-Laithier/pristine
```

```sh
pristine guide            # print the rules hub and the rule index
pristine check src tests  # check files and directories against the rules
pristine project          # check the repository root against the Tooling chapter
```

Given this `reminders.py`:

```python
def send_overdue_reminders(invoices, mailer):
    for invoice in invoices:
        if invoice.is_overdue():
            for contact in invoice.customer.contacts:
                if contact.accepts_email:
                    try:
                        mailer.send(contact.email, invoice.reminder())
                    except Exception:
                        pass
```

`pristine check reminders.py` prints:

```
reminders.py:6: CR-13 error: function 'send_overdue_reminders' nests 5 levels deep (target 2, hard limit 3); use guard clauses or extract the deepest block into a named helper
reminders.py:8: BS-4 error: 'except Exception' swallows every failure with 'pass'; catch only what this code can recover from
summary: 2 errors, 0 warnings, 1 checked file, 0 unchecked files, 0 skipped files, 0 missing paths
by rule: BS-4 1, CR-13 1
next: fix every finding, or report it by rule ID as a deliberate break with its reason. This check favors precision over recall: a clean result proves nothing about the rules it cannot decide, so review your change against every relevant rule yourself.
```

`pristine rule CR-13` prints one rule in full, and `pristine rules` lists every rule with how it is checked. The exit code is 1 when a check finds an error, or 3 when verification is incomplete. `pristine check` returns the full report after the run finishes: text by default, or JSON with `--json`. `--jobs N` caps the worker processes, with half the CPU cores as the default. `--max N` limits printed findings while the summary still counts them all; without it, every finding prints.

Requirements: [uv](https://docs.astral.sh/uv/), which fetches Python 3.15 or later when needed, and [gitleaks](https://github.com/gitleaks/gitleaks) on the path for the secret scan. Each language grammar downloads on its first use. The `pristine` package on PyPI is an unrelated project.

## How it works

The agent reads the guide, writes the code, runs `pristine check` and `pristine project`, and fixes the findings. It then reviews its change against the rules no tool can decide, and reports every deliberate break by rule ID.

The checks favor precision over recall. A check reports only what it can judge with certainty, because an agent acts on every finding and a false positive costs more than a miss. A finding is reliable. A clean run proves nothing about the rules a static analysis cannot decide, and the agent's review covers those.

To set it up, add this line to the agent's instructions, such as `AGENTS.md` or `CLAUDE.md`:

```
Before coding, run `pristine guide` and follow it.
```

## Rules

The rules live in [src/pristine/rules/](src/pristine/rules/README.md), one file per rule.

| Chapter | Scope | Rules | `check` | `project` | Review |
| --- | --- | ---: | ---: | ---: | ---: |
| Core Rules (CR) | Size, nesting, naming, comments, dispatch | 22 | 14 | | 8 |
| Boundary Safety (BS) | Input, injection, secrets, timeouts, errors, logs | 15 | 9 | | 6 |
| Composability (CO) | Interfaces, dependencies, side effects, exports | 14 | 5 | | 9 |
| Testing (TST) | What to test, minimal and deterministic suites | 8 | 5 | | 3 |
| Tooling (TL) | Makefile contract, quality gates, lockfiles | 4 | | 4 | |
| Total | | 63 | 33 | 4 | 26 |

`check` rules are judged on source files, `project` rules on the repository root, and review rules by the agent.

`pristine project` recognizes Python, JavaScript/TypeScript, Go, and Rust repositories. For Go it reads `go.mod` and accepts the native toolchain (`gofmt`, `go vet`, `go test`, `go build`) plus golangci-lint and staticcheck. For Rust it reads `Cargo.toml` and accepts `cargo fmt`, `cargo clippy`, `cargo check`, `cargo test`, and `cargo build`.

Dead-code checking belongs in `make check`. Supported capabilities include Vulture, Pylint with `--enable=unreachable`, Ruff with F401 and F841, Knip with unused-code issue types enabled, TypeScript with `noUnusedLocals` and `noUnusedParameters`, Go compilation of `./...`, and Rust compilation or Clippy with `-D warnings`. Native lint and compiler checks are limited checks for unused locals, imports, or private code, not whole-project unused-function detection. Vulture scopes and exclusions are checked against discovered non-test Python sources (or tests when no application sources exist). Ruff literal scopes are checked too; inspection-only or fixing modes cannot certify unused-code checks. Deprecated Ruff selectors require migration, and custom unused-rule suppressions require review. Custom source filters, changed working directories, explicit TypeScript source/build scopes, and Knip project/workspace filters also require review. No-source configurations are verification gaps, not evidence of successful analysis. These checks inspect supported configuration fields, not the providers' entire schemas.

Recognized vulnerability audit commands include `pip-audit`, `npm audit`, `pnpm audit`, `bun audit`, `govulncheck`, and `cargo audit`. Project inspection never runs them or fetches vulnerability databases. An unverified audit mechanism produces a TL-4 warning, not a claim that audits are absent or dependencies are vulnerable. Network audits stay outside `make check`; regular audit targets may stay outside `check-all` under TL-4. HTTP caches, report formats, database paths, and mere config-file presence do not establish offline execution. Local or ambiguous database settings that do not prove a fast, fail-closed check produce verification gaps. Cargo's supported offline setup is `--no-fetch --no-yanked --file <local-lockfile>` (or equivalent versioned fetch/yanked settings); it must reach `check-all` or its fast gate. Govulncheck structured reports require a reviewed fail-closed consumer in a quality gate because the tool exits successfully even with vulnerabilities.
For Python, `project` verifies an explicit-annotation capability in `make check`: strict mypy or Ruff's ANN001/002/003/201/202/204/205/206 rules. Inference alone does not satisfy this check. Recognized suppressions disable the capability; unsupported overrides, exclusions, or incomplete source scope produce verification findings. Pristine reads the configuration without running those tools; the gate checks the actual annotations.

TypeScript CR-21 also warns on double assertions through `unknown`, including parenthesized and angle-bracket assertions. Single assertions and operations whose result remains `unknown` are not reported.

## Languages

Parsing uses [tree-sitter](https://tree-sitter.github.io/). Every language with a grammar gets the shared checks: file and function size, nesting, comments, if/else dispatch chains, asset and directory layout, test location, and secrets.

| Language | Checks |
| --- | --- |
| Python | All checks |
| TypeScript, JavaScript | Shared checks, plus BS-3, BS-4, BS-10, CO-8, CO-11, CO-13, CR-6, CR-7, CR-8, and TST-8. CR-21 for TypeScript. |
| Go | Shared checks, plus BS-3, BS-4, BS-10, CR-6, and CR-8 |
| Java, Kotlin, C# | Shared checks, plus BS-4 |
| Rust | Shared checks, plus CR-6 |
| Ruby, PHP, Swift, and others | Shared checks |

`pristine rules` names the languages and patterns each check covers.

## Performance

Wall time of `pristine check` on open-source repositories at the linked revisions, using Python 3.15.2 on an Apple silicon laptop with the default 9 workers (half the cores). Times are medians of 5 runs after a warmup, with cached grammars and bytecode. Files and lines count successfully analyzed code files. Time covers the full repository scan.

| Repository | Language | Files | Lines | Time |
| --- | --- | ---: | ---: | ---: |
| [requests](https://github.com/psf/requests/tree/3c7baaa05ab4aa49cc819ce3a819d260de19c157) | Python | 48 | 12,490 | 1.2 s |
| [ky](https://github.com/sindresorhus/ky/tree/3541888878c4d303a8bc2ad61815f4e048f55a5d) | TypeScript | 98 | 36,231 | 1.0 s |
| [cobra](https://github.com/spf13/cobra/tree/adbc8813901bba65827259daa8e22ff94ec1f30e) | Go | 38 | 16,810 | 0.6 s |
| [fd](https://github.com/sharkdp/fd/tree/24d90b28d25438af2a8f2e7f7e46d03d6828da94) | Rust | 33 | 9,598 | 0.5 s |
| [gson](https://github.com/google/gson/tree/65df6e5a99747f73d386f3a61d887a0257255e0f) | Java | 270 | 58,076 | 1.1 s |
| [Newtonsoft.Json](https://github.com/JamesNK/Newtonsoft.Json/tree/52fa3aef1f2cadcd3a3f874251eddc98d3efbbaa) | C# | 884 | 144,617 | 3.7 s |

## Contributing

See [AGENTS.md](AGENTS.md) for the architecture, the quality gate, and the process for changing the rules.

## License

[MIT](LICENSE)
