# CR-16 Inspect Before Implementing

Before implementing a feature, a fix, or a refactor, inspect the existing code paths, call sites, tests, utilities, services, dependencies, configuration, conventions, and extension points related to it. Use what the project already provides.

Follow this order of preference:
1. Reuse an existing mechanism when it already fits.
2. Improve or extend the mechanism that owns the responsibility.
3. Create a new implementation only when existing code cannot cleanly satisfy the requirement.

Never force an unrelated abstraction to support a new use case. When reuse would create unclear ownership, hidden coupling, or a worse interface, create the smallest suitable implementation and record why the existing mechanism was left aside.

This rule owns discovery and reuse inside the project. [CR-2](cr-2-do-not-reinvent.md) owns discovery and reuse of standard-library and third-party solutions. [CR-5](cr-5-dry-don-t-repeat-yourself.md) owns extracting behavior that is genuinely shared.
