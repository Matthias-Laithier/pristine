# Coding rules

Rules for every agent that writes, reviews, or refactors code for the user. Each rule is a file in this directory, and agents cite rules by their ID. `pristine guide` prints this hub followed by the rule index, and `pristine rule <ID>` prints one rule.

## Precedence
When instructions conflict, the higher one wins:
1. The user's explicit instruction for the task at hand.
2. The project's own rules: its AGENTS.md, CONTRIBUTING.md, style guide, linter config, and typechecker config.
3. These rules.

These rules are the default when the project is silent. They never override the project or the user.

## Before coding
1. Read this hub and the rule index `pristine guide` prints after it. The index gives each rule's ID, title, how it is checked, and its statement.
2. Read CR-20 in full on every coding task.
3. Read in full, with `pristine rule <ID>`, every rule whose statement touches the task. When in doubt, read it.
4. A statement only routes. Judge a rule from its full text before relying on it.

## While coding
Apply the rules while writing the code. When a decision genuinely conflicts with a rule, never pick a side silently. Cite the rule ID and state the conflict in the response.

## Self-check before finishing
1. Run `pristine check` on the directories the task touched, or on the repository root, so checks that span files, such as import cycles, see the unchanged files too. Fix every finding in the code the task wrote or changed, or keep it as a deliberate break.
2. Run `pristine project` on the repository root.
3. Handle findings in code the task did not change. Fix them when they sit in a unit the task rewrote, as CR-11 requires. Otherwise leave them and count them per rule ID.
4. Walk the review rules relevant to the change, marked `review` in `pristine rules`. Confirm compliance against the full rule.
5. Complete the CR-20 subtraction pass and growth account.
6. Report three things: every deliberate break with its rule ID and reason, the pre-existing findings counted per rule ID, and the CR-20 growth account.

## Automated checks
The installed `pristine` command checks the rules a parser or a file path can judge reliably.
- `pristine check <paths>` checks files and directories. `--exclude <glob>` skips paths, and `--json` prints a structured report.
- `pristine project [root]` checks the repository root against the Tooling chapter: the Makefile contract, the check gates, the code-quality tools, and the lockfile.
- `pristine rules` lists every rule and how it is checked: by `pristine check`, by `pristine project`, or by the agent's own review. That list is the authority on coverage. `--help` on each command documents the rest.
- Each finding gives the file, the line, the rule ID, and a severity. An error breaks a hard limit or a strict rule. A warning passes a target.
- An error exits with code 1, and warnings alone exit with code 0. Both still need a fix or a reported reason.
- Files without a grammar are listed as unchecked. Those files, and every rule the tool does not check, still need the agent's own review.
- The tool reads no project configuration. When the project's own rules set other limits, the project wins, and the agent reports the difference.

## Chapters
Each item gives a rule ID and title. Read a rule with `pristine rule <ID>`.

### Core Rules (CR)
How code is written and organized.
- CR-1 Code File Size
- CR-2 Do Not Reinvent
- CR-3 No Comments Except Machine-Read Text
- CR-4 Naming
- CR-5 DRY (Don't Repeat Yourself)
- CR-6 Global Variables Are Defined at the Top of the File
- CR-7 Global Variables Are Config, Never Mutated
- CR-8 Services Live in a Dedicated `services` Folder
- CR-9 Assets Live in an Organized `assets` Folder
- CR-10 Business Logic Lives in the Backend
- CR-11 Every Change Includes Cleanup
- CR-12 Function Size
- CR-13 Nesting Depth
- CR-14 Value Dispatch Through a Registry
- CR-15 Group Files by Cohesive Responsibility
- CR-16 Inspect Before Implementing
- CR-17 Keep Function Signatures Cohesive
- CR-18 Name Domain-Significant Values
- CR-19 Keep One Level of Abstraction per Function
- CR-20 Minimize the Resulting Codebase
- CR-21 Never Escape the Type Checker
- CR-22 Instants Are Aware UTC, Money Is Exact, Quantities Name Their Unit

### Boundary Safety (BS)
How code guards trust boundaries, failure paths, and shared resources: input validation, injection, authorization, idempotency, async blocking, load bounds, and logging.
- BS-1 Validate Untrusted Input at the Boundary
- BS-2 Keep Secrets Out of Code and Output
- BS-3 Bound Every External Call
- BS-4 Do Not Swallow Failures
- BS-5 State Changes Are Atomic
- BS-6 Make Concurrent State Transitions Race-Safe
- BS-7 Represent Domain Invariants in Types
- BS-8 Resources Have Explicit Owners and Lifetimes
- BS-9 Boundaries Expose Stable Error Contracts
- BS-10 Untrusted Values Never Change the Structure of a Query, Command, Markup, or Path
- BS-11 Authorize Every Operation Against the Resource It Touches
- BS-12 Handlers of Redelivered Work Are Idempotent
- BS-13 Async Code Never Blocks the Event Loop
- BS-14 Bound Every Load, Response, and Fan-Out
- BS-15 Log Diagnosable Events, Never Personal Data

### Composability (CO)
How code is designed for composition.
- CO-1 Favor Composition Over Inheritance
- CO-2 Small, Focused Units
- CO-3 Design for Combination Over Modification
- CO-4 Clear Interfaces
- CO-5 Functions Where Possible, Classes Where Needed
- CO-6 Wrap External Clients in Singleton Services
- CO-7 Make Extension Points Pluggable
- CO-8 No Circular Dependencies
- CO-9 Keep Side Effects at the Edges
- CO-10 Dependencies Point Toward Domain Policy
- CO-11 Export Only the Public Contract
- CO-12 Localize Mutation
- CO-13 Imports Do Not Perform External Work
- CO-14 Evolve Persisted Data and Public Contracts in Compatible Steps

### Testing (TST)
What to test and how to keep the suite minimal.
- TST-1 Test Behavior Through the Public Interface
- TST-2 Pin the Boundaries
- TST-3 Minimal Test Count
- TST-4 Tests Live in a Dedicated `tests` Folder
- TST-5 Every Bug Gets a Regression Test
- TST-6 Tests Are Deterministic
- TST-7 Expected Results Come From an Independent Oracle
- TST-8 Model Quality Is Measured by Evals, Code by Deterministic Tests

### Tooling (TL)
The project's tooling and entry points.
- TL-1 Every Project Has a Makefile
- TL-2 `make check` Is Fast, `make check-all` Runs Everything
- TL-3 Automate Formatting and Static Analysis
- TL-4 Keep Dependencies Minimal, Declared, and Audited

## Changing the rules
The process for changing the rules, and the conventions for rule files, IDs, and examples, live in the repository's AGENTS.md.
