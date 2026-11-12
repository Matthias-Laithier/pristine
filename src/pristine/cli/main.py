import argparse
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from pristine.cli.arguments import parser
lazy from pristine.audit.osv_json import parse_osv_json
lazy from pristine.catalog.check_listing import render_checks_json, render_checks_text
lazy from pristine.catalog.guide import GUIDE
lazy from pristine.checks.registry import path_checks
lazy from pristine.cli.audit import render_json as render_audit_json
lazy from pristine.cli.audit import render_text as render_audit_text
lazy from pristine.cli.rendering import render_json, render_text
lazy from pristine.engine.grammar_downloads import grammar_download_notices
lazy from pristine.files.discovery import discover_files, missing_paths
lazy from pristine.project.inspection import inspect_project
lazy from pristine.reports.findings import Severity
lazy from pristine.reports.report import Report, build_report
lazy from pristine.services import osv_scanner
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
    for notice in grammar_download_notices(files):
        print(notice, file=sys.stderr)
    checks = path_checks()
    with ThreadPoolExecutor(max_workers=len(checks)) as executor:
        pending = [executor.submit(check.run, files) for check in checks]
        with worker_outcomes(files, jobs) as completed:
            outcomes = dict(completed)
        path_findings = [finding for future in pending for finding in future.result()]
    missing = missing_paths(arguments.paths)
    report = build_report(outcomes, path_findings, missing)
    return print_report(report, arguments)


def run_project(arguments: argparse.Namespace) -> int:
    if not arguments.path.is_dir():
        print(f"pristine: not a directory: {arguments.path}", file=sys.stderr)
        return EXIT_USAGE
    return print_report(inspect_project(arguments.path), arguments)


def run_audit(arguments: argparse.Namespace) -> int:
    result = osv_scanner.scan_lockfile(arguments.path)
    report = parse_osv_json(result.stdout, (result.problem,) if result.problem is not None else ())
    target_matches = (
        result.target_path is not None
        and len(report.sources) == 1
        and report.sources[0].path == result.target_path
        and report.sources[0].source_type == "lockfile"
    )
    if not target_matches and (result.target_path is not None or result.problem is None):
        report = replace(
            report, problems=(*report.problems, "native source evidence does not match the requested lockfile")
        )
    if result.problem is None and result.extracted_packages != report.counts["packages"]:
        report = replace(
            report, problems=(*report.problems, "native extraction count contradicts its package evidence")
        )
    if (result.returncode == EXIT_CLEAN and report.findings) or (
        result.returncode == EXIT_ERRORS_FOUND and not report.findings
    ):
        report = replace(
            report, problems=(*report.problems, "OSV-Scanner exit status contradicts its advisory findings")
        )
    print(render_audit_json(report, arguments.max) if arguments.json else render_audit_text(report, arguments.max))
    if report.verification_failed:
        return EXIT_INCOMPLETE_VERIFICATION
    return EXIT_ERRORS_FOUND if report.findings else EXIT_CLEAN


def run_checks(arguments: argparse.Namespace) -> int:
    print(render_checks_json() if arguments.json else render_checks_text())
    return EXIT_CLEAN


def run_guide(_: argparse.Namespace) -> int:
    print(GUIDE, end="")
    return EXIT_CLEAN


def command_handlers() -> dict[str, CommandHandler]:
    return {
        "check": run_check,
        "project": run_project,
        "audit": run_audit,
        "guide": run_guide,
        "checks": run_checks,
    }


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    return command_handlers()[arguments.command](arguments)
