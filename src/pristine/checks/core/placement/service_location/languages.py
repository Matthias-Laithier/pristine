from collections.abc import Callable, Iterator
from dataclasses import dataclass

from tree_sitter import Node

from pristine.checks.core.placement.service_location.clients import (
    GO_CLIENTS,
    GO_MODEL_CLIENTS,
    PYTHON_CLIENTS,
    PYTHON_MODEL_CLIENTS,
    SCRIPT_CLIENTS,
    SCRIPT_MODEL_CLIENTS,
)
from pristine.checks.core.placement.service_location.python_imports import python_import_targets
from pristine.registration import registering
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.parsing import all_nodes, line_of, node_text

STRING_LITERAL_KINDS = frozenset({"string", "interpreted_string_literal", "raw_string_literal"})
SCRIPT_LOADER_NAMES = frozenset({"require", "import"})
NON_CLIENT_SEGMENTS = frozenset({"errors", "exceptions", "models", "types"})
NON_CLIENT_SUFFIXES = ("Error", "Exception", "pb")


@dataclass(frozen=True)
class ImportedModule:
    name: str
    line: int


type ImportReader = Callable[[Node], Iterator[ImportedModule]]


@dataclass(frozen=True)
class ClientImport:
    line: int
    client: str


@dataclass(frozen=True)
class ClientTable:
    packages: tuple[str, ...]
    model_packages: tuple[str, ...]
    separator: str
    read_imports: ImportReader

    def clients(self, root: Node) -> list[ClientImport]:
        return self.imports_of(root, self.packages)

    def model_clients(self, root: Node) -> list[ClientImport]:
        return self.imports_of(root, self.model_packages)

    def imports_of(self, root: Node, packages: tuple[str, ...]) -> list[ClientImport]:
        imports = [(module.line, self.package_of(module.name, packages)) for module in self.read_imports(root)]
        return [ClientImport(line, client) for line, client in imports if client is not None]

    def package_of(self, module: str, packages: tuple[str, ...]) -> str | None:
        if self.is_non_client_reference(module):
            return None
        return next((package for package in packages if self.is_within(module, package)), None)

    def is_non_client_reference(self, module: str) -> bool:
        parts = module.split(self.separator)[1:]
        return any(part in NON_CLIENT_SEGMENTS or part.endswith(NON_CLIENT_SUFFIXES) for part in parts)

    def is_within(self, module: str, package: str) -> bool:
        return module == package or module.startswith(package + self.separator)


_CLIENT_TABLES: dict[str, ClientTable] = {}


def client_table(language: str) -> ClientTable | None:
    return _CLIENT_TABLES.get(language)


def library_names(clients: list[ClientImport]) -> str:
    return ", ".join(sorted({client.client for client in clients}))


def reads_clients(
    packages: tuple[str, ...], model_packages: tuple[str, ...], separator: str, *languages: str
) -> Callable[[ImportReader], ImportReader]:
    def register(reader: ImportReader) -> ImportReader:
        registering(_CLIENT_TABLES, *languages)(ClientTable(packages, model_packages, separator, reader))
        return reader

    return register


@reads_clients(PYTHON_CLIENTS, PYTHON_MODEL_CLIENTS, ".", "python")
def read_python_imports(root: Node) -> Iterator[ImportedModule]:
    yield from (ImportedModule(target, line) for target, line in python_import_targets(root))


def is_type_only_import(statement: Node) -> bool:
    return any(child.type == "type" for child in statement.children)


def import_bindings(statement: Node) -> list[Node]:
    clause = next((child for child in statement.named_children if child.type == "import_clause"), None)
    return [] if clause is None else clause.named_children


def named_import_targets(source: str, named_imports: Node) -> list[str]:
    specifiers = [specifier for specifier in named_imports.named_children if not is_type_only_import(specifier)]
    return [f"{source}/{node_text(specifier.child_by_field_name('name'))}" for specifier in specifiers]


def script_import_targets(statement: Node) -> list[str]:
    source = string_content(statement.child_by_field_name("source"))
    if source is None or is_type_only_import(statement):
        return []
    bindings = import_bindings(statement)
    if [binding.type for binding in bindings] != ["named_imports"]:
        return [source]
    return named_import_targets(source, bindings[0])


def script_loader_targets(call: Node) -> list[str]:
    loader = node_text(call.child_by_field_name("function"))
    arguments = call.child_by_field_name("arguments")
    if loader not in SCRIPT_LOADER_NAMES or arguments is None or arguments.named_child_count != 1:
        return []
    source = string_content(arguments.named_children[0])
    return [] if source is None else [source]


def string_content(node: Node | None) -> str | None:
    if node is None or node.type not in STRING_LITERAL_KINDS:
        return None
    return (node_text(node) or "").strip("\"'`")


@reads_clients(SCRIPT_CLIENTS, SCRIPT_MODEL_CLIENTS, "/", *SCRIPT_LANGUAGES)
def read_script_imports(root: Node) -> Iterator[ImportedModule]:
    for node in all_nodes(root):
        targets = script_import_targets(node) if node.type == "import_statement" else []
        targets += script_loader_targets(node) if node.type == "call_expression" else []
        yield from (ImportedModule(target, line_of(node)) for target in targets)


@reads_clients(GO_CLIENTS, GO_MODEL_CLIENTS, "/", "go")
def read_go_imports(root: Node) -> Iterator[ImportedModule]:
    for node in all_nodes(root):
        source = string_content(node.child_by_field_name("path")) if node.type == "import_spec" else None
        if source is not None:
            yield ImportedModule(source, line_of(node))
