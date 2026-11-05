import argparse
import sys
from pathlib import Path

from pristine.checks.registry import path_checks
from pristine.discovery import PathNotFound, discover_files
from pristine.findings import Severity
from pristine.project.inspection import inspect_project
from pristine.rendering import render_json, render_rules_json, render_rules_text, render_text
from pristine.report import Report, build_report
from pristine.rule_documents import UnknownRule, find_rule, guide_text, rule_documents
from pristine.services.isolated_inspection import inspect_in_workers

EXIT_CLEAN = 0
EXIT_ERRORS_FOUND = 1
EXIT_USAGE = 2

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


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="pristine", description=DESCRIPTION)
    commands = root.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check files and directories", description=CHECK_DESCRIPTION)
    check.add_argument("paths", nargs="+", type=Path, help="files or directories to check")
    check.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip paths matching this glob, relative to the working directory; '**' crosses directories, and a "
        "directory pattern such as 'vendor' skips everything under it; repeat for several patterns",
    )
    check.add_argument("--json", action="store_true", help="print a JSON report instead of text lines")
    check.set_defaults(handler=run_check)
    project = commands.add_parser(
        "project", help="check the repository tooling contract (TL-1 to TL-4)", description=PROJECT_DESCRIPTION
    )
    project.add_argument("path", nargs="?", default=Path("."), type=Path, help="repository root, default '.'")
    project.add_argument("--json", action="store_true", help="print a JSON report instead of text lines")
    project.set_defaults(handler=run_project)
    add_rule_commands(commands)
    return root


def add_rule_commands(commands: argparse._SubParsersAction) -> None:
    guide = commands.add_parser(
        "guide", help="print the rules hub to read before coding", description=GUIDE_DESCRIPTION
    )
    guide.set_defaults(handler=run_guide)
    rule = commands.add_parser("rule", help="print the full text of rules by ID", description=RULE_DESCRIPTION)
    rule.add_argument("rule_ids", nargs="+", metavar="ID", help="rule IDs such as CR-13, case-insensitive")
    rule.set_defaults(handler=run_rule)
    rules = commands.add_parser("rules", help="list every rule and how it is checked", description=RULES_DESCRIPTION)
    rules.add_argument("--json", action="store_true", help="print the list as JSON")
    rules.set_defaults(handler=run_rules)


def print_report(report: Report, arguments: argparse.Namespace) -> int:
    print(render_json(report) if arguments.json else render_text(report))
    return EXIT_ERRORS_FOUND if report.count(Severity.ERROR) else EXIT_CLEAN


def run_check(arguments: argparse.Namespace) -> int:
    try:
        files = discover_files(arguments.paths, arguments.exclude)
    except PathNotFound as error:
        print(f"pristine: path not found: {error}", file=sys.stderr)
        return EXIT_USAGE
    path_findings = [finding for check in path_checks() for finding in check.run(files)]
    return print_report(build_report(inspect_in_workers(files), path_findings), arguments)


def run_project(arguments: argparse.Namespace) -> int:
    if not arguments.path.is_dir():
        print(f"pristine: not a directory: {arguments.path}", file=sys.stderr)
        return EXIT_USAGE
    return print_report(inspect_project(arguments.path), arguments)


def run_rules(arguments: argparse.Namespace) -> int:
    print(render_rules_json() if arguments.json else render_rules_text())
    return EXIT_CLEAN


def run_guide(_: argparse.Namespace) -> int:
    print(guide_text(), end="")
    return EXIT_CLEAN


def run_rule(arguments: argparse.Namespace) -> int:
    try:
        documents = [find_rule(rule_id) for rule_id in arguments.rule_ids]
    except UnknownRule as error:
        known = ", ".join(document.rule_id for document in rule_documents())
        print(f"pristine: unknown rule ID: {error}. Known IDs: {known}", file=sys.stderr)
        return EXIT_USAGE
    print("\n".join(document.text for document in documents), end="")
    return EXIT_CLEAN


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    return arguments.handler(arguments)
