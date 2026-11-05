import json
import re
import tomllib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from pristine.project.tools import Ecosystem

PYPROJECT = "pyproject.toml"
PACKAGE_JSON = "package.json"
REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
PYTHON_NAME_SEPARATORS = re.compile(r"[-_.]+")
PACKAGE_DEPENDENCY_TABLES = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")


@dataclass(frozen=True)
class Manifest:
    path: str
    dependencies: frozenset[str]
    settings_keys: frozenset[str]
    scripts: Mapping[str, str]


def table(document: object, key: str) -> dict[str, Any]:
    value = document.get(key) if isinstance(document, dict) else None
    return value if isinstance(value, dict) else {}


def array(document: object, key: str) -> list[Any]:
    value = document.get(key) if isinstance(document, dict) else None
    return value if isinstance(value, list) else []


def python_name(name: str) -> str:
    return PYTHON_NAME_SEPARATORS.sub("-", name).lower()


def requirement_names(requirements: Iterable[object]) -> set[str]:
    matches = (REQUIREMENT_NAME.match(requirement) for requirement in requirements if isinstance(requirement, str))
    return {python_name(match[1]) for match in matches if match}


def pyproject_dependencies(document: dict[str, Any]) -> frozenset[str]:
    project, tool = table(document, "project"), table(document, "tool")
    poetry = table(tool, "poetry")
    requirement_lists = [
        array(project, "dependencies"),
        array(table(tool, "uv"), "dev-dependencies"),
        *(value for value in table(project, "optional-dependencies").values() if isinstance(value, list)),
        *(value for value in table(document, "dependency-groups").values() if isinstance(value, list)),
    ]
    poetry_tables = [
        table(poetry, "dependencies"),
        table(poetry, "dev-dependencies"),
        *(table(group, "dependencies") for group in table(poetry, "group").values()),
    ]
    names = {name for requirements in requirement_lists for name in requirement_names(requirements)}
    return frozenset(names | {python_name(name) for dependencies in poetry_tables for name in dependencies})


def read_pyproject(path: str, text: str) -> Manifest:
    document = tomllib.loads(text)
    return Manifest(path, pyproject_dependencies(document), frozenset(table(document, "tool")), {})


def read_package_json(path: str, text: str) -> Manifest:
    document = json.loads(text)
    if not isinstance(document, dict):
        raise TypeError("the top level is not a JSON object")
    dependencies = frozenset(name for key in PACKAGE_DEPENDENCY_TABLES for name in table(document, key))
    scripts = {name: body for name, body in table(document, "scripts").items() if isinstance(body, str)}
    return Manifest(path, dependencies, frozenset(document), scripts)


MANIFEST_READERS: dict[Ecosystem, tuple[str, Callable[[str, str], Manifest]]] = {
    Ecosystem.PYTHON: (PYPROJECT, read_pyproject),
    Ecosystem.JAVASCRIPT: (PACKAGE_JSON, read_package_json),
}
