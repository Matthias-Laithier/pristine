from pathlib import PurePath

from pristine.checks.registry import FileCheck, register_file_check
from pristine.checks.service_location.languages import client_table
from pristine.findings import Finding, Severity
from pristine.parsing import ParsedFile
from pristine.path_roles import is_test_path

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
    imports = [(module.line, table.client_of(module.name)) for module in table.read_imports(parsed.root)]
    clients = [(line, client) for line, client in imports if client is not None]
    if not clients:
        return []
    libraries = ", ".join(dict.fromkeys(client for _, client in clients))
    message = (
        f"imports external-system client library {libraries} outside a services/ folder; "
        "wrap it in a service under services/ and build it in the composition root"
    )
    return [Finding(parsed.path, min(clients)[0], RULE_ID, Severity.WARNING, message)]


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Files importing an external-system client library (HTTP, cloud SDK, database, broker, LLM, mail) outside "
            "a services/ folder. Tests, composition roots, and type-only imports are exempt."
        ),
        run=check_service_location,
    )
)
