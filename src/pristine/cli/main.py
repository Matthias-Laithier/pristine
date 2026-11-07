import argparse
import sys
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

from pristine.cli.help import (
    CHECK_DESCRIPTION,
    DESCRIPTION,
    GUIDE_DESCRIPTION,
    PROJECT_DESCRIPTION,
    RULE_DESCRIPTION,
    RULES_DESCRIPTION,
)
lazy from pristine.catalog.rule_documents import UnknownRule, rule_documents, select_rules
lazy from pristine.catalog.rule_listing import render_guide, render_rules_json, render_rules_text
lazy from pristine.checks.registry import path_checks
lazy from pristine.cli.rendering import render_json, render_text
lazy from pristine.cli.streaming import stream_complete, stream_file_outcome, stream_path_findings
lazy from pristine.engine.grammar_downloads import grammar_download_notices
lazy from pristine.files.discovery import discover_files, missing_paths
lazy from pristine.project.inspection import inspect_project
lazy from pristine.reports.findings import Finding, Severity
lazy from pristine.reports.outcomes import Outcome
lazy from pristine.reports.report import Report, build_report
lazy from pristine.services.isolated_inspection import default_jobs, worker_outcomes

EXIT_CLEAN = 0
EXIT_ERRORS_FOUND = 1
EXIT_USAGE = 2
EXIT_INCOMPLETE_VERIFICATION = 3

type CommandHandler = Callable[[argparse.Namespace], int]


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="pristine", description=DESCRIPTION)
    root.add_argument("--version", action="version", version=f"%(prog)s {version('pristine')}")
    commands = root.add_subparsers(dest="command", required=True)
    add_check_command(commands)
    project = commands.add_parser(
        "project", help="check the repository tooling contract (TL-1 to TL-4)", description=PROJECT_DESCRIPTION
    )
    project.add_argument("path", nargs="?", default=Path("."), type=Path, help="repository root, default '.'")
    add_report_options(project)
    add_rule_commands(commands)
    return root


def add_check_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
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
    check.add_argument(
        "--jobs",
        type=positive_count,
        default=None,
        metavar="N",
        help="run at most N worker processes, at least 1; default: half the CPU cores, at least 1",
    )
    check.add_argument(
        "--stream",
        action="store_true",
        help="print compact NDJSON events as files complete; cannot be combined with --json or --max",
    )
    add_report_options(check)


def positive_count(text: str) -> int:
    count = int(text)
    if count < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {count}")
    return count


def add_report_options(command: argparse.ArgumentParser) -> None:
    command.add_argument("--json", action="store_true", help="print a JSON report instead of text lines")
    command.add_argument(
        "--max",
        type=positive_count,
        metavar="N",
        help="print at most N findings, then a line counting the omitted ones; the summary still counts every "
        "finding, and --json truncates the findings list and reports the rest as summary.omitted; default: all",
    )


def add_rule_commands(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    commands.add_parser("guide", help="print the rules hub to read before coding", description=GUIDE_DESCRIPTION)
    rule = commands.add_parser(
        "rule", help="print rules by ID, by chapter, or all of them", description=RULE_DESCRIPTION
    )
    rule.add_argument(
        "selectors",
        nargs="+",
        metavar="ID",
        help="rule IDs such as CR-13, chapter prefixes such as BS, or all, case-insensitive",
    )
    rules = commands.add_parser("rules", help="list every rule and how it is checked", description=RULES_DESCRIPTION)
    rules.add_argument("--json", action="store_true", help="print the list as JSON")


def print_report(report: Report, arguments: argparse.Namespace) -> int:
    print(render_json(report, arguments.max) if arguments.json else render_text(report, arguments.max))
    return report_exit_code(report)


def report_exit_code(report: Report) -> int:
    if report.verification_failed:
        return EXIT_INCOMPLETE_VERIFICATION
    return EXIT_ERRORS_FOUND if report.count(Severity.ERROR) else EXIT_CLEAN


def reject_stream_conflicts(arguments: argparse.Namespace) -> None:
    if arguments.stream and (arguments.json or arguments.max is not None):
        parser().error("--stream cannot be combined with --json or --max")


def stream_report(files: list[str], jobs: int, path_findings: list[Finding], missing: tuple[str, ...]) -> int:
    print(stream_path_findings(path_findings))
    outcomes: dict[str, Outcome] = {}
    with worker_outcomes(files, jobs) as completed:
        for path, outcome in completed:
            outcomes[path] = outcome
            print(stream_file_outcome(path, outcome))
    report = build_report(outcomes, path_findings, missing)
    print(stream_complete(report))
    return report_exit_code(report)


def run_check(arguments: argparse.Namespace) -> int:
    reject_stream_conflicts(arguments)
    jobs = arguments.jobs if arguments.jobs is not None else default_jobs()
    files = discover_files(arguments.paths, arguments.exclude)
    path_findings = [finding for check in path_checks() for finding in check.run(files)]
    for notice in grammar_download_notices(files):
        print(notice, file=sys.stderr)
    missing = missing_paths(arguments.paths)
    if arguments.stream:
        return stream_report(files, jobs, path_findings, missing)
    with worker_outcomes(files, jobs) as completed:
        outcomes = dict(completed)
    report = build_report(outcomes, path_findings, missing)
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


def command_handlers() -> dict[str, CommandHandler]:
    return {"check": run_check, "project": run_project, "guide": run_guide, "rule": run_rule, "rules": run_rules}


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    return command_handlers()[arguments.command](arguments)
