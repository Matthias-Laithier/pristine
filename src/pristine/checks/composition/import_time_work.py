import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import PurePath

lazy from tree_sitter import Node

from pristine.checks.composition.script_eager import eager_children
from pristine.checks.definitions import FileCheck
from pristine.files.path_roles import is_test_path
from pristine.reports.findings import Finding, Severity
from pristine.services.grammars import SCRIPT_LANGUAGES
from pristine.syntax.nodes import FUNCTION_KINDS
from pristine.syntax.parsing import ParsedFile, line_of, node_text

CHECK_ID = "DEP-5"
PREVIEW_LENGTH = 60
SHEBANG = "#!"
WHITESPACE = re.compile(r"\s+")
ENTRYPOINT_FILES = r"(__main__|manage|setup|noxfile|tasks|(alembic|migrations)/env)\.py|[^/]+\.config\.\w+"
ENTRYPOINT_DIRECTORIES = r"(scripts|bin|examples)/.+"
ENTRYPOINT_PATH = re.compile(rf"(.*/)?({ENTRYPOINT_FILES}|{ENTRYPOINT_DIRECTORIES})")
MAIN_GUARD = re.compile(r"\(?(__name__==['\"]__main__['\"]|['\"]__main__['\"]==__name__|require\.main===module)\)?")
SUBJECT_FIELDS = {"call": "function", "call_expression": "function", "new_expression": "constructor"}
DEFERRED_OR_DECLARATIVE_KINDS = frozenset(
    {"class_definition", "class_declaration", "abstract_class_declaration", "class", "decorator", "generator_function"}
)
STOP_KINDS = FUNCTION_KINDS | DEFERRED_OR_DECLARATIVE_KINDS
PYTHON_EAGER_FIELDS = {
    "assignment": ("left", "right"),
    "class_definition": ("superclasses", "body"),
    "function_definition": ("parameters",),
    "lambda": ("parameters",),
    "default_parameter": ("value",),
    "typed_default_parameter": ("value",),
    "typed_parameter": (),
}
BUNDLER_INLINED_ENV = r"(?!NEXT_PUBLIC_|NODE_ENV\b)"


@dataclass(frozen=True)
class ExternalWork:
    description: str
    severity: Severity


@dataclass(frozen=True)
class WorkPattern:
    kind: str
    pattern: str
    work: ExternalWork


ENVIRONMENT = ExternalWork("environment read", Severity.ERROR)
FILE_ACCESS = ExternalWork("file access", Severity.ERROR)
NETWORK = ExternalWork("network call or client construction", Severity.ERROR)
PROCESS = ExternalWork("thread or process start", Severity.ERROR)
SIGNAL = ExternalWork("signal handler registration", Severity.ERROR)
OUTPUT = ExternalWork("output or logging", Severity.WARNING)
DOTENV = ExternalWork("dotenv loading", Severity.ERROR)
PYTHON_PATTERNS = (
    WorkPattern("attribute", r"os\.environ", ENVIRONMENT),
    WorkPattern("call", r"(os\.)?getenv", ENVIRONMENT),
    WorkPattern("call", r"(io\.|codecs\.)?open|os\.(makedirs|mkdir|listdir|scandir|remove|unlink)", FILE_ACCESS),
    WorkPattern("call", r".+\.(read_text|read_bytes|write_text|write_bytes|mkdir|touch)", FILE_ACCESS),
    WorkPattern("call", r"(requests|httpx)\.(get|post|put|patch|delete|head|request|Session|(Async)?Client)", NETWORK),
    WorkPattern("call", r"boto3\.(client|resource|Session)|(redis\.)?(Strict)?Redis(\.from_url)?", NETWORK),
    WorkPattern("call", r"(sqlalchemy\.)?create_(async_)?engine|(pymongo\.)?MongoClient|AsyncIOMotorClient", NETWORK),
    WorkPattern("call", r"(psycopg2?|sqlite3|pymysql|asyncpg)\.connect|(urllib\.request\.)?urlopen", NETWORK),
    WorkPattern("call", r"(openai\.)?(Async)?OpenAI|(anthropic\.)?(Async)?Anthropic|(mistralai\.)?Mistral", NETWORK),
    WorkPattern("call", r"redis\.from_url|QdrantClient|socket\.(socket|create_connection)", NETWORK),
    WorkPattern("call", r"subprocess\.(run|call|check_call|check_output|Popen)|os\.(system|popen|fork)", PROCESS),
    WorkPattern("call", r".*(Thread|Process|Timer)\(.*\)\.start", PROCESS),
    WorkPattern("call", r"signal\.signal", SIGNAL),
    WorkPattern("call", r"print|pprint|sys\.(stdout|stderr)\.write|logging\.(basicConfig|config\.\w+)", OUTPUT),
    WorkPattern("call", r"(logging|logger|log|LOGGER)\.(debug|info|warning|error|exception|critical)", OUTPUT),
    WorkPattern("call", r"(dotenv\.)?(load_dotenv|dotenv_values)", DOTENV),
)
SCRIPT_PATTERNS = (
    WorkPattern("member_expression", rf"process\.env\.{BUNDLER_INLINED_ENV}\w+", ENVIRONMENT),
    WorkPattern("subscript_expression", r"process\.env\[.+\]", ENVIRONMENT),
    WorkPattern("variable_declarator", r"\{.*\}=process\.env", ENVIRONMENT),
    WorkPattern("call_expression", r"(fs|fsp|fs\.promises)\.\w+", FILE_ACCESS),
    WorkPattern("call_expression", r"(readFile|writeFile|appendFile|exists|mkdir|readdir|stat)Sync", FILE_ACCESS),
    WorkPattern("call_expression", r"fetch|axios\.(get|post|put|patch|delete|request)|mongoose\.connect", NETWORK),
    WorkPattern("call_expression", r"(\w+\.)?createClient|createPool", NETWORK),
    WorkPattern("new_expression", r"PrismaClient|I?Redis|Pool|MongoClient|OpenAI|Anthropic|Mistral|Sequelize", NETWORK),
    WorkPattern("new_expression", r"Stripe|WebSocket|(S3|DynamoDB|SQS|SNS|SecretsManager|Lambda)Client", NETWORK),
    WorkPattern("call_expression", r"(child_process\.)?(exec|spawn|execFile)(Sync)?", PROCESS),
    WorkPattern("new_expression", r"Worker", PROCESS),
    WorkPattern("call_expression", r"process\.(on|once)", SIGNAL),
    WorkPattern("call_expression", r"console\.\w+", OUTPUT),
    WorkPattern("call_expression", r"dotenv\.config|require\(['\"]dotenv['\"]\)\.config", DOTENV),
    WorkPattern("expression_statement", r"require\(['\"]dotenv/config['\"]\);?", DOTENV),
    WorkPattern("import_statement", r"import['\"]dotenv/config['\"];?", DOTENV),
)
PATTERNS_BY_LANGUAGE = {"python": PYTHON_PATTERNS} | dict.fromkeys(SCRIPT_LANGUAGES, SCRIPT_PATTERNS)


