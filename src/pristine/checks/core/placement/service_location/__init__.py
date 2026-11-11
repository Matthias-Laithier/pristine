from pathlib import PurePath

from pristine.checks.definitions import FileCheck
from pristine.clients.tables import client_table, library_names
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile

RULE_ID = "CR-8"
SERVICES_DIRECTORY = "services"
STORYBOOK_MARKER = ".stories."
TYPE_DECLARATION_SUFFIX = ".d.ts"
COMPOSITION_ROOT_NAMES = frozenset(
    {
        "main.py",
        "__main__.py",
        "app.py",
        "main.ts",
        "index.ts",
        "server.ts",
        "main.js",
        "index.js",
        "server.js",
        "main.go",
    }
)


def is_composition_root(location: PurePath) -> bool:
    return location.name in COMPOSITION_ROOT_NAMES


def is_exempt(path: str) -> bool:
    location = PurePath(path)
    in_services = SERVICES_DIRECTORY in location.parent.parts
    is_development_only = location.name.endswith(TYPE_DECLARATION_SUFFIX) or STORYBOOK_MARKER in location.name
    return in_services or is_development_only or is_test_path(location) or is_composition_root(location)


def check_service_location(parsed: ParsedFile) -> list[Finding]:
    table = client_table(parsed.language)
    if table is None or is_exempt(parsed.path):
        return []
    clients = table.clients(parsed)
    if not clients:
        return []
    message = (
        f"imports external-system client library {library_names(clients)} outside a services/ folder; "
        "wrap it in a service under services/ and build it in the composition root"
    )
    return [Finding(parsed.path, min(client.line for client in clients), RULE_ID, Severity.WARNING, message)]


CHECK = FileCheck(
    rule_id=RULE_ID,
    title="Services Live in a Dedicated services Folder",
    summary=(
        "Files importing an external-system client library (HTTP, cloud SDK, database, broker, LLM, mail) outside "
        "a services/ folder. Tests, composition roots, and type-only imports are exempt."
    ),
    run=check_service_location,
)
