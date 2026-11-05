from collections.abc import Callable
from dataclasses import dataclass

from pristine.project.jsonc import parse_jsonc
from pristine.project.loading import Project

STRICT_FLAG = "--strict"

type Arguments = list[list[str]]


@dataclass(frozen=True)
class Shortfall:
    path: str
    fix: str


type StrictnessCheck = Callable[[Project, Arguments], Shortfall | None]


@dataclass(frozen=True)
class Probe:
    subject: str
    check: StrictnessCheck


class UnverifiedConfigError(Exception):
    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


def passes_strict_flag(calls: Arguments) -> bool:
    return any(STRICT_FLAG in arguments for arguments in calls)


def read_json_config(project: Project, path: str) -> dict[str, object]:
    text = project.reader.text(path)
    if text is None:
        raise UnverifiedConfigError(path, f"{path} is unreadable")
    try:
        document = parse_jsonc(text)
    except ValueError as error:
        raise UnverifiedConfigError(path, f"{path} is not valid JSON with comments ({error})") from error
    if not isinstance(document, dict):
        raise UnverifiedConfigError(path, f"the top level of {path} is not a JSON object")
    return dict[str, object](document)
