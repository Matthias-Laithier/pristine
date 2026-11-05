# Working on pristine

This guide is for agents that change this repository. [README.md](README.md) covers installation and usage.

Code changes follow the rules in [src/pristine/rules/](src/pristine/rules/README.md). Read the hub before coding, or run `pristine guide`.

## Architecture

### Checks
- Checks live in `src/pristine/checks/`, one module or package per rule.
- Each check registers itself through [checks/registry.py](src/pristine/checks/registry.py). The registry imports every module of the `checks` package on first use, so a new check is a new module and nothing else.
- A file check, registered with `register_file_check`, receives one parsed file and returns its findings. It runs on every file with a grammar.
- A path check, registered with `register_path_check`, receives the list of discovered paths and returns its findings. It runs once in the main process over every discovered file and never parses with tree-sitter.

### Worker isolation
- File checks run in worker processes, each reporting after every file.
- A worker that crashes or exceeds its time budget loses only the file it was on. The report lists that file as unchecked, and a new worker continues with the rest.
- Grammar downloads run inside the same budget.
- Directory expansion leaves out vendored directories such as `node_modules` and `.venv`.

### Packages
- `services/` wraps every external dependency: git, gitleaks, the tree-sitter grammars, and the worker processes.
- `project/` implements `pristine project`: it loads a repository root and checks it against the Tooling chapter, TL-1 to TL-4.
- `imports/` reads import edges for the import-cycle check, CO-8. Each reader registers itself for the file suffixes it handles, through the same auto-discovery as the checks.
- `rules/` holds the rule documents. They ship inside the package, and `pristine guide` and `pristine rule <ID>` print them.

### Parsing
Parsing uses tree-sitter grammars from `tree-sitter-language-pack`, downloaded on first use of each language into the user cache. The tests parse with real grammars, so their first run needs network access to download the Python, JavaScript, TypeScript, and Rust grammars.

## Adding a check
1. Add a module to `src/pristine/checks/` that registers a file check or a path check for one rule ID.
2. Test it through the `run_pristine` fixture of [tests/conftest.py](tests/conftest.py), which writes files to a temporary directory and runs `pristine check` on them. Tests live in `tests/checks/`.
3. Validate it on real code. Run it on several real repositories and inspect every finding by hand.
4. Favor reliability over recall. A check reports only what it judges with certainty. A false positive costs more than a missed finding, since agents act on every finding. Leave the uncertain cases to the agent's own review.

## Quality gate
- `make check` formats, lints, type-checks, tests, and runs `pristine check` on its own source. It must report 0 findings.
- `make check-all` runs `make check`, then a gitleaks scan of the git history.
- `pristine project .` must report 0 findings on this repository.

## Pins
- `tree-sitter` stays below 0.26. Version 0.26.0 crashed with segmentation faults and bus errors while walking TSX and TypeScript trees, and 0.25.2 parses the same files cleanly. Lift the pin once a newer release walks large TSX and TypeScript code bases without a crash.
- gitleaks must be on the path for the secret scan of BS-2. When it is missing or fails, the report carries a BS-2 warning that the scan did not run.

## Commits
- One-line conventional messages: `type(scope): summary`, such as `feat(checks): exempt interactive terminal processes from BS-3`.
- Each commit passes `make check`.

## Changing the rules
The rules change only on the user's explicit request.

When the user gives a rule or a thought, determine its scope first. A request about how the rules themselves are kept edits this section directly and creates no chapter. Anything else is a coding rule or thought to debate and integrate:
1. Read the chapter lists of the hub, then debate. Read them first, so the debate happens against the rules that exist and never against memory. Push back when the proposal overlaps with an existing rule, contradicts one, feels incomplete, or could be stated better. Never accept it blindly. Argue, refine, and reach a sharper version together with the user.
2. Propose a full plan before writing anything: the rule files and sections to create, the files to update and what changes, the content to delete because it becomes redundant or replaced, and the files or chapters to move, rename, merge, or split. When the chapter lists change, show the new structure.
3. Wait for the user to approve the plan before changing anything.
4. Execute, then update the chapter lists of the hub: add an entry for each new rule, remove the entry of each deleted rule, and rebuild the chapters when they change.
5. Audit every existing example. Whenever a rule is added or changes materially, check every existing example against it. Update every Good example that violates the new practice. Update every Bad example whose violation is unrelated to the rule it teaches. A rule is integrated only once this audit is complete.
6. Run the tests. The rule document tests and the example tests must keep passing.

### Rule files
- A rule file is `src/pristine/rules/<id>-<slug>.md`, such as `cr-13-nesting-depth.md`. Its first line is `# <ID> <Title>`, such as `# CR-13 Nesting Depth`.
- A rule file holds the statement, the argument, the exceptions, and an example when one adds clarity. It is the single source of truth for that rule. The chapter lists of the hub hold only IDs and titles, since a statement copied elsewhere drifts.
- A rule file stays under 150 lines, with 200 as the hard limit. A file approaching the limit splits along clean topic boundaries.
- A chapter whose list grows too long splits into sub-chapters along clean topic boundaries.
- Rules cross-link. When a rule relates to another, the rule file links it with a relative markdown link and the target's ID as the link text. When two rules are commonly confused, one sentence names the split: which rule owns which concern.
- Rule files follow [the style guide](src/pristine/rules/STYLE.md). They also start with the point and never announce what they are about to say. They never manufacture nuance where the answer is clear. They name the exceptions: the rule, then its exceptions, then what to do when taking one, such as documenting why. Unstated exceptions get rediscovered by every reader.

### Rule IDs
- Every rule has an ID made of its chapter prefix and a number. The prefix takes the first letter of each word of the chapter name, such as CR for Coding Rules. Rules are numbered in sequence within the chapter: CR-1, CR-2, CR-3.
- IDs are stable for life. A rule keeps its ID when its file moves. IDs are never renumbered and never reused, which is why BS-6 and BS-7 do not exist.
- Prefixes are unique across all chapters. Before creating a chapter, check its initials against every existing prefix. On a collision, pick an unambiguous alternative, such as TST for Testing when T is taken.
- Titles are the relevance filter. A rule title is specific enough for an agent reading the chapter list to judge whether the rule touches its task without opening the file. The one-line description of a chapter meets the same bar.
- Agents cite rule IDs to report compliance or violations when writing or reviewing code.

### Examples in rule files
- Examples are optional. Include one only when it makes the rule clearer. When a comparison helps, show a Bad and a Good example.
- Code examples are in Python unless the rule is specific to an ecosystem. Keep them as language-agnostic as possible, so a reader who does not know Python understands the principle.
- Examples use concrete domains, such as `monthly_report`, `send_invoice`, or `FileStorage`. Placeholders such as `foo`, `bar`, or `MyClass` never appear.
- The Bad example is genuinely bad. It commits the full sin the rule argues against, so the reader sees the actual pain. A Bad example that partially complies teaches nothing.
- The difference between Bad and Good is the rule and nothing else. A pair that also turns a class into a function, while the rule is about unit size, teaches the wrong rule. Isolate the change the rule teaches.
- The Good example passes its own rule and every other rule. Check it against the chapter lists before writing it. An example that breaks one rule while teaching another is a defect.
- Examples are real code: no attribute a class never assigned, no bytes written to a text-mode file, no names with wrong semantics. Undefined collaborators are fine, since they stand for the reader's own libraries. The example's own classes carry no defect.
- One or two sentences follow each example. After a Bad example, name the concrete pain. After a Good example, name the concrete payoff. An example whose payoff cannot be stated does not demonstrate the rule.
