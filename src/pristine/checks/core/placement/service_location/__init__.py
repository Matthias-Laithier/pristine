from pathlib import PurePath

from pristine.checks.definitions import FileCheck
from pristine.checks.prefilters import heads, mentions_any, requiring
from pristine.clients.libraries import PYTHON_CLIENTS, PYTHON_ENTRY_POINTS, SCRIPT_CLIENTS, SCRIPT_ENTRY_POINTS
from pristine.clients.tables import client_table, library_names
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.parsing import ParsedFile

CHECK_ID = "STR-6"
REQUIRED_TEXT = {
    "python": heads((*PYTHON_CLIENTS, *PYTHON_ENTRY_POINTS)),
    **dict.fromkeys(SCRIPT_LANGUAGES, heads((*SCRIPT_CLIENTS, *SCRIPT_ENTRY_POINTS), "/")),
}
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
    return [Finding(parsed.path, min(client.line for client in clients), CHECK_ID, Severity.WARNING, message)]


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Service Placement",
    summary=(
        "Files importing an external-system client library (HTTP, cloud SDK, database, broker, LLM, mail) outside "
        "a services/ folder. Tests, composition roots, and type-only imports are exempt."
    ),
    run=requiring(mentions_any(REQUIRED_TEXT), check_service_location),
)
