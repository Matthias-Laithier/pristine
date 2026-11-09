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
uv tool install --python 3.15 git+https://github.com/Matthias-Laithier/pristine
```

```sh
pristine guide            # print the rules hub and the rule index
pristine rule all         # read every rule in full before coding, in chunks if needed
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
Findings (ranked by distinct code rules, then path)

[ ] reminders.py: 2 rules, 2 findings
  fix: BS-4, CR-13
  reminders.py:6: CR-13 error: function 'send_overdue_reminders' nests 5 levels deep (target 2, hard limit 3); use guard clauses or extract the deepest block into a named helper
  reminders.py:8: BS-4 error: 'except Exception' swallows every failure with 'pass'; catch only what this code can recover from

Mechanical checks
summary: 2 errors, 0 warnings
files: 1 checked file, 0 unchecked files, 0 skipped files, 0 missing paths
by rule: BS-4 1, CR-13 1
verification: complete, 0 failures

Required agent review
  - read every rule in full with 'pristine rule all' before coding.
  - Before finishing, review your change against every rule, including checked rules.
  - Automated checks cover only mechanical parts.
  - A clean report does not establish full rule compliance.
  - Fix every finding or report it by rule ID as a deliberate break with its reason.
```

`pristine rule CR-13` prints one rule in full, and `pristine rules` lists every rule with how it is checked. The exit code is 1 when a check finds an error, or 3 when verification is incomplete. `pristine check` returns the full report after the run finishes: text by default, or JSON with `--json`. Both formats include the reading and review obligation, through `next_step` in JSON. `verification_status` describes mechanical verification only. `--jobs N` caps the worker processes, with half the CPU cores as the default. `--max N` limits printed findings while the summary still counts them all; without it, every finding prints.

Text groups findings into spaced file sections, ranked by the number of distinct code rules, then by path alphabetically. Each file has a checklist with separate `fix` and `verify` lines. Verification failures do not count as violated code rules. Mechanical totals and the mandatory agent review checklist follow. With `--max`, text shows details from the highest-ranked files first, but keeps every file's checklist and full counts. JSON keeps findings in path/line/rule order and adds a ranked `triage` array: each entry has `path`, `distinct_rules`, the total `findings` count, and `fix` and `verify` maps of rule IDs to counts. Those maps cover the full report, not just printed findings.

Requirements: [uv](https://docs.astral.sh/uv/), which fetches Python 3.15 or later when needed, and [gitleaks](https://github.com/gitleaks/gitleaks) on the path for the secret scan. Each language grammar downloads on its first use. The `pristine` package on PyPI is an unrelated project.

## How it works

Before coding, the agent runs `pristine guide` and reads every rule in full with `pristine rule all`. It reads long output in chunks through the final rule, or requests every chapter separately. The guide's index does not replace reading the full rules.

Before finishing, the agent runs `pristine check` and `pristine project`, fixes the findings, and reviews its change against every rule, including checked rules. Each rule's full requirement and exceptions must be assessed. Rules outside the change's scope are inapplicable. The agent reports every deliberate break by rule ID.

Automated checks cover only mechanical parts of the rules. They favor precision over recall. A checked rule may be checked only in part. A clean report does not establish full rule compliance. The CLI communicates the reading and review obligation. It cannot verify that an agent fulfilled it.

To set it up, add this line to the agent's instructions, such as `AGENTS.md` or `CLAUDE.md`:

```
Before coding, run `pristine guide` and read every rule in full with `pristine rule all`, in chunks if needed. Before finishing, review your change against every rule, including checked rules. Automated checks cover only mechanical parts. A clean report does not establish full rule compliance.
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

`check` marks mechanical checks on source files, `project` marks mechanical checks on the repository root, and `review` marks rules with no automated check. Every rule still requires the agent's review.

`pristine project` recognizes Python, JavaScript/TypeScript, Go, and Rust repositories. For Go it reads `go.mod` and accepts the native toolchain (`gofmt`, `go vet`, `go test`, `go build`) plus golangci-lint and staticcheck. For Rust it reads `Cargo.toml` and accepts `cargo fmt`, `cargo clippy`, `cargo check`, `cargo test`, and `cargo build`.

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
