import ast
import re
import tomllib
from pathlib import Path

lazy from tree_sitter import Node

from pristine.syntax.parsing import ParsedFile, node_text
from pristine.syntax.python_calls import qualified_callee

SHEBANG = "#!"
PACKAGE_MAIN = "__main__.py"
PACKAGE_INIT = "__init__"
MANIFEST = "pyproject.toml"
TASK_DECORATORS = ("invoke.task", "invoke.tasks.task", "nox.session")
MAIN_GUARD = re.compile(r"^if __name__ == ['\"]__main__['\"]:", re.MULTILINE)


def is_within(qualified: str | None, modules: tuple[str, ...]) -> bool:
    return qualified is not None and any(
        qualified == module or qualified.startswith(f"{module}.") for module in modules
    )


def table(value: object, key: str) -> dict[object, object]:
    entry = value.get(key) if isinstance(value, dict) else None
    return dict[object, object](entry) if isinstance(entry, dict) else {}


def manifest_entry_modules(directory: Path) -> frozenset[str]:
    try:
        manifest = tomllib.loads((directory / MANIFEST).read_text())
    except OSError, UnicodeDecodeError, tomllib.TOMLDecodeError:
        return frozenset[str]()
    project = table(manifest, "project")
    poetry = table(table(manifest, "tool"), "poetry")
    scripts = [table(project, "scripts"), table(project, "gui-scripts"), table(poetry, "scripts")]
    targets = [target for entries in scripts for target in entries.values() if isinstance(target, str)]
    return frozenset[str](target.partition(":")[0].strip() for target in targets)


def import_sources(node: ast.ImportFrom, package: str) -> list[str]:
    if node.level == 0:
        return [] if node.module is None else [node.module]
    if node.level > 1:
        return []
    return (
        [f"{package}.{node.module}"] if node.module is not None else [f"{package}.{alias.name}" for alias in node.names]
    )


def package_main_imports(directory: Path) -> frozenset[str]:
    try:
        tree = ast.parse((directory / PACKAGE_MAIN).read_text())
    except OSError, UnicodeDecodeError, SyntaxError, ValueError:
        return frozenset[str]()
    imports = (node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    return frozenset[str](source for node in imports for source in import_sources(node, directory.name))


def module_parts(location: Path) -> tuple[str, ...]:
    parts = location.with_suffix("").parts
    return parts[:-1] if parts[-1] == PACKAGE_INIT else parts


def ends_with(parts: tuple[str, ...], dotted: str) -> bool:
    suffix = tuple(dotted.split("."))
    return parts[-len(suffix) :] == suffix


def is_named_entry(path: str) -> bool:
    location = Path(path).resolve()
    parts = module_parts(location)
    manifest_modules = (module for directory in location.parents for module in manifest_entry_modules(directory))
    is_script_module = any(ends_with(parts, module) for module in manifest_modules)
    package_sources = package_main_imports(location.parent)
    return is_script_module or any(
        ends_with(parts, source) and len(source.split(".")) > 1 for source in package_sources
    )


def is_task(decorator: Node, bindings: dict[str, str]) -> bool:
    expression = next(iter(decorator.named_children), None)
    name = (node_text(expression) or "").partition("(")[0]
    return is_within(qualified_callee(name, bindings), TASK_DECORATORS)


def is_composition_root(parsed: ParsedFile, bindings: dict[str, str]) -> bool:
    is_launched = parsed.text.startswith(SHEBANG) or MAIN_GUARD.search(parsed.text) is not None
    if is_launched or Path(parsed.path).name == PACKAGE_MAIN:
        return True
    decorators = parsed.nodes_of("decorator")
    return any(is_task(decorator, bindings) for decorator in decorators) or is_named_entry(parsed.path)
