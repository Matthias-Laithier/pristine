import re
from collections.abc import Iterator
from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.checks.core.values.model_settings_script import SAMPLING_DEFAULTS
from pristine.checks.core.values.model_settings_script import hardcoded_settings as script_settings
from pristine.checks.definitions import FileCheck
from pristine.checks.prefilters import mentions_any, requiring
from pristine.clients.libraries import PYTHON_MODEL_CLIENTS
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.calls import callee_of, calls_of
from pristine.syntax.parsing import ParsedFile, all_nodes, line_of, module_statements, node_text, typed_nodes
from pristine.syntax.python_calls import import_bindings, keyword_values, qualified_callee
from pristine.syntax.python_strings import is_constant_string

CHECK_ID = "SAFE-13"
SHEBANG = "#!"
MODEL_KEYWORD = "model"
NEUTRAL_SAMPLING = {"temperature": 0.0, "top_p": 1.0}
REQUIRED_TEXT = {
    "python": (MODEL_KEYWORD, *NEUTRAL_SAMPLING),
    **dict.fromkeys(SCRIPT_LANGUAGES, (MODEL_KEYWORD, *SAMPLING_DEFAULTS)),
}
NUMBER_KINDS = frozenset({"integer", "float"})
TYPE_NAME_KINDS = frozenset({"identifier", "attribute", "string_content"})
TYPED_PARAMETER_KINDS = frozenset({"typed_parameter", "typed_default_parameter"})
BOUND_SOURCE_KINDS = TYPED_PARAMETER_KINDS | {"assignment", "as_pattern"}
DECIMAL = re.compile(r"(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?")
MODEL_FAMILY = re.compile(
    r"gpt|claude|mistral|gemini|llama|ministral|codestral|pixtral|magistral|devstral|voxtral|(?<![a-z0-9])o[134](?!\d)",
    re.IGNORECASE,
)
VENDOR_PREFIXED = re.compile(r"[\w.-]+/[\w.:@-]+")
IDENTIFIER_TOKEN = re.compile(r"[\w.:@/-]+")
FIX = "read it from a typed configuration field, so a model switch reaches every caller and evals judge it"


def is_model_identifier(node: Node, *, is_client_call: bool) -> bool:
    text = (node_text(node) or "").strip("'\"")
    if not is_constant_string(node) or IDENTIFIER_TOKEN.fullmatch(text) is None:
        return False
    return is_client_call or MODEL_FAMILY.search(text) is not None or VENDOR_PREFIXED.fullmatch(text) is not None


def is_tuned_number(node: Node, neutral: float) -> bool:
    operand = node.named_children[-1] if node.type == "unary_operator" and node.named_children else node
    text = (node_text(operand) or "").replace("_", "")
    is_neutral = DECIMAL.fullmatch(text) is not None and float(text) == neutral
    return operand.type in NUMBER_KINDS and not is_neutral


def module_literals(parsed: ParsedFile) -> dict[str, Node]:
    assignments = (statement for statement in module_statements(parsed.root) if statement.type == "assignment")
    pairs = ((node_text(node.child_by_field_name("left")), node.child_by_field_name("right")) for node in assignments)
    return {name: value for name, value in pairs if name is not None and value is not None}


def resolved(value: Node, literals: dict[str, Node]) -> Node:
    return literals.get(node_text(value) or "", value) if value.type == "identifier" else value


def is_model_sdk(name: str, bindings: dict[str, str]) -> bool:
    qualified = qualified_callee(name, bindings) or ""
    return any(qualified == client or qualified.startswith(f"{client}.") for client in PYTHON_MODEL_CLIENTS)


def bound_sources(node: Node) -> Iterator[tuple[Node | None, Node | None]]:
    if node.type == "assignment":
        yield node.child_by_field_name("left"), node.child_by_field_name("right")
        yield node.child_by_field_name("left"), node.child_by_field_name("type")
    elif node.type in TYPED_PARAMETER_KINDS:
        name = node.child_by_field_name("name") or next(iter(node.named_children), None)
        yield name, node.child_by_field_name("type")
    elif node.type == "as_pattern":
        yield node.child_by_field_name("alias"), next(iter(node.named_children), None)


def names_model_client(source: Node, bindings: dict[str, str]) -> bool:
    if source.type == "call":
        return is_model_sdk(callee_of(source), bindings)
    names = (node_text(node) or "" for node in all_nodes(source) if node.type in TYPE_NAME_KINDS)
    return source.type == "type" and any(is_model_sdk(name, bindings) for name in names)


def model_clients(parsed: ParsedFile, bindings: dict[str, str]) -> set[str]:
    pairs = (pair for node in typed_nodes(parsed, *BOUND_SOURCE_KINDS) for pair in bound_sources(node))
    return {
        node_text(target) or ""
        for target, source in pairs
        if target is not None and source is not None and names_model_client(source, bindings)
    }


def is_client_call(callee: str, bindings: dict[str, str], clients: set[str]) -> bool:
    segments = callee.split(".")
    receivers = {".".join(segments[:end]) for end in range(1, len(segments))}
    return is_model_sdk(callee, bindings) or not receivers.isdisjoint(clients)


def hardcoded_settings(
    keywords: dict[str, Node], literals: dict[str, Node], *, is_client: bool
) -> Iterator[tuple[str, Node]]:
    model = keywords.get(MODEL_KEYWORD)
    names_model = model is not None and is_model_identifier(resolved(model, literals), is_client_call=is_client)
    if model is not None and names_model:
        yield MODEL_KEYWORD, model
    for name, neutral in NEUTRAL_SAMPLING.items():
        value = keywords.get(name)
        if (is_client or names_model) and value is not None and is_tuned_number(resolved(value, literals), neutral):
            yield name, value


def setting_finding(parsed: ParsedFile, name: str, value: Node, literals: dict[str, Node]) -> Finding:
    shown = node_text(value) or ""
    literal = resolved(value, literals)
    origin = "" if literal is value else f", a module constant holding {node_text(literal)},"
    message = f"'{name}={shown}'{origin} hardcodes a model setting at a call site; {FIX}"
    return Finding(parsed.path, line_of(value), CHECK_ID, Severity.WARNING, message)


def check_model_settings_literals(parsed: ParsedFile) -> list[Finding]:
    if is_test_path(PurePath(parsed.path)) or parsed.text.startswith(SHEBANG):
        return []
    if parsed.language in SCRIPT_LANGUAGES:
        return [setting_finding(parsed, name, value, {}) for name, value in script_settings(parsed)]
    if parsed.language != "python":
        return []
    literals = module_literals(parsed)
    bindings = import_bindings(parsed)
    clients = model_clients(parsed, bindings)
    findings = []
    for _, callee, arguments in calls_of(parsed, "call"):
        is_client = is_client_call(callee, bindings, clients)
        settings = hardcoded_settings(keyword_values(arguments), literals, is_client=is_client)
        findings.extend(setting_finding(parsed, name, value, literals) for name, value in settings)
    return sorted(findings, key=lambda finding: finding.line)


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Hardcoded Model Settings",
    summary=(
        "Python and JS/TS calls passing a literal model identifier or a literal temperature or top_p/topP, directly or "
        "through a same-module literal constant. Any literal model counts on a call to a model SDK client "
        "(openai, anthropic, mistralai, google.generativeai, cohere) resolved through imports, assignments, "
        "annotations, and with-statements; elsewhere, a literal naming a known model family or a vendor-prefixed "
        "model marks the call. Temperature 0, top_p 1, tests, and shebang scripts are exempt."
    ),
    run=requiring(mentions_any(REQUIRED_TEXT), check_model_settings_literals),
)
