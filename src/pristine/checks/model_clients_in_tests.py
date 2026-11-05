import re
from pathlib import PurePath

from pristine.checks.registry import FileCheck, register_file_check
from pristine.checks.service_location.languages import ClientTable, client_table
from pristine.findings import Finding, Severity
from pristine.parsing import ParsedFile
from pristine.path_roles import PYTEST_CONFTEST, is_test_file
from pristine.services.grammars import SCRIPT_LANGUAGES

RULE_ID = "TST-8"
EVALS_DIRECTORY = "evals"
API_KEY_NAME = r"[\"'`]?(?P<key>[A-Z0-9_]*API_KEY)\b[\"'`]?+\]?+(?!\s*=[^=])"
API_KEY_READ = re.compile(rf"(environ(\.get)?\s*[\[(]|getenv\s*\(|(process|import\.meta)\.env(\.|\[))\s*{API_KEY_NAME}")
MODEL_SURFACE = re.compile(
    r"\.(chat|fim|embeddings|ocr|agents|conversations|classifiers|messages|responses|completions)\.\w+|\.generate_content\b"
)
PYTHON_MODEL_CLIENTS = (
    "openai",
    "anthropic",
    "mistralai.Mistral",
    "mistralai.client.Mistral",
    "google.generativeai",
    "cohere",
)
SCRIPT_MODEL_CLIENTS = ("openai", "@anthropic-ai/sdk", "@mistralai/mistralai")
MODEL_CLIENTS = {"python": PYTHON_MODEL_CLIENTS} | dict.fromkeys(SCRIPT_LANGUAGES, SCRIPT_MODEL_CLIENTS)


def is_test_module(path: str) -> bool:
    location = PurePath(path)
    is_test = is_test_file(location) or location.name == PYTEST_CONFTEST
    return is_test and EVALS_DIRECTORY not in location.parts


def model_client_table(parsed: ParsedFile) -> ClientTable | None:
    packages = MODEL_CLIENTS.get(parsed.language)
    imports = client_table(parsed.language)
    if packages is None or imports is None or not is_test_module(parsed.path):
        return None
    return ClientTable(packages, imports.separator, imports.read_imports)


def model_clients(parsed: ParsedFile) -> list[tuple[int, str]]:
    table = model_client_table(parsed)
    if table is None:
        return []
    imports = [(module.line, table.client_of(module.name)) for module in table.read_imports(parsed.root)]
    return [(line, client) for line, client in imports if client is not None]


def check_model_clients_in_tests(parsed: ParsedFile) -> list[Finding]:
    clients = model_clients(parsed)
    key_read = API_KEY_READ.search(parsed.text)
    if not clients or key_read is None or MODEL_SURFACE.search(parsed.text) is None:
        return []
    libraries = ", ".join(dict.fromkeys(client for _, client in clients))
    message = (
        f"test calls a real model through {libraries} with the {key_read['key']} key; replace the model with a "
        "fake that returns scripted outputs, and measure model quality with evals (make eval)"
    )
    return [Finding(parsed.path, min(clients)[0], RULE_ID, Severity.WARNING, message)]


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Test files importing a real LLM SDK client (Python openai, anthropic, mistralai Mistral, "
            "google.generativeai, cohere; JS/TS openai, @anthropic-ai/sdk, @mistralai/mistralai) and reading an "
            "API key from the environment, with a model API in use. Evals and type-only imports are exempt."
        ),
        run=check_model_clients_in_tests,
    )
)
