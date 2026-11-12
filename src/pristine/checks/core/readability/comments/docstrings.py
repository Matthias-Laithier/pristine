lazy from tree_sitter import Node

from pristine.syntax.parsing import ParsedFile, is_docstring, line_of, node_text

FRAMEWORK_DECORATOR_NAMES = frozenset(
    {
        "tool",
        "tool_plain",
        "function_tool",
        "resource",
        "prompt",
        "command",
        "group",
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "api_route",
    }
)
EXPLICIT_DESCRIPTION_KEYWORD = "description"
MODULE_DOCSTRING_NAME = "__doc__"
NON_READING_FIELDS = {"attribute": "attribute", "keyword_argument": "name", "assignment": "left"}


def decorator_name(expression: Node | None) -> str | None:
    if expression is not None and expression.type == "attribute":
        expression = expression.child_by_field_name("attribute")
    return node_text(expression)


def call_keywords(call: Node) -> set[str]:
    arguments = call.child_by_field_name("arguments")
    keywords = [] if arguments is None else arguments.named_children
    return {
        node_text(keyword.child_by_field_name("name")) or ""
        for keyword in keywords
        if keyword.type == "keyword_argument"
    }


def publishes_docstring(decorator: Node) -> bool:
    expression = decorator.named_children[0] if decorator.named_children else None
    if expression is None or expression.type != "call":
        return decorator_name(expression) in FRAMEWORK_DECORATOR_NAMES
    name = decorator_name(expression.child_by_field_name("function"))
    return name in FRAMEWORK_DECORATOR_NAMES and EXPLICIT_DESCRIPTION_KEYWORD not in call_keywords(expression)


def framework_docstring_line(decorated: Node) -> int | None:
    definition = decorated.child_by_field_name("definition")
    if definition is None or definition.type != "function_definition":
        return None
    body = definition.child_by_field_name("body")
    decorators = [child for child in decorated.named_children if child.type == "decorator"]
    if body is None or not body.named_children or not any(map(publishes_docstring, decorators)):
        return None
    return line_of(body.named_children[0])


def is_module_docstring_read(node: Node) -> bool:
    parent = node.parent
    field = None if parent is None else NON_READING_FIELDS.get(parent.type)
    is_written_or_named = parent is not None and field is not None and parent.child_by_field_name(field) == node
    return node.type == "identifier" and node_text(node) == MODULE_DOCSTRING_NAME and not is_written_or_named


def runtime_docstring_lines(parsed: ParsedFile) -> set[int]:
    first = parsed.root.named_children[:1]
    if not first or not is_docstring(first[0]) or not any(map(is_module_docstring_read, parsed.nodes_of("identifier"))):
        return set()
    return {line_of(first[0])}


def machine_read_docstring_lines(parsed: ParsedFile) -> set[int]:
    if parsed.language != "python":
        return set()
    decorated = parsed.nodes_of("decorated_definition")
    framework_lines = {line for line in map(framework_docstring_line, decorated) if line is not None}
    return framework_lines | runtime_docstring_lines(parsed)
