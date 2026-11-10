# CR-20 Minimize the Resulting Codebase

Maintain the smallest clear implementation of the project's present requirements that satisfies all applicable rules. Minimize the resulting codebase. The size of the patch is not the measure. A broader change to the existing owner can leave less code than a small patch that adds another layer.

Count everything the project must maintain: production code, tests, configuration, documentation, assets, dependencies, and custom generators. Moving machinery to another file, package, or repository does not remove its cost. Prefer fewer maintained lines and fewer independently maintained mechanisms. Never reduce the line count through compressed formatting or hidden coupling.

## Before implementation
1. Identify the concrete behavior and guarantees the task requires. Inspect the existing paths, callers, tests, and owning units under [CR-2](cr-2-do-not-reinvent.md).
2. Find the smallest solution by removing unnecessary machinery, simplifying the existing path, or extending its owner. Use existing library and platform capabilities under [CR-2](cr-2-do-not-reinvent.md). Add a parallel mechanism only when reuse would conflate distinct responsibilities or violate a required contract.
3. Before introducing an abstraction, a layer, a dependency, a configuration option, a fallback, a compatibility path, or a stored representation, identify which present requirement would fail without it and why the smaller alternative falls short.

Possible future use, hypothetical reuse, and architectural convention alone justify no addition. An agent's implementation choices create no new product requirements. A plugin framework needing discovery, configuration, and registries does not show that the project needs a plugin framework.

## The subtraction pass
Before finishing, examine the complete affected paths and their consumers. Identify what can be removed, inlined, combined, derived from other data in place of being stored, or delegated to an existing mechanism while keeping the required behavior and guarantees. Perform those simplifications before declaring the task complete. Include tests, configuration, documentation, assets, and dependencies in the pass.

Challenge the mechanisms the change introduces as well as existing ones. A working addition still needs to earn its place. This rule owns whether machinery needs to exist. [CR-11](cr-11-every-change-includes-cleanup.md) owns removing obsolete parts and repairing the touched structure.

Keep the pass within the affected system. Investigate unknown usage and external consumers before deleting. Never remove supported behavior or meaningful tests to meet a size target. Preserve [TST-3](tst-3-minimal-test-count.md): sufficient protection for every distinct behavior and failure mode.

## Constraints and justified growth
Choose among implementations that satisfy the user's instructions, the project rules, and every applicable rule of [the coding rules](README.md). This rule relaxes nothing on correctness, security, boundary validation, failure handling, resource ownership, supported contracts, or required verification. Structure required by another rule is a constraint. [CR-14](cr-14-value-dispatch-through-a-registry.md) stays mandatory: minimize the surrounding machinery and keep its required registry literal.

Growth is allowed when a smaller implementation would fail a concrete present requirement or one of these constraints. Name that requirement or cite the governing rule, identify the smaller alternative, and explain its specific shortfall. Generic claims about flexibility, scalability, or maintainability are insufficient. There is no net-negative line quota and no permission to offset growth with unrelated deletion.

For a review, apply the same questions, report unnecessary machinery, and change no file without authorization.

## The growth account
In the final response:
1. Report the maintained lines and files added and removed relative to the starting working tree of the task, plus the dependencies added or removed. Separate generated and lockfile churn from maintained source changes. If a count cannot be measured, say so and give no estimate.
2. State what the subtraction pass removed or simplified. If nothing could safely be removed, state which affected paths were examined and why their remaining structure is needed.
3. When the result grows, give the concrete requirement and the smaller-alternative justification above. Account for new mechanisms even when the total line count falls.

Keep this account brief and in the response. Never create a tracking document or new tooling only to satisfy it. Counts expose growth for review. They establish no correctness and prove no minimality.
