from collections.abc import Callable, Iterator
from dataclasses import dataclass

lazy from tree_sitter import Node

from pristine.clients.go_imports import go_import_modules
from pristine.clients.injection import no_injected_clients
from pristine.clients.injection.python import python_injected_clients
from pristine.clients.injection.script import script_injected_clients
from pristine.clients.libraries import (
    GO_CLIENTS,
    GO_MODEL_CLIENTS,
    PYTHON_CLIENTS,
    PYTHON_MODEL_CLIENTS,
    SCRIPT_CLIENTS,
    SCRIPT_MODEL_CLIENTS,
)
from pristine.clients.python_imports import python_import_targets
from pristine.clients.script_imports import script_import_modules
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.parsing import ParsedFile

type ImportReader = Callable[[Node | ParsedFile], Iterator[tuple[str, int]]]


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
    read_injected: ImportReader

    def clients(self, source: Node | ParsedFile) -> list[ClientImport]:
        return self.matches([*self.read_imports(source), *self.read_injected(source)], self.packages)

    def model_clients(self, source: Node | ParsedFile) -> list[ClientImport]:
        return self.matches(list(self.read_imports(source)), self.model_packages)

    def matches(self, modules: list[tuple[str, int]], packages: tuple[str, ...]) -> list[ClientImport]:
        imports = [(line, self.package_of(module, packages)) for module, line in modules]
        return [ClientImport(line, client) for line, client in imports if client is not None]

    def package_of(self, module: str, packages: tuple[str, ...]) -> str | None:
        return next((package for package in packages if self.is_within(module, package)), None)

    def is_within(self, module: str, package: str) -> bool:
        return module == package or module.startswith(package + self.separator)


SCRIPT_TABLE = ClientTable(SCRIPT_CLIENTS, SCRIPT_MODEL_CLIENTS, "/", script_import_modules, script_injected_clients)
CLIENT_TABLES = {
    "python": ClientTable(PYTHON_CLIENTS, PYTHON_MODEL_CLIENTS, ".", python_import_targets, python_injected_clients),
    "go": ClientTable(GO_CLIENTS, GO_MODEL_CLIENTS, "/", go_import_modules, no_injected_clients),
    **dict.fromkeys(SCRIPT_LANGUAGES, SCRIPT_TABLE),
}


def client_table(language: str) -> ClientTable | None:
    return CLIENT_TABLES.get(language)


def library_names(clients: list[ClientImport]) -> str:
    return ", ".join(sorted({client.client for client in clients}))
