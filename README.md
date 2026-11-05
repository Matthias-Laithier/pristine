# pristine

Opinionated coding rules for AI coding agents, with a CLI that serves them and checks their mechanical part.

[![check](https://github.com/Matthias-Laithier/pristine/actions/workflows/check.yml/badge.svg)](https://github.com/Matthias-Laithier/pristine/actions/workflows/check.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

## Why

Agents write most code now. Style guides written for humans are long and vague, and agents skim them or ignore them. pristine gives an agent a precise rulebook. Each rule has a stable ID, a statement, its exceptions, and Bad and Good examples. A checker then judges the rules a parser can judge, and every finding names the rule and the fix.

Linters such as ruff and eslint cover syntax, formatting, and known bug patterns. pristine covers code structure, trust boundaries, composability, testing, and project tooling. It also defines a workflow: the agent reads the rules, writes the code, checks its own work, and reports every violation by rule ID.

## Quick start

Install the CLI with [uv](https://docs.astral.sh/uv/):

```
uv tool install git+https://github.com/Matthias-Laithier/pristine
```

Pin a release with `uv tool install git+https://github.com/Matthias-Laithier/pristine@v0.1.0`.

```
pristine guide              # print the rules hub to read before coding
pristine rule CR-13         # print one rule in full
pristine check src tests    # check files and directories against the rules
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
summary: 2 errors, 0 warnings, 1 checked files, 0 unchecked files, 0 skipped files
next: fix every finding, or report it by rule ID as a deliberate break with its reason. Unchecked files and every rule this tool cannot check still need your own review against the coding rules.
```

The exit code is 0 without error findings, 1 with at least one error finding, and 2 on a usage problem. `--json` prints a structured report, and `--help` on each command documents the rest.

## Requirements

- [uv](https://docs.astral.sh/uv/). It fetches Python 3.13 or later when the system lacks it.
- [gitleaks](https://github.com/gitleaks/gitleaks) on the path, for the secret scan of BS-2. Without it, the report carries a warning that the scan did not run.
- Network access on the first use of each language, to download its tree-sitter grammar into the user cache.

## What's inside

The rules live in [src/pristine/rules/](src/pristine/rules/README.md), one file per rule, grouped in chapters:

| Chapter | Covers |
| --- | --- |
| Coding Rules (CR) | How code is written and organized: size, nesting, naming, comments, dispatch. |
| Boundary Safety (BS) | Trust boundaries and failure paths: input validation, secrets, timeouts, errors. |
| Composability (CO) | Design for composition: interfaces, dependencies, side effects, exports. |
| Testing (TST) | What to test and how to keep the suite minimal and deterministic. |
| Tooling (TL) | The Makefile contract, the check gates, code-quality tools, and lockfiles. |

Each rule is covered in one of three ways:

- `check`: `pristine check <paths>` judges it on source files.
- `project`: `pristine project [root]` judges it on the repository root.
- `review`: no automated check. The agent reviews its own code against the rule.

`pristine rules` lists every rule with its coverage and what the check detects.

### Languages

Parsing uses the tree-sitter grammars of [tree-sitter-language-pack](https://github.com/xberg-io/tree-sitter-language-pack). The file size, function size, nesting, comment, and if/else dispatch checks run on every language it parses. The deeper checks target specific ecosystems:

- Python, JavaScript, and TypeScript: import cycles, export contracts, global placement and mutation, service placement, import-time work, unbounded calls, and swallowed failures.
- Go: global placement, service placement, unbounded calls, swallowed failures, and switch dispatch.
- Java, Kotlin, and C#: swallowed failures and switch dispatch.

Files without a grammar are listed as unchecked.

## How agents use it

Add this line to the agent's instructions, such as an AGENTS.md or CLAUDE.md file:

```
Before coding, run `pristine guide` and follow it.
```

The guide then drives the workflow:

1. Read the hub and every rule whose title touches the task.
2. Apply the rules while writing the code.
3. Run `pristine check` on every changed file and `pristine project` on the repository root, then fix the findings.
4. Walk the remaining rules by hand.
5. Report every violation and every deliberate break by rule ID, with the reason.

## Not the PyPI package

The `pristine` package on PyPI is an unrelated project. Install this one from GitHub, as shown above.

## Contributing

See [AGENTS.md](AGENTS.md) for the architecture, the quality gate, and the process for changing the rules.

## License

MIT, see [LICENSE](LICENSE).
