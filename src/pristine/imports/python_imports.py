import posixpath

from pristine.imports.cycles import cyclic_components, dependency_graph
from pristine.imports.edges import ImportEdge, SourceFile
from pristine.imports.python_modules import PACKAGE_INIT, ModuleIndex, PythonModule, dotted_prefixes, python_module
from pristine.imports.python_scan import candidate_imports
from pristine.imports.python_statements import PythonImport, python_imports


def module_edges(index: ModuleIndex, imports: dict[PythonModule, list[PythonImport]]) -> list[ImportEdge]:
    return [
        ImportEdge(module.path, target, statement.line)
        for module, statements in imports.items()
        for statement in statements
        for target in index.targets(module, statement)
    ]


def python_modules(paths: list[str], candidates: list[PythonImport]) -> list[PythonModule]:
    package_directories = {posixpath.dirname(path) for path in paths if posixpath.basename(path) == PACKAGE_INIT}
    imported_prefixes = dotted_prefixes(candidates)
    modules = [python_module(path, package_directories, imported_prefixes) for path in paths]
    return [module for module in modules if module is not None]


def read_python_edges(files: list[SourceFile]) -> list[ImportEdge]:
    texts = {file.path: file.text for file in files}
    candidates = {path: list(candidate_imports(text)) for path, text in texts.items()}
    modules = python_modules(list(texts), [statement for statements in candidates.values() for statement in statements])
    index = ModuleIndex(modules)
    possible_edges = module_edges(index, {module: candidates[module.path] for module in modules})
    suspects = set().union(*cyclic_components(dependency_graph(possible_edges)))
    exact = {module: python_imports(texts[module.path]) for module in modules if module.path in suspects}
    return module_edges(index, exact)
