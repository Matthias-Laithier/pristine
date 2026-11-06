from collections.abc import Iterator

from tree_sitter import Node

from pristine.checks.injection.constructed import Injection
from pristine.checks.injection.script_processes import scan_processes
from pristine.checks.injection.script_values import is_trusted
from pristine.syntax.parsing import ParsedFile, all_nodes, node_text

MARKUP_PROPERTIES = frozenset({"innerHTML", "outerHTML"})
ASSIGNMENT_KINDS = frozenset({"assignment_expression", "augmented_assignment_expression"})
DANGEROUS_ATTRIBUTE = "dangerouslySetInnerHTML"
HTML_KEY = "__html"
RAW_UNSAFE_METHODS = frozenset({"$queryRawUnsafe", "$executeRawUnsafe"})
EVALUATOR = "eval"
FUNCTION_CONSTRUCTOR = "Function"
MARKUP_FIX = "render text through the framework or textContent, or sanitize the markup at one owning boundary"
RAW_FIX = "use the tagged $queryRaw or $executeRaw template, which binds every value"
EVAL_FIX = "parse the value into data, such as with JSON.parse"


def html_values(attribute: Node) -> list[Node]:
    expressions = [child for child in attribute.named_children if child.type == "jsx_expression"]
    objects = [inner for expression in expressions for inner in expression.named_children if inner.type == "object"]
    pairs = [pair for value in objects for pair in value.named_children if pair.type == "pair"]
    return [
        pair.child_by_field_name("value") or pair
        for pair in pairs
        if node_text(pair.child_by_field_name("key")) == HTML_KEY
    ]


def markup_injection(node: Node) -> str | None:
    if (
        node.type == "jsx_attribute"
        and node.named_children
        and node_text(node.named_children[0]) == DANGEROUS_ATTRIBUTE
    ):
        dynamic = not all(map(is_trusted, html_values(node)))
        return f"'{DANGEROUS_ATTRIBUTE}' renders non-literal markup; {MARKUP_FIX}" if dynamic else None
    left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
    if node.type not in ASSIGNMENT_KINDS or left is None or right is None or left.type != "member_expression":
        return None
    property_name = node_text(left.child_by_field_name("property"))
    if property_name not in MARKUP_PROPERTIES or is_trusted(right):
        return None
    return f"'{property_name}' receives non-literal markup; {MARKUP_FIX}"


def evaluation_injection(node: Node) -> str | None:
    arguments_node = node.child_by_field_name("arguments")
    arguments = [] if arguments_node is None else arguments_node.named_children
    dynamic = not all(map(is_trusted, arguments))
    function = node.child_by_field_name("function") or node.child_by_field_name("constructor")
    name = node_text(function) or ""
    method = node_text(function.child_by_field_name("property")) if function is not None else None
    if node.type == "call_expression" and method in RAW_UNSAFE_METHODS and arguments and not is_trusted(arguments[0]):
        return f"'{method}' runs SQL built from non-literal values; {RAW_FIX}"
    is_evaluator = (node.type, name) in {("call_expression", EVALUATOR), ("new_expression", FUNCTION_CONSTRUCTOR)}
    return f"'{name}' evaluates a non-literal value as code; {EVAL_FIX}" if is_evaluator and dynamic else None


def scan_script(parsed: ParsedFile) -> Iterator[Injection]:
    yield from scan_processes(parsed.root)
    for node in all_nodes(parsed.root):
        message = markup_injection(node) or evaluation_injection(node)
        if message is not None:
            yield Injection(node, message)
