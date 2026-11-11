from collections.abc import Callable
from dataclasses import dataclass

from pristine.reports.findings import Finding
lazy from pristine.syntax.parsing import ParsedFile


@dataclass(frozen=True)
class FileCheck:
    rule_id: str
    title: str
    summary: str
    run: Callable[[ParsedFile], list[Finding]]


@dataclass(frozen=True)
class PathCheck:
    rule_id: str
    title: str
    summary: str
    run: Callable[[list[str]], list[Finding]]
