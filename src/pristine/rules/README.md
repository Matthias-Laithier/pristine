# Coding rules

Rules for every agent that writes, reviews, or refactors code for the user. Each rule is a file in this directory, and agents cite rules by their ID. `pristine guide` prints this hub, and `pristine rule <ID>` prints one rule.

## Precedence
When instructions conflict, the higher one wins:
1. The user's explicit instruction for the task at hand.
2. The project's own rules: its AGENTS.md, CONTRIBUTING.md, style guide, linter config, and typechecker config.
3. These rules.

These rules are the default when the project is silent. They never override the project or the user.

## Before coding
1. Read this hub. Its chapter lists route to every rule.
2. Read and apply [CR-20](cr-20-minimize-the-resulting-codebase.md) on every coding task, before selecting other rules.
3. Read the rule list of every chapter relevant to the task. When in doubt, read all of them.
4. Open every rule whose title touches the task. While the rules are few, open all of them, since it costs nothing. Judge every rule from its full statement and never from a summary.

## While coding
Apply the rules while writing the code. When a decision genuinely conflicts with a rule, never pick a side silently. Cite the rule ID and state the conflict in the response.

## Self-check before finishing
1. Run `pristine check` on every file the task created or changed, and `pristine project` on the repository root, as the Automated checks section describes. Fix every finding, or keep it as a deliberate break for step 5.
2. Walk every rule ID of the chapters read.
3. For each rule plausibly relevant to the changes, confirm compliance against the full rule. Open the rule when it is out of context.
4. Complete the subtraction pass and the growth account that CR-20 requires.
5. Report by rule ID every violation and every rule deliberately broken, with the reason.

## Automated checks
The installed `pristine` command checks the rules a parser or a file path can judge reliably.
- `pristine check <paths>` checks files and directories. `--exclude <glob>` skips paths, and `--json` prints a structured report.
- `pristine project [root]` checks the repository root against the Tooling chapter: the Makefile contract, the check gates, the code-quality tools, and the lockfile.
- `pristine rules` lists every rule the tool checks, how it checks it, and which command does. That list is the authority on coverage. `--help` on each command documents the rest.
- Each finding gives the file, the line, the rule ID, and a severity. An error breaks a hard limit or a strict rule. A warning passes a target.
- An error exits with code 1, and warnings alone exit with code 0. Both still need a fix or a reported reason.
- Files without a grammar are listed as unchecked. Those files, and every rule the tool does not check, still need the agent's own review.
- The tool reads no project configuration. When the project's own rules set other limits, the project wins, and the agent reports the difference.

## Chapters

