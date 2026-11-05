# pristine

An opinionated set of coding rules for agents, and a CLI that serves them. The rules cover code structure, boundary safety, composability, testing, and tooling. The CLI prints the rules for an agent to read before coding, and checks code against the rules a parser or a file path can judge reliably.

## Install

```
uv tool install git+https://github.com/Matthias-Laithier/pristine
```

The secret scan of rule BS-2 needs [gitleaks](https://github.com/gitleaks/gitleaks) on the path. Without it, the report carries a warning that the scan did not run.

## Read the rules

```
pristine guide
pristine rule CR-13
```

`pristine guide` prints the hub: precedence, what to do before and while coding, the self-check, and the list of every rule. `pristine rule <ID>` prints one rule in full.

## Check code

```
pristine check src tests
pristine project .
pristine rules
```

`pristine check <paths>` checks files and directories. `pristine project [root]` checks a repository root against the tooling rules, such as the Makefile contract. `pristine rules` lists every rule the tool checks and how. `--json` prints a structured report, and `--help` on each command documents the rest.

Each finding gives the file, the line, the rule ID, a severity, and a fix:

```
billing.py:5: CR-13 error: function 'f' nests 4 levels deep (target 2, hard limit 3); use guard clauses or extract the deepest block into a named helper
summary: 1 errors, 0 warnings, 1 checked files, 0 unchecked files, 0 skipped files
```

The exit code is 0 without error findings, 1 with at least one error finding, and 2 on a usage problem such as a missing path. Warnings alone exit with 0.

## Point an agent at it

Add this line to the agent's instructions, such as an AGENTS.md or CLAUDE.md file:

```
Before coding, run `pristine guide` and follow it.
```

## License

MIT, see [LICENSE](LICENSE).
