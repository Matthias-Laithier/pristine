DESCRIPTION = (
    "Check code against the coding rules and print the rules themselves. Built for agents: run 'pristine guide' "
    "before coding to read how to apply the rules, 'pristine rule <ID>' to read a rule, and 'pristine check' on "
    "the files you wrote or changed before finishing a task. Exit code 0 means success with no error findings "
    "(warnings may remain), 1 means at least one error finding, 2 means a usage problem such as a missing path or "
    "an unknown rule ID."
)
GUIDE_DESCRIPTION = (
    "Print the rules hub verbatim as markdown: precedence, the steps to follow before coding, while coding, and "
    "before finishing, and the chapter lists with every rule ID and title. Read it before coding. Exit code 0."
)
RULE_DESCRIPTION = (
    "Print the full markdown text of each given rule, in the order given, separated by a blank line. IDs match "
    "case-insensitively, such as cr-13 or CR-13. Exit code 0, or 2 when an ID is unknown, with the known IDs on "
    "stderr and nothing on stdout."
)
RULES_DESCRIPTION = (
    "List every rule, in chapter and number order, with how it is checked: 'check' (pristine check), 'project' "
    "(pristine project), or 'review' (no automated check: review your code against it yourself). Text lines read "
    "'ID Title (checked_by): summary', the summary only for checked rules, then a 'next:' line. --json prints a list of objects with "
    "rule_id, title, checked_by, and summary (null for review). Exit code 0."
)
CHECK_DESCRIPTION = (
    "Check files and directories. Directories expand to their git-tracked and untracked, non-ignored files, "
    "or to every non-hidden file outside a git repository. Prose, data, lockfiles, binaries, and files marked "
    "as generated are skipped. Files without a known grammar, unreadable files, and files whose parser crashes or "
    "times out are listed as unchecked, never silently passed. Files are parsed in parallel worker processes. "
    "Each text finding reads 'path:line: RULE-ID severity: message'. Fix every finding, or report it by rule ID "
    "as a deliberate break with its reason."
)
PROJECT_DESCRIPTION = (
    "Check the tooling contract of a repository, given its root directory. TL-1: a root Makefile (error if "
    "missing) with the targets dev, check, and check-all (error per missing target), a build target when the "
    "project produces artifacts, detected by a container build file or a root package.json build script "
    "(warning), and no component Makefiles below the root (warning). TL-2: check-all runs check, as a "
    "prerequisite or through '$(MAKE) check' (error). TL-3: when the root has a pyproject.toml or a package.json, "
    "a formatter, a linter, and for TypeScript a type checker are declared in a dependency list, a tool section, "
    "or a config file anywhere in the repository, and 'make check', followed through prerequisites, sub-make "
    "calls, and root package.json scripts, runs each of them, the formatter in check mode (error per gap). TL-4: "
    "a deployable application, detected by a container build file, has a committed lockfile for each root "
    "manifest, verified with git ls-files (warning). Paths under node_modules, vendor, third_party, and template "
    "directories are ignored. Output and exit codes match 'check': text lines 'path:line: RULE-ID severity: "
    "message' or --json, then exit 0 without error findings, 1 with at least one, 2 when PATH is not a "
    "directory. Makefiles and manifests read count as checked files; unreadable or invalid ones are listed as "
    "unchecked."
)
