import json
import re
import tomllib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from pristine.project.repository.go_manifests import parse_go_mod
from pristine.project.repository.tools import Ecosystem

PYPROJECT = "pyproject.toml"
PACKAGE_JSON = "package.json"
GO_MOD = "go.mod"
CARGO_TOML = "Cargo.toml"
REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
PYTHON_NAME_SEPARATORS = re.compile(r"[-_.]+")
JAVASCRIPT_RUNTIMES = frozenset({"node", "bun"})
BUN_PACKAGE_MANAGER = "bun@"
PACKAGE_DEPENDENCY_TABLES = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")
CARGO_DEPENDENCY_TABLES = ("dependencies", "dev-dependencies", "build-dependencies")


@dataclass(frozen=True)
class Manifest:
    path: str
    dependencies: frozenset[str]
    settings: Mapping[str, object]
    scripts: Mapping[str, str]
    pins_runtime: bool
    needs_lockfile: bool | None = True


def table(document: object, key: str) -> dict[str, object]:
    value = document.get(key) if isinstance(document, dict) else None
    return dict[str, object](value) if isinstance(value, dict) else {}


def array(document: object, key: str) -> list[object]:
    value = document.get(key) if isinstance(document, dict) else None
    return list[object](value) if isinstance(value, list) else []


def python_name(name: str) -> str:
    return PYTHON_NAME_SEPARATORS.sub("-", name).lower()


def requirement_names(requirements: Iterable[object]) -> set[str]:
    matches = (REQUIREMENT_NAME.match(requirement) for requirement in requirements if isinstance(requirement, str))
    return {python_name(match[1]) for match in matches if match}


def pyproject_dependencies(document: dict[str, object]) -> frozenset[str]:
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


def pins_python_runtime(document: dict[str, object]) -> bool:
    poetry_dependencies = table(table(table(document, "tool"), "poetry"), "dependencies")
    return "requires-python" in table(document, "project") or "python" in poetry_dependencies


def read_pyproject(path: str, text: str) -> Manifest:
    document = tomllib.loads(text)
    tool = table(document, "tool")
    return Manifest(path, pyproject_dependencies(document), tool, {}, pins_python_runtime(document))


def pins_javascript_runtime(document: dict[str, object]) -> bool:
    package_manager = document.get("packageManager")
    runs_on_bun = isinstance(package_manager, str) and package_manager.startswith(BUN_PACKAGE_MANAGER)
    return runs_on_bun or not table(document, "engines").keys().isdisjoint(JAVASCRIPT_RUNTIMES)


def read_go_mod(path: str, text: str) -> Manifest:
    dependencies, pins_runtime, needs_lockfile = parse_go_mod(text)
    return Manifest(path, dependencies, {}, {}, pins_runtime, needs_lockfile)


def cargo_dependencies(document: dict[str, object]) -> frozenset[str]:
    workspace = table(document, "workspace")
    dependency_tables = [table(document, name) for name in CARGO_DEPENDENCY_TABLES]
    dependency_tables.extend(table(workspace, name) for name in CARGO_DEPENDENCY_TABLES)
    target_tables = [
        table(target, name) for target in table(document, "target").values() for name in CARGO_DEPENDENCY_TABLES
    ]
    return frozenset({name for dependencies in dependency_tables + target_tables for name in dependencies})


def pins_rust_runtime(document: dict[str, object]) -> bool:
    workspace = table(document, "workspace")
    return "rust-version" in table(document, "package") or "rust-version" in table(workspace, "package")


def read_cargo_toml(path: str, text: str) -> Manifest:
    document = tomllib.loads(text)
    return Manifest(path, cargo_dependencies(document), document, {}, pins_rust_runtime(document))


def read_package_json(path: str, text: str) -> Manifest:
    document = json.loads(text)
    if not isinstance(document, dict):
        raise TypeError("the top level is not a JSON object")
    dependencies = frozenset(name for key in PACKAGE_DEPENDENCY_TABLES for name in table(document, key))
    scripts = {name: body for name, body in table(document, "scripts").items() if isinstance(body, str)}
    return Manifest(path, dependencies, document, scripts, pins_javascript_runtime(document))


MANIFEST_READERS: dict[Ecosystem, tuple[str, Callable[[str, str], Manifest]]] = {
    Ecosystem.PYTHON: (PYPROJECT, read_pyproject),
    Ecosystem.JAVASCRIPT: (PACKAGE_JSON, read_package_json),
    Ecosystem.GO: (GO_MOD, read_go_mod),
    Ecosystem.RUST: (CARGO_TOML, read_cargo_toml),
}
