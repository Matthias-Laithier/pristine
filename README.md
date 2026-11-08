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

Paired `pristine check` runs compare exact baseline commit `01a20db` with the current build on Python 3.15.2. Both versions used cached grammars, a fresh shared bytecode cache, and the same immutable 721-file corpus set; each measured command had one warmup. The default worker count is 9 on an 18-core host. Medians use 10 samples for the 1-file, 50-file, and multi-language corpora, and 5 for the 176-file and real-code corpora. Findings count errors and warnings. Across all 10 corpus and worker-count groups, the full JSON reports matched on every repeat and between versions, as did exit codes and summary counts, with no unchecked files.

| Corpus | Files discovered / checked | Findings | 1 job previous | 1 job current | 1 job change | Default previous | Default current | Default change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 Python file | 1 / 1 | 0 | 0.313 s | 0.299 s | -4.7% | 0.305 s | 0.297 s | -2.7% |
| 50 Python files | 50 / 50 | 0 | 1.352 s | 0.992 s | -26.6% | 0.735 s | 0.597 s | -18.7% |
| Pristine-derived 176-file fixture | 176 / 176 | 0 | 3.512 s | 2.421 s | -31.1% | 1.168 s | 0.933 s | -20.1% |
| Multi-language corpus | 42 / 41 | 328 | 2.524 s | 1.870 s | -25.9% | 1.368 s | 1.003 s | -26.7% |
| Real-code corpus | 452 / 451 | 2075 | 17.427 s | 11.533 s | -33.8% | 5.408 s | 3.274 s | -39.5% |

Startup medians also moved from 140 to 130 ms for `pristine guide`, 142 to 129 ms for `pristine rules`, and 85 to 97 ms for `pristine rule CR-20`; this run did not improve every startup command. Parent RSS is the only memory measurement; worker aggregate memory was not measured. At the default worker count on the real-code corpus, parent RSS rose from 80.8 MB to 87.6 MB.

## Contributing

See [AGENTS.md](AGENTS.md) for the architecture, the quality gate, and the process for changing the rules.

## License

[MIT](LICENSE)
