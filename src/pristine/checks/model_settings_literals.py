import re
from collections.abc import Iterator
from pathlib import PurePath

from tree_sitter import Node

from pristine.calls import calls_of
from pristine.checks.registry import FileCheck, register_file_check
from pristine.findings import Finding, Severity
from pristine.parsing import ParsedFile, line_of, module_statements, node_text
from pristine.path_roles import is_test_path
from pristine.python_calls import keyword_values
from pristine.python_strings import is_constant_string

RULE_ID = "CR-18"
SHEBANG = "#!"
EXEMPT_DIRECTORY = re.compile(
    r"(\w+[-_])?(evals?|evaluations?|examples?|scripts|playground|cookbooks?|tutorials?|notebooks?)([-_]\w+)?",
    re.IGNORECASE,
)
MODEL_KEYWORD = "model"
NEUTRAL_SAMPLING = {"temperature": 0.0, "top_p": 1.0}
PROMPT_KEYWORDS = frozenset({"messages", "prompt", "input", "inputs"})
NUMBER_KINDS = frozenset({"integer", "float"})
DECIMAL = re.compile(r"(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?")
MODEL_FAMILY = re.compile(
    r"gpt|claude|mistral|gemini|llama|ministral|codestral|pixtral|magistral|devstral|voxtral|(?<![a-z0-9])o[134](?!\d)",
    re.IGNORECASE,
)
VENDOR_PREFIXED = re.compile(r"[\w.-]+/[\w.:@-]+")
IDENTIFIER_TOKEN = re.compile(r"[\w.:@/-]+")
COMPLETION_SEGMENT = re.compile(r"(?i:\w*(chat|complet|create|generat|stream|respons|message)\w*)")
MODEL_CLIENT_SEGMENT = re.compile(r"(?=[A-Z])\w*(OpenAI|Mistral|Anthropic|Claude|Gemini|LLM|Llm|ChatModel)\w*")
FIX = "read it from a typed configuration field, so a model switch reaches every caller and evals judge it"


def is_model_identifier(node: Node) -> bool:
    text = (node_text(node) or "").strip("'\"")
    if not is_constant_string(node) or IDENTIFIER_TOKEN.fullmatch(text) is None:
        return False
    return MODEL_FAMILY.search(text) is not None or VENDOR_PREFIXED.fullmatch(text) is not None


def is_tuned_number(node: Node, neutral: float) -> bool:
    operand = node.named_children[-1] if node.type == "unary_operator" and node.named_children else node
    text = (node_text(operand) or "").replace("_", "")
    is_neutral = DECIMAL.fullmatch(text) is not None and float(text) == neutral
    return operand.type in NUMBER_KINDS and not is_neutral


def module_literals(root: Node) -> dict[str, Node]:
    assignments = (statement for statement in module_statements(root) if statement.type == "assignment")
    pairs = ((node_text(node.child_by_field_name("left")), node.child_by_field_name("right")) for node in assignments)
    return {name: value for name, value in pairs if name is not None and value is not None}


def resolved(value: Node, literals: dict[str, Node]) -> Node:
    return literals.get(node_text(value) or "", value) if value.type == "identifier" else value


def is_model_call(callee: str) -> bool:
    segments = callee.split(".")
    is_client = any(MODEL_CLIENT_SEGMENT.fullmatch(segment) for segment in segments)
    return is_client or any(COMPLETION_SEGMENT.fullmatch(segment) for segment in segments)


def hardcoded_settings(callee: str, keywords: dict[str, Node], literals: dict[str, Node]) -> Iterator[tuple[str, Node]]:
    if not is_model_call(callee):
        return
    model = keywords.get(MODEL_KEYWORD)
    names_model = model is not None and is_model_identifier(resolved(model, literals))
    if model is not None and names_model:
        yield MODEL_KEYWORD, model
    is_prompted = names_model or not PROMPT_KEYWORDS.isdisjoint(keywords) or MODEL_CLIENT_SEGMENT.search(callee)
    for name, neutral in NEUTRAL_SAMPLING.items():
        value = keywords.get(name)
        if is_prompted and value is not None and is_tuned_number(resolved(value, literals), neutral):
            yield name, value


def setting_finding(parsed: ParsedFile, name: str, value: Node, literals: dict[str, Node]) -> Finding:
    shown = node_text(value) or ""
    literal = resolved(value, literals)
    origin = "" if literal is value else f", a module constant holding {node_text(literal)},"
    message = f"'{name}={shown}'{origin} hardcodes a model setting at a call site; {FIX}"
    return Finding(parsed.path, line_of(value), RULE_ID, Severity.WARNING, message)


def is_exempt(parsed: ParsedFile) -> bool:
    location = PurePath(parsed.path)
    is_tooling = any(EXEMPT_DIRECTORY.fullmatch(name) for name in location.parts[:-1])
    return is_tooling or is_test_path(location) or parsed.text.startswith(SHEBANG)


def check_model_settings_literals(parsed: ParsedFile) -> list[Finding]:
    if parsed.language != "python" or is_exempt(parsed):
        return []
    literals = module_literals(parsed.root)
    findings = []
    for _, callee, arguments in calls_of(parsed.root, "call"):
        settings = hardcoded_settings(callee, keyword_values(arguments), literals)
        findings.extend(setting_finding(parsed, name, value, literals) for name, value in settings)
    return sorted(findings, key=lambda finding: finding.line)


register_file_check(
    FileCheck(
        rule_id=RULE_ID,
        summary=(
            "Python model-client and completion calls passing a literal model identifier (model='gpt-4o', "
            "'mistral-large-latest', 'openai/...') or a literal temperature or top_p, directly or through a "
            "same-module literal constant. Temperature 0 and top_p 1, tests, evals, examples, and scripts are exempt."
        ),
        run=check_model_settings_literals,
    )
)