def compact_text(node: Node | None) -> str:
    return WHITESPACE.sub("", node_text(node) or "")


def is_main_guard(node: Node) -> bool:
    condition = compact_text(node.child_by_field_name("condition"))
    return node.type == "if_statement" and bool(MAIN_GUARD.fullmatch(condition))


def import_time_children(node: Node, language: str) -> list[Node]:
    if language in SCRIPT_LANGUAGES and (children := eager_children(node)) is not None:
        return children
    if language == "python" and node.type == "generator_expression":
        first_clause = next((child for child in node.named_children if child.type == "for_in_clause"), None)
        iterable = None if first_clause is None else first_clause.child_by_field_name("right")
        return [] if iterable is None else [iterable]
    fields = PYTHON_EAGER_FIELDS.get(node.type) if language == "python" else None
    if fields is not None:
        return [child for field in fields if (child := node.child_by_field_name(field)) is not None]
    if language == "python" and node.type == "decorator":
        return node.named_children
    return [] if node.type in STOP_KINDS else node.named_children


def import_time_nodes(root: Node, language: str) -> Iterator[Node]:
    pending = list(reversed(root.named_children))
    while pending:
        node = pending.pop()
        if is_main_guard(node):
            continue
        yield node
        pending.extend(reversed(import_time_children(node, language)))


def subject_of(node: Node) -> Node | None:
    subject_field = SUBJECT_FIELDS.get(node.type)
    return node if subject_field is None else node.child_by_field_name(subject_field)


def work_of(node: Node, language_patterns: tuple[WorkPattern, ...]) -> ExternalWork | None:
    candidates = [pattern for pattern in language_patterns if pattern.kind == node.type]
    subject = compact_text(subject_of(node)) if candidates else ""
    return next((candidate.work for candidate in candidates if re.fullmatch(candidate.pattern, subject)), None)


def is_entrypoint_or_test(parsed: ParsedFile) -> bool:
    is_entrypoint = bool(ENTRYPOINT_PATH.fullmatch(parsed.path)) or parsed.text.startswith(SHEBANG)
    return is_entrypoint or is_test_path(PurePath(parsed.path))


def work_finding(parsed: ParsedFile, node: Node, work: ExternalWork) -> Finding:
    preview = parsed.text.splitlines()[line_of(node) - 1].strip()[:PREVIEW_LENGTH]
    message = f"{work.description} at import time ('{preview}'); move it into a function the entrypoint calls"
    return Finding(parsed.path, line_of(node), CHECK_ID, work.severity, message)


def check_import_time_work(parsed: ParsedFile) -> list[Finding]:
    language_patterns = PATTERNS_BY_LANGUAGE.get(parsed.language)
    if language_patterns is None or is_entrypoint_or_test(parsed):
        return []
    findings: dict[int, Finding] = {}
    for node in import_time_nodes(parsed.root, parsed.language):
        work = work_of(node, language_patterns)
        if work is not None and line_of(node) not in findings:
            findings[line_of(node)] = work_finding(parsed, node, work)
    return list(findings.values())


CHECK = FileCheck(
    check_id=CHECK_ID,
    title="Import-Time External Work",
    summary=(
        "Known env, file, network, process, signal, dotenv, and output work in eager module expressions. "
        "Python eager class expressions and JS/TS static fields, blocks and computed names are included. "
        "Main guards, tests and recognized entrypoints are exempt."
    ),
    run=check_import_time_work,
)
