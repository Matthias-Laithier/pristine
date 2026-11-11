import re
from collections.abc import Callable, Iterator
from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.checks.definitions import FileCheck
from pristine.checks.testing.model_clients_in_tests.live_clients import LiveClient, key_label
from pristine.checks.testing.model_clients_in_tests.python_keys import python_live_clients
from pristine.checks.testing.model_clients_in_tests.script_keys import script_live_clients
from pristine.clients.tables import client_table, library_names
from pristine.files.path_roles import PYTEST_CONFTEST, is_test_file
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.parsing import ParsedFile

RULE_ID = "TST-8"
EVALS_DIRECTORY = "evals"
MODEL_SURFACE = re.compile(
    r"\.(chat|fim|embeddings|ocr|agents|conversations|classifiers|messages|responses|completions)\.\w+|\.generate_content\b"
)
LIVE_CLIENT_READERS: dict[str, Callable[[Node | ParsedFile], Iterator[LiveClient]]] = {
    "python": python_live_clients,
    **dict.fromkeys(SCRIPT_LANGUAGES, script_live_clients),
}


def is_test_module(path: str) -> bool:
    location = PurePath(path)
    is_test = is_test_file(location) or location.name == PYTEST_CONFTEST
    return is_test and EVALS_DIRECTORY not in location.parts


def check_model_clients_in_tests(parsed: ParsedFile) -> list[Finding]:
    table, read_live_clients = client_table(parsed.language), LIVE_CLIENT_READERS.get(parsed.language)
    if table is None or read_live_clients is None or not is_test_module(parsed.path):
        return []
    clients = table.model_clients(parsed)
    live = list(read_live_clients(parsed)) if clients else []
    if not live or MODEL_SURFACE.search(parsed.text) is None:
        return []
    message = (
        f"test calls a real model through {library_names(clients)} with {key_label(live[0].key)} from the "
        "environment; replace the model with a fake that returns scripted outputs, and measure model quality with "
        "evals (make eval)"
    )
    return [Finding(parsed.path, live[0].line, RULE_ID, Severity.WARNING, message)]


CHECK = FileCheck(
    rule_id=RULE_ID,
    title="No Live Model Clients in Tests",
    summary=(
        "Test files constructing a real LLM SDK client (Python openai, anthropic, mistralai Mistral, "
        "google.generativeai, cohere; JS/TS openai, @anthropic-ai/sdk, @mistralai/mistralai) whose API key "
        "argument reads the environment, with a model API in use. Evals and type-only imports are exempt."
    ),
    run=check_model_clients_in_tests,
)