### Coding Rules (CR)
How code is written and organized.
- [CR-1 Code File Size](cr-1-code-file-size.md)
- [CR-2 Do Not Reinvent](cr-2-do-not-reinvent.md)
- [CR-3 No Comments Except Machine-Read Text](cr-3-no-comments-except-machine-read-text.md)
- [CR-4 Naming](cr-4-naming.md)
- [CR-5 DRY (Don't Repeat Yourself)](cr-5-dry-don-t-repeat-yourself.md)
- [CR-6 Global Variables Are Defined at the Top of the File](cr-6-global-variables-are-defined-at-the-top-of-the-file.md)
- [CR-7 Global Variables Are Config, Never Mutated](cr-7-global-variables-are-config-never-mutated.md)
- [CR-8 Services Live in a Dedicated services Folder](cr-8-services-live-in-a-dedicated-services-folder.md)
- [CR-9 Assets Live in an Organized assets Folder](cr-9-assets-live-in-an-organized-assets-folder.md)
- [CR-10 Business Logic Lives in the Backend](cr-10-business-logic-lives-in-the-backend.md)
- [CR-11 Every Change Includes Cleanup](cr-11-every-change-includes-cleanup.md)
- [CR-12 Function Size](cr-12-function-size.md)
- [CR-13 Nesting Depth](cr-13-nesting-depth.md)
- [CR-14 Value Dispatch Through a Registry](cr-14-value-dispatch-through-a-registry.md)
- [CR-15 Group Files by Cohesive Responsibility](cr-15-group-files-by-cohesive-responsibility.md)
- [CR-16 Inspect Before Implementing](cr-16-inspect-before-implementing.md)
- [CR-17 Keep Function Signatures Cohesive](cr-17-keep-function-signatures-cohesive.md)
- [CR-18 Name Domain-Significant Values](cr-18-name-domain-significant-values.md)
- [CR-19 Keep One Level of Abstraction per Function](cr-19-keep-one-level-of-abstraction-per-function.md)
- [CR-20 Minimize the Resulting Codebase](cr-20-minimize-the-resulting-codebase.md)

### Boundary Safety (BS)
Rules that protect trust boundaries and failure paths.
- [BS-1 Validate Untrusted Input at the Boundary](bs-1-validate-untrusted-input-at-the-boundary.md)
- [BS-2 Keep Secrets Out of Code and Output](bs-2-keep-secrets-out-of-code-and-output.md)
- [BS-3 Bound Every External Call](bs-3-bound-every-external-call.md)
- [BS-4 Do Not Swallow Failures](bs-4-do-not-swallow-failures.md)
- [BS-5 State Changes Are Atomic](bs-5-state-changes-are-atomic.md)
- [BS-8 Make Concurrent State Transitions Race-Safe](bs-8-make-concurrent-state-transitions-race-safe.md)
- [BS-9 Represent Domain Invariants in Types](bs-9-represent-domain-invariants-in-types.md)
- [BS-10 Resources Have Explicit Owners and Lifetimes](bs-10-resources-have-explicit-owners-and-lifetimes.md)
- [BS-11 Boundaries Expose Stable Error Contracts](bs-11-boundaries-expose-stable-error-contracts.md)

### Composability (CO)
How code is designed for composition.
- [CO-1 Favor Composition Over Inheritance](co-1-favor-composition-over-inheritance.md)
- [CO-2 Small, Focused Units](co-2-small-focused-units.md)
- [CO-3 Design for Combination Over Modification](co-3-design-for-combination-over-modification.md)
- [CO-4 Clear Interfaces](co-4-clear-interfaces.md)
- [CO-5 Functions Where Possible, Classes Where Needed](co-5-functions-where-possible-classes-where-needed.md)
- [CO-6 Wrap External Clients in Singleton Services](co-6-wrap-external-clients-in-singleton-services.md)
- [CO-7 Make Extension Points Pluggable](co-7-make-extension-points-pluggable.md)
- [CO-8 No Circular Dependencies](co-8-no-circular-dependencies.md)
- [CO-9 Keep Side Effects at the Edges](co-9-keep-side-effects-at-the-edges.md)
- [CO-10 Dependencies Point Toward Domain Policy](co-10-dependencies-point-toward-domain-policy.md)
- [CO-11 Export Only the Public Contract](co-11-export-only-the-public-contract.md)
- [CO-12 Localize Mutation](co-12-localize-mutation.md)
- [CO-13 Imports Do Not Perform External Work](co-13-imports-do-not-perform-external-work.md)

### Testing (TST)
What to test and how to keep the suite minimal.
- [TST-1 Test Behavior Through the Public Interface](tst-1-test-behavior-through-the-public-interface.md)
- [TST-2 Pin the Boundaries](tst-2-pin-the-boundaries.md)
- [TST-3 Minimal Test Count](tst-3-minimal-test-count.md)
- [TST-4 Tests Live in a Dedicated tests Folder](tst-4-tests-live-in-a-dedicated-tests-folder.md)
- [TST-5 Every Bug Gets a Regression Test](tst-5-every-bug-gets-a-regression-test.md)
- [TST-6 Tests Are Deterministic](tst-6-tests-are-deterministic.md)
- [TST-7 Expected Results Come From an Independent Oracle](tst-7-expected-results-come-from-an-independent-oracle.md)

### Tooling (TL)
The project's tooling and entry points.
- [TL-1 Every Project Has a Makefile](tl-1-every-project-has-a-makefile.md)
- [TL-2 make check Is Fast, make check-all Runs Everything](tl-2-make-check-is-fast-make-check-all-runs-everything.md)
- [TL-3 Automate Formatting and Static Analysis](tl-3-automate-formatting-and-static-analysis.md)
- [TL-4 Keep Dependencies Minimal, Declared, and Audited](tl-4-keep-dependencies-minimal-declared-and-audited.md)

## Changing the rules
The process for changing the rules, and the conventions for rule files, IDs, and examples, live in the repository's AGENTS.md.
