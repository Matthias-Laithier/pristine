import argparse
from importlib.metadata import version
from pathlib import Path

from pristine.cli.help import (
    AUDIT_DESCRIPTION,
    CHECK_DESCRIPTION,
    DESCRIPTION,
    GROWTH_DESCRIPTION,
    GUIDE_DESCRIPTION,
    PROJECT_DESCRIPTION,
    RULE_DESCRIPTION,
    RULES_DESCRIPTION,
)


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
    add_audit_command(commands)
    add_growth_command(commands)
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


def add_growth_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    growth = commands.add_parser(
        "growth", help="count maintained lines added and removed for CR-20", description=GROWTH_DESCRIPTION
    )
    growth.add_argument(
        "base",
        nargs="?",
        default=None,
        help="git revision to compare with; default: merge base with the default branch",
    )
    growth.add_argument("--path", type=Path, default=Path("."), help="a directory inside the repository, default '.'")
    growth.add_argument("--json", action="store_true", help="print the counts as JSON")


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
