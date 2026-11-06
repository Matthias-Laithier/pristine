from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

from pristine.package_modules import import_package_modules
from pristine.registration import registering
from pristine.reports.findings import Finding
from pristine.syntax.parsing import ParsedFile

CHECKS_PACKAGE = "pristine.checks"


@dataclass(frozen=True)
class FileCheck:
    rule_id: str
    summary: str
    run: Callable[[ParsedFile], list[Finding]]


@dataclass(frozen=True)
class PathCheck:
    rule_id: str
    summary: str
    run: Callable[[list[str]], list[Finding]]


_FILE_CHECKS: dict[str, FileCheck] = {}
_PATH_CHECKS: dict[str, PathCheck] = {}


def register_file_check(check: FileCheck) -> None:
    registering(_FILE_CHECKS, check.rule_id)(check)


def register_path_check(check: PathCheck) -> None:
    registering(_PATH_CHECKS, check.rule_id)(check)


@cache
def load_check_modules() -> None:
    import_package_modules(CHECKS_PACKAGE)


def file_checks() -> list[FileCheck]:
    load_check_modules()
    return [_FILE_CHECKS[rule_id] for rule_id in sorted(_FILE_CHECKS)]


def path_checks() -> list[PathCheck]:
    load_check_modules()
    return [_PATH_CHECKS[rule_id] for rule_id in sorted(_PATH_CHECKS)]
