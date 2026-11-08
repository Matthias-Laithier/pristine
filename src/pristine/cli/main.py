import argparse
import sys
from collections.abc import Callable

from pristine.cli.arguments import parser
lazy from pristine.catalog.rule_documents import UnknownRule, rule_documents, select_rules
lazy from pristine.catalog.rule_listing import render_guide, render_rules_json, render_rules_text
lazy from pristine.checks.registry import path_checks
lazy from pristine.cli.rendering import render_json, render_text
lazy from pristine.engine.grammar_downloads import grammar_download_notices
lazy from pristine.files.discovery import discover_files, missing_paths
lazy from pristine.project.inspection import inspect_project
lazy from pristine.reports.findings import Severity
lazy from pristine.reports.report import Report, build_report
lazy from pristine.services.isolated_inspection import default_jobs, worker_outcomes

EXIT_CLEAN = 0
EXIT_ERRORS_FOUND = 1
EXIT_USAGE = 2
EXIT_INCOMPLETE_VERIFICATION = 3

type CommandHandler = Callable[[argparse.Namespace], int]


def print_report(report: Report, arguments: argparse.Namespace) -> int:
    print(render_json(report, arguments.max) if arguments.json else render_text(report, arguments.max))
    return report_exit_code(report)


def report_exit_code(report: Report) -> int:
    if report.verification_failed:
        return EXIT_INCOMPLETE_VERIFICATION
    return EXIT_ERRORS_FOUND if report.count(Severity.ERROR) else EXIT_CLEAN


def run_check(arguments: argparse.Namespace) -> int:
    jobs = arguments.jobs if arguments.jobs is not None else default_jobs()
    files = discover_files(arguments.paths, arguments.exclude)
    path_findings = [finding for check in path_checks() for finding in check.run(files)]
    for notice in grammar_download_notices(files):
        print(notice, file=sys.stderr)
    with worker_outcomes(files, jobs) as completed:
        outcomes = dict(completed)
    missing = missing_paths(arguments.paths)
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
