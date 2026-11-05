import argparse
import sys
from importlib.metadata import version
from pathlib import Path

from pristine.checks.registry import path_checks
from pristine.cli_help import (
    CHECK_DESCRIPTION,
    DESCRIPTION,
    GUIDE_DESCRIPTION,
    PROJECT_DESCRIPTION,
    RULE_DESCRIPTION,
    RULES_DESCRIPTION,
)
from pristine.discovery import discover_files, missing_paths
from pristine.findings import Severity
from pristine.grammar_downloads import grammar_download_notices
from pristine.project.inspection import inspect_project
from pristine.rendering import render_json, render_text
from pristine.report import Report, build_report
from pristine.rule_documents import UnknownRule, rule_documents, select_rules
from pristine.rule_listing import render_guide, render_rules_json, render_rules_text
from pristine.services.isolated_inspection import inspect_in_workers

EXIT_CLEAN = 0
EXIT_ERRORS_FOUND = 1
EXIT_USAGE = 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="pristine", description=DESCRIPTION)
    root.add_argument("--version", action="version", version=f"%(prog)s {version('pristine')}")
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
    add_report_options(check)
    check.set_defaults(handler=run_check)
    project = commands.add_parser(
        "project", help="check the repository tooling contract (TL-1 to TL-4)", description=PROJECT_DESCRIPTION
    )
    project.add_argument("path", nargs="?", default=Path("."), type=Path, help="repository root, default '.'")
    add_report_options(project)
    project.set_defaults(handler=run_project)
    add_rule_commands(commands)
    return root


def finding_limit(text: str) -> int:
    limit = int(text)
    if limit < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {limit}")
    return limit


def add_report_options(command: argparse.ArgumentParser) -> None:
    command.add_argument("--json", action="store_true", help="print a JSON report instead of text lines")
    command.add_argument(
        "--max",
        type=finding_limit,
        metavar="N",
        help="print at most N findings, then a line counting the omitted ones; the summary still counts every "
        "finding, and --json truncates the findings list and reports the rest as summary.omitted; default: all",
    )


def add_rule_commands(commands: argparse._SubParsersAction) -> None:
    guide = commands.add_parser(
        "guide", help="print the rules hub to read before coding", description=GUIDE_DESCRIPTION
    )
    guide.set_defaults(handler=run_guide)
    rule = commands.add_parser(
        "rule", help="print rules by ID, by chapter, or all of them", description=RULE_DESCRIPTION
    )
    rule.add_argument(
        "selectors",
        nargs="+",
        metavar="ID",
        help="rule IDs such as CR-13, chapter prefixes such as BS, or all, case-insensitive",
    )
    rule.set_defaults(handler=run_rule)
    rules = commands.add_parser("rules", help="list every rule and how it is checked", description=RULES_DESCRIPTION)
    rules.add_argument("--json", action="store_true", help="print the list as JSON")
    rules.set_defaults(handler=run_rules)


def print_report(report: Report, arguments: argparse.Namespace) -> int:
    print(render_json(report, arguments.max) if arguments.json else render_text(report, arguments.max))
    return EXIT_ERRORS_FOUND if report.count(Severity.ERROR) else EXIT_CLEAN


def run_check(arguments: argparse.Namespace) -> int:
    files = discover_files(arguments.paths, arguments.exclude)
    path_findings = [finding for check in path_checks() for finding in check.run(files)]
    for notice in grammar_download_notices(files):
        print(notice, file=sys.stderr)
    report = build_report(inspect_in_workers(files), path_findings, missing_paths(arguments.paths))
    return print_report(report, arguments)


def run_project(arguments: argparse.Namespace) -> int:
    if not arguments.path.is_dir():
        print(f"pristine: not a directory: {arguments.path}", file=sys.stderr)
        return EXIT_USAGE
    return print_report(inspect_project(arguments.path), arguments)


def run_rules(arguments: argparse.Namespace) -> int:
    print(render_rules_json() if arguments.json else render_rules_text())
    return EXIT_CLEAN


def run_guide(_: argparse.Namespace) -> int:
    print(render_guide(), end="")
    return EXIT_CLEAN


def run_rule(arguments: argparse.Namespace) -> int:
    try:
        documents = [document for selector in arguments.selectors for document in select_rules(selector)]
    except UnknownRule as error:
        known = ", ".join(document.rule_id for document in rule_documents())
        print(f"pristine: unknown rule ID or chapter: {error}. Known IDs: {known}", file=sys.stderr)
        return EXIT_USAGE
    print("\n".join(document.text for document in documents), end="")
    return EXIT_CLEAN


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    return arguments.handler(arguments)
