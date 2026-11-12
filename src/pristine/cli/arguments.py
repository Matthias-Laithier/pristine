import argparse
from importlib.metadata import version
from pathlib import Path

from pristine.cli.help import (
    AUDIT_DESCRIPTION,
    CHECK_DESCRIPTION,
    CHECKS_DESCRIPTION,
    DESCRIPTION,
    GUIDE_DESCRIPTION,
    PROJECT_DESCRIPTION,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="pristine", description=DESCRIPTION)
    root.add_argument("--version", action="version", version=f"%(prog)s {version('pristine')}")
    commands = root.add_subparsers(dest="command", required=True)
    add_check_command(commands)
    project = commands.add_parser(
        "project", help="check the repository tooling contract (PROJ-1 to PROJ-4)", description=PROJECT_DESCRIPTION
    )
    project.add_argument("path", nargs="?", default=Path("."), type=Path, help="repository root, default '.'")
    add_report_options(project)
    add_audit_command(commands)
    commands.add_parser("guide", help="print the short implementation guide", description=GUIDE_DESCRIPTION)
    checks = commands.add_parser("checks", help="list executable checks", description=CHECKS_DESCRIPTION)
    checks.add_argument("--json", action="store_true", help="print check metadata as JSON")
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
        "--no-cache",
        action="store_true",
        help="check every file again instead of reusing results of unchanged files from .pristine_cache/",
    )
    add_report_options(check)


def positive_count(text: str) -> int:
    count = int(text)
    if count < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {count}")
    return count


def add_audit_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    audit = commands.add_parser(
        "audit", help="audit resolved dependencies with optional OSV-Scanner", description=AUDIT_DESCRIPTION
    )
    audit.add_argument(
        "path", type=Path, metavar="PATH", help="uv.lock or directory containing a root uv.lock; no recursion"
    )
    add_report_options(audit)


def add_report_options(command: argparse.ArgumentParser) -> None:
    command.add_argument("--json", action="store_true", help="print a JSON report instead of text lines")
    command.add_argument(
        "--max",
        type=positive_count,
        metavar="N",
        help="print at most N findings, then a line counting the omitted ones; the summary still counts every "
        "finding, and --json truncates the findings list and reports the rest as summary.omitted; default: all",
    )
