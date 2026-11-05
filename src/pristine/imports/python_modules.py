import posixpath
from collections import defaultdict
from dataclasses import dataclass

from pristine.imports.python_statements import PythonImport

PACKAGE_INIT = "__init__.py"
PYTHON_SUFFIX = ".py"
PARENT_DIRECTORY = ".."
MAX_NAMESPACE_DEPTH = 3


@dataclass(frozen=True)
class PythonModule:
    path: str
    name: str
    root: str


def dotted_prefixes(imports: list[PythonImport]) -> set[str]:
    absolute = [statement for statement in imports if statement.level == 0]
    names = {statement.module for statement in absolute}
    names.update(f"{statement.module}.{name}" for statement in absolute for name in statement.names)
    split_names = [name.split(".") for name in names]
    return {".".join(parts[:end]) for parts in split_names for end in range(1, len(parts) + 1)}


def package_chain(path: str, package_directories: set[str]) -> tuple[str, list[str]]:
    directory = posixpath.dirname(path)
    parts = [] if posixpath.basename(path) == PACKAGE_INIT else [posixpath.basename(path)[: -len(PYTHON_SUFFIX)]]
    while directory and directory in package_directories:
        parts.insert(0, posixpath.basename(directory))
        directory = posixpath.dirname(directory)
    return directory, parts


def enclosing_namespaces(root: str, top_level: str, imported_prefixes: set[str]) -> list[str]:
    names: list[str] = []
    namespaces: list[str] = []
    directory = root
    for _ in range(MAX_NAMESPACE_DEPTH):
        if not posixpath.basename(directory):
            break
        names.insert(0, posixpath.basename(directory))
        directory = posixpath.dirname(directory)
        if ".".join([*names, top_level]) in imported_prefixes:
            namespaces = list(names)
    return namespaces


def python_module(path: str, package_directories: set[str], imported_prefixes: set[str]) -> PythonModule | None:
    root, parts = package_chain(path, package_directories)
    if not parts:
        return None
    namespaces = enclosing_namespaces(root, parts[0], imported_prefixes)
    for _ in namespaces:
        root = posixpath.dirname(root)
    return PythonModule(path, ".".join([*namespaces, *parts]), root)


def module_location(path: str) -> str:
    if posixpath.basename(path) == PACKAGE_INIT:
        return posixpath.normpath(posixpath.dirname(path))
    return path[: -len(PYTHON_SUFFIX)]


def shared_depth(first: str, second: str) -> int:
    depth = 0
    for first_part, second_part in zip(first.split("/"), second.split("/"), strict=False):
        if first_part != second_part:
            break
        depth += 1
    return depth


class ModuleIndex:
    def __init__(self, modules: list[PythonModule]) -> None:
        self.by_name: dict[str, list[PythonModule]] = defaultdict(list)
        for module in modules:
            self.by_name[module.name].append(module)
        self.by_location = {module_location(module.path): module.path for module in modules}

    def absolute(self, importer: PythonModule, name: str) -> str | None:
        candidates = self.by_name.get(name, [])
        own_root = [candidate.path for candidate in candidates if candidate.root == importer.root]
        if own_root:
            return own_root[0]
        if "." not in name or not candidates:
            return None
        depths = sorted((shared_depth(importer.path, candidate.path), candidate.path) for candidate in candidates)
        closest_depth, closest_path = depths[-1]
        is_unique = len(depths) == 1 or depths[-2][0] < closest_depth
        return closest_path if is_unique else None

    def relative(self, importer: PythonModule, level: int, name: str) -> str | None:
        package = posixpath.join(posixpath.dirname(importer.path), *[PARENT_DIRECTORY] * (level - 1))
        return self.by_location.get(posixpath.normpath(posixpath.join(package, *name.split("."))))

    def resolve(self, importer: PythonModule, level: int, name: str) -> str | None:
        if level == 0:
            return self.absolute(importer, name)
        return self.relative(importer, level, name)

    def targets(self, importer: PythonModule, statement: PythonImport) -> list[str]:
        module = statement.module
        if not statement.names:
            return [target for target in [self.resolve(importer, statement.level, module)] if target is not None]
        submodules = [".".join(part for part in (module, name) if part) for name in statement.names]
        resolved = [
            self.resolve(importer, statement.level, submodule) or self.resolve(importer, statement.level, module)
            for submodule in submodules
        ]
        return [target for target in resolved if target is not None]
