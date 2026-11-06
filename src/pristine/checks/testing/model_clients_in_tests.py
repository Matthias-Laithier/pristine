import re
from pathlib import PurePath

from pristine.checks.registry import FileCheck, register_file_check
from pristine.clients.tables import ClientImport, client_table, library_names
from pristine.files.path_roles import PYTEST_CONFTEST, is_test_file
from pristine.reports.findings import Finding, Severity
from pristine.syntax.parsing import ParsedFile

RULE_ID = "TST-8"
EVALS_DIRECTORY = "evals"
API_KEY_NAME = r"[\"'`]?(?P<key>[A-Z0-9_]*API_KEY)\b[\"'`]?+\]?+(?!\s*=[^=])"
API_KEY_READ = re.compile(rf"(environ(\.get)?\s*[\[(]|getenv\s*\(|(process|import\.meta)\.env(\.|\[))\s*{API_KEY_NAME}")
MODEL_SURFACE = re.compile(
    r"\.(chat|fim|embeddings|ocr|agents|conversations|classifiers|messages|responses|completions)\.\w+|\.generate_content\b"
)


def is_test_module(path: str) -> bool:
    location = PurePath(path)
    is_test = is_test_file(location) or location.name == PYTEST_CONFTEST
    return is_test and EVALS_DIRECTORY not in location.parts


def model_clients(parsed: ParsedFile) -> list[ClientImport]:
    table = client_table(parsed.language)
    return [] if table is None or not is_test_module(parsed.path) else table.model_clients(parsed.root)


def check_model_clients_in_tests(parsed: ParsedFile) -> list[Finding]:
    clients = model_clients(parsed)
    key_read = API_KEY_READ.search(parsed.text)
    if not clients or key_read is None or MODEL_SURFACE.search(parsed.text) is None:
        return []
    message = (
        f"test calls a real model through {library_names(clients)} with the {key_read['key']} key; replace the model with a "
        "fake that returns scripted outputs, and measure model quality with evals (make eval)"
    )
    return [Finding(parsed.path, min(client.line for client in clients), RULE_ID, Severity.WARNING, message)]


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
